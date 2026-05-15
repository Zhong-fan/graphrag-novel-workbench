from __future__ import annotations

from .contracts import (
    ArcPlanOut,
    BatchGenerationJobOut,
    ChapterOutlineOut,
    DraftVersionOut,
    MediaAssetOut,
    OutlineFeedbackItemOut,
    OutlineRevisionPlanOut,
    SeriesPlanOut,
    SeriesPlanVersionOut,
    StoryboardOut,
    StoryboardShotOut,
    VideoTaskOut,
)
from .json_utils import json_loads_list, json_loads_object
from .models import (
    ArcPlan,
    BatchGenerationJob,
    ChapterOutline,
    DraftVersion,
    MediaAsset,
    OutlineFeedbackItem,
    OutlineRevisionPlan,
    SeriesPlan,
    SeriesPlanVersion,
    Storyboard,
    StoryboardShot,
    VideoTask,
)


def _series_plan_version_out(version: SeriesPlanVersion) -> SeriesPlanVersionOut:
    return SeriesPlanVersionOut(
        id=version.id,
        series_plan_id=version.series_plan_id,
        version_no=version.version_no,
        summary=json_loads_object(version.summary_json),
        change_note=version.change_note,
        source_feedback_snapshot=version.source_feedback_snapshot,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _arc_plan_out(arc: ArcPlan) -> ArcPlanOut:
    return ArcPlanOut(
        id=arc.id,
        series_plan_id=arc.series_plan_id,
        version_id=arc.version_id,
        arc_no=arc.arc_no,
        start_chapter_no=arc.start_chapter_no,
        end_chapter_no=arc.end_chapter_no,
        title=arc.title,
        goal=arc.goal,
        conflict=arc.conflict,
        turning_points=json_loads_list(arc.turning_points_json),
        status=arc.status,
    )


def _chapter_outline_out(outline: ChapterOutline) -> ChapterOutlineOut:
    return ChapterOutlineOut(
        id=outline.id,
        project_id=outline.project_id,
        series_plan_id=outline.series_plan_id,
        arc_plan_id=outline.arc_plan_id,
        chapter_no=outline.chapter_no,
        title=outline.title,
        outline=json_loads_object(outline.outline_json),
        status=outline.status,
        locked_at=outline.locked_at,
        created_at=outline.created_at,
        updated_at=outline.updated_at,
    )


def _draft_version_out(draft: DraftVersion) -> DraftVersionOut:
    return DraftVersionOut(
        id=draft.id,
        project_id=draft.project_id,
        chapter_outline_id=draft.chapter_outline_id,
        generation_run_id=draft.generation_run_id,
        parent_version_id=draft.parent_version_id,
        version_no=draft.version_no,
        title=draft.title,
        summary=draft.summary,
        content=draft.content,
        status=draft.status,
        revision_reason=draft.revision_reason,
        created_at=draft.created_at,
    )


def _series_plan_out(plan: SeriesPlan) -> SeriesPlanOut:
    versions = sorted(plan.versions, key=lambda item: item.version_no)
    arcs = sorted(plan.arc_plans, key=lambda item: item.arc_no)
    chapters = sorted(plan.chapter_outlines, key=lambda item: item.chapter_no)
    return SeriesPlanOut(
        id=plan.id,
        project_id=plan.project_id,
        title=plan.title,
        target_chapter_count=plan.target_chapter_count,
        theme=plan.theme,
        main_conflict=plan.main_conflict,
        ending_direction=plan.ending_direction,
        status=plan.status,
        current_version_id=plan.current_version_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        current_version=_series_plan_version_out(plan.current_version) if plan.current_version is not None else None,
        versions=[_series_plan_version_out(item) for item in versions],
        arcs=[_arc_plan_out(item) for item in arcs],
        chapters=[_chapter_outline_out(item) for item in chapters],
    )


def _outline_feedback_out(feedback: OutlineFeedbackItem) -> OutlineFeedbackItemOut:
    return OutlineFeedbackItemOut.model_validate(feedback)


def _outline_revision_plan_out(plan: OutlineRevisionPlan) -> OutlineRevisionPlanOut:
    return OutlineRevisionPlanOut(
        id=plan.id,
        feedback_item_id=plan.feedback_item_id,
        target_type=plan.target_type,
        target_id=plan.target_id,
        plan=json_loads_object(plan.plan_json),
        applied=plan.applied,
        created_at=plan.created_at,
    )


def _batch_job_out(job: BatchGenerationJob) -> BatchGenerationJobOut:
    return BatchGenerationJobOut(
        id=job.id,
        project_id=job.project_id,
        series_plan_id=job.series_plan_id,
        start_chapter_no=job.start_chapter_no,
        end_chapter_no=job.end_chapter_no,
        job_status=job.job_status,
        current_chapter_no=job.current_chapter_no,
        result_summary=json_loads_object(job.result_summary_json),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _storyboard_shot_out(shot: StoryboardShot) -> StoryboardShotOut:
    return StoryboardShotOut(
        id=shot.id,
        storyboard_id=shot.storyboard_id,
        shot_no=shot.shot_no,
        narration_text=shot.narration_text,
        visual_prompt=shot.visual_prompt,
        character_refs=json_loads_list(shot.character_refs_json),
        scene_refs=json_loads_list(shot.scene_refs_json),
        duration_seconds=shot.duration_seconds,
        status=shot.status,
    )


def _storyboard_out(storyboard: Storyboard) -> StoryboardOut:
    return StoryboardOut(
        id=storyboard.id,
        project_id=storyboard.project_id,
        title=storyboard.title,
        source_chapter_ids=json_loads_list(storyboard.source_chapter_ids_json),
        status=storyboard.status,
        summary=storyboard.summary,
        shots=[_storyboard_shot_out(item) for item in sorted(storyboard.shots, key=lambda shot: shot.shot_no)],
        created_at=storyboard.created_at,
        updated_at=storyboard.updated_at,
    )


def _video_task_out(task: VideoTask) -> VideoTaskOut:
    return VideoTaskOut(
        id=task.id,
        project_id=task.project_id,
        storyboard_id=task.storyboard_id,
        task_status=task.task_status,
        output_uri=task.output_uri,
        progress=json_loads_object(task.progress_json),
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _media_asset_out(asset: MediaAsset) -> MediaAssetOut:
    return MediaAssetOut(
        id=asset.id,
        project_id=asset.project_id,
        storyboard_id=asset.storyboard_id,
        shot_id=asset.shot_id,
        asset_type=asset.asset_type,
        uri=asset.uri,
        prompt=asset.prompt,
        status=asset.status,
        meta=json_loads_object(asset.meta_json),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )
