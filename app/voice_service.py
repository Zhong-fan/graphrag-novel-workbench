from __future__ import annotations

import json
import re
import urllib.request
import uuid
import base64
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .json_utils import json_dumps, json_loads_object
from .models import CharacterCard, MediaAsset, Project, Storyboard, StoryboardShot


class VoiceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def require_config(self) -> None:
        provider = self._provider("")
        missing = []
        if provider == "volcengine_doubao":
            if not self.settings.volcengine_tts_app_id:
                missing.append("VOLCENGINE_TTS_APP_ID")
            if not (self.settings.volcengine_tts_access_key or self.settings.volcengine_tts_api_key):
                missing.append("VOLCENGINE_TTS_ACCESS_KEY 或 VOLCENGINE_TTS_API_KEY")
            if not self.settings.volcengine_tts_resource_id:
                missing.append("VOLCENGINE_TTS_RESOURCE_ID")
            if not self.settings.volcengine_tts_speaker:
                missing.append("VOLCENGINE_TTS_SPEAKER")
        else:
            if not self.settings.tts_api_key:
                missing.append("CHENFLOW_TTS_API_KEY")
            if not self.settings.tts_base_url:
                missing.append("CHENFLOW_TTS_BASE_URL")
            if not self.settings.tts_model:
                missing.append("CHENFLOW_TTS_MODEL")
            if not self.settings.tts_voice:
                missing.append("CHENFLOW_TTS_VOICE")
        if missing:
            raise RuntimeError("配音生成配置缺失：" + "、".join(missing))

    def generate_storyboard_voice(
        self,
        *,
        db: Session,
        project: Project,
        storyboard: Storyboard,
        voice_profile: str = "",
        provider: str = "openai_compatible",
        voice_role: str = "narrator",
        character: CharacterCard | None = None,
        dialogue_text: str = "",
        speed: float = 1.0,
        emotion: str = "",
        text_override: str = "",
    ) -> list[MediaAsset]:
        self.require_config()
        assets: list[MediaAsset] = []
        for shot in sorted(storyboard.shots, key=lambda item: item.shot_no):
            if (voice_role or "").strip().lower() == "dialogue":
                script = json_loads_object(shot.meta_json).get("audio_script")
                for item in self._dialogue_items(script):
                    item_character = self._resolve_character(
                        project=project,
                        character_card_id=item.get("character_card_id"),
                        character_name=str(item.get("character_name") or ""),
                    )
                    asset = self.generate_shot_voice(
                        db=db,
                        project=project,
                        storyboard=storyboard,
                        shot=shot,
                        voice_profile=voice_profile or str(item.get("voice_profile") or ""),
                        provider=provider,
                        voice_role="dialogue",
                        character=item_character,
                        dialogue_text=str(item.get("line") or ""),
                        speed=speed,
                        emotion=emotion or str(item.get("emotion") or ""),
                        text_override="",
                        dialogue_index=int(item.get("dialogue_index") or 0),
                    )
                    meta = json_loads_object(asset.meta_json)
                    meta["character_name"] = str(item.get("character_name") or "")
                    meta["dialogue_index"] = item.get("dialogue_index")
                    asset.meta_json = json_dumps(meta)
                    assets.append(asset)
                continue
            if (text_override or shot.narration_text or "").strip():
                asset = self.generate_shot_voice(
                    db=db,
                    project=project,
                    storyboard=storyboard,
                    shot=shot,
                    voice_profile=voice_profile,
                    provider=provider,
                    voice_role=voice_role,
                    character=character,
                    dialogue_text=dialogue_text,
                    speed=speed,
                    emotion=emotion,
                    text_override=text_override,
                )
                assets.append(asset)
        if not assets:
            raise RuntimeError("分镜稿没有可用于生成配音的文本。")
        return assets

    def generate_shot_voice(
        self,
        *,
        db: Session,
        project: Project,
        storyboard: Storyboard,
        shot: StoryboardShot,
        voice_profile: str = "",
        provider: str = "openai_compatible",
        voice_role: str = "narrator",
        character: CharacterCard | None = None,
        dialogue_text: str = "",
        speed: float = 1.0,
        emotion: str = "",
        text_override: str = "",
        dialogue_index: int = 0,
    ) -> MediaAsset:
        self.require_config()
        normalized_role = (voice_role or "narrator").strip().lower()
        text = (dialogue_text if normalized_role == "dialogue" else text_override or shot.narration_text or "").strip()
        if not text:
            label = "对白" if normalized_role == "dialogue" else "旁白"
            raise RuntimeError(f"镜头 {shot.shot_no} 没有{label}文本。")

        asset_type = "dialogue" if normalized_role == "dialogue" else "voice"
        effective_provider = self._provider(provider if provider.strip() else (character.voice_provider if character else ""))
        effective_voice_profile = (
            voice_profile.strip()
            or (character.voice_speaker.strip() if character and character.voice_speaker.strip() else "")
            or self._default_voice_profile(effective_provider)
        )
        effective_speed = speed if abs(speed - 1.0) > 0.001 else (character.voice_speed if character and character.voice_speed else 1.0)
        asset = self._voice_asset(
            db=db,
            project=project,
            storyboard=storyboard,
            shot=shot,
            asset_type=asset_type,
            character=character,
            dialogue_index=dialogue_index,
        )
        existing_meta = json_loads_object(asset.meta_json)
        if asset.status == "completed" and existing_meta.get("locked") is True and asset.uri and Path(asset.uri).exists():
            return asset
        asset.status = "processing"
        asset.prompt = text
        asset.meta_json = json_dumps(
            {
                **existing_meta,
                "shot_no": shot.shot_no,
                "purpose": "角色对白" if asset_type == "dialogue" else "旁白",
                "voice_role": normalized_role,
                "character_card_id": character.id if character else None,
                "character_name": character.name if character else "",
                "voice_style": character.voice_style if character else "",
                "voice_pitch": character.voice_pitch if character else 0.0,
                "voice_profile": effective_voice_profile,
                "provider": effective_provider,
                "model": self._model_name(effective_provider),
                "speed": effective_speed,
                "emotion": emotion,
                "mime_type": "audio/mpeg",
                "dialogue_index": dialogue_index if dialogue_index > 0 else None,
            }
        )
        db.flush()

        output_dir = self._output_dir(project=project, storyboard=storyboard)
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / self._audio_file_name(shot=shot, asset_type=asset_type, character=character, dialogue_index=dialogue_index)
        try:
            self._write_tts_audio(
                path=audio_path,
                text=text,
                voice_profile=effective_voice_profile,
                provider=effective_provider,
                speed=effective_speed,
                emotion=emotion,
            )
        except Exception:
            asset.status = "failed"
            db.flush()
            raise

        asset.uri = str(audio_path)
        asset.status = "completed"
        asset.meta_json = json_dumps(
            {
                **json_loads_object(asset.meta_json),
                "file_name": audio_path.name,
                "size_bytes": audio_path.stat().st_size,
            }
        )
        db.flush()
        return asset

    def _write_tts_audio(self, *, path: Path, text: str, voice_profile: str, provider: str, speed: float, emotion: str) -> None:
        if self._provider(provider) == "volcengine_doubao":
            self._write_volcengine_doubao_audio(path=path, text=text, voice_profile=voice_profile, speed=speed, emotion=emotion)
            return
        self._write_openai_compatible_audio(path=path, text=text, voice_profile=voice_profile, speed=speed, emotion=emotion)

    def _write_openai_compatible_audio(self, *, path: Path, text: str, voice_profile: str, speed: float, emotion: str) -> None:
        payload: dict[str, Any] = {
            "model": self.settings.tts_model,
            "voice": voice_profile.strip() or self.settings.tts_voice,
            "input": text,
            "response_format": "mp3",
        }
        if speed and abs(speed - 1.0) > 0.001:
            payload["speed"] = speed
        if emotion.strip():
            payload["instructions"] = f"Use a {emotion.strip()} narrator delivery."

        request = urllib.request.Request(
            f"{self.settings.tts_base_url.rstrip('/')}/audio/speech",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.tts_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(f"TTS 接口调用失败：{exc}") from exc
        if not content:
            raise RuntimeError("TTS 接口返回空音频。")
        path.write_bytes(content)

    def _write_volcengine_doubao_audio(self, *, path: Path, text: str, voice_profile: str, speed: float, emotion: str) -> None:
        speaker = voice_profile.strip() or self.settings.volcengine_tts_speaker
        request_id = str(uuid.uuid4())
        payload = {
            "user": {"uid": "chenflow"},
            "req_params": {
                "text": text,
                "speaker": speaker,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": self.settings.volcengine_tts_sample_rate,
                    "enable_timestamp": False,
                },
                "additions": self._volcengine_additions(speed=speed, emotion=emotion),
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Api-App-Id": self.settings.volcengine_tts_app_id,
            "X-Api-Access-Key": self.settings.volcengine_tts_access_key or self.settings.volcengine_tts_api_key,
            "X-Api-Resource-Id": self.settings.volcengine_tts_resource_id,
            "X-Api-Request-Id": request_id,
        }
        if self.settings.volcengine_tts_model:
            headers["X-Api-Model"] = self.settings.volcengine_tts_model
        request = urllib.request.Request(
            self.settings.volcengine_tts_endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(f"豆包语音接口调用失败：{exc}") from exc
        audio_bytes = self._extract_volcengine_audio(content)
        if not audio_bytes:
            raise RuntimeError("豆包语音接口返回空音频。")
        path.write_bytes(audio_bytes)

    def _extract_volcengine_audio(self, content: bytes) -> bytes:
        chunks: list[bytes] = []
        last_error = ""
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line.decode("utf-8"))
            except Exception as exc:
                last_error = str(exc)
                continue
            code = payload.get("code")
            if code not in (None, 0, 20000000):
                raise RuntimeError(f"豆包语音接口返回错误：{payload}")
            data = payload.get("data")
            if isinstance(data, str) and data:
                chunks.append(base64.b64decode(data))
        if chunks:
            return b"".join(chunks)
        try:
            payload = json.loads(content.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"豆包语音接口返回无法解析：{last_error or exc}") from exc
        data = payload.get("data")
        if isinstance(data, str) and data:
            return base64.b64decode(data)
        raise RuntimeError(f"豆包语音接口没有返回音频 data：{payload}")

    def _volcengine_additions(self, *, speed: float, emotion: str) -> dict[str, str]:
        additions: dict[str, str] = {}
        if speed and abs(speed - 1.0) > 0.001:
            additions["speed_ratio"] = f"{speed:.2f}"
        if emotion.strip():
            additions["emotion"] = emotion.strip()
        return additions

    def _dialogue_items(self, script: Any) -> list[dict[str, Any]]:
        if not isinstance(script, dict):
            return []
        items: list[dict[str, Any]] = []
        for index, item in enumerate(script.get("dialogues") if isinstance(script.get("dialogues"), list) else [], start=1):
            if not isinstance(item, dict):
                continue
            if not str(item.get("line") or "").strip():
                continue
            items.append({**item, "dialogue_index": index})
        return items

    def _provider(self, provider: str) -> str:
        return (provider or self.settings.tts_provider or "openai_compatible").strip().lower()

    def _default_voice_profile(self, provider: str) -> str:
        if self._provider(provider) == "volcengine_doubao":
            return self.settings.volcengine_tts_speaker
        return self.settings.tts_voice

    def _model_name(self, provider: str) -> str:
        if self._provider(provider) == "volcengine_doubao":
            return self.settings.volcengine_tts_model or self.settings.volcengine_tts_resource_id
        return self.settings.tts_model

    def _resolve_character(
        self,
        *,
        project: Project,
        character_card_id: Any,
        character_name: str,
    ) -> CharacterCard | None:
        if isinstance(character_card_id, int):
            for item in project.character_cards:
                if item.deleted_at is None and item.id == character_card_id:
                    return item
        normalized_name = character_name.strip().lower()
        if normalized_name:
            for item in project.character_cards:
                if item.deleted_at is None and item.name.strip().lower() == normalized_name:
                    return item
        return None

    def _voice_asset(
        self,
        *,
        db: Session,
        project: Project,
        storyboard: Storyboard,
        shot: StoryboardShot,
        asset_type: str,
        character: CharacterCard | None,
        dialogue_index: int = 0,
    ) -> MediaAsset:
        expected_meta_character_id = character.id if character and asset_type == "dialogue" else None
        expected_dialogue_index = dialogue_index if asset_type == "dialogue" else None
        asset = db.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == project.id,
                MediaAsset.storyboard_id == storyboard.id,
                MediaAsset.shot_id == shot.id,
                MediaAsset.asset_type == asset_type,
            )
        )
        if asset is not None and asset_type != "dialogue":
            return asset
        if asset is not None and asset_type == "dialogue":
            asset_meta = json_loads_object(asset.meta_json)
            if (
                asset_meta.get("character_card_id") == expected_meta_character_id
                and int(asset_meta.get("dialogue_index") or 0) == int(expected_dialogue_index or 0)
            ):
                return asset
            asset = None
        if asset is not None:
            return asset
        if asset_type == "dialogue":
            existing_assets = db.scalars(
                select(MediaAsset).where(
                    MediaAsset.project_id == project.id,
                    MediaAsset.storyboard_id == storyboard.id,
                    MediaAsset.shot_id == shot.id,
                    MediaAsset.asset_type == asset_type,
                )
            ).all()
            for existing in existing_assets:
                existing_meta = json_loads_object(existing.meta_json)
                if (
                    existing_meta.get("character_card_id") == expected_meta_character_id
                    and int(existing_meta.get("dialogue_index") or 0) == int(expected_dialogue_index or 0)
                ):
                    return existing
        asset = MediaAsset(
            project_id=project.id,
            storyboard=storyboard,
            shot=shot,
            asset_type=asset_type,
            uri="",
            prompt=shot.narration_text,
            status="pending",
            meta_json=json_dumps(
                {
                    "shot_no": shot.shot_no,
                    "purpose": "角色对白" if asset_type == "dialogue" else "旁白",
                    "character_card_id": expected_meta_character_id,
                    "character_name": character.name if character else "",
                    "dialogue_index": expected_dialogue_index,
                }
            ),
        )
        db.add(asset)
        db.flush()
        return asset

    def _output_dir(self, *, project: Project, storyboard: Storyboard) -> Path:
        return (
            self.settings.output_dir
            / "projects"
            / f"{project.id:04d}-{self._path_slug(project.title)}"
            / "storyboards"
            / f"{storyboard.id:04d}-{self._path_slug(storyboard.title)}"
            / "voice"
        )

    def _audio_file_name(self, *, shot: StoryboardShot, asset_type: str, character: CharacterCard | None, dialogue_index: int = 0) -> str:
        if asset_type == "dialogue":
            name = self._path_slug(character.name if character else "character", fallback="character")
            suffix = f"-{dialogue_index:02d}" if dialogue_index > 0 else ""
            return f"shot-{shot.shot_no:03d}-dialogue-{name}{suffix}.mp3"
        return f"shot-{shot.shot_no:03d}-voice.mp3"

    def _path_slug(self, value: str, *, fallback: str = "untitled") -> str:
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value.strip())
        text = re.sub(r"\s+", "-", text).strip(".- ")
        return (text or fallback)[:80]
