from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import time
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .config import Settings
from .jimeng_video_client import JimengVideoClient
from .json_utils import json_dumps, json_loads_list, json_loads_object
from .models import MediaAsset, NovelChapter, StoryboardShot, TaskEvent, VideoTask
from .visual_style_prompt import build_visual_generation_prompt, project_visual_style_summary


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

        output_dir = self._output_dir(db=db, task=task)
        output_dir.mkdir(parents=True, exist_ok=True)
        shots = sorted(task.storyboard.shots, key=lambda item: item.shot_no)
        if not shots:
            raise RuntimeError("分镜稿没有镜头，无法生成视频。")

        if self._jimeng_enabled():
            return self._render_with_jimeng(db=db, task=task, shots=shots, output_dir=output_dir)
        return self._render_with_local_pipeline(db=db, task=task, shots=shots, output_dir=output_dir)

    def _render_with_jimeng(
        self,
        *,
        db: Session,
        task: VideoTask,
        shots: list[StoryboardShot],
        output_dir: Path,
    ) -> VideoTask:
        client = JimengVideoClient(
            access_key=self.settings.jimeng_access_key,
            secret_key=self.settings.jimeng_secret_key,
            endpoint=self.settings.jimeng_endpoint,
            region=self.settings.jimeng_region,
            service=self.settings.jimeng_service,
            req_key=self.settings.jimeng_req_key,
        )
        segment_paths: list[Path] = []
        for shot in shots:
            prompt = self._build_jimeng_prompt(task, shot)
            self._set_progress(
                task,
                stage="jimeng_submit",
                message=f"提交即梦 720P 镜头 {shot.shot_no} 视频任务。",
                extra={
                    "provider": "jimeng",
                    "req_key": self.settings.jimeng_req_key,
                    "shot_no": shot.shot_no,
                    "frames": self.settings.jimeng_frames,
                    "aspect_ratio": self.settings.jimeng_aspect_ratio,
                },
            )
            self._add_event(
                db,
                task=task,
                event_type="video_task_jimeng_submit",
                message=f"提交即梦镜头 {shot.shot_no} 视频任务。",
                payload={"shot_no": shot.shot_no, "req_key": self.settings.jimeng_req_key, "prompt": prompt},
            )
            db.commit()
            jimeng_task_id, submit_response = client.submit_text_to_video(
                prompt=prompt,
                frames=self.settings.jimeng_frames,
                aspect_ratio=self.settings.jimeng_aspect_ratio,
            )
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="video",
                uri="",
                prompt=prompt,
                status="running",
                meta={
                    "provider": "jimeng",
                    "jimeng_task_id": jimeng_task_id,
                    "submit_response": submit_response,
                    "req_key": self.settings.jimeng_req_key,
                },
            )
            self._set_progress(
                task,
                stage="jimeng_poll",
                message=f"等待即梦镜头 {shot.shot_no} 生成完成。",
                extra={"shot_no": shot.shot_no, "jimeng_task_id": jimeng_task_id},
            )
            db.commit()
            video_url, result_response = self._wait_for_jimeng_result(client=client, task_id=jimeng_task_id)
            segment_path = output_dir / f"segment-{shot.shot_no:03d}.mp4"
            self._download_file(url=video_url, path=segment_path)
            segment_paths.append(segment_path)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="video",
                uri=str(segment_path),
                prompt=prompt,
                status="completed",
                meta={
                    "provider": "jimeng",
                    "jimeng_task_id": jimeng_task_id,
                    "video_url": video_url,
                    "result_response": result_response,
                    "req_key": self.settings.jimeng_req_key,
                },
            )
            self._add_event(
                db,
                task=task,
                event_type="video_task_jimeng_segment_completed",
                message=f"即梦镜头 {shot.shot_no} 视频生成完成。",
                payload={"shot_no": shot.shot_no, "jimeng_task_id": jimeng_task_id, "segment_path": str(segment_path)},
            )
            db.commit()

        self._set_progress(task, stage="compose", message="合成最终 MP4。", extra={"provider": "jimeng"})
        self._add_event(db, task=task, event_type="video_task_compose", message="合成最终 MP4。")
        db.commit()
        final_path = self._concat_segments(segment_paths=segment_paths, output_dir=output_dir)
        task.output_uri = str(final_path)
        task.task_status = "completed"
        task.storyboard.status = "video_completed"
        self._set_progress(task, stage="completed", message="视频生产完成。", extra={"output_uri": task.output_uri})
        self._add_event(db, task=task, event_type="video_task_completed", message="视频生产完成。", payload={"output_uri": task.output_uri})
        db.commit()
        db.refresh(task)
        return task

    def _render_with_local_pipeline(
        self,
        *,
        db: Session,
        task: VideoTask,
        shots: list[StoryboardShot],
        output_dir: Path,
    ) -> VideoTask:
        segment_paths: list[Path] = []
        for shot in shots:
            self._set_progress(task, stage="image", message=f"生成镜头 {shot.shot_no} 图片。")
            self._add_event(db, task=task, event_type="video_task_image", message=f"生成镜头 {shot.shot_no} 图片。")
            db.commit()
            image_prompt = self._build_image_prompt(task, shot)
            image_path = self._generate_image(prompt=image_prompt, shot=shot, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="image",
                uri=str(image_path),
                prompt=image_prompt,
                status="completed",
                meta={"visual_style": project_visual_style_summary(task.project)},
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
        task.storyboard.status = "video_completed"
        self._set_progress(task, stage="completed", message="视频生产完成。")
        self._add_event(db, task=task, event_type="video_task_completed", message="视频生产完成。", payload={"output_uri": task.output_uri})
        db.commit()
        db.refresh(task)
        return task

    def _require_config(self) -> None:
        if self._jimeng_enabled():
            missing = []
            if not self.settings.jimeng_access_key:
                missing.append("JIMENG_ACCESS_KEY")
            if not self.settings.jimeng_secret_key:
                missing.append("JIMENG_SECRET_KEY")
            if not self.settings.ffmpeg_path:
                missing.append("CHENFLOW_FFMPEG_PATH")
            if missing:
                raise RuntimeError("即梦视频生产配置缺失：" + "、".join(missing))
            if self.settings.jimeng_frames not in {121, 241}:
                raise RuntimeError("JIMENG_VIDEO_FRAMES 只能配置为 121（5秒）或 241（10秒）。")
            return

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

    def _jimeng_enabled(self) -> bool:
        return bool(self.settings.jimeng_access_key or self.settings.jimeng_secret_key)

    def _build_jimeng_prompt(self, task: VideoTask, shot: StoryboardShot) -> str:
        return build_visual_generation_prompt(
            project=task.project,
            shot=shot,
            include_narration=True,
            max_length=1200,
        )

    def _build_image_prompt(self, task: VideoTask, shot: StoryboardShot) -> str:
        return build_visual_generation_prompt(
            project=task.project,
            shot=shot,
            include_narration=False,
            max_length=1800,
        )

    def _wait_for_jimeng_result(self, *, client: JimengVideoClient, task_id: str) -> tuple[str, dict[str, Any]]:
        deadline = time.monotonic() + self.settings.jimeng_poll_timeout_seconds
        last_response: dict[str, Any] = {}
        while time.monotonic() < deadline:
            result = client.get_result(task_id=task_id)
            last_response = result.raw
            if result.status == "done":
                if result.video_url:
                    return result.video_url, result.raw
                raise RuntimeError(f"即梦任务已完成但没有返回 video_url：{task_id}")
            if result.status in {"not_found", "expired"}:
                raise RuntimeError(f"即梦任务状态异常：{result.status}，task_id={task_id}")
            if result.status not in {"in_queue", "generating"}:
                raise RuntimeError(f"即梦任务返回未知状态：{result.status}，task_id={task_id}")
            time.sleep(self.settings.jimeng_poll_interval_seconds)
        raise RuntimeError(f"即梦任务等待超时：task_id={task_id}, last_response={last_response}")

    def _download_file(self, *, url: str, path: Path) -> None:
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(f"下载即梦视频失败：{exc}") from exc
        if not content:
            raise RuntimeError("下载即梦视频失败：返回空文件。")
        path.write_bytes(content)

    def _output_dir(self, *, db: Session, task: VideoTask) -> Path:
        project = task.project
        storyboard = task.storyboard
        project_dir = f"{project.id:04d}-{self._path_slug(project.title)}" if project is not None else f"project-{task.project_id:04d}"
        chapter_dir = self._chapter_dir_name(db=db, task=task)
        storyboard_dir = f"{storyboard.id:04d}-{self._path_slug(storyboard.title)}"
        return (
            self.settings.output_dir
            / "projects"
            / project_dir
            / "chapters"
            / chapter_dir
            / "storyboards"
            / storyboard_dir
            / "video_tasks"
            / f"{task.id:04d}"
        )

    def _chapter_dir_name(self, *, db: Session, task: VideoTask) -> str:
        chapter_ids = [int(item) for item in json_loads_list(task.storyboard.source_chapter_ids_json) if str(item).isdigit()]
        if not chapter_ids:
            return "chapter-unassigned"
        chapters = db.query(NovelChapter).filter(NovelChapter.id.in_(chapter_ids)).order_by(NovelChapter.chapter_no.asc()).all()
        if len(chapters) == 1:
            chapter = chapters[0]
            return f"chapter-{chapter.chapter_no:03d}-{self._path_slug(chapter.title)}"
        chapter_numbers = "-".join(str(item.chapter_no).zfill(3) for item in chapters)
        return f"chapters-{chapter_numbers or 'mixed'}"

    def _path_slug(self, value: str, *, fallback: str = "untitled") -> str:
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value.strip())
        text = re.sub(r"\s+", "-", text).strip(".- ")
        return (text or fallback)[:80]

    def _generate_image(self, *, prompt: str, shot: StoryboardShot, output_dir: Path) -> Path:
        payload = {
            "model": self.settings.image_model,
            "prompt": prompt,
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
        meta: dict[str, Any] | None = None,
    ) -> None:
        asset = next((item for item in task.storyboard.media_assets if item.shot_id == shot.id and item.asset_type == asset_type), None)
        asset_meta = {"video_task_id": task.id, "shot_no": shot.shot_no, "mime_type": mimetypes.guess_type(uri)[0] or ""}
        if meta:
            asset_meta.update(meta)
        if asset is None:
            asset = MediaAsset(
                project_id=task.project_id,
                storyboard=task.storyboard,
                shot=shot,
                asset_type=asset_type,
                uri=uri,
                prompt=prompt,
                status=status,
                meta_json=json_dumps(asset_meta),
            )
            db.add(asset)
            return
        asset.uri = uri
        asset.prompt = prompt
        asset.status = status
        asset.meta_json = json_dumps({**json_loads_object(asset.meta_json), **asset_meta})

    def _set_progress(self, task: VideoTask, *, stage: str, message: str, extra: dict[str, Any] | None = None) -> None:
        payload = json_loads_object(task.progress_json)
        payload["stage"] = stage
        payload["message"] = message
        if extra:
            payload.update(extra)
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
