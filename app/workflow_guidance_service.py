"""Guided coordinator: one deterministic production state and one next action.

The normal workflow never asks the creator to pick provider, model, prompt
template, upload order, or retry parameters: those are resolved here from
centralized settings and the prompt registry, then recorded for inspection.
User input is reserved for material exceptions (identity ambiguity, cost
approval, repeated quality failures) which surface in the exception inbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .context_pack_service import ContextPackService
from .exception_inbox_service import list_inbox_items
from .json_utils import json_loads_object
from .models import Project, Storyboard, VideoTask
from .prompt_registry import PROMPT_REGISTRY
from .video_preflight_service import video_quality_gate_failures


@dataclass(frozen=True)
class WorkflowGuidance:
    state: str
    next_action: str
    reason: str
    defaults: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)


def recommend_next_action(db: Session, *, project: Project, settings: Settings) -> WorkflowGuidance:
    """Derive the single recommended next action from persisted project state."""
    pack = ContextPackService().latest_for_project(db, project.id)
    if pack is None or pack.status != "confirmed":
        return WorkflowGuidance(
            state="needs_context_pack",
            next_action="完成生成前校对并确认创作上下文包",
            reason="项目尚未有已确认的创作上下文包，后续生成都依赖它。",
            defaults=_defaults(settings),
        )

    storyboard = db.scalar(
        select(Storyboard)
        .where(Storyboard.project_id == project.id)
        .order_by(Storyboard.id.desc())
    )
    if storyboard is None:
        return WorkflowGuidance(
            state="needs_storyboard",
            next_action="生成分镜稿",
            reason="项目还没有分镜稿，需要先生成分镜再进入视觉生产。",
            defaults=_defaults(settings),
        )
    if storyboard.status in {"queued", "running"}:
        return WorkflowGuidance(
            state="storyboard_generating",
            next_action="等待分镜生成完成",
            reason="分镜任务正在运行，完成后会自动进入下一阶段。",
            defaults=_defaults(settings),
        )
    if storyboard.status == "failed":
        return WorkflowGuidance(
            state="storyboard_failed",
            next_action="查看异常收件箱并修复分镜",
            reason=f"分镜生成失败：{storyboard.error_message or '未知原因'}",
            defaults=_defaults(settings),
        )

    active_task = db.scalar(
        select(VideoTask)
        .where(VideoTask.project_id == project.id, VideoTask.task_status.in_(("queued", "running")))
        .order_by(VideoTask.id.desc())
    )
    if active_task is not None:
        return WorkflowGuidance(
            state="rendering",
            next_action="等待视频渲染完成",
            reason="已有视频任务在渲染中，完成后进入质量验收。",
            defaults=_defaults(settings),
        )

    gate_failures = video_quality_gate_failures(db, settings=settings, project=project, storyboard=storyboard)
    if gate_failures:
        open_items = list_inbox_items(db, project_id=project.id, status="open")
        inbox_hint = (
            "；异常收件箱已有待处理条目，可先查看"
            if any(item.item_type in {"creative_identity", "repeated_quality_failure", "conflicting_constraints"} for item in open_items)
            else ""
        )
        return WorkflowGuidance(
            state="first_frame_blocked",
            next_action="补齐首帧前置素材或修复门禁问题",
            reason="；".join(gate_failures[:5]) + inbox_hint,
            defaults=_defaults(settings),
            blockers=gate_failures,
        )

    budget_items = [
        item for item in list_inbox_items(db, project_id=project.id, status="open") if item.item_type == "budget_approval"
    ]
    if budget_items:
        return WorkflowGuidance(
            state="budget_approval",
            next_action="确认视频生成预算或改用预览分辨率",
            reason=budget_items[0].reason or "视频生成估算成本超过项目阈值，需要确认。",
            defaults=_defaults(settings),
        )

    latest_task = db.scalar(select(VideoTask).where(VideoTask.project_id == project.id).order_by(VideoTask.id.desc()))
    if latest_task is not None:
        progress = json_loads_object(latest_task.progress_json)
        quality_result = progress.get("video_quality_result") if isinstance(progress.get("video_quality_result"), dict) else {}
        quality_status = str(quality_result.get("status") or "unknown")
        if latest_task.task_status == "completed":
            if quality_status == "accepted":
                return WorkflowGuidance(
                    state="completed",
                    next_action="短片已完成并验收，可继续下一个片段或调整素材",
                    reason="最后一个视频任务已完成并通过质量验收。",
                    defaults=_defaults(settings),
                )
            return WorkflowGuidance(
                state="needs_review",
                next_action="验收镜头质量或发起修复",
                reason=f"最后一个视频任务已完成，但质量状态为 {quality_status}，需要创作者验收。",
                defaults=_defaults(settings),
            )
        if latest_task.task_status == "failed":
            return WorkflowGuidance(
                state="render_failed",
                next_action="查看渲染失败原因并重试",
                reason=latest_task.error_message or "视频渲染失败。",
                defaults=_defaults(settings),
            )

    return WorkflowGuidance(
        state="ready_to_render",
        next_action="创建视频任务开始渲染（自动使用默认 provider/模型/提示词版本）",
        reason="分镜、规范身份与首帧门禁均已就绪，可以直接进入渲染。",
        defaults=_defaults(settings),
    )


def _defaults(settings: Settings) -> dict[str, Any]:
    return {
        "image_provider": settings.image_provider or "jimeng",
        "video_provider": "ark_seedance",
        "video_model": settings.ark_video_model,
        "preview_resolution": settings.ark_video_preview_resolution,
        "final_resolution": settings.ark_video_resolution,
        "prompt_contracts": {
            contract.prompt_id: contract.version for contract in PROMPT_REGISTRY.values()
        },
    }
