from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .capabilities import AdapterError, AdapterErrorCategory, VoiceDesignRequest
from .models import CharacterCard, Project, VoiceDesign
from .voice_capability import VoiceDesignCapability, build_voice_design_capability

PENDING = "pending_approval"
APPROVED = "approved"
REJECTED = "rejected"

_STATUS_LABELS = {
    PENDING: "待审批",
    APPROVED: "已审批",
    REJECTED: "已拒绝",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VoiceDesignService:
    """Approval-gated voice design workflow.

    Voice design produces a candidate reference that stays ``pending_approval``
    until the creator approves it. Speech synthesis is a separate capability
    and must not run for a designed voice that is not approved; preset
    speakers on character cards remain usable without a design record.
    """

    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self._capability: VoiceDesignCapability | None = None

    def _design_capability(self) -> VoiceDesignCapability:
        if self._capability is None:
            self._capability = build_voice_design_capability(self.settings)
        return self._capability

    def submit_preset_design(
        self,
        *,
        db: Session,
        project: Project,
        character: CharacterCard,
        preset_speaker: str,
        description: str = "",
    ) -> VoiceDesign:
        """Create a pending design, bind it to the character, and gate synthesis on approval.

        Binding is part of submission so a designed voice can never be used
        implicitly: until the creator approves the new design, synthesis for
        this character is blocked with an actionable message.
        """
        if not (preset_speaker or "").strip():
            raise AdapterError(
                AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                safe_message="预设音色设计需要 preset_speaker。",
            )
        request = VoiceDesignRequest(
            character_name=character.name,
            preset_speaker=preset_speaker.strip(),
            description=description.strip(),
        )
        result = self._design_capability().design(request)
        design = VoiceDesign(
            project_id=project.id,
            character_card_id=character.id,
            provider=result.provider,
            model=result.model,
            voice_ref=result.voice_ref,
            status=PENDING,
        )
        db.add(design)
        db.flush()
        character.voice_design_id = design.id
        db.flush()
        return design

    def approve_design(self, *, db: Session, design_id: int) -> VoiceDesign:
        design = self._get(db, design_id)
        if design.status == REJECTED:
            raise RuntimeError(
                f"音色设计 {design_id} 已拒绝，无法审批；请先提交新的设计。"
            )
        design.status = APPROVED
        design.reason = ""
        design.approved_at = _utcnow()
        design.rejected_at = None
        db.flush()
        return design

    def reject_design(self, *, db: Session, design_id: int, reason: str = "") -> VoiceDesign:
        design = self._get(db, design_id)
        design.status = REJECTED
        design.reason = (reason or "").strip()
        design.rejected_at = _utcnow()
        db.flush()
        return design

    def approved_voice_ref(self, *, db: Session, character: CharacterCard) -> str | None:
        """Return the approved voice reference for a character.

        Returns ``None`` when the character has no design binding (preset
        speakers stay usable). Raises an actionable error when the bound
        design is missing, pending, or rejected so synthesis can never
        silently use an unapproved voice.
        """
        design_id = getattr(character, "voice_design_id", None)
        if design_id is None:
            return None
        design = db.get(VoiceDesign, design_id)
        if design is None:
            raise RuntimeError(
                f"角色 {character.id} 绑定的音色设计 {design_id} 已不存在；请重新提交设计。"
            )
        if design.character_card_id != character.id:
            raise RuntimeError(
                f"角色 {character.id} 绑定的音色设计 {design_id} 属于其他角色；请重新提交设计。"
            )
        if design.status != APPROVED:
            raise RuntimeError(
                f"角色 {character.id} 的音色设计 {design_id} 状态为{_STATUS_LABELS.get(design.status, design.status)}；"
                "审批通过前禁止语音合成。"
            )
        return design.voice_ref

    def _get(self, db: Session, design_id: int) -> VoiceDesign:
        design = db.get(VoiceDesign, design_id)
        if design is None:
            raise LookupError(f"音色设计 {design_id} 不存在。")
        return design
