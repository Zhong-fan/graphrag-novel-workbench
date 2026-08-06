"""Shadow-mode visual checks for character-bearing first frames.

A real vision adapter is not required: when no vision reporter is configured,
checks return checked=False with reason "visual_check_not_configured" and the
frame proceeds unverified. When a normalized VisionReport is available, the
service enforces the continuity contract deterministically (medium mismatch,
identity drift, identity swap) and records findings without silently passing.

The vision reporter boundary is deliberate: image understanding (classifying
medium, comparing appearances) belongs to the adapter; the service only
translates its report into blocking/advisory findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .character_identity_service import CharacterIdentityService
from .config import Settings
from .models import CharacterCard, MediaAsset, Project, StoryboardShot

VISUAL_MEDIUM_MISMATCH = "visual_medium_mismatch"
IDENTITY_DRIFT = "identity_drift"
IDENTITY_SWAP = "identity_swap"


@dataclass(frozen=True)
class VisionCharacterReport:
    character_name: str
    matches_canonical: bool = True
    swapped_with: str = ""


@dataclass(frozen=True)
class VisionReport:
    medium: str = ""
    characters: tuple[VisionCharacterReport, ...] = ()


@dataclass(frozen=True)
class VisualFinding:
    category: str
    severity: str  # blocking | advisory
    shot_id: int | None
    detail: str


@dataclass(frozen=True)
class VisualCheckResult:
    checked: bool
    blocked: bool
    findings: tuple[VisualFinding, ...] = ()
    reason: str = ""


def medium_mismatch(expected_medium: str, actual_medium: str) -> bool:
    """判断预期媒介与实际媒介是否冲突；未知媒介不误报。"""
    expected = expected_medium.strip().lower()
    actual = actual_medium.strip().lower()
    if not expected or not actual:
        return False
    anime_expected = any(key in expected for key in ("动画", "anime", "2d", "卡通"))
    live_expected = any(key in expected for key in ("实拍", "live", "真人"))
    if anime_expected:
        return any(key in actual for key in ("live_action", "3d", "实拍", "真人"))
    if live_expected:
        return any(key in actual for key in ("2d", "anime", "动画"))
    return False


class VisualCheckService:
    def __init__(self, settings: Settings, *, vision_reporter: Callable[[MediaAsset], VisionReport] | None = None) -> None:
        self.settings = settings
        self._vision_reporter = vision_reporter

    def check_first_frame(
        self,
        *,
        db: Session,
        project: Project,
        shot: StoryboardShot,
        first_frame_asset: MediaAsset,
    ) -> VisualCheckResult:
        # 影子模式：没有配置视觉适配器时，首帧按未验证放行，不阻塞生产流程。
        if self._vision_reporter is None:
            return VisualCheckResult(checked=False, blocked=False, reason="visual_check_not_configured")
        report = self._vision_reporter(first_frame_asset)
        findings: list[VisualFinding] = []
        if medium_mismatch(project.visual_style_medium, report.medium):
            findings.append(
                VisualFinding(
                    category=VISUAL_MEDIUM_MISMATCH,
                    severity="blocking",
                    shot_id=shot.id,
                    detail=f"项目要求媒介 {project.visual_style_medium}，首帧被判定为 {report.medium}。",
                )
            )
        bound_ids = {
            item.get("character_card_id")
            for item in CharacterIdentityService(self.settings).shot_identity_bindings(shot=shot)
            if isinstance(item, dict) and item.get("character_card_id") is not None
        }
        name_by_id: dict[int, str] = {}
        if bound_ids:
            for card in db.scalars(select(CharacterCard).where(CharacterCard.id.in_(bound_ids))).all():
                name_by_id[card.id] = card.name
        bound_names = {name_by_id.get(character_id) for character_id in bound_ids}
        for char in report.characters:
            if char.swapped_with:
                findings.append(
                    VisualFinding(
                        category=IDENTITY_SWAP,
                        severity="blocking",
                        shot_id=shot.id,
                        detail=f"角色 {char.character_name} 与 {char.swapped_with} 的特征互换，不能自动采纳。",
                    )
                )
            elif char.character_name in bound_names and not char.matches_canonical:
                findings.append(
                    VisualFinding(
                        category=IDENTITY_DRIFT,
                        severity="blocking",
                        shot_id=shot.id,
                        detail=f"角色 {char.character_name} 偏离规范身份，不能自动采纳。",
                    )
                )
        blocked = any(finding.severity == "blocking" for finding in findings)
        return VisualCheckResult(
            checked=True,
            blocked=blocked,
            findings=tuple(findings),
            reason="shadow_check_completed" if blocked else "shadow_check_passed",
        )
