from __future__ import annotations

from typing import Any

from .contracts import (
    ArcPlanOut,
    BatchGenerationChapterTaskOut,
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
    TaskEventOut,
    VideoTaskOut,
)
from .json_utils import json_loads_list, json_loads_object
from .models import (
    ArcPlan,
    BatchGenerationChapterTask,
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
    TaskEvent,
    VideoTask,
)
from .video_quality_service import build_review_findings


def ensure_phase1_progress_contract(progress: dict[str, object] | None) -> dict[str, object]:
    base: dict[str, object] = dict(progress or {})
    base.setdefault("preflight_summary", {})
    base.setdefault("generation_trace", [])
    base.setdefault("review_findings", [])
    base.setdefault("rework_hints", [])
    return base


def build_storyboard_state_payload(
    storyboard: dict[str, object],
    media_assets: list[dict[str, object]],
    video_tasks: list[dict[str, object]],
) -> dict[str, object]:
    payload = dict(storyboard)
    payload["progress"] = ensure_phase1_progress_contract(payload.get("progress") if isinstance(payload.get("progress"), dict) else None)
    payload["media_assets"] = list(media_assets)
    payload["video_tasks"] = list(video_tasks)
    return payload


def _generation_trace_status(*, storyboard_status: str, blocked: bool = False, warning: bool = False) -> str:
    if blocked:
        return "blocked"
    if warning:
        return "warning"
    if storyboard_status in {"draft", "video_completed"}:
        return "completed"
    if storyboard_status in {"queued", "running"}:
        return "ready"
    return "warning"


def _generation_trace(storyboard: Storyboard, *, queued_payload: dict[str, Any], preflight_summary: dict[str, Any], latest_video_task: VideoTask | None) -> list[dict[str, Any]]:
    source_mode = str(queued_payload.get("source_mode") or "novel_chapters")
    source_trace = queued_payload.get("source_trace") if isinstance(queued_payload.get("source_trace"), dict) else {}
    source_chapter_ids = [int(item) for item in json_loads_list(storyboard.source_chapter_ids_json) if str(item).isdigit()]
    shot_metas = [json_loads_object(shot.meta_json) for shot in storyboard.shots]
    ordered_shots = sorted(storyboard.shots, key=lambda item: item.shot_no)
    first_frame_assets = [asset for asset in storyboard.media_assets if asset.asset_type == "shot_first_frame" and asset.status == "completed"]
    locked_first_frame_assets = [asset for asset in first_frame_assets if json_loads_object(asset.meta_json).get("locked") is True]
    locked_turnarounds = [
        asset
        for asset in storyboard.media_assets
        if asset.asset_type == "character_turnaround" and asset.status == "completed" and json_loads_object(asset.meta_json).get("locked") is True
    ]
    previous_last_frame_shots = sum(
        1
        for meta in shot_metas
        if isinstance(meta.get("continuity"), dict) and str(meta["continuity"].get("first_frame_source") or "") == "previous_last_frame"
    )
    blocked_reasons = [str(item) for item in preflight_summary.get("quality_gate_failures", []) if str(item).strip()]
    warning_reasons = [str(item) for item in preflight_summary.get("risk_warnings", []) if str(item).strip()]
    latest_render_progress = json_loads_object(latest_video_task.progress_json) if latest_video_task is not None else {}
    latest_render_steps = latest_render_progress.get("steps") if isinstance(latest_render_progress.get("steps"), list) else []
    latest_render_shots = latest_render_progress.get("shots") if isinstance(latest_render_progress.get("shots"), list) else []
    storyboard_prompt_preview = "\n\n".join(
        f"镜头 {shot.shot_no}\n旁白：{shot.narration_text}\n提示词：{shot.visual_prompt}"
        for shot in ordered_shots[:3]
    )
    asset_prompt_preview = "\n\n".join(
        f"{asset.asset_type}#{asset.id}\n{asset.prompt}"
        for asset in first_frame_assets[:3]
        if asset.prompt
    )
    render_prompt_preview = ""
    if latest_video_task is not None:
        if isinstance(latest_render_progress.get("video_quality_plan"), dict):
            render_prompt_preview = str(json_loads_object(latest_video_task.progress_json).get("message") or "")
        if not render_prompt_preview:
            video_assets = [
                asset
                for asset in storyboard.media_assets
                if asset.asset_type == "video" and asset.status in {"running", "completed"} and asset.prompt
            ]
            if video_assets:
                render_prompt_preview = "\n\n".join(asset.prompt for asset in video_assets[:2])
    render_prompt_sources = []
    for asset in storyboard.media_assets:
        if asset.asset_type not in {"video", "image", "subtitle"}:
            continue
        if asset.status not in {"running", "completed"}:
            continue
        if not asset.prompt:
            continue
        render_prompt_sources.append(
            {
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "shot_id": asset.shot_id,
                "status": asset.status,
                "prompt": asset.prompt,
            }
        )
    render_prompt_sources = render_prompt_sources[:6]
    render_inputs = []
    for item in latest_render_shots[:5]:
        if not isinstance(item, dict):
            continue
        render_inputs.append(
            {
                "shot_no": item.get("shot_no"),
                "used_first_frame": bool(item.get("used_first_frame")),
                "image_status": item.get("image_status") or "",
                "dialogue_status": item.get("dialogue_status") or "",
                "subtitle_status": item.get("subtitle_status") or "",
                "composed_status": item.get("composed_status") or "",
                "warnings": item.get("warnings") if isinstance(item.get("warnings"), list) else [],
            }
        )
    first_frame_refs = [
        {
            "asset_id": asset.id,
            "shot_id": asset.shot_id,
            "locked": json_loads_object(asset.meta_json).get("locked") is True,
            "prompt": asset.prompt,
        }
        for asset in first_frame_assets[:5]
    ]

    return [
        {
            "step_key": "source",
            "label": "来源准备",
            "status": "completed" if storyboard.shots else "ready",
            "source_mode": source_mode,
            "summary_lines": [
                f"来源模式：{source_mode}",
                f"章节数：{len(source_trace.get('novel_chapter_ids') or source_chapter_ids)}",
                f"参考图数：{len(source_trace.get('reference_image_asset_ids') or [])}",
            ],
            "prompt_text": str(source_trace.get("reference_video_brief") or ""),
            "parameters": {
                "source_trace": source_trace,
                "title": storyboard.title,
                "summary": storyboard.summary,
            },
            "inherited_inputs": [
                {"kind": "source_mode", "label": "来源模式", "value": source_mode},
                {"kind": "key_image_strategy", "label": "关键图策略", "value": str(source_trace.get("key_image_strategy") or "generate_first_frames")},
                {"kind": "chapter_ids", "label": "章节输入", "value": ",".join(str(item) for item in (source_trace.get("novel_chapter_ids") or source_chapter_ids)) or "无"},
            ],
        },
        {
            "step_key": "storyboard",
            "label": "分镜规划",
            "status": _generation_trace_status(storyboard_status=storyboard.status),
            "source_mode": source_mode,
            "summary_lines": [
                f"镜头数：{len(storyboard.shots)}",
                f"已锁定镜头：{sum(1 for shot in storyboard.shots if shot.status == 'locked')}",
            ],
            "prompt_text": storyboard_prompt_preview,
            "parameters": {
                "shot_count": len(storyboard.shots),
                "shots": [
                    {
                        "shot_no": shot.shot_no,
                        "duration_seconds": shot.duration_seconds,
                        "character_ref_count": len(json_loads_list(shot.character_refs_json)),
                        "scene_ref_count": len(json_loads_list(shot.scene_refs_json)),
                    }
                    for shot in ordered_shots[:5]
                ],
            },
            "inherited_inputs": [
                {"kind": "source_trace", "label": "来源追踪", "value": str(source_trace.get("reference_video_brief") or source_mode)},
            ],
        },
        {
            "step_key": "assets",
            "label": "视觉资产准备",
            "status": _generation_trace_status(
                storyboard_status=storyboard.status,
                blocked=bool(blocked_reasons),
                warning=not blocked_reasons and (bool(first_frame_assets) or bool(locked_turnarounds)),
            ),
            "source_mode": source_mode,
            "summary_lines": [
                f"首帧素材：{len(first_frame_assets)}",
                f"已锁定首帧：{len(locked_first_frame_assets)}",
                f"已锁定三视图：{len(locked_turnarounds)}",
                f"尾帧续镜头：{previous_last_frame_shots}",
            ],
            "prompt_text": asset_prompt_preview,
            "parameters": {
                "first_frame_asset_ids": [asset.id for asset in first_frame_assets[:10]],
                "locked_first_frame_asset_ids": [asset.id for asset in locked_first_frame_assets[:10]],
                "locked_turnaround_asset_ids": [asset.id for asset in locked_turnarounds[:10]],
            },
            "inherited_inputs": [
                {"kind": "locked_assets", "label": "锁定角色资产", "value": str(len(locked_turnarounds))},
                {"kind": "first_frames", "label": "可用首帧", "value": str(len(first_frame_assets))},
            ],
        },
        {
            "step_key": "preflight",
            "label": "视频预检",
            "status": "blocked" if blocked_reasons else "warning" if warning_reasons else ("completed" if preflight_summary else "ready"),
            "source_mode": source_mode,
            "summary_lines": [
                f"阻断项：{len(blocked_reasons)}",
                f"风险提示：{len(warning_reasons)}",
            ],
            "parameters": preflight_summary,
            "inherited_inputs": [
                {"kind": "blocked_reason", "label": "门禁阻断", "value": blocked_reasons[0] if blocked_reasons else "无"},
            ],
        },
        {
            "step_key": "render",
            "label": "视频生成",
            "status": (
                "completed"
                if latest_video_task and latest_video_task.task_status == "completed"
                else "blocked"
                if latest_video_task and latest_video_task.task_status == "failed"
                else "ready"
            ),
            "source_mode": source_mode,
            "summary_lines": [
                f"任务状态：{latest_video_task.task_status if latest_video_task is not None else 'not_started'}",
                f"当前阶段：{latest_render_progress.get('current_step') or ''}",
            ],
            "prompt_text": render_prompt_preview,
            "parameters": {
                "current_step": latest_render_progress.get("current_step") or "",
                "steps": latest_render_steps,
                "completed_shot_count": latest_render_progress.get("completed_shot_count") or 0,
                "video_quality_plan": latest_render_progress.get("video_quality_plan") if isinstance(latest_render_progress.get("video_quality_plan"), dict) else {},
                "render_inputs": render_inputs,
                "first_frame_refs": first_frame_refs,
                "provider": latest_render_progress.get("provider") or "",
                "render_prompt_sources": render_prompt_sources,
            },
            "inherited_inputs": [
                {"kind": "provider", "label": "执行通道", "value": str(latest_render_progress.get("provider") or "未开始")},
                {"kind": "current_step", "label": "当前步骤", "value": str(latest_render_progress.get("current_step") or "未开始")},
                {"kind": "first_frame_reuse", "label": "首帧复用镜头数", "value": str(sum(1 for item in render_inputs if item.get("used_first_frame")) )},
            ],
        },
    ]


def _public_asset_url(uri: str) -> str:
    if not uri:
        return ""
    normalized = uri.replace("\\", "/")
    marker = "/output/"
    if marker in normalized:
        return "/output/" + normalized.split(marker, 1)[1]
    if normalized.startswith("output/"):
        return "/" + normalized
    return ""


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
        chapter_no=draft.chapter_outline.chapter_no if draft.chapter_outline is not None else 0,
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
    tasks = sorted(job.chapter_tasks, key=lambda item: item.chapter_no)
    events = sorted(job.events, key=lambda item: item.created_at)
    return BatchGenerationJobOut(
        id=job.id,
        project_id=job.project_id,
        series_plan_id=job.series_plan_id,
        start_chapter_no=job.start_chapter_no,
        end_chapter_no=job.end_chapter_no,
        job_status=job.job_status,
        current_chapter_no=job.current_chapter_no,
        result_summary=json_loads_object(job.result_summary_json),
        worker_id=job.worker_id,
        worker_started_at=job.worker_started_at,
        last_heartbeat_at=job.last_heartbeat_at,
        chapter_tasks=[_batch_chapter_task_out(item) for item in tasks],
        events=[_task_event_out(item) for item in events[-80:]],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _batch_chapter_task_out(task: BatchGenerationChapterTask) -> BatchGenerationChapterTaskOut:
    return BatchGenerationChapterTaskOut(
        id=task.id,
        job_id=task.job_id,
        chapter_outline_id=task.chapter_outline_id,
        chapter_no=task.chapter_no,
        status=task.status,
        draft_version_id=task.draft_version_id,
        generation_run_id=task.generation_run_id,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _task_event_out(event: TaskEvent) -> TaskEventOut:
    return TaskEventOut(
        id=event.id,
        project_id=event.project_id,
        job_id=event.job_id,
        storyboard_id=event.storyboard_id,
        video_task_id=event.video_task_id,
        chapter_task_id=event.chapter_task_id,
        event_type=event.event_type,
        message=event.message,
        payload=json_loads_object(event.payload_json),
        created_at=event.created_at,
    )


def _storyboard_shot_out(shot: StoryboardShot) -> StoryboardShotOut:
    meta = json_loads_object(shot.meta_json)
    audio_script = meta.get("audio_script") if isinstance(meta.get("audio_script"), dict) else {}
    audio_script = {**audio_script, "audio_script_locked": bool(audio_script.get("audio_script_locked"))}
    continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
    return StoryboardShotOut(
        id=shot.id,
        storyboard_id=shot.storyboard_id,
        shot_no=shot.shot_no,
        narration_text=shot.narration_text,
        visual_prompt=shot.visual_prompt,
        character_refs=json_loads_list(shot.character_refs_json),
        scene_refs=json_loads_list(shot.scene_refs_json),
        audio_script=audio_script,
        continuity=continuity,
        duration_seconds=shot.duration_seconds,
        status=shot.status,
    )


def _storyboard_out(storyboard: Storyboard) -> StoryboardOut:
    events = sorted(storyboard.events, key=lambda item: item.created_at)
    return StoryboardOut(
        id=storyboard.id,
        project_id=storyboard.project_id,
        title=storyboard.title,
        source_chapter_ids=json_loads_list(storyboard.source_chapter_ids_json),
        status=storyboard.status,
        summary=storyboard.summary,
        progress=_storyboard_progress(storyboard, events),
        worker_id=storyboard.worker_id,
        worker_started_at=storyboard.worker_started_at,
        last_heartbeat_at=storyboard.last_heartbeat_at,
        error_message=storyboard.error_message,
        shots=[_storyboard_shot_out(item) for item in sorted(storyboard.shots, key=lambda shot: shot.shot_no)],
        events=[_task_event_out(item) for item in events[-80:]],
        created_at=storyboard.created_at,
        updated_at=storyboard.updated_at,
    )


def _storyboard_progress(storyboard: Storyboard, events: list[TaskEvent]) -> dict[str, Any]:
    latest_event = events[-1] if events else None
    latest_payload = json_loads_object(latest_event.payload_json) if latest_event is not None else {}
    queued_event = next((item for item in events if item.event_type == "storyboard_queued"), None)
    queued_payload = json_loads_object(queued_event.payload_json) if queued_event is not None else {}
    import_event = next((item for item in events if item.event_type == "storyboard_imported"), None)
    if queued_event is None and import_event is not None:
        queued_payload = json_loads_object(import_event.payload_json)
        queued_payload.setdefault("source_mode", "json_import")
    preflight_event = next(
        (
            item
            for item in reversed(events)
            if item.event_type in {"storyboard_preflight_completed", "storyboard_preflight_blocked"}
        ),
        None,
    )
    preflight_summary = json_loads_object(preflight_event.payload_json) if preflight_event is not None else {}
    latest_video_task = max(storyboard.video_tasks, key=lambda item: item.created_at, default=None)
    review_findings: list[dict[str, object]] = []
    if latest_video_task is not None:
        task_progress = json_loads_object(latest_video_task.progress_json)
        quality_result = task_progress.get("video_quality_result") if isinstance(task_progress.get("video_quality_result"), dict) else {}
        if isinstance(quality_result.get("review_findings"), list):
            review_findings = [item for item in quality_result["review_findings"] if isinstance(item, dict)]
        elif isinstance(task_progress.get("shot_results"), list):
            review_findings = build_review_findings([item for item in task_progress["shot_results"] if isinstance(item, dict)])
    rework_hints = []
    for finding in review_findings:
        level = finding.get("recommended_rework_level")
        if isinstance(level, str) and level not in rework_hints:
            rework_hints.append(level)
    shot_count = len(storyboard.shots)
    source_chapter_ids = json_loads_list(storyboard.source_chapter_ids_json)
    last_event_type = latest_event.event_type if latest_event is not None else ""
    failure_stage = "storyboard_generate" if storyboard.status == "failed" else ""
    current_step = ""
    if last_event_type == "storyboard_started":
        current_step = "storyboard_generate"
    elif last_event_type == "storyboard_shots_parsed":
        current_step = "storyboard_parse"
    elif last_event_type == "storyboard_completed":
        current_step = "storyboard_done"
    elif last_event_type == "storyboard_imported":
        current_step = "storyboard_imported"
    progress = {
        "stage": storyboard.status,
        "current_step": current_step,
        "failure_stage": failure_stage,
        "status": storyboard.status,
        "source_mode": str(queued_payload.get("source_mode") or "novel_chapters"),
        "source_trace": queued_payload.get("source_trace") if isinstance(queued_payload.get("source_trace"), dict) else {},
        "reference_video_brief": str(queued_payload.get("reference_video_brief") or ""),
        "key_image_strategy": str(queued_payload.get("key_image_strategy") or "generate_first_frames"),
        "reference_image_asset_ids": queued_payload.get("reference_image_asset_ids") if isinstance(queued_payload.get("reference_image_asset_ids"), list) else [],
        "source_chapter_count": len(source_chapter_ids),
        "shot_count": shot_count,
        "last_event_type": last_event_type,
        "last_event_message": latest_event.message if latest_event is not None else "",
        "last_event_payload": latest_payload,
        "preflight_summary": preflight_summary,
        "generation_trace": _generation_trace(
            storyboard,
            queued_payload=queued_payload,
            preflight_summary=preflight_summary,
            latest_video_task=latest_video_task,
        ),
        "review_findings": review_findings,
        "rework_hints": rework_hints,
        "last_updated_at": storyboard.last_heartbeat_at or storyboard.updated_at,
        "error_message": storyboard.error_message or "",
    }
    return ensure_phase1_progress_contract(progress)


def _video_task_out(task: VideoTask) -> VideoTaskOut:
    events = sorted(task.events, key=lambda item: item.created_at)
    progress = ensure_phase1_progress_contract(json_loads_object(task.progress_json))
    quality_result = progress.get("video_quality_result") if isinstance(progress.get("video_quality_result"), dict) else {}
    progress["quality_status"] = str(quality_result.get("status") or "unknown")
    public_url = _public_asset_url(task.output_uri)
    if public_url:
        progress = {**progress, "public_url": public_url}
    return VideoTaskOut(
        id=task.id,
        project_id=task.project_id,
        storyboard_id=task.storyboard_id,
        task_status=task.task_status,
        output_uri=task.output_uri,
        progress=progress,
        error_message=task.error_message,
        events=[_task_event_out(item) for item in events[-80:]],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _media_asset_out(asset: MediaAsset) -> MediaAssetOut:
    meta = json_loads_object(asset.meta_json)
    public_url = _public_asset_url(asset.uri)
    if public_url:
        meta = {**meta, "public_url": public_url}
    return MediaAssetOut(
        id=asset.id,
        project_id=asset.project_id,
        storyboard_id=asset.storyboard_id,
        shot_id=asset.shot_id,
        asset_type=asset.asset_type,
        uri=asset.uri,
        prompt=asset.prompt,
        status=asset.status,
        meta=meta,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        deleted_at=asset.deleted_at,
    )
