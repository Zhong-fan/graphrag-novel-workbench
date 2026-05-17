from __future__ import annotations

import time
import base64
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .config import Settings
from .jimeng_image_client import JimengImageClient
from .json_utils import json_dumps
from .models import CharacterCard, MediaAsset, Project, TaskEvent
from .video_render_service import VideoRenderService
from .visual_style_prompt import build_character_visual_prompt, project_visual_style_summary


class VisualAssetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_character_turnaround(
        self,
        *,
        db: Session,
        project: Project,
        character: CharacterCard,
        chapter_no: int | None = None,
        prompt_note: str = "",
    ) -> MediaAsset:
        self._require_jimeng_image_config()
        prompt = self._build_turnaround_prompt(project=project, character=character, prompt_note=prompt_note)
        client = JimengImageClient(
            access_key=self.settings.jimeng_access_key,
            secret_key=self.settings.jimeng_secret_key,
            endpoint=self.settings.jimeng_endpoint,
            region=self.settings.jimeng_region,
            service=self.settings.jimeng_service,
            req_key=self.settings.jimeng_image_req_key,
        )
        task_id, submit_response = client.submit_text_to_image(
            prompt=prompt,
            width=self.settings.jimeng_image_width,
            height=self.settings.jimeng_image_height,
        )
        if task_id:
            image_payload, result_response = self._wait_for_image_result(client=client, task_id=task_id)
        else:
            data = submit_response.get("data") if isinstance(submit_response.get("data"), dict) else {}
            urls = client._extract_image_urls(data)
            images = client._extract_image_base64(data)
            if urls:
                image_payload = {"kind": "url", "value": urls[0]}
            elif images:
                image_payload = {"kind": "base64", "value": images[0]}
            else:
                raise RuntimeError("即梦图片接口没有返回 task_id 或图片 URL。")
            result_response = submit_response

        output_dir = self._visual_output_dir(project=project, chapter_no=chapter_no, character=character)
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / "turnaround-v001.png"
        self._save_image_payload(payload=image_payload, path=image_path)

        asset = MediaAsset(
            project_id=project.id,
            storyboard_id=None,
            shot_id=None,
            asset_type="character_turnaround",
            uri=str(image_path),
            prompt=prompt,
            status="completed",
            meta_json=json_dumps(
                {
                    "character_card_id": character.id,
                    "character_name": character.name,
                    "version": 1,
                    "locked": False,
                    "views": ["front", "side", "back"],
                    "provider": "jimeng",
                    "req_key": self.settings.jimeng_image_req_key,
                    "jimeng_task_id": task_id,
                    "submit_response": submit_response,
                    "result_response": result_response,
                    "image_source": image_payload["kind"],
                    "width": self.settings.jimeng_image_width,
                    "height": self.settings.jimeng_image_height,
                    "mime_type": "image/png",
                    "visual_style": project_visual_style_summary(project),
                }
            ),
        )
        db.add(asset)
        db.add(
            TaskEvent(
                project_id=project.id,
                event_type="visual_asset_character_turnaround_completed",
                message=f"{character.name} 三视图生成完成。",
                payload_json=json_dumps({"asset_type": asset.asset_type, "uri": str(image_path), "character_card_id": character.id}),
            )
        )
        db.commit()
        db.refresh(asset)
        return asset

    def _require_jimeng_image_config(self) -> None:
        missing = []
        if not self.settings.jimeng_access_key:
            missing.append("JIMENG_ACCESS_KEY")
        if not self.settings.jimeng_secret_key:
            missing.append("JIMENG_SECRET_KEY")
        if not self.settings.jimeng_image_req_key:
            missing.append("JIMENG_IMAGE_REQ_KEY")
        if missing:
            raise RuntimeError("即梦图片生成配置缺失：" + "、".join(missing))

    def _wait_for_image_result(self, *, client: JimengImageClient, task_id: str) -> tuple[dict[str, str], dict[str, Any]]:
        deadline = time.monotonic() + self.settings.jimeng_poll_timeout_seconds
        last_response: dict[str, Any] = {}
        while time.monotonic() < deadline:
            result = client.get_image_result(task_id=task_id)
            last_response = result.raw
            if result.status == "done":
                if result.image_urls:
                    return {"kind": "url", "value": result.image_urls[0]}, result.raw
                if result.image_base64:
                    return {"kind": "base64", "value": result.image_base64[0]}, result.raw
                raise RuntimeError(f"即梦图片任务已完成但没有返回图片 URL 或 base64：{task_id}")
            if result.status in {"not_found", "expired"}:
                raise RuntimeError(f"即梦图片任务状态异常：{result.status}，task_id={task_id}")
            if result.status not in {"in_queue", "generating"}:
                raise RuntimeError(f"即梦图片任务返回未知状态：{result.status}，task_id={task_id}")
            time.sleep(self.settings.jimeng_poll_interval_seconds)
        raise RuntimeError(f"即梦图片任务等待超时：task_id={task_id}, last_response={last_response}")

    def _download_file(self, *, url: str, path: Path) -> None:
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(f"下载即梦图片失败：{exc}") from exc
        if not content:
            raise RuntimeError("下载即梦图片失败：返回空文件。")
        path.write_bytes(content)

    def _save_image_payload(self, *, payload: dict[str, str], path: Path) -> None:
        if payload["kind"] == "url":
            self._download_file(url=payload["value"], path=path)
            return
        if payload["kind"] == "base64":
            path.write_bytes(base64.b64decode(payload["value"]))
            return
        raise RuntimeError(f"不支持的图片返回类型：{payload['kind']}")

    def _visual_output_dir(self, *, project: Project, chapter_no: int | None, character: CharacterCard) -> Path:
        path_helper = VideoRenderService(self.settings)
        project_dir = f"{project.id:04d}-{path_helper._path_slug(project.title)}"
        chapter_dir = f"chapter-{chapter_no:03d}" if chapter_no is not None else "characters"
        character_dir = f"{character.id:04d}-{path_helper._path_slug(character.name)}"
        return self.settings.output_dir / "projects" / project_dir / "chapters" / chapter_dir / "visual_assets" / "characters" / character_dir

    def _build_turnaround_prompt(self, *, project: Project, character: CharacterCard, prompt_note: str) -> str:
        details = [
            f"角色名：{character.name}",
            f"年龄：{character.age}",
            f"性别：{character.gender}",
            f"角色定位：{character.story_role}",
            f"性格：{character.personality}",
            f"背景：{character.background}",
        ]
        return build_character_visual_prompt(project=project, character_details=details, prompt_note=prompt_note)
