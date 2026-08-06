"""Persisted generation evidence: one row per real or blocked attempt.

Business services keep deciding generation strategy; this module only turns a
typed evidence draft into an append-only database row with secret redaction
and bounded output retention. Providers and models remain traceable but are
never treated as domain rules here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from .capabilities import sanitize_provider_payload
from .models import GenerationAttempt

MAX_RAW_OUTPUT_CHARS = 200_000


@dataclass(frozen=True)
class GenerationEvidence:
    """Draft for one generation attempt; JSON fields are redacted on write."""

    stage: str
    status: str  # succeeded | failed | blocked | requires_review
    provider: str = ""
    model: str = ""
    project_id: int | None = None
    storyboard_id: int | None = None
    video_task_id: int | None = None
    shot_id: int | None = None
    adopted_asset_id: int | None = None
    prompt_contract_id: str = ""
    prompt_version: str = ""
    rendered_prompt: str = ""
    raw_output: str = ""
    parsed_output: dict[str, Any] | None = None
    validation_results: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    input_asset_versions: dict[str, Any] | None = None
    cost_estimate_usd: float | None = None
    quality_outcome: str = ""
    provider_ref: str = ""
    error_category: str = ""
    error_message: str = ""


def _redact(value: Any) -> Any:
    # sanitize_provider_payload trims base64/binary keys, oversized lists and
    # long strings so persisted evidence never carries full provider blobs.
    return sanitize_provider_payload(value)


def record_generation_evidence(db: Session, *, evidence: GenerationEvidence) -> GenerationAttempt:
    """Append one attempt row. The caller owns the surrounding transaction."""

    row = GenerationAttempt(
        project_id=evidence.project_id,
        storyboard_id=evidence.storyboard_id,
        video_task_id=evidence.video_task_id,
        shot_id=evidence.shot_id,
        adopted_asset_id=evidence.adopted_asset_id,
        stage=evidence.stage,
        status=evidence.status,
        provider=(evidence.provider or "")[:120],
        model=(evidence.model or "")[:120],
        prompt_contract_id=(evidence.prompt_contract_id or "")[:120],
        prompt_version=(evidence.prompt_version or "")[:120],
        rendered_prompt=(evidence.rendered_prompt or "")[:MAX_RAW_OUTPUT_CHARS],
        raw_output=(evidence.raw_output or "")[:MAX_RAW_OUTPUT_CHARS],
        parsed_output=json.dumps(_redact(evidence.parsed_output or {}), ensure_ascii=False),
        validation_results=json.dumps(_redact(evidence.validation_results or {}), ensure_ascii=False),
        parameters=json.dumps(_redact(evidence.parameters or {}), ensure_ascii=False),
        usage=json.dumps(_redact(evidence.usage or {}), ensure_ascii=False),
        input_asset_versions=json.dumps(_redact(evidence.input_asset_versions or {}), ensure_ascii=False),
        cost_estimate_usd=evidence.cost_estimate_usd,
        quality_outcome=(evidence.quality_outcome or "")[:40],
        provider_ref=(evidence.provider_ref or "")[:200],
        error_category=(evidence.error_category or "")[:60],
        error_message=(evidence.error_message or "")[:MAX_RAW_OUTPUT_CHARS],
    )
    db.add(row)
    db.flush()
    return row
