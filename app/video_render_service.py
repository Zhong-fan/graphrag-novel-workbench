from __future__ import annotations

import base64
import json
import mimetypes
import re
import subprocess
import time
import urllib.request
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .config import Settings
from .jimeng_video_client import JimengVideoClient
from .json_utils import ensure_list, json_dumps, json_loads_list, json_loads_object
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
        text_client = JimengVideoClient(
            access_key=self.settings.jimeng_access_key,
            secret_key=self.settings.jimeng_secret_key,
            endpoint=self.settings.jimeng_endpoint,
            region=self.settings.jimeng_region,
            service=self.settings.jimeng_service,
            req_key=self.settings.jimeng_req_key,
        )
        image_client = JimengVideoClient(
            access_key=self.settings.jimeng_access_key,
            secret_key=self.settings.jimeng_secret_key,
            endpoint=self.settings.jimeng_endpoint,
            region=self.settings.jimeng_region,
            service=self.settings.jimeng_service,
            req_key=self.settings.jimeng_i2v_req_key,
        )
        composed_paths: list[Path] = []
        for shot in shots:
            self._set_current_shot(task, shot=shot, step="jimeng_submit")
            first_frame_asset = self._shot_first_frame_asset(task=task, shot=shot)
            prompt = self._build_jimeng_prompt(task, shot, first_frame_asset=first_frame_asset)
            self._set_progress(
                task,
                stage="jimeng_submit",
                message=f"提交即梦镜头 {shot.shot_no} 视频任务。",
                extra={"provider": "jimeng", "shot_no": shot.shot_no, "used_first_frame": first_frame_asset is not None},
            )
            self._add_event(
                db,
                task=task,
                event_type="video_task_jimeng_submit",
                message=f"提交即梦镜头 {shot.shot_no} 视频任务。",
                payload={
                    "shot_no": shot.shot_no,
                    "req_key": self.settings.jimeng_req_key,
                    "prompt": prompt,
                    "used_first_frame": first_frame_asset is not None,
                    "first_frame_asset_id": first_frame_asset.id if first_frame_asset is not None else None,
                },
            )
            self._mark_step(task, "image", "running")
            self._update_shot_progress(task, shot, image_status="running")
            db.commit()

            if first_frame_asset is not None:
                first_frame_url = self._resolvable_asset_url(first_frame_asset)
                if first_frame_url:
                    jimeng_task_id, submit_response = image_client.submit_first_frame_to_video(
                        prompt=prompt,
                        image_url=first_frame_url,
                        frames=self.settings.jimeng_frames,
                        aspect_ratio=self.settings.jimeng_aspect_ratio,
                    )
                else:
                    jimeng_task_id, submit_response = text_client.submit_text_to_video(
                        prompt=prompt,
                        frames=self.settings.jimeng_frames,
                        aspect_ratio=self.settings.jimeng_aspect_ratio,
                    )
            else:
                jimeng_task_id, submit_response = text_client.submit_text_to_video(
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
                    "req_key": self.settings.jimeng_i2v_req_key if first_frame_asset is not None else self.settings.jimeng_req_key,
                    "used_first_frame": first_frame_asset is not None,
                    "shot_first_frame_asset_id": first_frame_asset.id if first_frame_asset is not None else None,
                },
            )
            self._set_progress(
                task,
                stage="jimeng_poll",
                message=f"等待即梦镜头 {shot.shot_no} 生成完成。",
                extra={
                    "provider": "jimeng",
                    "shot_no": shot.shot_no,
                    "jimeng_task_id": jimeng_task_id,
                    "used_first_frame": first_frame_asset is not None,
                },
            )
            self._set_current_shot(task, shot=shot, step="jimeng_poll")
            db.commit()

            video_url, result_response = self._wait_for_jimeng_result(client=image_client if first_frame_asset is not None else text_client, task_id=jimeng_task_id)
            segment_path = output_dir / f"segment-{shot.shot_no:03d}.mp4"
            self._download_file(url=video_url, path=segment_path)
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
                    "req_key": self.settings.jimeng_i2v_req_key if first_frame_asset is not None else self.settings.jimeng_req_key,
                    "used_first_frame": first_frame_asset is not None,
                    "shot_first_frame_asset_id": first_frame_asset.id if first_frame_asset is not None else None,
                },
            )
            self._mark_step(task, "image", "running")
            self._increment_progress_counter(task, "segment_count")
            self._update_shot_progress(
                task,
                shot,
                image_status="completed",
                segment_status="completed",
                segment_uri=str(segment_path),
                used_first_frame=first_frame_asset is not None,
            )
            self._add_event(
                db,
                task=task,
                event_type="video_task_jimeng_segment_completed",
                message=f"即梦镜头 {shot.shot_no} 视频生成完成。",
                payload={"shot_no": shot.shot_no, "jimeng_task_id": jimeng_task_id, "segment_path": str(segment_path)},
            )
            db.commit()

            self._set_current_shot(task, shot=shot, step="shot_post_process")
            composed_paths.append(self._post_process_shot(db=db, task=task, shot=shot, output_dir=output_dir, segment_path=segment_path))
            self._mark_shot_completed(task, shot=shot)
            db.commit()

        return self._finalize_video_task(db=db, task=task, output_dir=output_dir, segment_paths=composed_paths, provider="jimeng")

    def _render_with_local_pipeline(
        self,
        *,
        db: Session,
        task: VideoTask,
        shots: list[StoryboardShot],
        output_dir: Path,
    ) -> VideoTask:
        composed_paths: list[Path] = []
        for shot in shots:
            self._set_current_shot(task, shot=shot, step="image_generate")
            first_frame_asset = self._shot_first_frame_asset(task=task, shot=shot)
            if first_frame_asset is not None and first_frame_asset.uri and Path(first_frame_asset.uri).exists():
                self._set_progress(task, stage="image", message=f"复用镜头 {shot.shot_no} 已确认首帧。", extra={"shot_no": shot.shot_no, "used_first_frame": True})
                self._add_event(db, task=task, event_type="video_task_image", message=f"复用镜头 {shot.shot_no} 已确认首帧。")
            else:
                self._set_progress(task, stage="image", message=f"生成镜头 {shot.shot_no} 图片。", extra={"shot_no": shot.shot_no})
                self._add_event(db, task=task, event_type="video_task_image", message=f"生成镜头 {shot.shot_no} 图片。")
            self._mark_step(task, "image", "running")
            self._update_shot_progress(task, shot, image_status="running")
            db.commit()

            image_prompt = self._build_image_prompt(task, shot)
            if first_frame_asset is not None and first_frame_asset.uri and Path(first_frame_asset.uri).exists():
                image_path = Path(first_frame_asset.uri)
            else:
                image_path = self._generate_image(prompt=image_prompt, shot=shot, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="image",
                uri=str(image_path),
                prompt=image_prompt,
                status="completed",
                meta={
                    "visual_style": project_visual_style_summary(task.project),
                    "source": "shot_first_frame" if first_frame_asset is not None and first_frame_asset.uri and Path(first_frame_asset.uri).exists() else "generated_image",
                    "shot_first_frame_asset_id": first_frame_asset.id if first_frame_asset is not None else None,
                },
            )
            self._mark_step(task, "image", "running")
            self._update_shot_progress(task, shot, image_status="completed")

            self._set_progress(task, stage="voice", message=f"生成镜头 {shot.shot_no} 旁白。", extra={"shot_no": shot.shot_no})
            self._add_event(db, task=task, event_type="video_task_voice", message=f"生成镜头 {shot.shot_no} 旁白。")
            self._mark_step(task, "voice", "running")
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
            self._mark_step(task, "voice", "running")

            self._set_current_shot(task, shot=shot, step="segment_compose")
            self._set_progress(task, stage="compose", message=f"合成镜头 {shot.shot_no} 片段。", extra={"shot_no": shot.shot_no})
            self._mark_step(task, "compose", "running")
            db.commit()

            segment_path = self._compose_segment_from_image(shot=shot, image_path=image_path, audio_path=audio_path, output_dir=output_dir)
            self._upsert_asset(
                db,
                task=task,
                shot=shot,
                asset_type="video",
                uri=str(segment_path),
                prompt=image_prompt,
                status="completed",
                meta={"provider": "local_pipeline"},
            )
            self._increment_progress_counter(task, "segment_count")
            self._update_shot_progress(task, shot, segment_status="completed", segment_uri=str(segment_path))

            composed_paths.append(self._post_process_shot(db=db, task=task, shot=shot, output_dir=output_dir, segment_path=segment_path))
            self._mark_shot_completed(task, shot=shot)
            db.commit()

        return self._finalize_video_task(db=db, task=task, output_dir=output_dir, segment_paths=composed_paths, provider="local_pipeline")

    def _post_process_shot(
        self,
        *,
        db: Session,
        task: VideoTask,
        shot: StoryboardShot,
        output_dir: Path,
        segment_path: Path,
    ) -> Path:
        self._set_current_shot(task, shot=shot, step="subtitle_generate")
        subtitle_path = self._write_subtitle(shot=shot, output_dir=output_dir)
        self._upsert_asset(
            db,
            task=task,
            shot=shot,
            asset_type="subtitle",
            uri=str(subtitle_path),
            prompt=self._subtitle_prompt(shot),
            status="completed",
        )
        self._mark_step(task, "subtitle", "running")
        self._increment_progress_counter(task, "subtitle_count")
        self._update_shot_progress(task, shot, subtitle_status="completed", subtitle_uri=str(subtitle_path))

        self._set_current_shot(task, shot=shot, step="dialogue_merge")
        dialogue_assets = self._dialogue_assets(task=task, shot=shot)
        dialogue_path = self._merge_dialogue_audio(shot=shot, dialogue_assets=dialogue_assets, output_dir=output_dir)
        warning: str | None = None
        if dialogue_assets and dialogue_path is not None:
            self._set_current_shot(task, shot=shot, step="dialogue_compose")
            composed_path = self._compose_segment_with_dialogue(shot=shot, segment_path=segment_path, dialogue_path=dialogue_path, output_dir=output_dir)
            self._mark_step(task, "voice", "running")
            self._mark_step(task, "compose", "running")
            self._increment_progress_counter(task, "audio_composed_count")
            self._update_shot_progress(
                task,
                shot,
                dialogue_status="completed",
                dialogue_uri=str(dialogue_path),
                composed_status="completed",
                composed_uri=str(composed_path),
            )
            return composed_path

        if dialogue_assets:
            warning = "镜头存在对白资产，但没有找到可用音频文件，已保留无声片段。"
            self._update_shot_progress(task, shot, dialogue_status="failed", composed_status="completed", composed_uri=str(segment_path), warning=warning)
        else:
            warning = "镜头没有对白音频，已直接使用原始视频片段。"
            self._update_shot_progress(task, shot, dialogue_status="missing", composed_status="completed", composed_uri=str(segment_path), warning=warning)
        return segment_path

    def _finalize_video_task(
        self,
        *,
        db: Session,
        task: VideoTask,
        output_dir: Path,
        segment_paths: list[Path],
        provider: str,
    ) -> VideoTask:
        self._set_progress(task, stage="compose", message="合成最终 MP4。", extra={"provider": provider})
        payload = json_loads_object(task.progress_json)
        payload["failure_stage"] = ""
        task.progress_json = json_dumps(payload)
        self._set_current_step(task, step="final_concat")
        self._mark_step(task, "compose", "running")
        self._add_event(db, task=task, event_type="video_task_compose", message="合成最终 MP4。")
        db.commit()

        final_path = self._concat_segments(segment_paths=segment_paths, output_dir=output_dir)
        task.output_uri = str(final_path)
        task.task_status = "completed"
        task.storyboard.status = "video_completed"
        self._mark_step(task, "image", "completed")
        self._mark_step(task, "voice", "completed")
        self._mark_step(task, "subtitle", "completed")
        self._mark_step(task, "compose", "completed")
        self._clear_current_shot(task)
        self._set_progress(task, stage="completed", message="视频生产完成。", extra={"output_uri": task.output_uri, "provider": provider})
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
                raise RuntimeError("JIMENG_VIDEO_FRAMES 只能配置为 121（5 秒）或 241（10 秒）。")
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

    def _build_jimeng_prompt(self, task: VideoTask, shot: StoryboardShot, first_frame_asset: MediaAsset | None = None) -> str:
        prompt = build_visual_generation_prompt(project=task.project, shot=shot, include_narration=True, max_length=1200)
        if first_frame_asset is None:
            return prompt
        return (
            f"{prompt}\n"
            "已存在用户确认的镜头首帧，请严格保持首帧中的主体外观、构图、机位和画面氛围一致，"
            "将该首帧视为本镜头的视频起始画面参考。"
        )[:1400]

    def _build_image_prompt(self, task: VideoTask, shot: StoryboardShot) -> str:
        return build_visual_generation_prompt(project=task.project, shot=shot, include_narration=False, max_length=1800)

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
        return self.settings.output_dir / "projects" / project_dir / "chapters" / chapter_dir / "storyboards" / storyboard_dir / "video_tasks" / f"{task.id:04d}"

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
        payload = {"model": self.settings.image_model, "prompt": prompt, "size": self.settings.image_size, "n": 1}
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
            headers={"Authorization": f"Bearer {self.settings.tts_api_key}", "Content-Type": "application/json"},
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
        subtitle_path = output_dir / f"shot-{shot.shot_no:03d}.srt"
        lines = self._subtitle_lines(shot)
        subtitle_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return subtitle_path

    def _subtitle_lines(self, shot: StoryboardShot) -> list[str]:
        script = json_loads_object(shot.meta_json).get("audio_script")
        dialogue_items = [item for item in self._dialogue_items(script) if str(item.get("line") or "").strip()]
        duration = max(float(shot.duration_seconds or 4), 0.5)
        if dialogue_items:
            per_item = duration / max(len(dialogue_items), 1)
            lines: list[str] = []
            for index, item in enumerate(dialogue_items, start=1):
                start = per_item * (index - 1)
                end = duration if index == len(dialogue_items) else min(duration, per_item * index)
                lines.extend(
                    [
                        str(index),
                        f"{self._srt_time(start)} --> {self._srt_time(end)}",
                        str(item.get("line") or "").strip(),
                        "",
                    ]
                )
            return lines
        subtitle_text = self._subtitle_prompt(shot)
        return ["1", f"00:00:00,000 --> {self._srt_time(duration)}", subtitle_text, ""]

    def _subtitle_prompt(self, shot: StoryboardShot) -> str:
        script = json_loads_object(shot.meta_json).get("audio_script")
        if isinstance(script, dict):
            subtitle_text = str(script.get("subtitle_text") or "").strip()
            if subtitle_text:
                return subtitle_text
        return shot.narration_text.strip()

    def _compose_segment_from_image(self, *, shot: StoryboardShot, image_path: Path, audio_path: Path, output_dir: Path) -> Path:
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

    def _compose_segment_with_dialogue(self, *, shot: StoryboardShot, segment_path: Path, dialogue_path: Path, output_dir: Path) -> Path:
        composed_path = output_dir / f"shot-composed-{shot.shot_no:03d}.mp4"
        self._run_ffmpeg(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-i",
                str(segment_path),
                "-i",
                str(dialogue_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(composed_path),
            ]
        )
        return composed_path

    def _merge_dialogue_audio(self, *, shot: StoryboardShot, dialogue_assets: list[MediaAsset], output_dir: Path) -> Path | None:
        valid_paths = [Path(asset.uri) for asset in dialogue_assets if asset.status == "completed" and asset.uri and Path(asset.uri).exists()]
        if not valid_paths:
            return None
        if len(valid_paths) == 1:
            return valid_paths[0]
        concat_file = output_dir / f"dialogue-{shot.shot_no:03d}.txt"
        concat_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in valid_paths), encoding="utf-8")
        mixed_path = output_dir / f"shot-{shot.shot_no:03d}-dialogue-mix.mp3"
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
                str(mixed_path),
            ]
        )
        return mixed_path

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

    def _dialogue_assets(self, *, task: VideoTask, shot: StoryboardShot) -> list[MediaAsset]:
        return sorted(
            [
                asset
                for asset in task.storyboard.media_assets
                if asset.shot_id == shot.id and asset.asset_type == "dialogue"
            ],
            key=lambda asset: int(json_loads_object(asset.meta_json).get("dialogue_index") or 0),
        )

    def _shot_first_frame_asset(self, *, task: VideoTask, shot: StoryboardShot) -> MediaAsset | None:
        candidates = [
            asset
            for asset in task.storyboard.media_assets
            if asset.shot_id == shot.id and asset.asset_type == "shot_first_frame" and asset.status == "completed"
        ]
        if not candidates:
            return None
        locked = [asset for asset in candidates if json_loads_object(asset.meta_json).get("locked") is True]
        return locked[0] if locked else candidates[0]

    def _resolvable_asset_url(self, asset: MediaAsset) -> str:
        meta = json_loads_object(asset.meta_json)
        public_url = meta.get("public_url")
        if isinstance(public_url, str) and public_url.strip():
            return public_url.strip()
        if asset.uri and Path(asset.uri).exists():
            return Path(asset.uri).resolve().as_uri()
        return ""

    def _dialogue_items(self, script: Any) -> list[dict[str, Any]]:
        if not isinstance(script, dict):
            return []
        items: list[dict[str, Any]] = []
        for index, item in enumerate(ensure_list(script.get("dialogues")), start=1):
            if not isinstance(item, dict):
                continue
            line = str(item.get("line") or "").strip()
            if not line:
                continue
            items.append({**item, "dialogue_index": index})
        return items

    def _json_request(self, *, url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        if extra:
            payload.update(extra)
        task.progress_json = json_dumps(payload)

    def _increment_progress_counter(self, task: VideoTask, key: str, amount: int = 1) -> None:
        payload = json_loads_object(task.progress_json)
        payload[key] = int(payload.get(key) or 0) + amount
        task.progress_json = json_dumps(payload)

    def _mark_step(self, task: VideoTask, key: str, status: str) -> None:
        payload = json_loads_object(task.progress_json)
        steps = payload.get("steps")
        if not isinstance(steps, list):
            return
        for item in steps:
            if isinstance(item, dict) and item.get("key") == key:
                item["status"] = status
        task.progress_json = json_dumps(payload)

    def _set_current_shot(self, task: VideoTask, *, shot: StoryboardShot, step: str) -> None:
        payload = json_loads_object(task.progress_json)
        payload["current_shot_no"] = shot.shot_no
        payload["current_step"] = step
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        task.progress_json = json_dumps(payload)

    def _set_current_step(self, task: VideoTask, *, step: str) -> None:
        payload = json_loads_object(task.progress_json)
        payload["current_step"] = step
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        task.progress_json = json_dumps(payload)

    def _clear_current_shot(self, task: VideoTask) -> None:
        payload = json_loads_object(task.progress_json)
        payload["current_shot_no"] = None
        payload["current_step"] = ""
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        task.progress_json = json_dumps(payload)

    def _set_failure_stage(self, task: VideoTask, *, failure_stage: str) -> None:
        payload = json_loads_object(task.progress_json)
        payload["failure_stage"] = failure_stage
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        task.progress_json = json_dumps(payload)

    def _mark_shot_completed(self, task: VideoTask, *, shot: StoryboardShot) -> None:
        payload = json_loads_object(task.progress_json)
        shots = payload.get("shots")
        if isinstance(shots, list):
            completed = 0
            for item in shots:
                if isinstance(item, dict) and int(item.get("shot_id") or 0) == shot.id:
                    item["completed"] = True
                if isinstance(item, dict) and item.get("composed_status") == "completed":
                    completed += 1
            payload["completed_shot_count"] = completed
        payload["last_updated_at"] = datetime.utcnow().isoformat()
        task.progress_json = json_dumps(payload)

    def _update_shot_progress(
        self,
        task: VideoTask,
        shot: StoryboardShot,
        *,
        image_status: str | None = None,
        dialogue_status: str | None = None,
        subtitle_status: str | None = None,
        segment_status: str | None = None,
        composed_status: str | None = None,
        segment_uri: str | None = None,
        dialogue_uri: str | None = None,
        subtitle_uri: str | None = None,
        composed_uri: str | None = None,
        warning: str | None = None,
        used_first_frame: bool | None = None,
    ) -> None:
        payload = json_loads_object(task.progress_json)
        shots = payload.get("shots")
        if not isinstance(shots, list):
            return
        for item in shots:
            if not isinstance(item, dict) or int(item.get("shot_id") or 0) != shot.id:
                continue
            if image_status is not None:
                item["image_status"] = image_status
            if dialogue_status is not None:
                item["dialogue_status"] = dialogue_status
            if subtitle_status is not None:
                item["subtitle_status"] = subtitle_status
            if segment_status is not None:
                item["segment_status"] = segment_status
            if composed_status is not None:
                item["composed_status"] = composed_status
            if segment_uri is not None:
                item["segment_uri"] = segment_uri
            if dialogue_uri is not None:
                item["dialogue_uri"] = dialogue_uri
            if subtitle_uri is not None:
                item["subtitle_uri"] = subtitle_uri
            if composed_uri is not None:
                item["composed_uri"] = composed_uri
            if warning:
                warnings = item.get("warnings")
                if not isinstance(warnings, list):
                    warnings = []
                if warning not in warnings:
                    warnings.append(warning)
                item["warnings"] = warnings
            if used_first_frame is not None:
                item["used_first_frame"] = used_first_frame
            break
        payload["last_updated_at"] = datetime.utcnow().isoformat()
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
        delta = timedelta(seconds=max(seconds, 0))
        total = int(delta.total_seconds())
        millis = int(round((delta.total_seconds() - total) * 1000))
        if millis >= 1000:
            total += 1
            millis = 0
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
