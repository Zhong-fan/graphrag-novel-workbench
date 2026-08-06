from __future__ import annotations

import json
import socket
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .context_pack_service import ContextPackService
from .json_utils import ensure_list, json_dumps, json_loads_object
from .models import GenerationAttempt, Novel, NovelChapter, Project, Storyboard, StoryboardShot, TaskEvent
from .exception_inbox_service import create_inbox_item
from .generation_evidence_service import record_generation_evidence
from .storyboard_service import StoryboardService
from .storyboard_source_service import StoryboardSourceService


class StoryboardJobService:
    ACTIVE_STATUSES = ("queued", "running")

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.context_pack_service = ContextPackService()

    def create_job(
        self,
        *,
        db: Session,
        project: Project,
        current_user_id: int,
        novel_chapter_ids: list[int],
        title: str,
        source_mode: str = "novel_chapters",
        reference_video_brief: str = "",
        key_image_strategy: str = "generate_first_frames",
        reference_image_asset_ids: list[int] | None = None,
    ) -> Storyboard:
        source = StoryboardSourceService().build(
            db,
            project=project,
            current_user_id=current_user_id,
            source_mode=source_mode,
            title=title,
            novel_chapter_ids=novel_chapter_ids,
            reference_video_brief=reference_video_brief,
            key_image_strategy=key_image_strategy,
            reference_image_asset_ids=reference_image_asset_ids or [],
        )

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
            title=source.title.strip() or (f"{project.title} 读后短片" if source.source_mode == "novel_chapters" else f"{project.title} 图片先行短片"),
            source_chapter_ids_json=source.source_chapter_ids_json(),
            summary=source.reference_video_brief if source.source_mode != "novel_chapters" else "",
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
            payload=source.event_payload(),
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
        source_payload = self._source_payload(storyboard)
        source_mode = str(source_payload.get("source_mode") or "novel_chapters")
        chapter_ids = [int(item) for item in ensure_list(json.loads(storyboard.source_chapter_ids_json or "[]"))]
        chapters: list[NovelChapter] = []
        if source_mode == "novel_chapters":
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
            context_pack_inputs = self.context_pack_service.resolved_inputs(self.context_pack_service.require_confirmed(db, project))
            service = StoryboardService(
                self.settings,
                evidence_sink=lambda evidence: record_generation_evidence(db, evidence=evidence),
            )
            if source_mode == "novel_chapters":
                generated = service.generate_storyboard(
                    project=project,
                    chapters=chapters,
                    title=storyboard.title,
                    context_pack_inputs=context_pack_inputs,
                )
            else:
                generated = service.generate_image_first_storyboard(
                    project=project,
                    title=storyboard.title,
                    reference_video_brief=str(source_payload.get("reference_video_brief") or storyboard.summary),
                    reference_image_notes=[
                        str(item).strip()
                        for item in ensure_list(source_payload.get("reference_image_notes"))
                        if str(item).strip()
                    ],
                    context_pack_inputs=context_pack_inputs,
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
            shot_count = self._replace_shots(
                db,
                storyboard=storyboard,
                shots=ensure_list(generated.get("shots")),
                source_payload=source_payload,
            )
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
            # 收件箱路由是尽力而为的遥测：失败时绝不能掩盖分镜失败本身，
            # 因此记录失败时吞掉，failed 状态与事件照常提交。
            try:
                latest_attempt = db.scalar(
                    select(GenerationAttempt)
                    .where(
                        GenerationAttempt.project_id == project.id,
                        GenerationAttempt.storyboard_id == storyboard.id,
                        GenerationAttempt.status == "failed",
                    )
                    .order_by(GenerationAttempt.id.desc())
                )
                create_inbox_item(
                    db,
                    project=project,
                    item_type="repeated_quality_failure",
                    title=f"分镜生成重复失败：{storyboard.title}",
                    reason=str(exc),
                    recommended_action="修复分镜提示词或更换生成模型后重试。",
                    options=[
                        {"label": "重试生成", "impact": "使用当前配置再次尝试，失败会再次进入收件箱。"},
                        {"label": "修改提示词后重试", "impact": "创作者先调整输入，再重新发起分镜任务。"},
                    ],
                    evidence={
                        "storyboard_id": storyboard.id,
                        "generation_attempt_id": latest_attempt.id if latest_attempt is not None else None,
                    },
                    severity="medium",
                )
            except Exception:
                pass
        db.commit()
        db.refresh(storyboard)
        return storyboard

    def _source_payload(self, storyboard: Storyboard) -> dict[str, Any]:
        queued_event = next(
            (item for item in sorted(storyboard.events, key=lambda event: event.created_at) if item.event_type == "storyboard_queued"),
            None,
        )
        if queued_event is None:
            return {"source_mode": "novel_chapters"}
        payload = json_loads_object(queued_event.payload_json)
        if not payload.get("source_mode"):
            payload["source_mode"] = "novel_chapters"
        return payload

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

    def _replace_shots(
        self,
        db: Session,
        *,
        storyboard: Storyboard,
        shots: list[Any],
        source_payload: dict[str, Any] | None = None,
    ) -> int:
        valid_shots = [item for item in shots if isinstance(item, dict)]
        if not valid_shots:
            return 0
        source_payload = source_payload or {"source_mode": "novel_chapters"}
        for existing in list(storyboard.shots):
            db.delete(existing)
        db.flush()
        created_count = 0
        for index, shot_payload in enumerate(valid_shots, start=1):
            shot_no = int(shot_payload.get("shot_no") or index)
            continuity = self._normalize_continuity(shot_payload.get("continuity"), shot_no=shot_no)
            source_mode = str(source_payload.get("source_mode") or "novel_chapters")
            source_trace = source_payload.get("source_trace") if isinstance(source_payload.get("source_trace"), dict) else {}
            if not source_trace:
                source_trace = {
                    "source_mode": source_mode,
                    "novel_chapter_ids": ensure_list(source_payload.get("novel_chapter_ids")),
                    "reference_video_brief": str(source_payload.get("reference_video_brief") or ""),
                    "reference_image_asset_ids": ensure_list(source_payload.get("reference_image_asset_ids")),
                    "key_image_strategy": str(source_payload.get("key_image_strategy") or "generate_first_frames"),
                }
            db.add(
                StoryboardShot(
                    storyboard=storyboard,
                    shot_no=shot_no,
                    narration_text=str(shot_payload.get("narration_text") or "").strip(),
                    visual_prompt=str(shot_payload.get("visual_prompt") or "").strip(),
                    character_refs_json=json_dumps(ensure_list(shot_payload.get("character_refs"))),
                    scene_refs_json=json_dumps(ensure_list(shot_payload.get("scene_refs"))),
                    meta_json=json_dumps(
                        {
                            "source_mode": source_mode,
                            "source_trace": source_trace,
                            "audio_script": self._normalize_audio_script(shot_payload.get("audio_script")),
                            "continuity": continuity,
                        }
                    ),
                    duration_seconds=float(shot_payload.get("duration_seconds") or 4),
                    status="draft",
                )
            )
            created_count += 1
        db.flush()
        return created_count

    def _normalize_continuity(self, value: Any, *, shot_no: int) -> dict[str, Any]:
        payload = value if isinstance(value, dict) else {}
        shot_type = str(payload.get("shot_type") or "new").strip()
        if shot_type not in {"new", "continuation", "camera_move", "transition"}:
            shot_type = "new"
        depends = payload.get("depends_on_shot_no")
        try:
            depends_on = int(depends) if depends is not None and str(depends).strip() else None
        except (TypeError, ValueError):
            depends_on = None
        first_frame_source = str(payload.get("first_frame_source") or "").strip()
        if first_frame_source not in {"generated", "previous_last_frame"}:
            first_frame_source = "previous_last_frame" if shot_type in {"continuation", "camera_move"} else "generated"
        if shot_type in {"continuation", "camera_move"} and depends_on is None and shot_no > 1:
            depends_on = shot_no - 1
        return {
            "shot_type": shot_type,
            "depends_on_shot_no": depends_on,
            "first_frame_source": first_frame_source,
            "requires_i2v": self._normalize_bool(payload.get("requires_i2v"), default=True),
            "end_frame_usage": str(payload.get("end_frame_usage") or "none").strip(),
            "camera_motion": str(payload.get("camera_motion") or "").strip(),
            "character_state_delta": str(payload.get("character_state_delta") or "").strip(),
            "continuity_constraints": [
                str(item).strip() for item in ensure_list(payload.get("continuity_constraints")) if str(item).strip()
            ],
        }

    def _normalize_bool(self, value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        return bool(value)

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
