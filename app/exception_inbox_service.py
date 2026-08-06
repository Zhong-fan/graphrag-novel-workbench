"""Exception inbox: material decisions are routed to the creator, never auto-made.

The coordinator only needs user input when the choice changes creative
identity, story meaning, quality acceptance, cost exposure, or irreversible
state. Each item carries one recommended action, the reason, impact, and at
most three options. Items are append-only; resolution is recorded on the row.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ExceptionInboxItem, Project

MAX_OPTIONS = 3


def create_inbox_item(
    db: Session,
    *,
    project: Project,
    item_type: str,
    title: str,
    reason: str,
    recommended_action: str,
    options: list[dict[str, str]] | None = None,
    evidence: dict[str, Any] | None = None,
    severity: str = "medium",
) -> ExceptionInboxItem:
    """Create an open item, or return the identical open item (idempotent).

    Deduplication key: item_type + title + evidence, so repeated failures and
    repeated budget blocks do not flood the inbox.
    """
    options = (options or [])[:MAX_OPTIONS]
    evidence_payload = dict(evidence or {})
    for existing in db.scalars(
        select(ExceptionInboxItem).where(
            ExceptionInboxItem.project_id == project.id,
            ExceptionInboxItem.status == "open",
        )
    ).all():
        if (
            existing.item_type == item_type
            and existing.title == title
            and json.loads(existing.evidence_json or "{}") == evidence_payload
        ):
            return existing
    row = ExceptionInboxItem(
        project_id=project.id,
        item_type=item_type,
        status="open",
        severity=severity,
        title=title,
        reason=reason,
        recommended_action=recommended_action,
        options_json=json.dumps(options, ensure_ascii=False),
        evidence_json=json.dumps(evidence_payload, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def list_inbox_items(db: Session, *, project_id: int, status: str | None = None) -> list[ExceptionInboxItem]:
    query = select(ExceptionInboxItem).where(ExceptionInboxItem.project_id == project_id)
    if status:
        query = query.where(ExceptionInboxItem.status == status)
    return list(db.scalars(query.order_by(ExceptionInboxItem.created_at.desc())).all())


def resolve_inbox_item(
    db: Session,
    *,
    project_id: int,
    item_id: int,
    resolution: str,
) -> ExceptionInboxItem:
    """Resolve or dismiss an item; only open items can transition."""
    item = db.scalar(
        select(ExceptionInboxItem).where(
            ExceptionInboxItem.id == item_id,
            ExceptionInboxItem.project_id == project_id,
        )
    )
    if item is None:
        raise LookupError(f"收件箱条目不存在：{item_id}")
    if item.status != "open":
        return item
    item.status = "resolved"
    item.resolution = resolution
    item.resolved_at = datetime.utcnow()
    db.flush()
    return item
