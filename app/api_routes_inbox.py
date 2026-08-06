from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .config import Settings
from .db import get_db
from .exception_inbox_service import list_inbox_items, resolve_inbox_item
from .models import ExceptionInboxItem, Project, User

VALID_RESOLUTIONS = {"accepted", "dismissed"}


class ResolveInboxItemRequest(BaseModel):
    resolution: str


def register_inbox_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/projects/{project_id}/exception-inbox")
    def get_exception_inbox(
        project_id: int,
        status: str | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        project = _project_or_404(db, current_user.id, project_id)
        # 默认只返回待处理条目；status=all 返回含已解决/忽略的完整历史。
        if status is None:
            status = "open"
        elif status == "all":
            status = None
        items = list_inbox_items(db, project_id=project.id, status=status)
        return {"items": [_inbox_item_out(item) for item in items]}

    @router.post("/api/projects/{project_id}/exception-inbox/{item_id}/resolve")
    def resolve_exception_inbox_item(
        project_id: int,
        item_id: int,
        payload: ResolveInboxItemRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        project = _project_or_404(db, current_user.id, project_id)
        resolution = payload.resolution.strip()
        if resolution not in VALID_RESOLUTIONS:
            raise HTTPException(status_code=422, detail="resolution 必须是 accepted 或 dismissed。")
        try:
            item = resolve_inbox_item(db, project_id=project.id, item_id=item_id, resolution=resolution)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        db.commit()
        return _inbox_item_out(item)


def _project_or_404(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user_id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    return project


def _inbox_item_out(item: ExceptionInboxItem) -> dict:
    return {
        "id": item.id,
        "item_type": item.item_type,
        "status": item.status,
        "severity": item.severity,
        "title": item.title,
        "reason": item.reason,
        "recommended_action": item.recommended_action,
        "options": json.loads(item.options_json or "[]"),
        "evidence": json.loads(item.evidence_json or "{}"),
        "resolution": item.resolution,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
