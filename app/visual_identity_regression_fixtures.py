"""Regression fixtures for character-identity visual checks.

Each fixture names a mandatory scenario that the shadow-mode visual gate must
classify correctly once a real vision adapter is configured. Tests drive
VisualCheckService with these reports so the classification contract cannot
silently regress. Categories: visual_medium_mismatch, identity_drift,
identity_swap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .visual_check_service import VisionCharacterReport, VisionReport

FIXTURE_CATEGORIES = (
    "visual_medium_mismatch",
    "identity_drift",
    "identity_swap",
)


@dataclass(frozen=True)
class VisualRegressionFixture:
    name: str
    scenario: str
    expected_medium: str
    report: VisionReport
    expected_findings: tuple[str, ...]
    shot_character_names: tuple[str, ...] = ()


VISUAL_REGRESSION_FIXTURES: tuple[VisualRegressionFixture, ...] = (
    VisualRegressionFixture(
        name="anime_to_live_action_drift",
        scenario="要求 2D 动画的项目生成了实拍风首帧。",
        expected_medium="2D动画",
        report=VisionReport(medium="live_action", characters=()),
        expected_findings=("visual_medium_mismatch",),
    ),
    VisualRegressionFixture(
        name="costume_change",
        scenario="角色服装被替换，但脸型/发型仍匹配规范身份。",
        expected_medium="日系动画",
        report=VisionReport(
            medium="2d_anime",
            characters=(VisionCharacterReport(character_name="阿离", matches_canonical=False),),
        ),
        expected_findings=("identity_drift",),
        shot_character_names=("阿离",),
    ),
    VisualRegressionFixture(
        name="lighting_change",
        scenario="光源/色调大幅偏离规范三视图但身份可辨认。",
        expected_medium="日系动画",
        report=VisionReport(
            medium="2d_anime",
            characters=(VisionCharacterReport(character_name="阿离", matches_canonical=True),),
        ),
        expected_findings=(),
        shot_character_names=("阿离",),
    ),
    VisualRegressionFixture(
        name="profile_view",
        scenario="侧脸视角，身份仍匹配规范三视图。",
        expected_medium="日系动画",
        report=VisionReport(
            medium="2d_anime",
            characters=(VisionCharacterReport(character_name="阿离", matches_canonical=True),),
        ),
        expected_findings=(),
        shot_character_names=("阿离",),
    ),
    VisualRegressionFixture(
        name="occlusion",
        scenario="前景遮挡导致角色局部不可见，但可辨认身份。",
        expected_medium="日系动画",
        report=VisionReport(
            medium="2d_anime",
            characters=(VisionCharacterReport(character_name="阿离", matches_canonical=True),),
        ),
        expected_findings=(),
        shot_character_names=("阿离",),
    ),
    VisualRegressionFixture(
        name="two_character_identity_swap",
        scenario="两个角色的标志性特征互换。",
        expected_medium="日系动画",
        report=VisionReport(
            medium="2d_anime",
            characters=(
                VisionCharacterReport(character_name="阿离", swapped_with="青禾"),
                VisionCharacterReport(character_name="青禾", swapped_with="阿离"),
            ),
        ),
        expected_findings=("identity_swap",),
        shot_character_names=("阿离", "青禾"),
    ),
)
