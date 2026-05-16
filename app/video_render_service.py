from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .config import Settings
from .json_utils import json_dumps, json_loads_object
from .models import MediaAsset, StoryboardShot, TaskEvent, VideoTask


class VideoRenderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render(self, *, db: Session, task: VideoTask) -> VideoTask:
        self._require_config()
        task.task_status = "running"
        task.error_message = ""
        self._set_progress(task, stage="running", message="视频生产开始。")
        self._add_event(db, task=task, event_type="video_task_running", message="视频生产开始。")
        db.commit()

        output_dir = self.settings.output_dir / "video_tasks" / str(task.id)
        output_dir.mkdir(parents=True, exist_ok=True)
        shots = sorted(task.storyboard.shots, key=lambda item: item.shot_no)
        if not shots:
            raise RuntimeError("分镜稿没有镜头，无法生成视频。")

        segment_paths: list[Path] = []
        for shot in shots:
            self._set_progress(task, stage="image", message=f"生成镜头 {shot.shot_no} 图片。")
            self._add_event(db, task=task, event_type="video_task_image", message=f"生成镜头 {shot.shot_no} 图片。")
            db.commit()
            image_path = self._generate_image(shot=shot, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="image",
                uri=str(image_path),
                prompt=shot.visual_prompt,
                status="completed",
            )

            self._set_progress(task, stage="voice", message=f"生成镜头 {shot.shot_no} 旁白。")
            self._add_event(db, task=task, event_type="video_task_voice", message=f"生成镜头 {shot.shot_no} 旁白。")
            db.commit()
            audio_path = self._generate_voice(shot=shot, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="voice",
                uri=str(audio_path),
                prompt=shot.narration_text,
                status="completed",
            )

            subtitle_path = self._write_subtitle(shot=shot, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="subtitle",
                uri=str(subtitle_path),
                prompt=shot.narration_text,
                status="completed",
            )

            self._set_progress(task, stage="compose", message=f"合成镜头 {shot.shot_no} 片段。")
            db.commit()
            segment_paths.append(self._compose_segment(shot=shot, image_path=image_path, audio_path=audio_path, output_dir=output_dir))

        self._set_progress(task, stage="compose", message="合成最终 MP4。")
        self._add_event(db, task=task, event_type="video_task_compose", message="合成最终 MP4。")
        db.commit()
        final_path = self._concat_segments(segment_paths=segment_paths, output_dir=output_dir)
        task.output_uri = str(final_path)
        task.task_status = "completed"
        self._set_progress(task, stage="completed", message="视频生产完成。")
        self._add_event(db, task=task, event_type="video_task_completed", message="视频生产完成。", payload={"output_uri": task.output_uri})
        db.commit()
        db.refresh(task)
        return task

    def _require_config(self) -> None:
        missing = []
        if not self.settings.image_api_key:
            missing.append("CHENFLOW_IMAGE_API_KEY")
        if not self.settings.image_base_url:
            missing.append("CHENFLOW_IMAGE_BASE_URL")
        if not self.settings.image_model:
            missing.append("CHENFLOW_IMAGE_MODEL")
        if not self.settings.tts_api_key:
            missing.append("CHENFLOW_TTS_API_KEY")
        if not self.settings.tts_base_url:
            missing.append("CHENFLOW_TTS_BASE_URL")
        if not self.settings.tts_model:
            missing.append("CHENFLOW_TTS_MODEL")
        if not self.settings.tts_voice:
            missing.append("CHENFLOW_TTS_VOICE")
        if missing:
            raise RuntimeError("视频生产配置缺失：" + "、".join(missing))

    def _generate_image(self, *, shot: StoryboardShot, output_dir: Path) -> Path:
        payload = {
            "model": self.settings.image_model,
            "prompt": shot.visual_prompt,
            "size": self.settings.image_size,
            "n": 1,
        }
        response = self._json_request(
            url=f"{self.settings.image_base_url.rstrip('/')}/images/generations",
            api_key=self.settings.image_api_key,
            payload=payload,
        )
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError("图像生成接口没有返回 data。")
        first = data[0] if isinstance(data[0], dict) else {}
        image_path = output_dir / f"shot-{shot.shot_no:03d}.png"
        if isinstance(first.get("b64_json"), str) and first["b64_json"]:
            image_path.write_bytes(base64.b64decode(first["b64_json"]))
            return image_path
        if isinstance(first.get("url"), str) and first["url"]:
            with urllib.request.urlopen(first["url"], timeout=120) as response_file:
                image_path.write_bytes(response_file.read())
            return image_path
        raise RuntimeError("图像生成接口没有返回 b64_json 或 url。")

    def _generate_voice(self, *, shot: StoryboardShot, output_dir: Path) -> Path:
        payload = {
            "model": self.settings.tts_model,
            "voice": self.settings.tts_voice,
            "input": shot.narration_text,
            "response_format": "mp3",
        }
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
        audio_path = output_dir / f"shot-{shot.shot_no:03d}.mp3"
        audio_path.write_bytes(content)
        return audio_path

    def _write_subtitle(self, *, shot: StoryboardShot, output_dir: Path) -> Path:
        duration = max(float(shot.duration_seconds or 4), 0.5)
        subtitle_path = output_dir / f"shot-{shot.shot_no:03d}.srt"
        subtitle_path.write_text(
            "\n".join(
                [
                    "1",
                    f"00:00:00,000 --> {self._srt_time(duration)}",
                    shot.narration_text.strip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return subtitle_path

    def _compose_segment(self, *, shot: StoryboardShot, image_path: Path, audio_path: Path, output_dir: Path) -> Path:
        segment_path = output_dir / f"segment-{shot.shot_no:03d}.mp4"
        duration = max(float(shot.duration_seconds or 4), 0.5)
        self._run_ffmpeg(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-loop",
                "1",
                "-t",
                str(duration),
                "-i",
                str(image_path),
                "-i",
                str(audio_path),
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-shortest",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(segment_path),
            ]
        )
        return segment_path

    def _concat_segments(self, *, segment_paths: list[Path], output_dir: Path) -> Path:
        concat_file = output_dir / "segments.txt"
        concat_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in segment_paths), encoding="utf-8")
        final_path = output_dir / "final.mp4"
        self._run_ffmpeg(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(final_path),
            ]
        )
        return final_path

    def _json_request(self, *, url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise RuntimeError(f"接口调用失败：{exc}") from exc
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("接口没有返回合法 JSON。") from exc
        if not isinstance(data, dict):
            raise RuntimeError("接口返回不是 JSON 对象。")
        return data

    def _run_ffmpeg(self, args: list[str]) -> None:
        try:
            completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(f"找不到 FFmpeg：{self.settings.ffmpeg_path}") from exc
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg 执行失败：{completed.stderr.strip()}")

    def _upsert_asset(
        self,
        db: Session,
        *,
        task: VideoTask,
        shot: StoryboardShot,
        asset_type: str,
        uri: str,
        prompt: str,
        status: str,
    ) -> None:
        asset = next((item for item in task.storyboard.media_assets if item.shot_id == shot.id and item.asset_type == asset_type), None)
        meta = {"video_task_id": task.id, "shot_no": shot.shot_no, "mime_type": mimetypes.guess_type(uri)[0] or ""}
        if asset is None:
            asset = MediaAsset(
                project_id=task.project_id,
                storyboard=task.storyboard,
                shot=shot,
                asset_type=asset_type,
                uri=uri,
                prompt=prompt,
                status=status,
                meta_json=json_dumps(meta),
            )
            db.add(asset)
            return
        asset.uri = uri
        asset.prompt = prompt
        asset.status = status
        asset.meta_json = json_dumps({**json_loads_object(asset.meta_json), **meta})

    def _set_progress(self, task: VideoTask, *, stage: str, message: str) -> None:
        payload = json_loads_object(task.progress_json)
        payload["stage"] = stage
        payload["message"] = message
        task.progress_json = json_dumps(payload)

    def _add_event(self, db: Session, *, task: VideoTask, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        db.add(
            TaskEvent(
                project_id=task.project_id,
                storyboard_id=task.storyboard_id,
                video_task=task,
                event_type=event_type,
                message=message,
                payload_json=json_dumps(payload or {}),
            )
        )

    def _srt_time(self, seconds: float) -> str:
        delta = timedelta(seconds=seconds)
        total = int(delta.total_seconds())
        millis = int((delta.total_seconds() - total) * 1000)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
