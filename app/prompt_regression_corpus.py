"""Compact prompt regression corpus guarding mandatory generation cases.

Changes to registered prompt builders, validators, or versions must keep every
mandatory case green; the guard test in tests/test_prompt_regression_corpus.py
fails the build otherwise. Corpus inputs use plain namespace objects so the
corpus stays readable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class PromptRegressionCase:
    prompt_id: str
    version: str
    title: str
    build_kwargs: dict[str, Any]
    golden_payload: dict[str, Any]
    mandatory_prompt_markers: tuple[str, ...] = ()


def _project(*, title: str = "测试项目", genre: str = "古风") -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        genre=genre,
        visual_style_locked=True,
        visual_style_medium="日系动画",
        visual_style_artists=["新海诚"],
        visual_style_positive=["高饱和天空"],
        visual_style_negative=["实拍感"],
        visual_style_notes="",
        reference_work="",
        reference_work_creator="",
        reference_work_medium="",
        reference_work_synopsis="",
        reference_work_style_traits_json="[]",
        reference_work_world_traits_json="[]",
        reference_work_narrative_constraints_json="[]",
        reference_work_confidence_note="",
        reference_inheritance_mode="style_only",
        reference_rewrite_start="",
        reference_authorized_changes="",
        story_boundary_text="",
        story_boundary_rules_json="[]",
        world_brief="架空世界，雨夜都市。",
        character_cards=[
            SimpleNamespace(id=1, name="阿离", story_role="女主", deleted_at=None),
            SimpleNamespace(id=2, name="青禾", story_role="男主", deleted_at=None),
        ],
    )


def _chapter() -> SimpleNamespace:
    return SimpleNamespace(chapter_no=1, title="第一章", summary="雨夜重逢。", content=("雨夜，街口。" * 40))


def _shot(*, shot_no: int, prompt: str, requires_i2v: bool = True, character: bool = True) -> dict[str, Any]:
    shot: dict[str, Any] = {
        "shot_no": shot_no,
        "visual_prompt": prompt,
        "scene_refs": [{"name": "街口", "role": "开场"}],
        "continuity": {
            "shot_type": "new" if requires_i2v else "transition",
            "requires_i2v": requires_i2v,
            "first_frame_source": "generated" if requires_i2v else "previous_last_frame",
            "depends_on_shot_no": None,
        },
        "audio_script": {"dialogues": [], "narration": "", "subtitle_text": "", "music_cue": "", "sound_effects": []},
        "duration_seconds": 4,
    }
    if character:
        shot["character_refs"] = [{"character_card_id": 1, "name": "阿离", "role": "女主"}]
    return shot


PROMPT_REGRESSION_CORPUS: tuple[PromptRegressionCase, ...] = (
    PromptRegressionCase(
        prompt_id="storyboard.shots.v1",
        version="v1",
        title="小说章节转分镜：多角色场景与连续性",
        build_kwargs={
            "project": _project(),
            "chapters": [_chapter()],
            "title": "短片A",
            "context_pack_inputs": None,
        },
        golden_payload={
            "title": "短片A",
            "summary": "雨夜街口，男女主重逢。",
            "shots": [
                _shot(shot_no=1, prompt="日系动画电影，雨夜街口，蓝绿色光束，女主撑伞回头。", requires_i2v=True),
                _shot(shot_no=2, prompt="日系动画电影，雨夜街口，前景男主背影，女主特写。", requires_i2v=True),
            ],
        },
        mandatory_prompt_markers=(
            "shots",
            "visual_prompt",
            "character_refs",
            "continuity",
            "requires_i2v",
        ),
    ),
    PromptRegressionCase(
        prompt_id="storyboard.image_first.v1",
        version="v1",
        title="图片先行分镜：参考视频与参考图说明",
        build_kwargs={
            "project": _project(),
            "title": "短片B",
            "reference_video_brief": "两人在雨夜街口错肩而过。",
            "reference_image_notes": ["参考图1：雨夜蓝绿色街灯"],
            "context_pack_inputs": None,
        },
        golden_payload={
            "title": "短片B",
            "summary": "图片先行，雨夜街口错肩。",
            "shots": [
                _shot(shot_no=1, prompt="日系动画电影，雨夜街口，蓝绿色光束，男女主错肩。", requires_i2v=True),
            ],
        },
        mandatory_prompt_markers=(
            "图生视频",
            "用户目标片段",
            "requires_i2v",
        ),
    ),
)
