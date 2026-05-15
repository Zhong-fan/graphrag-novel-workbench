from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_support import _project_or_404
from .api_support_longform import (
    _batch_job_out,
    _chapter_outline_out,
    _draft_version_out,
    _outline_feedback_out,
    _outline_revision_plan_out,
    _series_plan_out,
    _storyboard_out,
    _video_task_out,
    _media_asset_out,
)
from .auth import get_current_user
from .batch_generation_service import BatchGenerationService
from .config import Settings
from .contracts import (
    BatchGenerationJobOut,
    BatchGenerationRequest,
    CanonicalizeDraftVersionRequest,
    ChapterOutlineOut,
    CreateStoryboardRequest,
    GenerateSeriesPlanRequest,
    LockChapterOutlinesRequest,
    OutlineRevisionResponse,
    SeriesPlanningStateOut,
    SeriesPlanOut,
    StoryboardOut,
    SubmitOutlineFeedbackRequest,
    DraftVersionOut,
    ReviseDraftVersionRequest,
    VideoTaskOut,
    UpdateChapterOutlineRequest,
    UpdateStoryboardShotRequest,
    UpdateMediaAssetRequest,
    MediaAssetOut,
    CreateStoryboardShotRequest,
    ReorderStoryboardShotsRequest,
    UpdateVideoTaskRequest,
)
from .db import get_db
from .json_utils import ensure_list, json_dumps, json_loads_list, json_loads_object
from .models import (
    ArcPlan,
    BatchGenerationJob,
    ChapterOutline,
    DraftVersion,
    Novel,
    NovelChapter,
    OutlineFeedbackItem,
    OutlineRevisionPlan,
    Project,
    SeriesPlan,
    SeriesPlanVersion,
    Storyboard,
    StoryboardShot,
    User,
    GenerationRun,
    VideoTask,
    MediaAsset,
    ProjectChapter,
)
from .draft_revision_service import DraftRevisionService
from .media_pipeline_service import MediaPipelineService
from .outline_revision_service import OutlineRevisionService
from .series_planning_service import SeriesPlanningService
from .storyboard_service import StoryboardService


def register_longform_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/projects/{project_id}/longform", response_model=SeriesPlanningStateOut)
    def longform_state(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> SeriesPlanningStateOut:
        project = _project_or_404(db, current_user.id, project_id)
        return _state_out(db, project)

    @router.post("/api/projects/{project_id}/series-plans/generate", response_model=SeriesPlanOut)
    def generate_series_plan(
        project_id: int,
        payload: GenerateSeriesPlanRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> SeriesPlanOut:
        project = _project_or_404(db, current_user.id, project_id)
        try:
            generated = SeriesPlanningService(settings).generate_plan(
                project=project,
                target_chapter_count=payload.target_chapter_count,
                user_brief=payload.user_brief,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        plan = _persist_generated_plan(db, project, generated, created_by="planner")
        db.commit()
        db.refresh(plan)
        return _series_plan_out(plan)

    @router.post("/api/projects/{project_id}/outline-feedback", response_model=OutlineRevisionResponse)
    def submit_outline_feedback(
        project_id: int,
        payload: SubmitOutlineFeedbackRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> OutlineRevisionResponse:
        project = _project_or_404(db, current_user.id, project_id)
        series_plan = _series_plan_for_feedback(db, project, payload.target_type, payload.target_id)
        current_payload = (
            json_loads_object(series_plan.current_version.summary_json)
            if series_plan.current_version is not None
            else _series_payload_from_rows(series_plan)
        )
        feedback = OutlineFeedbackItem(
            project=project,
            target_type=payload.target_type,
            target_id=payload.target_id,
            feedback_text=payload.feedback_text.strip(),
            feedback_type=payload.feedback_type.strip() or "general",
            priority=payload.priority,
            status="parsing",
        )
        db.add(feedback)
        db.flush()

        try:
            revised = OutlineRevisionService(settings).revise_plan(
                current_plan=current_payload,
                feedback_text=payload.feedback_text,
                target_type=payload.target_type,
            )
        except RuntimeError as exc:
            feedback.status = "failed"
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        revision = OutlineRevisionPlan(
            feedback_item=feedback,
            target_type=payload.target_type,
            target_id=payload.target_id,
            plan_json=json_dumps(revised["revision_plan"]),
            applied=True,
        )
        feedback.status = "applied"
        db.add(revision)
        _replace_plan_rows(
            db,
            series_plan=series_plan,
            payload=revised["revised_plan"],
            change_note=str(revised.get("change_note") or "按反馈修订概要"),
            source_feedback_snapshot=payload.feedback_text.strip(),
            created_by="feedback_parser",
        )
        db.commit()
        db.refresh(series_plan)
        db.refresh(feedback)
        db.refresh(revision)
        return OutlineRevisionResponse(
            feedback=_outline_feedback_out(feedback),
            revision_plan=_outline_revision_plan_out(revision),
            series_plan=_series_plan_out(series_plan),
        )

    @router.post("/api/projects/{project_id}/series-plans/{series_plan_id}/lock", response_model=SeriesPlanOut)
    def lock_series_plan(
        project_id: int,
        series_plan_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> SeriesPlanOut:
        project = _project_or_404(db, current_user.id, project_id)
        plan = _series_plan_or_404(db, project.id, series_plan_id)
        plan.status = "locked"
        for arc in plan.arc_plans:
            arc.status = "locked"
        for outline in plan.chapter_outlines:
            outline.status = "outline_locked"
            if outline.locked_at is None:
                outline.locked_at = datetime.utcnow()
        db.commit()
        db.refresh(plan)
        return _series_plan_out(plan)

    @router.post("/api/projects/{project_id}/series-plans/{series_plan_id}/versions/{version_id}/restore", response_model=SeriesPlanOut)
    def restore_series_plan_version(
        project_id: int,
        series_plan_id: int,
        version_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> SeriesPlanOut:
        project = _project_or_404(db, current_user.id, project_id)
        plan = _series_plan_or_404(db, project.id, series_plan_id)
        version = db.scalar(
            select(SeriesPlanVersion).where(
                SeriesPlanVersion.series_plan_id == plan.id,
                SeriesPlanVersion.id == version_id,
            )
        )
        if version is None:
            raise HTTPException(status_code=404, detail="概要版本不存在。")
        payload = json_loads_object(version.summary_json)
        _replace_plan_rows(
            db,
            series_plan=plan,
            payload=payload,
            change_note=f"恢复到版本 {version.version_no}",
            source_feedback_snapshot="",
            created_by="version_restore",
        )
        db.commit()
        db.refresh(plan)
        return _series_plan_out(plan)

    @router.post("/api/projects/{project_id}/chapter-outlines/lock", response_model=list[ChapterOutlineOut])
    def lock_chapter_outlines(
        project_id: int,
        payload: LockChapterOutlinesRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[ChapterOutlineOut]:
        project = _project_or_404(db, current_user.id, project_id)
        query = select(ChapterOutline).where(ChapterOutline.project_id == project.id)
        if payload.chapter_outline_ids:
            query = query.where(ChapterOutline.id.in_(payload.chapter_outline_ids))
        outlines = db.scalars(query.order_by(ChapterOutline.chapter_no.asc())).all()
        for outline in outlines:
            outline.status = "outline_locked"
            if outline.locked_at is None:
                outline.locked_at = datetime.utcnow()
        db.commit()
        return [_chapter_outline_out(item) for item in outlines]

    @router.put("/api/projects/{project_id}/chapter-outlines/{outline_id}", response_model=ChapterOutlineOut)
    def update_chapter_outline(
        project_id: int,
        outline_id: int,
        payload: UpdateChapterOutlineRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ChapterOutlineOut:
        project = _project_or_404(db, current_user.id, project_id)
        outline = _chapter_outline_or_404(db, project.id, outline_id)
        if outline.status == "chapter_canonical":
            raise HTTPException(status_code=409, detail="已定稿章节不能直接修改概要。")
        outline.title = payload.title.strip()
        outline.outline_json = json_dumps(payload.outline)
        outline.status = payload.status.strip() or "outline_draft"
        if outline.status == "outline_locked" and outline.locked_at is None:
            outline.locked_at = datetime.utcnow()
        if outline.status != "outline_locked":
            outline.locked_at = None
        outline.series_plan.status = "draft" if outline.status != "outline_locked" else outline.series_plan.status
        project_chapter = db.scalar(
            select(ProjectChapter).where(ProjectChapter.project_id == project.id, ProjectChapter.chapter_no == outline.chapter_no)
        )
        if project_chapter is not None:
            project_chapter.title = outline.title
            project_chapter.premise = _outline_payload_to_prompt(payload.outline)
        db.commit()
        db.refresh(outline)
        return _chapter_outline_out(outline)

    @router.post("/api/projects/{project_id}/batch-generation", response_model=BatchGenerationJobOut)
    def batch_generate(
        project_id: int,
        payload: BatchGenerationRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> BatchGenerationJobOut:
        if payload.end_chapter_no < payload.start_chapter_no:
            raise HTTPException(status_code=422, detail="结束章节不能小于开始章节。")
        project = _project_or_404(db, current_user.id, project_id)
        plan = _series_plan_or_404(db, project.id, payload.series_plan_id)
        if plan.status != "locked":
            raise HTTPException(status_code=409, detail="请先锁定长篇概要再批量生成正文。")
        try:
            job = BatchGenerationService(settings).run_job(
                db=db,
                project=project,
                series_plan=plan,
                start_chapter_no=payload.start_chapter_no,
                end_chapter_no=payload.end_chapter_no,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _batch_job_out(job)

    @router.post("/api/projects/{project_id}/batch-generation/{job_id}/retry", response_model=BatchGenerationJobOut)
    def retry_batch_generation(
        project_id: int,
        job_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> BatchGenerationJobOut:
        project = _project_or_404(db, current_user.id, project_id)
        previous_job = db.scalar(select(BatchGenerationJob).where(BatchGenerationJob.project_id == project.id, BatchGenerationJob.id == job_id))
        if previous_job is None:
            raise HTTPException(status_code=404, detail="批量任务不存在。")
        if previous_job.job_status == "completed":
            raise HTTPException(status_code=409, detail="已完成的批量任务不需要重试。")
        plan = _series_plan_or_404(db, project.id, previous_job.series_plan_id)
        if plan.status != "locked":
            raise HTTPException(status_code=409, detail="请先锁定长篇概要再重试批量生成。")
        retry_start = previous_job.start_chapter_no
        if previous_job.current_chapter_no is not None and previous_job.current_chapter_no < previous_job.end_chapter_no:
            retry_start = previous_job.current_chapter_no + 1
        try:
            job = BatchGenerationService(settings).run_job(
                db=db,
                project=project,
                series_plan=plan,
                start_chapter_no=retry_start,
                end_chapter_no=previous_job.end_chapter_no,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _batch_job_out(job)

    @router.post("/api/projects/{project_id}/draft-versions/{draft_version_id}/revise", response_model=DraftVersionOut)
    def revise_draft_version(
        project_id: int,
        draft_version_id: int,
        payload: ReviseDraftVersionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> DraftVersionOut:
        project = _project_or_404(db, current_user.id, project_id)
        draft = _draft_version_or_404(db, project.id, draft_version_id)
        outline = draft.chapter_outline
        outline_payload = json_loads_object(outline.outline_json)
        try:
            revised = DraftRevisionService(settings).revise(
                project=project,
                outline=outline,
                draft=draft,
                feedback_text=payload.feedback_text,
                outline_payload=outline_payload,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        generation = GenerationRun(
            project=project,
            project_chapter_id=draft.generation_run.project_chapter_id if draft.generation_run is not None else None,
            prompt=payload.feedback_text.strip(),
            search_method="draft_revision",
            response_type="全章重写",
            retrieval_context=json_dumps(
                {
                    "mode": "longform_draft_revision",
                    "parent_draft_version_id": draft.id,
                    "chapter_outline_id": outline.id,
                }
            ),
            scene_card="",
            evolution_snapshot=json_dumps({"process": {"revision": {"status": "done", "message": "正文重写已完成"}}}),
            generation_trace=json_dumps(
                {
                    "project": {"id": project.id, "title": project.title},
                    "chapter": {"outline_id": outline.id, "chapter_no": outline.chapter_no},
                    "request": {"mode": "longform_draft_revision"},
                    "result": {
                        "title": revised["title"],
                        "summary_length": len(revised["summary"]),
                        "content_length": len(revised["content"]),
                    },
                }
            ),
            title=revised["title"],
            summary=revised["summary"],
            content=revised["content"],
        )
        db.add(generation)
        db.flush()

        version_no = (
            db.scalar(
                select(DraftVersion.version_no)
                .where(DraftVersion.chapter_outline_id == outline.id)
                .order_by(DraftVersion.version_no.desc())
                .limit(1)
            )
            or 0
        ) + 1
        next_draft = DraftVersion(
            project=project,
            chapter_outline=outline,
            generation_run=generation,
            parent_version=draft,
            version_no=version_no,
            title=revised["title"],
            summary=revised["summary"],
            content=revised["content"],
            status="draft_revised",
            revision_reason=revised["change_note"],
        )
        outline.status = "draft_revised"
        db.add(next_draft)
        db.commit()
        db.refresh(next_draft)
        return _draft_version_out(next_draft)

    @router.post("/api/projects/{project_id}/draft-versions/{draft_version_id}/canonicalize", response_model=DraftVersionOut)
    def canonicalize_draft_version(
        project_id: int,
        draft_version_id: int,
        payload: CanonicalizeDraftVersionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> DraftVersionOut:
        project = _project_or_404(db, current_user.id, project_id)
        draft = _draft_version_or_404(db, project.id, draft_version_id)
        outline = draft.chapter_outline
        novel = None
        if payload.novel_id is not None:
            novel = db.scalar(
                select(Novel).where(
                    Novel.id == payload.novel_id,
                    Novel.owner_id == current_user.id,
                    Novel.project_id == project.id,
                    Novel.deleted_at.is_(None),
                )
            )
            if novel is None:
                raise HTTPException(status_code=404, detail="作品不存在。")
        else:
            novel = db.scalar(
                select(Novel).where(
                    Novel.owner_id == current_user.id,
                    Novel.project_id == project.id,
                    Novel.deleted_at.is_(None),
                )
            )
            if novel is None:
                novel = Novel(
                    owner=current_user,
                    project=project,
                    source_generation=draft.generation_run,
                    author_name=payload.author_name.strip() or current_user.display_name,
                    title=project.title,
                    summary=draft.summary,
                    genre=project.genre,
                    tagline=payload.tagline.strip(),
                    visibility=payload.visibility,
                    status="published",
                )
                db.add(novel)
                db.flush()

        existing_chapter = db.scalar(
            select(NovelChapter).where(NovelChapter.novel_id == novel.id, NovelChapter.chapter_no == outline.chapter_no)
        )
        if existing_chapter is None:
            db.add(
                NovelChapter(
                    novel=novel,
                    title=draft.title,
                    summary=draft.summary,
                    content=draft.content,
                    chapter_no=outline.chapter_no,
                )
            )
        else:
            existing_chapter.title = draft.title
            existing_chapter.summary = draft.summary
            existing_chapter.content = draft.content

        draft.status = "chapter_canonical"
        outline.status = "chapter_canonical"
        if draft.generation_run is not None and draft.generation_run.canonicalized_at is None:
            draft.generation_run.canonicalized_at = datetime.utcnow()
        db.commit()
        db.refresh(draft)
        return _draft_version_out(draft)

    @router.post("/api/projects/{project_id}/storyboards", response_model=StoryboardOut)
    def create_storyboard(
        project_id: int,
        payload: CreateStoryboardRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> StoryboardOut:
        project = _project_or_404(db, current_user.id, project_id)
        chapters = db.scalars(
            select(NovelChapter)
            .join(Novel, NovelChapter.novel_id == Novel.id)
            .where(
                Novel.owner_id == current_user.id,
                Novel.project_id == project.id,
                Novel.deleted_at.is_(None),
                NovelChapter.id.in_(payload.novel_chapter_ids),
            )
            .order_by(NovelChapter.chapter_no.asc())
        ).all()
        if len(chapters) != len(set(payload.novel_chapter_ids)):
            raise HTTPException(status_code=404, detail="只能选择当前项目下已发布/定稿章节生成分镜。")
        title = payload.title.strip() or f"{project.title} 读后短片"
        try:
            generated = StoryboardService(settings).generate_storyboard(project=project, chapters=chapters, title=title)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        storyboard = Storyboard(
            project=project,
            title=str(generated.get("title") or title).strip(),
            source_chapter_ids_json=json_dumps(payload.novel_chapter_ids),
            summary=str(generated.get("summary") or "").strip(),
            status="draft",
        )
        db.add(storyboard)
        db.flush()
        for index, shot_payload in enumerate(ensure_list(generated.get("shots")), start=1):
            if not isinstance(shot_payload, dict):
                continue
            db.add(
                StoryboardShot(
                    storyboard=storyboard,
                    shot_no=int(shot_payload.get("shot_no") or index),
                    narration_text=str(shot_payload.get("narration_text") or "").strip(),
                    visual_prompt=str(shot_payload.get("visual_prompt") or "").strip(),
                    character_refs_json=json_dumps(ensure_list(shot_payload.get("character_refs"))),
                    scene_refs_json=json_dumps(ensure_list(shot_payload.get("scene_refs"))),
                    duration_seconds=float(shot_payload.get("duration_seconds") or 4),
                    status="draft",
                )
            )
        db.commit()
        db.refresh(storyboard)
        return _storyboard_out(storyboard)

    @router.post("/api/projects/{project_id}/storyboards/{storyboard_id}/video-tasks", response_model=VideoTaskOut)
    def create_video_task(
        project_id: int,
        storyboard_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> VideoTaskOut:
        project = _project_or_404(db, current_user.id, project_id)
        storyboard = db.scalar(select(Storyboard).where(Storyboard.project_id == project.id, Storyboard.id == storyboard_id))
        if storyboard is None:
            raise HTTPException(status_code=404, detail="分镜稿不存在。")
        existing_task = db.scalar(
            select(VideoTask)
            .where(
                VideoTask.project_id == project.id,
                VideoTask.storyboard_id == storyboard.id,
                VideoTask.task_status.in_(("queued", "running")),
            )
            .order_by(VideoTask.created_at.desc())
        )
        if existing_task is not None:
            return _video_task_out(existing_task)
        service = MediaPipelineService()
        task = VideoTask(
            project_id=project.id,
            storyboard=storyboard,
            task_status="queued",
            output_uri="",
            progress_json=service.task_progress_json(storyboard=storyboard),
            error_message="",
        )
        existing_asset_keys = {
            (asset.shot_id, asset.asset_type)
            for asset in db.scalars(select(MediaAsset).where(MediaAsset.storyboard_id == storyboard.id)).all()
        }
        for shot in sorted(storyboard.shots, key=lambda item: item.shot_no):
            if (shot.id, "image") not in existing_asset_keys:
                db.add(
                    MediaAsset(
                        project_id=project.id,
                        storyboard=storyboard,
                        shot=shot,
                        asset_type="image",
                        uri="",
                        prompt=shot.visual_prompt,
                        status="pending",
                        meta_json=json_dumps({"shot_no": shot.shot_no, "purpose": "镜头图"}),
                    )
                )
                existing_asset_keys.add((shot.id, "image"))
            if (shot.id, "voice") not in existing_asset_keys:
                db.add(
                    MediaAsset(
                        project_id=project.id,
                        storyboard=storyboard,
                        shot=shot,
                        asset_type="voice",
                        uri="",
                        prompt=shot.narration_text,
                        status="pending",
                        meta_json=json_dumps({"shot_no": shot.shot_no, "purpose": "旁白"}),
                    )
                )
                existing_asset_keys.add((shot.id, "voice"))
            if (shot.id, "subtitle") not in existing_asset_keys:
                db.add(
                    MediaAsset(
                        project_id=project.id,
                        storyboard=storyboard,
                        shot=shot,
                        asset_type="subtitle",
                        uri="",
                        prompt=shot.narration_text,
                        status="pending",
                        meta_json=json_dumps({"shot_no": shot.shot_no, "purpose": "字幕"}),
                    )
                )
                existing_asset_keys.add((shot.id, "subtitle"))
        storyboard.status = "video_queued"
        db.add(task)
        db.commit()
        db.refresh(task)
        return _video_task_out(task)

    @router.put("/api/projects/{project_id}/video-tasks/{task_id}", response_model=VideoTaskOut)
    def update_video_task(
        project_id: int,
        task_id: int,
        payload: UpdateVideoTaskRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> VideoTaskOut:
        project = _project_or_404(db, current_user.id, project_id)
        task = db.scalar(select(VideoTask).where(VideoTask.project_id == project.id, VideoTask.id == task_id))
        if task is None:
            raise HTTPException(status_code=404, detail="视频任务不存在。")
        task.task_status = payload.task_status.strip() or "queued"
        task.output_uri = payload.output_uri.strip()
        task.progress_json = json_dumps(payload.progress)
        task.error_message = payload.error_message.strip()
        if task.task_status == "completed":
            task.storyboard.status = "video_completed"
        elif task.task_status == "failed":
            task.storyboard.status = "video_failed"
        db.commit()
        db.refresh(task)
        return _video_task_out(task)

    @router.post("/api/projects/{project_id}/storyboards/{storyboard_id}/shots", response_model=StoryboardOut)
    def create_storyboard_shot(
        project_id: int,
        storyboard_id: int,
        payload: CreateStoryboardShotRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> StoryboardOut:
        project = _project_or_404(db, current_user.id, project_id)
        storyboard = _storyboard_or_404(db, project.id, storyboard_id)
        shot_no = payload.shot_no or (max((shot.shot_no for shot in storyboard.shots), default=0) + 1)
        shifted = [shot for shot in sorted(storyboard.shots, key=lambda item: item.shot_no, reverse=True) if shot.shot_no >= shot_no]
        for index, shot in enumerate(shifted, start=1):
            shot.shot_no = 100_000 + index
        db.flush()
        for shot in shifted:
            shot.shot_no = shot.shot_no - 100_000 + shot_no
        db.add(
            StoryboardShot(
                storyboard=storyboard,
                shot_no=shot_no,
                narration_text=payload.narration_text.strip(),
                visual_prompt=payload.visual_prompt.strip(),
                character_refs_json=json_dumps(payload.character_refs),
                scene_refs_json=json_dumps(payload.scene_refs),
                duration_seconds=payload.duration_seconds,
                status=payload.status.strip() or "draft",
            )
        )
        storyboard.status = "draft"
        db.commit()
        db.refresh(storyboard)
        return _storyboard_out(storyboard)

    @router.put("/api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}", response_model=StoryboardOut)
    def update_storyboard_shot(
        project_id: int,
        storyboard_id: int,
        shot_id: int,
        payload: UpdateStoryboardShotRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> StoryboardOut:
        project = _project_or_404(db, current_user.id, project_id)
        storyboard = _storyboard_or_404(db, project.id, storyboard_id)
        shot = db.scalar(select(StoryboardShot).where(StoryboardShot.storyboard_id == storyboard.id, StoryboardShot.id == shot_id))
        if shot is None:
            raise HTTPException(status_code=404, detail="镜头不存在。")
        shot.narration_text = payload.narration_text.strip()
        shot.visual_prompt = payload.visual_prompt.strip()
        shot.character_refs_json = json_dumps(payload.character_refs)
        shot.scene_refs_json = json_dumps(payload.scene_refs)
        shot.duration_seconds = payload.duration_seconds
        shot.status = payload.status.strip() or "draft"
        storyboard.status = "draft"
        db.commit()
        db.refresh(storyboard)
        return _storyboard_out(storyboard)

    @router.delete("/api/projects/{project_id}/storyboards/{storyboard_id}/shots/{shot_id}", response_model=StoryboardOut)
    def delete_storyboard_shot(
        project_id: int,
        storyboard_id: int,
        shot_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> StoryboardOut:
        project = _project_or_404(db, current_user.id, project_id)
        storyboard = _storyboard_or_404(db, project.id, storyboard_id)
        shot = db.scalar(select(StoryboardShot).where(StoryboardShot.storyboard_id == storyboard.id, StoryboardShot.id == shot_id))
        if shot is None:
            raise HTTPException(status_code=404, detail="镜头不存在。")
        for asset in db.scalars(select(MediaAsset).where(MediaAsset.shot_id == shot.id)).all():
            db.delete(asset)
        db.delete(shot)
        db.flush()
        _renumber_storyboard_shots(storyboard)
        storyboard.status = "draft"
        db.commit()
        db.refresh(storyboard)
        return _storyboard_out(storyboard)

    @router.put("/api/projects/{project_id}/storyboards/{storyboard_id}/shots/reorder", response_model=StoryboardOut)
    def reorder_storyboard_shots(
        project_id: int,
        storyboard_id: int,
        payload: ReorderStoryboardShotsRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> StoryboardOut:
        project = _project_or_404(db, current_user.id, project_id)
        storyboard = _storyboard_or_404(db, project.id, storyboard_id)
        shot_by_id = {shot.id: shot for shot in storyboard.shots}
        if set(payload.shot_ids) != set(shot_by_id):
            raise HTTPException(status_code=422, detail="镜头排序必须包含当前分镜稿的全部镜头。")
        for index, shot_id in enumerate(payload.shot_ids, start=1):
            shot_by_id[shot_id].shot_no = 100_000 + index
        db.flush()
        for index, shot_id in enumerate(payload.shot_ids, start=1):
            shot_by_id[shot_id].shot_no = index
        storyboard.status = "draft"
        db.commit()
        db.refresh(storyboard)
        return _storyboard_out(storyboard)

    @router.put("/api/projects/{project_id}/media-assets/{asset_id}", response_model=MediaAssetOut)
    def update_media_asset(
        project_id: int,
        asset_id: int,
        payload: UpdateMediaAssetRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> MediaAssetOut:
        project = _project_or_404(db, current_user.id, project_id)
        asset = db.scalar(select(MediaAsset).where(MediaAsset.project_id == project.id, MediaAsset.id == asset_id))
        if asset is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        asset.uri = payload.uri.strip()
        asset.status = payload.status.strip() or "pending"
        asset.meta_json = json_dumps(payload.meta)
        db.commit()
        db.refresh(asset)
        return _media_asset_out(asset)


def _state_out(db: Session, project: Project) -> SeriesPlanningStateOut:
    plans = db.scalars(select(SeriesPlan).where(SeriesPlan.project_id == project.id).order_by(SeriesPlan.updated_at.desc())).all()
    drafts = db.scalars(select(DraftVersion).where(DraftVersion.project_id == project.id).order_by(DraftVersion.created_at.desc())).all()
    jobs = db.scalars(select(BatchGenerationJob).where(BatchGenerationJob.project_id == project.id).order_by(BatchGenerationJob.created_at.desc())).all()
    storyboards = db.scalars(select(Storyboard).where(Storyboard.project_id == project.id).order_by(Storyboard.created_at.desc())).all()
    video_tasks = db.scalars(select(VideoTask).where(VideoTask.project_id == project.id).order_by(VideoTask.created_at.desc())).all()
    media_assets = db.scalars(select(MediaAsset).where(MediaAsset.project_id == project.id).order_by(MediaAsset.created_at.desc())).all()
    return SeriesPlanningStateOut(
        series_plans=[_series_plan_out(item) for item in plans],
        draft_versions=[_draft_version_out(item) for item in drafts],
        batch_jobs=[_batch_job_out(item) for item in jobs],
        storyboards=[_storyboard_out(item) for item in storyboards],
        media_assets=[_media_asset_out(item) for item in media_assets],
        video_tasks=[_video_task_out(item) for item in video_tasks],
    )


def _persist_generated_plan(db: Session, project: Project, payload: dict, *, created_by: str) -> SeriesPlan:
    series = payload.get("series") if isinstance(payload.get("series"), dict) else {}
    plan = SeriesPlan(
        project=project,
        title=str(series.get("title") or project.title).strip(),
        target_chapter_count=int(series.get("target_chapter_count") or len(ensure_list(payload.get("chapters"))) or 12),
        theme=str(series.get("theme") or "").strip(),
        main_conflict=str(series.get("main_conflict") or "").strip(),
        ending_direction=str(series.get("ending_direction") or "").strip(),
        status="draft",
    )
    db.add(plan)
    db.flush()
    _replace_plan_rows(
        db,
        series_plan=plan,
        payload=payload,
        change_note=str(payload.get("change_note") or "生成初版长篇概要"),
        source_feedback_snapshot="",
        created_by=created_by,
    )
    return plan


def _replace_plan_rows(
    db: Session,
    *,
    series_plan: SeriesPlan,
    payload: dict,
    change_note: str,
    source_feedback_snapshot: str,
    created_by: str,
) -> None:
    series = payload.get("series") if isinstance(payload.get("series"), dict) else {}
    series_plan.title = str(series.get("title") or series_plan.title).strip()
    series_plan.target_chapter_count = int(series.get("target_chapter_count") or len(ensure_list(payload.get("chapters"))) or series_plan.target_chapter_count)
    series_plan.theme = str(series.get("theme") or series_plan.theme).strip()
    series_plan.main_conflict = str(series.get("main_conflict") or series_plan.main_conflict).strip()
    series_plan.ending_direction = str(series.get("ending_direction") or series_plan.ending_direction).strip()
    series_plan.status = "draft"
    next_version_no = max((item.version_no for item in series_plan.versions), default=0) + 1
    version = SeriesPlanVersion(
        series_plan=series_plan,
        version_no=next_version_no,
        summary_json=json_dumps(payload),
        change_note=change_note,
        source_feedback_snapshot=source_feedback_snapshot,
        created_by=created_by,
    )
    db.add(version)
    db.flush()
    series_plan.current_version = version

    for outline in list(series_plan.chapter_outlines):
        for draft in list(outline.draft_versions):
            db.delete(draft)
        db.delete(outline)
    for arc in list(series_plan.arc_plans):
        db.delete(arc)
    db.flush()

    arc_by_no: dict[int, ArcPlan] = {}
    for arc_payload in ensure_list(payload.get("arcs")):
        if not isinstance(arc_payload, dict):
            continue
        arc = ArcPlan(
            series_plan=series_plan,
            version=version,
            arc_no=int(arc_payload.get("arc_no") or len(arc_by_no) + 1),
            start_chapter_no=int(arc_payload.get("start_chapter_no") or 1),
            end_chapter_no=int(arc_payload.get("end_chapter_no") or 1),
            title=str(arc_payload.get("title") or "未命名阶段").strip(),
            goal=str(arc_payload.get("goal") or "").strip(),
            conflict=str(arc_payload.get("conflict") or "").strip(),
            turning_points_json=json_dumps(ensure_list(arc_payload.get("turning_points"))),
            status="draft",
        )
        db.add(arc)
        db.flush()
        arc_by_no[arc.arc_no] = arc

    for chapter_payload in ensure_list(payload.get("chapters")):
        if not isinstance(chapter_payload, dict):
            continue
        chapter_no = int(chapter_payload.get("chapter_no") or 1)
        arc = next((item for item in arc_by_no.values() if item.start_chapter_no <= chapter_no <= item.end_chapter_no), None)
        db.add(
            ChapterOutline(
                project_id=series_plan.project_id,
                series_plan=series_plan,
                arc_plan=arc,
                chapter_no=chapter_no,
                title=str(chapter_payload.get("title") or f"第 {chapter_no} 章").strip(),
                outline_json=json_dumps(chapter_payload),
                status="outline_draft",
            )
        )


def _series_plan_or_404(db: Session, project_id: int, series_plan_id: int) -> SeriesPlan:
    plan = db.scalar(select(SeriesPlan).where(SeriesPlan.project_id == project_id, SeriesPlan.id == series_plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="长篇概要不存在。")
    return plan


def _draft_version_or_404(db: Session, project_id: int, draft_version_id: int) -> DraftVersion:
    draft = db.scalar(select(DraftVersion).where(DraftVersion.project_id == project_id, DraftVersion.id == draft_version_id))
    if draft is None:
        raise HTTPException(status_code=404, detail="章节版本不存在。")
    return draft


def _chapter_outline_or_404(db: Session, project_id: int, outline_id: int) -> ChapterOutline:
    outline = db.scalar(select(ChapterOutline).where(ChapterOutline.project_id == project_id, ChapterOutline.id == outline_id))
    if outline is None:
        raise HTTPException(status_code=404, detail="章节概要不存在。")
    return outline


def _storyboard_or_404(db: Session, project_id: int, storyboard_id: int) -> Storyboard:
    storyboard = db.scalar(select(Storyboard).where(Storyboard.project_id == project_id, Storyboard.id == storyboard_id))
    if storyboard is None:
        raise HTTPException(status_code=404, detail="分镜稿不存在。")
    return storyboard


def _renumber_storyboard_shots(storyboard: Storyboard) -> None:
    ordered = sorted(storyboard.shots, key=lambda item: item.shot_no)
    for index, shot in enumerate(ordered, start=1):
        shot.shot_no = 100_000 + index
    for index, shot in enumerate(ordered, start=1):
        shot.shot_no = index


def _series_plan_for_feedback(db: Session, project: Project, target_type: str, target_id: int) -> SeriesPlan:
    if target_type == "series":
        return _series_plan_or_404(db, project.id, target_id)
    if target_type == "arc":
        arc = db.scalar(select(ArcPlan).join(SeriesPlan).where(ArcPlan.id == target_id, SeriesPlan.project_id == project.id))
        if arc is None:
            raise HTTPException(status_code=404, detail="阶段概要不存在。")
        return arc.series_plan
    outline = db.scalar(select(ChapterOutline).where(ChapterOutline.id == target_id, ChapterOutline.project_id == project.id))
    if outline is None:
        raise HTTPException(status_code=404, detail="章节概要不存在。")
    return outline.series_plan


def _series_payload_from_rows(series_plan: SeriesPlan) -> dict:
    return {
        "series": {
            "title": series_plan.title,
            "target_chapter_count": series_plan.target_chapter_count,
            "theme": series_plan.theme,
            "main_conflict": series_plan.main_conflict,
            "ending_direction": series_plan.ending_direction,
        },
        "arcs": [
            {
                "arc_no": item.arc_no,
                "start_chapter_no": item.start_chapter_no,
                "end_chapter_no": item.end_chapter_no,
                "title": item.title,
                "goal": item.goal,
                "conflict": item.conflict,
                "turning_points": json_loads_list(item.turning_points_json),
            }
            for item in sorted(series_plan.arc_plans, key=lambda arc: arc.arc_no)
        ],
        "chapters": [
            json_loads_object(item.outline_json)
            for item in sorted(series_plan.chapter_outlines, key=lambda outline: outline.chapter_no)
        ],
    }


def _outline_payload_to_prompt(outline_payload: dict) -> str:
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
