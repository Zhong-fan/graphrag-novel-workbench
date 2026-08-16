from __future__ import annotations

import hashlib
import json
import logging
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
from .json_utils import json_loads_list, json_loads_object
from .context_pack_service import ContextPackService
from .models import (
    BatchGenerationChapterTask,
    ChapterTaskAttempt,
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
from .story_boundary_service import StoryBoundaryService

logger = logging.getLogger(__name__)


class BatchGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.context_pack_service = ContextPackService()
        self.story_boundary_service = StoryBoundaryService()

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
        logger.info(
            "创建批量正文任务：project_id=%s series_plan_id=%s chapter_range=%s-%s",
            project.id,
            series_plan.id,
            start_chapter_no,
            end_chapter_no,
        )
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
            logger.warning("创建批量正文任务被拒绝：已有活跃任务 job_id=%s status=%s", active_job.id, active_job.job_status)
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
            logger.warning("创建批量正文任务被拒绝：章节范围内没有概要 project_id=%s series_plan_id=%s", project.id, series_plan.id)
            raise RuntimeError("没有找到可生成的章节概要。")
        missing_locked = [item.chapter_no for item in outlines if item.status != "outline_locked"]
        if missing_locked:
            logger.warning("创建批量正文任务被拒绝：章节概要未锁定 chapters=%s", missing_locked)
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
            task = BatchGenerationChapterTask(
                    job=job,
                    chapter_outline=outline,
                    chapter_no=outline.chapter_no,
                    status="queued",
                    error_message="",
                    current_step="resolve_inputs",
                    execution_steps_json=json.dumps(self._default_steps(), ensure_ascii=False),
                )
            db.add(task)
            self._resolve_task_manifest(task, project=project, series_plan=series_plan, outline=outline, db=db)
        self._add_event(
            db,
            job=job,
            event_type="job_queued",
            message=f"已创建批量生成任务：第 {start_chapter_no}-{end_chapter_no} 章。",
            payload={"start_chapter_no": start_chapter_no, "end_chapter_no": end_chapter_no},
        )
        self._rebuild_job_summary(job)
        db.commit()
        db.refresh(job)
        logger.info("批量正文任务已创建：job_id=%s task_count=%s", job.id, len(outlines))
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
        logger.info("取到待执行批量正文任务：job_id=%s status=%s", job.id, job.job_status)
        self.run_job(db=db, job=job)
        return True

    def run_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status in ("paused", "pause_requested", "canceled", "cancel_requested", "completed"):
            logger.info("跳过批量正文任务：job_id=%s status=%s", job.id, job.job_status)
            return job
        writer = StoryGenerationService(self.settings)
        evolution = EvolutionService(self.settings)
        self._touch_worker(job, started=True)
        job.job_status = "running"
        logger.info("批量正文任务开始执行：job_id=%s project_id=%s chapter_range=%s-%s", job.id, job.project_id, job.start_chapter_no, job.end_chapter_no)
        self._add_event(db, job=job, event_type="job_started", message="批量生成任务开始执行。")
        self._rebuild_job_summary(job)
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
            if task.chapter_no > job.start_chapter_no:
                previous = next((candidate for candidate in tasks if candidate.chapter_no == task.chapter_no - 1), None)
                if previous is not None and previous.status != "completed":
                    task.status = "waiting_for_dependency"
                    task.current_step = "waiting_for_dependency"
                    self._rebuild_job_summary(job)
                    db.commit()
                    continue
            outline = task.chapter_outline
            manifest_state = str(json_loads_object(task.manifest_json).get("input_state") or "planned")
            if not task.attempts and manifest_state.startswith("planned"):
                self._resolve_task_manifest(task, project=job.project, series_plan=job.series_plan, outline=outline, db=db)
            task.status = "running"
            task.current_step = "provider_generate"
            self._set_step_status(task, "resolve_inputs", "completed")
            self._set_step_status(task, "preflight", "completed")
            self._set_step_status(task, "provider_generate", "running")
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
            logger.info("章节正文开始生成：job_id=%s chapter_no=%s outline_id=%s", job.id, outline.chapter_no, outline.id)
            attempt = None
            generation_trace: dict[str, Any] = {}
            try:
                attempt = ChapterTaskAttempt(
                    chapter_task=task,
                    attempt_no=len(task.attempts) + 1,
                    kind="provider_generate",
                    manifest_fingerprint=task.manifest_fingerprint,
                    status="running",
                    started_at=datetime.utcnow(),
                )
                db.add(attempt)
                db.flush()
                generation, draft = self._generate_one(
                    db=db,
                    project=job.project,
                    series_plan=job.series_plan,
                    outline=outline,
                    writer=writer,
                    evolution=evolution,
                    task=task,
                    trace=generation_trace,
                )
                self._freeze_manifest_from_trace(task, generation_trace)
                attempt.manifest_fingerprint = task.manifest_fingerprint
                task.status = "completed"
                task.current_step = "completed"
                self._set_step_status(task, "provider_generate", "completed")
                self._set_step_status(task, "validate_output", "completed")
                self._set_step_status(task, "persist_output", "completed")
                task.output_validity = "valid"
                task.generation_run_id = generation.id
                task.draft_version_id = draft.id
                task.finished_at = datetime.utcnow()
                attempt.status = "succeeded"
                attempt.finished_at = datetime.utcnow()
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
                logger.info(
                    "章节正文生成完成：job_id=%s chapter_no=%s generation_id=%s draft_version_id=%s",
                    job.id,
                    outline.chapter_no,
                    generation.id,
                    draft.id,
                )
            except Exception as exc:
                logger.exception("章节正文生成失败：job_id=%s chapter_no=%s", job.id, outline.chapter_no)
                failure = {"chapter_no": outline.chapter_no, "outline_id": outline.id, "error": str(exc)}
                failed.append(failure)
                task.status = "failed"
                task.current_step = "provider_generate"
                self._set_step_status(task, "provider_generate", "failed")
                task.output_validity = "invalid"
                task.error_message = str(exc)
                task.finished_at = datetime.utcnow()
                if attempt is not None:
                    self._freeze_manifest_from_trace(task, generation_trace)
                    attempt.manifest_fingerprint = task.manifest_fingerprint
                    attempt.status = "failed"
                    attempt.error_message = str(exc)
                    attempt.finished_at = datetime.utcnow()
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
        unfinished = [task for task in tasks if task.status != "completed"]
        if unfinished:
            job.job_status = "failed"
            self._rebuild_job_summary(job)
            self._add_event(db, job=job, event_type="job_blocked", message="仍有章节未完成，任务不会被误标为已完成。")
            db.commit()
            db.refresh(job)
            return job
        job.job_status = "completed"
        job.current_chapter_no = job.end_chapter_no
        self._touch_worker(job)
        self._update_job_summary(job, generated, failed)
        self._add_event(db, job=job, event_type="job_completed", message="批量生成任务已完成。")
        db.commit()
        db.refresh(job)
        logger.info("批量正文任务完成：job_id=%s generated=%s failed=%s", job.id, len(generated), len(failed))
        return job

    def retry_job(self, *, db: Session, job: BatchGenerationJob) -> BatchGenerationJob:
        if job.job_status == "completed":
            return job
        if job.job_status in ("running", "pause_requested", "cancel_requested"):
            self._add_event(db, job=job, event_type="job_retry_rejected", message="任务正在执行或等待章节边界，暂不能重试。")
            db.commit()
            db.refresh(job)
            return job
        retryable_tasks = [task for task in sorted(job.chapter_tasks, key=lambda item: item.chapter_no) if task.status in ("failed", "canceled")]
        if not retryable_tasks:
            raise RuntimeError("任务组中没有可安全重试的失败或已取消章节。")
        for task in retryable_tasks:
            self._assert_same_input_retry_safe(db=db, task=task, check_job_state=False)
        for task in retryable_tasks:
            task.status = "queued"
            task.current_step = "provider_generate"
            task.output_validity = "pending"
            task.error_message = ""
            task.started_at = None
            task.finished_at = None
        job.job_status = "retry_queued"
        job.current_chapter_no = None
        self._rebuild_job_summary(job)
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

    def retry_chapter_task(self, *, db: Session, task: BatchGenerationChapterTask, mode: str = "same_inputs", input_overrides: dict[str, Any] | None = None) -> BatchGenerationChapterTask:
        if mode == "same_inputs":
            self._assert_same_input_retry_safe(db=db, task=task)
            task.status = "queued"
            task.current_step = "provider_generate"
            self._set_step_status(task, "provider_generate", "pending")
            self._set_step_status(task, "validate_output", "pending")
            self._set_step_status(task, "persist_output", "pending")
            task.error_message = ""
            task.output_validity = "pending"
            task.started_at = None
            task.finished_at = None
            self._add_event(db, job=task.job, chapter_task=task, event_type="chapter_retry_queued", message=f"第 {task.chapter_no} 章已按相同冻结输入重新排队。", payload={"manifest_fingerprint": task.manifest_fingerprint})
            if task.job is not None:
                self._rebuild_job_summary(task.job)
                task.job.job_status = "retry_queued"
            db.commit()
            db.refresh(task)
            return task

        overrides = input_overrides or {}
        unexpected = sorted(set(overrides) - {"user_instruction"})
        if unexpected:
            raise RuntimeError("暂不支持修改这些输入字段：" + "、".join(unexpected))
        user_instruction = str(overrides.get("user_instruction") or "").strip()
        if not user_instruction:
            raise RuntimeError("请先填写本次重新生成要追加的修改要求。")
        source = json_loads_object(task.manifest_json)
        source.pop("provider_request", None)
        source["input_state"] = "planned_edited"
        source["input_overrides"] = {"user_instruction": user_instruction}
        if task.job is not None and task.job.job_status in ("running", "queued", "retry_queued", "pause_requested", "cancel_requested"):
            raise RuntimeError("原章节任务组仍在执行，暂不能创建输入变更任务。")
        replacement_job = BatchGenerationJob(
            project_id=task.job.project_id if task.job is not None else task.chapter_outline.project_id,
            series_plan_id=task.job.series_plan_id if task.job is not None else task.chapter_outline.series_plan_id,
            start_chapter_no=task.chapter_no,
            end_chapter_no=task.chapter_no,
            job_status="queued",
            result_summary_json=json.dumps({}, ensure_ascii=False),
        )
        db.add(replacement_job)
        db.flush()
        replacement = BatchGenerationChapterTask(
            job=replacement_job,
            chapter_outline_id=task.chapter_outline_id,
            chapter_no=task.chapter_no,
            status="queued",
            error_message="",
            current_step="resolve_inputs",
            execution_steps_json=json.dumps(self._default_steps(), ensure_ascii=False),
            supersedes_task_id=task.id,
            manifest_json=json.dumps(source, ensure_ascii=False, sort_keys=True),
            manifest_fingerprint=hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            canonical_story_state_version=task.canonical_story_state_version,
            output_validity="pending",
        )
        db.add(replacement)
        downstream_tasks = db.scalars(
            select(BatchGenerationChapterTask)
            .join(BatchGenerationJob, BatchGenerationChapterTask.job_id == BatchGenerationJob.id)
            .where(
                BatchGenerationJob.series_plan_id == replacement_job.series_plan_id,
                BatchGenerationChapterTask.chapter_no > task.chapter_no,
                BatchGenerationChapterTask.output_validity == "valid",
            )
        ).all()
        for downstream in downstream_tasks:
            downstream.output_validity = "stale_dependency"
            self._add_event(
                db,
                job=downstream.job,
                chapter_task=downstream,
                event_type="chapter_output_invalidated",
                message=f"第 {downstream.chapter_no} 章因上游第 {task.chapter_no} 章开始重生成而需要重新确认。",
                payload={"changed_upstream_chapter_no": task.chapter_no, "replacement_task_id": replacement.id},
            )
        self._rebuild_job_summary(replacement_job)
        self._add_event(db, job=replacement_job, chapter_task=replacement, event_type="chapter_replacement_queued", message=f"第 {task.chapter_no} 章已按修改后的冻结输入创建新任务。", payload={"supersedes_task_id": task.id})
        db.commit()
        db.refresh(replacement)
        return replacement

    def create_stale_cascade_job(
        self,
        *,
        db: Session,
        project: Project,
        series_plan: SeriesPlan,
        start_chapter_no: int,
    ) -> BatchGenerationJob:
        if series_plan.status != "locked":
            raise RuntimeError("请先确认当前长篇规划版本，再进行级联重生成。")
        active_job = db.scalar(
            select(BatchGenerationJob)
            .where(
                BatchGenerationJob.project_id == project.id,
                BatchGenerationJob.job_status.in_(self.ACTIVE_JOB_STATUSES),
            )
            .order_by(BatchGenerationJob.created_at.desc(), BatchGenerationJob.id.desc())
            .limit(1)
        )
        if active_job is not None:
            raise RuntimeError(f"已有未结束的正文任务（#{active_job.id}），请等待它结束后再级联重生成。")

        all_tasks = db.scalars(
            select(BatchGenerationChapterTask)
            .join(BatchGenerationJob, BatchGenerationChapterTask.job_id == BatchGenerationJob.id)
            .where(BatchGenerationJob.series_plan_id == series_plan.id)
            .order_by(BatchGenerationChapterTask.chapter_no.asc(), BatchGenerationChapterTask.id.desc())
        ).all()
        latest_by_chapter: dict[int, BatchGenerationChapterTask] = {}
        for chapter_task in all_tasks:
            latest_by_chapter.setdefault(chapter_task.chapter_no, chapter_task)
        stale_tasks = [
            chapter_task
            for chapter_task in latest_by_chapter.values()
            if chapter_task.output_validity == "stale_dependency"
        ]
        if not stale_tasks:
            raise RuntimeError("当前没有因上游变化而失效的章节。")
        earliest = min(chapter_task.chapter_no for chapter_task in stale_tasks)
        if start_chapter_no != earliest:
            raise RuntimeError(f"必须从最早失效的第 {earliest} 章开始，不能跳过仍依赖旧版本的章节。")

        selected = sorted((task for task in stale_tasks if task.chapter_no >= earliest), key=lambda item: item.chapter_no)
        expected_chapters = list(range(selected[0].chapter_no, selected[-1].chapter_no + 1))
        actual_chapters = [task.chapter_no for task in selected]
        if actual_chapters != expected_chapters:
            raise RuntimeError("失效章节范围不连续，请先检查章节依赖记录，系统不会跳章生成。")
        job = BatchGenerationJob(
            project=project,
            series_plan=series_plan,
            start_chapter_no=selected[0].chapter_no,
            end_chapter_no=selected[-1].chapter_no,
            job_status="queued",
            result_summary_json=json.dumps({}, ensure_ascii=False),
        )
        db.add(job)
        db.flush()
        for stale_task in selected:
            replacement = BatchGenerationChapterTask(
                job=job,
                chapter_outline=stale_task.chapter_outline,
                chapter_no=stale_task.chapter_no,
                status="queued",
                error_message="",
                current_step="resolve_inputs",
                execution_steps_json=json.dumps(self._default_steps(), ensure_ascii=False),
                supersedes_task_id=stale_task.id,
                output_validity="pending",
            )
            db.add(replacement)
            self._resolve_task_manifest(
                replacement,
                project=project,
                series_plan=series_plan,
                outline=stale_task.chapter_outline,
                db=db,
            )
        self._rebuild_job_summary(job)
        self._add_event(
            db,
            job=job,
            event_type="cascade_regeneration_queued",
            message=f"已确认从第 {earliest} 章开始级联重生成，共 {len(selected)} 章。",
            payload={"start_chapter_no": earliest, "affected_chapter_nos": [task.chapter_no for task in selected]},
        )
        db.commit()
        db.refresh(job)
        return job

    def _assert_same_input_retry_safe(self, *, db: Session, task: BatchGenerationChapterTask, check_job_state: bool = True) -> None:
        """Guard the invariant that a same-input retry really replays one immutable provider request."""
        if task.job is None:
            raise RuntimeError("章节任务缺少所属任务组，不能安全重试。")
        if check_job_state and task.job.job_status in ("running", "queued", "retry_queued", "pause_requested", "cancel_requested"):
            raise RuntimeError("章节任务组仍在执行或排队，请勿重复提交重试。")
        if task.status not in ("failed", "canceled"):
            raise RuntimeError("只有失败或已取消的章节任务可以按相同输入重试。")
        manifest = json_loads_object(task.manifest_json)
        if manifest.get("input_state") != "frozen_actual":
            raise RuntimeError("该失败发生在模型输入冻结之前，不能承诺按相同输入重试；请修改要求后重新生成。")
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if not task.manifest_fingerprint or hashlib.sha256(encoded.encode("utf-8")).hexdigest() != task.manifest_fingerprint:
            raise RuntimeError("冻结输入指纹校验失败，不能按相同输入重试。")
        current_story_state = str(task.job.series_plan.current_version_id or task.job.series_plan.id)
        if task.canonical_story_state_version != current_story_state:
            raise RuntimeError("当前故事状态已变化，请改用“编辑输入并重新生成”。")
        if task.chapter_no > 1:
            predecessor_outline = db.scalar(select(ChapterOutline).where(ChapterOutline.series_plan_id == task.job.series_plan_id, ChapterOutline.chapter_no == task.chapter_no - 1))
            latest_predecessor = self._latest_draft_for_outline(db, predecessor_outline.id) if predecessor_outline else None
            if latest_predecessor is None or latest_predecessor.id != task.predecessor_chapter_version_id:
                raise RuntimeError("前一章版本已变化，请改用“编辑输入并重新生成”。")
        if any(attempt.status in ("queued", "running") for attempt in task.attempts):
            raise RuntimeError("该章节已有执行中的尝试，请勿重复提交。")

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
        task: BatchGenerationChapterTask,
        trace: dict[str, Any],
    ) -> tuple[GenerationRun, DraftVersion]:
        outline_payload = json_loads_object(outline.outline_json)
        project_chapter = self._ensure_project_chapter(db, project, outline, outline_payload)
        context_pack_inputs = self.context_pack_service.resolved_inputs(self.context_pack_service.require_confirmed(db, project))
        active_story_boundary_rules = self.story_boundary_service.active_rules_for_chapter(
            context_pack_inputs.get("story_boundary_rules", []),
            outline.chapter_no,
        )
        scene_card = self._build_outline_scene_card(
            db,
            project,
            series_plan,
            outline,
            outline_payload,
            active_story_boundary_rules=active_story_boundary_rules,
        )
        user_prompt = self._outline_to_prompt(outline_payload, active_story_boundary_rules=active_story_boundary_rules)
        memories = [{"title": item.title, "content": item.content} for item in project.memories]
        context_pack_inputs = {**context_pack_inputs, "active_story_boundary_rules": active_story_boundary_rules}
        frozen_request = json_loads_object(task.manifest_json).get("provider_request", {})
        input_overrides = json_loads_object(task.manifest_json).get("input_overrides", {})
        if not isinstance(frozen_request, dict):
            frozen_request = {}
        if isinstance(input_overrides, dict) and str(input_overrides.get("user_instruction") or "").strip() and not frozen_request:
            user_prompt = f"{user_prompt}\n\n用户本次追加修改要求：\n{str(input_overrides['user_instruction']).strip()}"
        title, summary, content = writer.generate(
            project_title=project.title,
            genre=project.genre,
            reference_work=project.reference_work,
            reference_work_synopsis=project.reference_work_synopsis,
            reference_work_style_traits=project.reference_work_style_traits,
            reference_work_world_traits=project.reference_work_world_traits,
            reference_work_narrative_constraints=project.reference_work_narrative_constraints,
            premise=project_chapter.premise,
            world_brief=project.world_brief,
            writing_rules=project.writing_rules,
            style_profile=project.style_profile,
            user_prompt=user_prompt,
            response_type="完整章节正文",
            scene_card=scene_card,
            memories=memories,
            use_refiner=True,
            context_pack_inputs=context_pack_inputs,
            resolved_system_prompt=str(frozen_request.get("system_prompt")) if frozen_request.get("system_prompt") else None,
            resolved_user_prompt=str(frozen_request.get("user_prompt")) if frozen_request.get("user_prompt") else None,
            trace=trace,
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

    @staticmethod
    def _default_steps() -> list[dict[str, Any]]:
        return [
            {"name": "resolve_inputs", "status": "pending", "recoverable": True},
            {"name": "preflight", "status": "pending", "recoverable": True},
            {"name": "provider_generate", "status": "pending", "recoverable": False},
            {"name": "validate_output", "status": "pending", "recoverable": True},
            {"name": "persist_output", "status": "pending", "recoverable": True},
        ]

    def _resolve_task_manifest(self, task: BatchGenerationChapterTask, *, project: Project, series_plan: SeriesPlan, outline: ChapterOutline, db: Session) -> None:
        previous_manifest = json_loads_object(getattr(task, "manifest_json", "{}"))
        input_overrides = previous_manifest.get("input_overrides") if isinstance(previous_manifest.get("input_overrides"), dict) else {}
        predecessor_outline = None
        if outline.chapter_no > 1:
            predecessor_outline = db.scalar(
                select(ChapterOutline).where(
                    ChapterOutline.series_plan_id == series_plan.id,
                    ChapterOutline.chapter_no == outline.chapter_no - 1,
                )
            )
        predecessor = self._latest_draft_for_outline(db, predecessor_outline.id) if predecessor_outline else None
        story_state = str(series_plan.current_version_id or series_plan.id)
        manifest = {
            "prompt_id": "longform.chapter_generation",
            "prompt_version": "1",
            "model": self.settings.writer_model,
            "parameters": {"response_type": "完整章节正文"},
            "project": {"id": project.id, "title": project.title, "genre": project.genre},
            "series_plan": {"id": series_plan.id, "version_id": series_plan.current_version_id},
            "chapter": {"outline_id": outline.id, "chapter_no": outline.chapter_no, "title": outline.title, "outline": json_loads_object(outline.outline_json)},
            "predecessor": {"draft_version_id": predecessor.id} if predecessor else None,
            "canonical_story_state_version": story_state,
            "exclusions": [],
            "truncation": None,
            "estimated_cost": 0.0,
            "input_state": "planned_edited" if input_overrides else "planned",
            "input_overrides": input_overrides,
        }
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        task.manifest_json = encoded
        task.manifest_fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        task.predecessor_chapter_version_id = predecessor.id if predecessor else None
        task.canonical_story_state_version = story_state
        task.estimated_cost = 0.0

    def _freeze_manifest_from_trace(self, task: BatchGenerationChapterTask, trace: dict[str, Any]) -> None:
        draft_trace = trace.get("draft") if isinstance(trace, dict) else None
        if not isinstance(draft_trace, dict) or not draft_trace.get("system_prompt") or not draft_trace.get("user_prompt"):
            return
        manifest = json_loads_object(task.manifest_json)
        manifest["input_state"] = "frozen_actual"
        manifest["provider_request"] = {
            "model": draft_trace.get("model") or self.settings.writer_model,
            "messages": [
                {"role": "system", "content": str(draft_trace["system_prompt"])},
                {"role": "user", "content": str(draft_trace["user_prompt"])},
            ],
            "system_prompt": str(draft_trace["system_prompt"]),
            "user_prompt": str(draft_trace["user_prompt"]),
            "response_format": "json",
        }
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        task.manifest_json = encoded
        task.manifest_fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _set_step_status(task: BatchGenerationChapterTask, name: str, status: str) -> None:
        steps = json_loads_list(task.execution_steps_json)
        for step in steps:
            if isinstance(step, dict) and step.get("name") == name:
                step["status"] = status
        task.execution_steps_json = json.dumps(steps, ensure_ascii=False)

    def _rebuild_job_summary(self, job: BatchGenerationJob) -> None:
        generated = []
        failed = []
        for task in sorted(job.chapter_tasks, key=lambda item: item.chapter_no):
            if task.status == "completed" and task.draft_version_id:
                generated.append({"chapter_no": task.chapter_no, "outline_id": task.chapter_outline_id, "generation_id": task.generation_run_id, "draft_version_id": task.draft_version_id})
            elif task.status == "failed":
                failed.append({"chapter_no": task.chapter_no, "outline_id": task.chapter_outline_id, "error": task.error_message})
        self._update_job_summary(job, generated, failed)

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
        processed = completed + len(failed) + canceled
        payload = {
            "generated": generated,
            "failed": failed,
            "summary": {
                "stage": job.job_status,
                "current_step": "chapter_generate" if job.job_status in ("running", "pause_requested") else "",
                "failure_stage": "chapter_generate" if job.job_status == "failed" else "",
                "total_chapters": total,
                "completed_chapters": completed,
                "failed_chapters": sum(1 for item in job.chapter_tasks if item.status == "failed"),
                "running_chapters": running,
                "queued_chapters": queued,
                "canceled_chapters": canceled,
                "processed_chapters": processed,
                "remaining_chapters": max(0, total - processed),
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
        active_story_boundary_rules: list[dict[str, Any]] | None = None,
    ) -> str:
        character_updates, relationship_updates, story_events, world_updates = _canonical_project_evolution(db, project)
        recent_events = "\n".join(f"- {item.title}: {item.impact_summary or item.summary}" for item in story_events[:8]) or "- 暂无"
        recent_characters = "\n".join(f"- {item.character_name}: {item.summary}" for item in character_updates[:8]) or "- 暂无"
        recent_relationships = (
            "\n".join(f"- {item.source_character}->{item.target_character}: {item.summary}" for item in relationship_updates[:8])
            or "- 暂无"
        )
        recent_world = "\n".join(f"- {item.observer_group} 对 {item.subject_name}: {item.change_summary}" for item in world_updates[:8]) or "- 暂无"
        active_story_boundary_lines = "\n".join(
            f"- {item}" for item in self.story_boundary_service.prompt_lines(active_story_boundary_rules or [])
        ) or "- 暂无"
        return "\n".join(
            [
                "长篇批量生成场景卡",
                f"全书规划：{series_plan.title}",
                f"章节：第 {outline.chapter_no} 章 / {outline.title}",
                "",
                "章节概要",
                self._outline_to_prompt(outline_payload, active_story_boundary_rules=active_story_boundary_rules),
                "",
                "当前故事边界硬约束",
                active_story_boundary_lines,
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

    def _outline_to_prompt(
        self,
        outline_payload: dict[str, Any],
        *,
        active_story_boundary_rules: list[dict[str, Any]] | None = None,
    ) -> str:
        lines = [
            f"本章目标：{outline_payload.get('chapter_goal', '')}",
            f"主要冲突：{outline_payload.get('conflict', '')}",
            f"情绪基调：{outline_payload.get('emotion_tone', '')}",
            f"必须发生：{outline_payload.get('must_happen', [])}",
            f"禁止发生：{outline_payload.get('must_not_happen', [])}",
            f"角色推进：{outline_payload.get('character_progress', [])}",
            f"结尾钩子：{outline_payload.get('ending_hook', '')}",
            f"预计篇幅：{outline_payload.get('estimated_length', '')}",
        ]
        story_boundary_lines = self.story_boundary_service.prompt_lines(active_story_boundary_rules or [])
        if story_boundary_lines:
            lines.append("当前故事边界硬约束：")
            lines.extend(f"- {item}" for item in story_boundary_lines)
        return "\n".join(lines).strip()
