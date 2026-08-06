from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .config import Settings
from .db import get_db
from .models import GenerationAttempt, Project, User


def register_evidence_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/projects/{project_id}/generation-attempts")
    def list_generation_attempts(
        project_id: int,
        stage: str | None = None,
        status: str | None = None,
        limit: int = 50,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        """渐进披露：只读列出项目的生成证据；默认最近 50 条，可按 stage/status 过滤。

        返回的是脱敏后的证据（Round 7 落库时已截断 base64 与长文本），供专家
        控制台查看，不参与正常流程决策。
        """
        project = db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        safe_limit = max(1, min(int(limit), 200))
        query = select(GenerationAttempt).where(GenerationAttempt.project_id == project.id)
        if stage:
            query = query.where(GenerationAttempt.stage == stage)
        if status:
            query = query.where(GenerationAttempt.status == status)
        rows = db.scalars(
            query.order_by(GenerationAttempt.id.desc()).limit(safe_limit)
        ).all()
        return {"items": [_attempt_out(item) for item in rows]}


def _attempt_out(item: GenerationAttempt) -> dict:
    return {
        "id": item.id,
        "stage": item.stage,
        "status": item.status,
        "provider": item.provider,
        "model": item.model,
        "prompt_contract_id": item.prompt_contract_id,
        "prompt_version": item.prompt_version,
        "shot_id": item.shot_id,
        "adopted_asset_id": item.adopted_asset_id,
        "quality_outcome": item.quality_outcome,
        "cost_estimate_usd": item.cost_estimate_usd,
        "provider_ref": item.provider_ref,
        "error_category": item.error_category,
        "error_message": item.error_message,
        "validation_results": json.loads(item.validation_results or "{}"),
        "parameters": json.loads(item.parameters or "{}"),
        "usage": json.loads(item.usage or "{}"),
        "input_asset_versions": json.loads(item.input_asset_versions or "{}"),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
