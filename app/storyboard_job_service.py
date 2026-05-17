from __future__ import annotations

import json
import socket
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .json_utils import ensure_list, json_dumps
from .models import Novel, NovelChapter, Project, Storyboard, StoryboardShot, TaskEvent
from .storyboard_service import StoryboardService


class StoryboardJobService:
    ACTIVE_STATUSES = ("queued", "running")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_job(
        self,
        *,
        db: Session,
        project: Project,
        current_user_id: int,
        novel_chapter_ids: list[int],
        title: str,
    ) -> Storyboard:
        chapters = self._chapters_for_project(
            db,
            project=project,
            current_user_id=current_user_id,
            novel_chapter_ids=novel_chapter_ids,
        )
        if len(chapters) != len(set(novel_chapter_ids)):
            raise RuntimeError("只能选择当前项目下已发布/定稿章节生成分镜。")

        active = db.scalar(
            select(Storyboard)
            .where(Storyboard.project_id == project.id, Storyboard.status.in_(self.ACTIVE_STATUSES))
            .order_by(Storyboard.created_at.asc())
            .limit(1)
        )
        if active is not None:
            raise RuntimeError(f"已有未完成的分镜生成任务（#{active.id}），请等待完成后再创建。")

        storyboard = Storyboard(
            project=project,
            title=title.strip() or f"{project.title} 读后短片",
            source_chapter_ids_json=json_dumps(novel_chapter_ids),
            summary="",
            status="queued",
            error_message="",
        )
        db.add(storyboard)
        db.flush()
        self._add_event(
            db,
            storyboard=storyboard,
            event_type="storyboard_queued",
            message="分镜生成任务已创建。",
            payload={"novel_chapter_ids": novel_chapter_ids},
        )
        db.commit()
        db.refresh(storyboard)
        return storyboard

    def run_next_queued_storyboard(self, *, db: Session) -> bool:
        storyboard = db.scalar(
            select(Storyboard)
            .where(Storyboard.status == "queued")
            .order_by(Storyboard.created_at.asc(), Storyboard.id.asc())
            .limit(1)
        )
        if storyboard is None:
            return False
        self.run_storyboard(db=db, storyboard=storyboard)
        return True

    def run_storyboard(self, *, db: Session, storyboard: Storyboard) -> Storyboard:
        if storyboard.status != "queued":
            return storyboard
        project = storyboard.project
        chapter_ids = [int(item) for item in ensure_list(json.loads(storyboard.source_chapter_ids_json or "[]"))]
        chapters = db.scalars(
            select(NovelChapter)
            .join(Novel, NovelChapter.novel_id == Novel.id)
            .where(
                Novel.project_id == project.id,
                Novel.deleted_at.is_(None),
                NovelChapter.id.in_(chapter_ids),
            )
            .order_by(NovelChapter.chapter_no.asc())
        ).all()
        if len(chapters) != len(set(chapter_ids)):
            storyboard.status = "failed"
            storyboard.error_message = "分镜任务引用的章节不存在或不属于当前项目。"
            self._add_event(
                db,
                storyboard=storyboard,
                event_type="storyboard_failed",
                message=storyboard.error_message,
            )
            db.commit()
            db.refresh(storyboard)
            return storyboard
        storyboard.status = "running"
        storyboard.error_message = ""
        self._touch_worker(storyboard, started=True)
        self._add_event(
            db,
            storyboard=storyboard,
            event_type="storyboard_started",
            message="分镜生成开始。",
            payload={"chapter_count": len(chapters)},
        )
        db.commit()

        try:
            generated = StoryboardService(self.settings).generate_storyboard(
                project=project,
                chapters=chapters,
                title=storyboard.title,
            )
            storyboard.title = str(generated.get("title") or storyboard.title).strip()
            storyboard.summary = str(generated.get("summary") or "").strip()
            self._touch_worker(storyboard)
            self._add_event(
                db,
                storyboard=storyboard,
                event_type="storyboard_shots_parsed",
                message="分镜内容已返回，正在整理镜头。",
                payload={"raw_shot_count": len(ensure_list(generated.get("shots")))},
            )
            shot_count = self._replace_shots(db, storyboard=storyboard, shots=ensure_list(generated.get("shots")))
            if shot_count <= 0:
                raise RuntimeError("分镜模型没有返回可用镜头。")
            storyboard.status = "draft"
            self._touch_worker(storyboard)
            self._add_event(
                db,
                storyboard=storyboard,
                event_type="storyboard_completed",
                message="分镜生成完成。",
                payload={"shot_count": shot_count},
            )
        except Exception as exc:
            storyboard.status = "failed"
            storyboard.error_message = str(exc)
            self._touch_worker(storyboard)
            self._add_event(
                db,
                storyboard=storyboard,
                event_type="storyboard_failed",
                message=f"分镜生成失败：{exc}",
            )
        db.commit()
        db.refresh(storyboard)
        return storyboard

    def _chapters_for_project(
        self,
        db: Session,
        *,
        project: Project,
        current_user_id: int,
        novel_chapter_ids: list[int],
    ) -> list[NovelChapter]:
        return db.scalars(
            select(NovelChapter)
            .join(Novel, NovelChapter.novel_id == Novel.id)
            .where(
                Novel.owner_id == current_user_id,
                Novel.project_id == project.id,
                Novel.deleted_at.is_(None),
                NovelChapter.id.in_(novel_chapter_ids),
            )
            .order_by(NovelChapter.chapter_no.asc())
        ).all()

    def _replace_shots(self, db: Session, *, storyboard: Storyboard, shots: list[Any]) -> int:
        valid_shots = [item for item in shots if isinstance(item, dict)]
        if not valid_shots:
            return 0
        for existing in list(storyboard.shots):
            db.delete(existing)
        db.flush()
        created_count = 0
        for index, shot_payload in enumerate(valid_shots, start=1):
            db.add(
                StoryboardShot(
                    storyboard=storyboard,
                    shot_no=int(shot_payload.get("shot_no") or index),
                    narration_text=str(shot_payload.get("narration_text") or "").strip(),
                    visual_prompt=str(shot_payload.get("visual_prompt") or "").strip(),
                    character_refs_json=json_dumps(ensure_list(shot_payload.get("character_refs"))),
                    scene_refs_json=json_dumps(ensure_list(shot_payload.get("scene_refs"))),
                    meta_json=json_dumps({"audio_script": self._normalize_audio_script(shot_payload.get("audio_script"))}),
                    duration_seconds=float(shot_payload.get("duration_seconds") or 4),
                    status="draft",
                )
            )
            created_count += 1
        db.flush()
        return created_count

    def _normalize_audio_script(self, value: Any) -> dict[str, Any]:
        payload = value if isinstance(value, dict) else {}
        dialogues = []
        for item in ensure_list(payload.get("dialogues")):
            if not isinstance(item, dict):
                continue
            line = str(item.get("line") or "").strip()
            if not line:
                continue
            dialogues.append(
                {
                    "character_name": str(item.get("character_name") or "").strip(),
                    "character_card_id": item.get("character_card_id") if isinstance(item.get("character_card_id"), int) else None,
                    "line": line,
                    "emotion": str(item.get("emotion") or "novel_dialog").strip(),
                    "voice_profile": str(item.get("voice_profile") or "").strip(),
                    "start_hint": item.get("start_hint"),
                    "duration_hint": item.get("duration_hint"),
                }
            )
        return {
            "dialogues": dialogues,
            "narration": str(payload.get("narration") or "").strip(),
            "subtitle_text": str(payload.get("subtitle_text") or "").strip(),
            "music_cue": str(payload.get("music_cue") or "").strip(),
            "sound_effects": [str(item).strip() for item in ensure_list(payload.get("sound_effects")) if str(item).strip()],
        }

    def _add_event(
        self,
        db: Session,
        *,
        storyboard: Storyboard,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        db.add(
            TaskEvent(
                project_id=storyboard.project_id,
                storyboard=storyboard,
                event_type=event_type,
                message=message,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
            )
        )

    def _touch_worker(self, storyboard: Storyboard, *, started: bool = False) -> None:
        now = datetime.utcnow()
        if started or not storyboard.worker_id:
            storyboard.worker_id = f"{socket.gethostname()}:{threading.current_thread().name}"
        if started or storyboard.worker_started_at is None:
            storyboard.worker_started_at = now
        storyboard.last_heartbeat_at = now
