from __future__ import annotations

import threading
import time

from sqlalchemy import select

from .batch_generation_service import BatchGenerationService
from .config import Settings
from .db import SessionLocal
from .models import BatchGenerationJob, Storyboard, VideoTask
from .storyboard_job_service import StoryboardJobService
from .video_render_service import VideoRenderService


_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def start_batch_generation_worker(settings: Settings) -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _mark_stale_running_jobs_retryable()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        args=(settings,),
        name="longform-batch-generation-worker",
        daemon=True,
    )
    _worker_thread.start()


def stop_batch_generation_worker() -> None:
    _stop_event.set()


def _worker_loop(settings: Settings) -> None:
    batch_service = BatchGenerationService(settings)
    storyboard_service = StoryboardJobService(settings)
    video_service = VideoRenderService(settings)
    while not _stop_event.is_set():
        did_work = False
        try:
            with SessionLocal() as db:
                did_work = batch_service.run_next_queued_job(db=db)
                if not did_work:
                    did_work = storyboard_service.run_next_queued_storyboard(db=db)
                if not did_work:
                    did_work = _run_next_video_task(db=db, video_service=video_service)
        except Exception:
            did_work = False
        if not did_work:
            _stop_event.wait(2.0)


def _mark_stale_running_jobs_retryable() -> None:
    with SessionLocal() as db:
        jobs = db.scalars(select(BatchGenerationJob).where(BatchGenerationJob.job_status == "running")).all()
        for job in jobs:
            job.job_status = "failed"
            job.worker_id = ""
            job.worker_started_at = None
            job.last_heartbeat_at = None
            for task in job.chapter_tasks:
                if task.status == "running":
                    task.status = "failed"
                    task.error_message = "服务重启后恢复为可重试状态。"
        storyboards = db.scalars(select(Storyboard).where(Storyboard.status == "running")).all()
        for storyboard in storyboards:
            storyboard.status = "failed"
            storyboard.error_message = "服务重启后恢复为失败状态，可重新创建分镜任务。"
            storyboard.worker_id = ""
            storyboard.worker_started_at = None
            storyboard.last_heartbeat_at = None
        video_tasks = db.scalars(select(VideoTask).where(VideoTask.task_status == "running")).all()
        for task in video_tasks:
            task.task_status = "failed"
            task.error_message = "服务重启后恢复为失败状态，可重新创建视频任务。"
        db.commit()


def _run_next_video_task(*, db, video_service: VideoRenderService) -> bool:
    task = db.scalar(
        select(VideoTask)
        .where(VideoTask.task_status == "queued")
        .order_by(VideoTask.created_at.asc(), VideoTask.id.asc())
        .limit(1)
    )
    if task is None:
        return False
    try:
        video_service.render(db=db, task=task)
    except Exception as exc:
        task.task_status = "failed"
        task.error_message = str(exc)
        video_service._set_progress(task, stage="failed", message=str(exc))
        video_service._add_event(db, task=task, event_type="video_task_failed", message=f"视频生产失败：{exc}")
        db.commit()
    return True
