from __future__ import annotations

import json
import socket
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_support_generation import _replace_canonical_evolution, _snapshot_with_process
from .api_support_project import _canonical_project_evolution
from .config import Settings
from .evolution_service import EvolutionService
from .json_utils import json_loads_object
from .models import (
    BatchGenerationChapterTask,
    BatchGenerationJob,
    ChapterOutline,
    DraftVersion,
    GenerationRun,
    Project,
    ProjectChapter,
    SeriesPlan,
    TaskEvent,
)
from .story_service import StoryGenerationService


class BatchGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    ACTIVE_JOB_STATUSES = ("queued", "retry_queued", "running", "pause_requested", "paused", "cancel_requested")

    def create_job(
        self,
        *,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        start_chapter_no: int,
        end_chapter_no: int,
    ) -> BatchGenerationJob:
        active_job = db.scalar(
            select(BatchGenerationJob)
            .where(
                BatchGenerationJob.project_id == project.id,
                BatchGenerationJob.series_plan_id == series_plan.id,
                BatchGenerationJob.job_status.in_(self.ACTIVE_JOB_STATUSES),
            )
            .order_by(BatchGenerationJob.created_at.asc())
            .limit(1)
        )
        if active_job is not None:
            raise RuntimeError(f"已有未结束的批量正文任务（#{active_job.id}），请先完成、取消或重试该任务。")

        outlines = db.scalars(
            select(ChapterOutline)
            .where(
                ChapterOutline.series_plan_id == series_plan.id,
                ChapterOutline.chapter_no >= start_chapter_no,
                ChapterOutline.chapter_no <= end_chapter_no,
            )
            .order_by(ChapterOutline.chapter_no.asc())
        ).all()
        if not outlines:
            raise RuntimeError("没有找到可生成的章节概要。")
        missing_locked = [item.chapter_no for item in outlines if item.status != "outline_locked"]
        if missing_locked:
            raise RuntimeError("以下章节概要尚未锁定：" + "、".join(str(item) for item in missing_locked))

        job = BatchGenerationJob(
            project=project,
            series_plan=series_plan,
            start_chapter_no=start_chapter_no,
            end_chapter_no=end_chapter_no,
            job_status="queued",
            result_summary_json=json.dumps({}, ensure_ascii=False),
        )
        db.add(job)
        db.flush()
        for outline in outlines:
            db.add(
                BatchGenerationChapterTask(
                    job=job,
                    chapter_outline=outline,
                    chapter_no=outline.chapter_no,
                    status="queued",
                    error_message="",
                )
            )
        self._add_event(
            db,
            job=job,
            event_type="job_queued",
            message=f"已创建批量生成任务：第 {start_chapter_no}-{end_chapter_no} 章。",
            payload={"start_chapter_no": start_chapter_no, "end_chapter_no": end_chapter_no},
        )
        self._update_job_summary(job, generated=[], failed=[])
        db.commit()
        db.refresh(job)
        return job

    def run_next_queued_job(self, *, db: Session) -> bool:
        job = db.scalar(
            select(BatchGenerationJob)
            .where(BatchGenerationJob.job_status.in_(("queued", "retry_queued")))
            .order_by(BatchGenerationJob.created_at.asc(), BatchGenerationJob.id.asc())
            .limit(1)
        )
        if job is None:
            return False
        self.run_job(db=db, job=job)
        return True

    def run_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status in ("paused", "pause_requested", "canceled", "cancel_requested", "completed"):
            return job
        writer = StoryGenerationService(self.settings)
        evolution = EvolutionService(self.settings)
        self._touch_worker(job, started=True)
        job.job_status = "running"
        self._add_event(db, job=job, event_type="job_started", message="批量生成任务开始执行。")
        self._update_job_summary(job, generated=[], failed=[])
        db.commit()

        tasks = db.scalars(
            select(BatchGenerationChapterTask)
            .where(BatchGenerationChapterTask.job_id == job.id)
            .order_by(BatchGenerationChapterTask.chapter_no.asc())
        ).all()
        generated = list(self._summary_payload(job).get("generated", []))
        failed: list[dict[str, Any]] = []

        for task in tasks:
            if self._stop_requested(db, job):
                return job
            if task.status == "completed":
                continue
            outline = task.chapter_outline
            existing_draft = self._latest_draft_for_outline(db, outline.id)
            if existing_draft is not None and task.status not in ("failed", "running"):
                task.status = "completed"
                task.draft_version_id = existing_draft.id
                task.generation_run_id = existing_draft.generation_run_id
                task.error_message = ""
                task.finished_at = task.finished_at or datetime.utcnow()
                generated = self._upsert_generated_summary(
                    generated,
                    {
                        "chapter_no": outline.chapter_no,
                        "outline_id": outline.id,
                        "generation_id": existing_draft.generation_run_id,
                        "draft_version_id": existing_draft.id,
                        "title": existing_draft.title,
                    },
                )
                self._update_job_summary(job, generated, failed)
                db.commit()
                continue

            task.status = "running"
            task.error_message = ""
            task.started_at = datetime.utcnow()
            task.finished_at = None
            self._touch_worker(job)
            job.current_chapter_no = outline.chapter_no
            self._add_event(
                db,
                job=job,
                chapter_task=task,
                event_type="chapter_started",
                message=f"开始生成第 {outline.chapter_no} 章。",
                payload={"chapter_no": outline.chapter_no, "outline_id": outline.id},
            )
            self._update_job_summary(job, generated, failed)
            db.commit()
            try:
                generation, draft = self._generate_one(
                    db=db,
                    project=job.project,
                    series_plan=job.series_plan,
                    outline=outline,
                    writer=writer,
                    evolution=evolution,
                )
                task.status = "completed"
                task.generation_run_id = generation.id
                task.draft_version_id = draft.id
                task.finished_at = datetime.utcnow()
                self._touch_worker(job)
                generated = self._upsert_generated_summary(
                    generated,
                    {
                        "chapter_no": outline.chapter_no,
                        "outline_id": outline.id,
                        "generation_id": generation.id,
                        "draft_version_id": draft.id,
                        "title": generation.title,
                    },
                )
                self._update_job_summary(job, generated, failed)
                self._add_event(
                    db,
                    job=job,
                    chapter_task=task,
                    event_type="chapter_completed",
                    message=f"第 {outline.chapter_no} 章生成完成。",
                    payload={"chapter_no": outline.chapter_no, "generation_id": generation.id, "draft_version_id": draft.id},
                )
                db.commit()
            except Exception as exc:
                failure = {"chapter_no": outline.chapter_no, "outline_id": outline.id, "error": str(exc)}
                failed.append(failure)
                task.status = "failed"
                task.error_message = str(exc)
                task.finished_at = datetime.utcnow()
                self._touch_worker(job)
                job.job_status = "failed"
                self._update_job_summary(job, generated, failed)
                self._add_event(
                    db,
                    job=job,
                    chapter_task=task,
                    event_type="chapter_failed",
                    message=f"第 {outline.chapter_no} 章生成失败：{exc}",
                    payload=failure,
                )
                db.commit()
                return job

        if self._stop_requested(db, job):
            return job
        job.job_status = "completed"
        job.current_chapter_no = job.end_chapter_no
        self._touch_worker(job)
        self._update_job_summary(job, generated, failed)
        self._add_event(db, job=job, event_type="job_completed", message="批量生成任务已完成。")
        db.commit()
        db.refresh(job)
        return job

    def retry_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status == "completed":
            return job
        if job.job_status in ("running", "pause_requested", "cancel_requested"):
            self._add_event(db, job=job, event_type="job_retry_rejected", message="任务正在执行或等待章节边界，暂不能重试。")
            db.commit()
            db.refresh(job)
            return job
        generated = list(self._summary_payload(job).get("generated", []))
        for task in sorted(job.chapter_tasks, key=lambda item: item.chapter_no):
            latest_draft = self._latest_draft_for_outline(db, task.chapter_outline_id)
            if latest_draft is not None:
                task.status = "completed"
                task.draft_version_id = latest_draft.id
                task.generation_run_id = latest_draft.generation_run_id
                task.error_message = ""
                generated = self._upsert_generated_summary(
                    generated,
                    {
                        "chapter_no": task.chapter_no,
                        "outline_id": task.chapter_outline_id,
                        "generation_id": latest_draft.generation_run_id,
                        "draft_version_id": latest_draft.id,
                        "title": latest_draft.title,
                    },
                )
                continue
            if task.status in ("failed", "running", "canceled"):
                task.status = "queued"
                task.error_message = ""
                task.started_at = None
                task.finished_at = None
        job.job_status = "retry_queued"
        job.current_chapter_no = None
        self._update_job_summary(job, generated, [])
        self._add_event(db, job=job, event_type="job_retry_queued", message="批量生成任务已重新排队。")
        db.commit()
        db.refresh(job)
        return job

    def pause_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status in ("completed", "failed", "canceled"):
            return job
        if job.job_status in ("queued", "retry_queued", "paused"):
            job.job_status = "paused"
            self._touch_worker(job)
            self._add_event(db, job=job, event_type="job_paused", message="批量生成任务已暂停。")
        elif job.job_status == "running":
            job.job_status = "pause_requested"
            self._touch_worker(job)
            self._add_event(db, job=job, event_type="job_pause_requested", message="将在当前章节完成后暂停任务。")
        self._update_job_summary(job, list(self._summary_payload(job).get("generated", [])), list(self._summary_payload(job).get("failed", [])))
        db.commit()
        db.refresh(job)
        return job

    def resume_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status not in ("paused", "pause_requested"):
            return job
        for task in job.chapter_tasks:
            if task.status == "canceled":
                task.status = "queued"
                task.finished_at = None
        job.job_status = "queued"
        job.worker_id = ""
        job.worker_started_at = None
        job.last_heartbeat_at = None
        self._add_event(db, job=job, event_type="job_resumed", message="批量生成任务已恢复排队。")
        self._update_job_summary(job, list(self._summary_payload(job).get("generated", [])), list(self._summary_payload(job).get("failed", [])))
        db.commit()
        db.refresh(job)
        return job

    def cancel_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status in ("completed", "failed", "canceled"):
            return job
        if job.job_status == "running":
            job.job_status = "cancel_requested"
            self._touch_worker(job)
            self._add_event(db, job=job, event_type="job_cancel_requested", message="将在当前章节完成后取消任务。")
        else:
            self._mark_job_canceled(job)
            self._add_event(db, job=job, event_type="job_canceled", message="批量生成任务已取消。")
        self._update_job_summary(job, list(self._summary_payload(job).get("generated", [])), list(self._summary_payload(job).get("failed", [])))
        db.commit()
        db.refresh(job)
        return job

    def _generate_one(
        self,
        *,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        outline: ChapterOutline,
        writer: StoryGenerationService,
        evolution: EvolutionService,
    ) -> tuple[GenerationRun, DraftVersion]:
        outline_payload = json_loads_object(outline.outline_json)
        project_chapter = self._ensure_project_chapter(db, project, outline, outline_payload)
        scene_card = self._build_outline_scene_card(db, project, series_plan, outline, outline_payload)
        user_prompt = self._outline_to_prompt(outline_payload)
        memories = [{"title": item.title, "content": item.content} for item in project.memories]
        title, summary, content = writer.generate(
            project_title=project.title,
            genre=project.genre,
            reference_work=project.reference_work,
            premise=project_chapter.premise,
            world_brief=project.world_brief,
            writing_rules=project.writing_rules,
            style_profile=project.style_profile,
            user_prompt=user_prompt,
            response_type="完整章节正文",
            scene_card=scene_card,
            memories=memories,
            use_refiner=True,
        )

        generation = GenerationRun(
            project=project,
            project_chapter=project_chapter,
            prompt=user_prompt,
            search_method="series_outline",
            response_type="完整章节正文",
            retrieval_context=json.dumps(
                {
                    "mode": "longform_batch_generation",
                    "series_plan_id": series_plan.id,
                    "chapter_outline_id": outline.id,
                    "chapter_no": outline.chapter_no,
                },
                ensure_ascii=False,
            ),
            scene_card=scene_card,
            evolution_snapshot=json.dumps(
                {
                    "process": {
                        "draft": {"status": "done", "message": "批量正文已生成"},
                        "refine": {"status": "done", "message": "正文已润色"},
                        "evolution": {"status": "pending", "message": "等待抽取变化"},
                    },
                    "characters": [],
                    "relationships": [],
                    "events": [],
                    "world_updates": [],
                },
                ensure_ascii=False,
            ),
            generation_trace=json.dumps(
                {
                    "project": {"id": project.id, "title": project.title},
                    "chapter": {"outline_id": outline.id, "chapter_no": outline.chapter_no, "title": outline.title},
                    "request": {"mode": "longform_batch_generation"},
                    "result": {"title": title, "summary_length": len(summary), "content_length": len(content)},
                },
                ensure_ascii=False,
            ),
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.flush()

        evolution_payload = evolution.extract_evolution(
            project_title=project.title,
            genre=project.genre,
            premise=project_chapter.premise,
            user_prompt=user_prompt,
            title=title,
            summary=summary,
            content=content,
        )
        _replace_canonical_evolution(db, project, generation, evolution_payload)
        generation.canonicalized_at = datetime.utcnow()
        generation.evolution_snapshot = _snapshot_with_process(
            evolution_payload,
            {
                "draft": {"status": "done", "message": "批量正文已生成"},
                "refine": {"status": "done", "message": "正文已润色"},
                "evolution": {"status": "done", "message": "变化抽取已完成"},
            },
        )

        version_no = (
            db.scalar(
                select(DraftVersion.version_no)
                .where(DraftVersion.chapter_outline_id == outline.id)
                .order_by(DraftVersion.version_no.desc())
                .limit(1)
            )
            or 0
        ) + 1
        draft = DraftVersion(
            project=project,
            chapter_outline=outline,
            generation_run=generation,
            version_no=version_no,
            title=title,
            summary=summary,
            content=content,
            status="draft_generated",
            revision_reason="batch_generation",
        )
        outline.status = "draft_generated"
        db.add(draft)
        db.commit()
        db.refresh(generation)
        db.refresh(draft)
        return generation, draft

    def _add_event(
        self,
        db: Session,
        *,
        job: BatchGenerationJob,
        event_type: str,
        message: str,
        chapter_task: BatchGenerationChapterTask | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        db.add(
            TaskEvent(
                project_id=job.project_id,
                job=job,
                chapter_task=chapter_task,
                event_type=event_type,
                message=message,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
            )
        )

    def _stop_requested(self, db: Session, job: BatchGenerationJob) -> bool:
        db.refresh(job)
        if job.job_status == "pause_requested":
            job.job_status = "paused"
            self._touch_worker(job)
            self._add_event(db, job=job, event_type="job_paused", message="批量生成任务已在章节边界暂停。")
            db.commit()
            return True
        if job.job_status == "cancel_requested":
            self._mark_job_canceled(job)
            self._add_event(db, job=job, event_type="job_canceled", message="批量生成任务已在章节边界取消。")
            db.commit()
            return True
        return False

    def _mark_job_canceled(self, job: BatchGenerationJob) -> None:
        job.job_status = "canceled"
        self._touch_worker(job)
        canceled: list[dict[str, Any]] = []
        for task in job.chapter_tasks:
            if task.status in ("queued", "running", "failed"):
                task.status = "canceled"
                task.finished_at = task.finished_at or datetime.utcnow()
                canceled.append({"chapter_no": task.chapter_no, "outline_id": task.chapter_outline_id})
        payload = self._summary_payload(job)
        generated = payload.get("generated", [])
        failed = payload.get("failed", [])
        job.result_summary_json = json.dumps(
            {"generated": generated if isinstance(generated, list) else [], "failed": failed if isinstance(failed, list) else [], "canceled": canceled},
            ensure_ascii=False,
        )

    def _touch_worker(self, job: BatchGenerationJob, *, started: bool = False) -> None:
        now = datetime.utcnow()
        if started or not job.worker_id:
            job.worker_id = f"{socket.gethostname()}:{threading.current_thread().name}"
        if started or job.worker_started_at is None:
            job.worker_started_at = now
        job.last_heartbeat_at = now

    def _latest_draft_for_outline(self, db: Session, outline_id: int) -> DraftVersion | None:
        return db.scalar(
            select(DraftVersion)
            .where(DraftVersion.chapter_outline_id == outline_id)
            .order_by(DraftVersion.version_no.desc())
            .limit(1)
        )

    def _summary_payload(self, job: BatchGenerationJob) -> dict[str, Any]:
        try:
            payload = json.loads(job.result_summary_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _update_job_summary(
        self,
        job: BatchGenerationJob,
        generated: list[dict[str, Any]],
        failed: list[dict[str, Any]],
    ) -> None:
        total = len(job.chapter_tasks)
        completed = sum(1 for item in job.chapter_tasks if item.status == "completed")
        running = sum(1 for item in job.chapter_tasks if item.status == "running")
        queued = sum(1 for item in job.chapter_tasks if item.status in ("queued", "retry_queued"))
        canceled = sum(1 for item in job.chapter_tasks if item.status == "canceled")
        payload = {
            "generated": generated,
            "failed": failed,
            "summary": {
                "stage": job.job_status,
                "current_step": "chapter_generate" if job.job_status in ("running", "pause_requested") else "",
                "failure_stage": "chapter_generate" if job.job_status == "failed" else "",
                "total_chapters": total,
                "completed_chapters": completed,
                "failed_chapters": len(failed),
                "running_chapters": running,
                "queued_chapters": queued,
                "canceled_chapters": canceled,
                "current_chapter_no": job.current_chapter_no,
                "job_status": job.job_status,
                "last_updated_at": datetime.utcnow().isoformat(),
            },
        }
        job.result_summary_json = json.dumps(payload, ensure_ascii=False)

    def _upsert_generated_summary(
        self,
        generated: list[dict[str, Any]],
        item: dict[str, Any],
    ) -> list[dict[str, Any]]:
        chapter_no = item.get("chapter_no")
        next_items = [row for row in generated if row.get("chapter_no") != chapter_no]
        next_items.append(item)
        return sorted(next_items, key=lambda row: int(row.get("chapter_no") or 0))

    def _ensure_project_chapter(
        self,
        db: Session,
        project: Project,
        outline: ChapterOutline,
        outline_payload: dict[str, Any],
    ) -> ProjectChapter:
        existing = db.scalar(
            select(ProjectChapter).where(ProjectChapter.project_id == project.id, ProjectChapter.chapter_no == outline.chapter_no)
        )
        premise = self._outline_to_prompt(outline_payload)
        if existing is not None:
            existing.title = outline.title
            existing.premise = premise
            db.flush()
            return existing
        chapter = ProjectChapter(
            project=project,
            title=outline.title,
            premise=premise,
            chapter_no=outline.chapter_no,
        )
        db.add(chapter)
        db.flush()
        return chapter

    def _build_outline_scene_card(
        self,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        outline: ChapterOutline,
        outline_payload: dict[str, Any],
    ) -> str:
        character_updates, relationship_updates, story_events, world_updates = _canonical_project_evolution(db, project)
        recent_events = "\n".join(f"- {item.title}: {item.impact_summary or item.summary}" for item in story_events[:8]) or "- 暂无"
        recent_characters = "\n".join(f"- {item.character_name}: {item.summary}" for item in character_updates[:8]) or "- 暂无"
        recent_relationships = (
            "\n".join(f"- {item.source_character}->{item.target_character}: {item.summary}" for item in relationship_updates[:8])
            or "- 暂无"
        )
        recent_world = "\n".join(f"- {item.observer_group} 对 {item.subject_name}: {item.change_summary}" for item in world_updates[:8]) or "- 暂无"
        return "\n".join(
            [
                "长篇批量生成场景卡",
                f"全书规划：{series_plan.title}",
                f"章节：第 {outline.chapter_no} 章 / {outline.title}",
                "",
                "章节概要",
                self._outline_to_prompt(outline_payload),
                "",
                "最近关键事件",
                recent_events,
                "",
                "最近人物状态",
                recent_characters,
                "",
                "最近关系状态",
                recent_relationships,
                "",
                "最近外界认知",
                recent_world,
            ]
        )

    def _outline_to_prompt(self, outline_payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"本章目标：{outline_payload.get('chapter_goal', '')}",
                f"主要冲突：{outline_payload.get('conflict', '')}",
                f"情绪基调：{outline_payload.get('emotion_tone', '')}",
                f"必须发生：{outline_payload.get('must_happen', [])}",
                f"禁止发生：{outline_payload.get('must_not_happen', [])}",
                f"角色推进：{outline_payload.get('character_progress', [])}",
                f"结尾钩子：{outline_payload.get('ending_hook', '')}",
                f"预计篇幅：{outline_payload.get('estimated_length', '')}",
            ]
        ).strip()
