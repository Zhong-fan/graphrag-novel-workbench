from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class CharacterRef(BaseModel):
    character_card_id: int | None = None
    name: str = ""
    role: str = ""


class SceneRef(BaseModel):
    name: str = ""
    role: str = ""


class Continuity(BaseModel):
    shot_type: str = "new"
    depends_on_shot_no: int | None = None
    first_frame_source: str = "generated"
    requires_i2v: bool
    end_frame_usage: str = "none"
    camera_motion: str = "无"
    character_state_delta: str = ""
    continuity_constraints: list[str] = Field(default_factory=list)


class AudioDialogue(BaseModel):
    character_name: str = ""
    line: str = ""
    emotion: str = ""
    voice_profile: str = ""
    start_hint: float | None = None
    duration_hint: float | None = None


class AudioScript(BaseModel):
    dialogues: list[AudioDialogue] = Field(default_factory=list)
    narration: str = ""
    subtitle_text: str = ""
    music_cue: str = ""
    sound_effects: list[str] = Field(default_factory=list)


class StoryboardShotModel(BaseModel):
    shot_no: int
    narration_text: str = ""
    visual_prompt: str
    character_refs: list[CharacterRef] = Field(default_factory=list)
    scene_refs: list[SceneRef] = Field(default_factory=list)
    continuity: Continuity = Field(default_factory=Continuity)
    audio_script: AudioScript = Field(default_factory=AudioScript)
    duration_seconds: float | None = None


class StoryboardPayloadModel(BaseModel):
    title: str = ""
    summary: str = ""
    shots: list[StoryboardShotModel] = Field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    @property
    def error_text(self) -> str:
        return "；".join(self.errors)


def _format_validation_error(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors():
        loc = ""
        for part in item.get("loc", ()):
            if isinstance(part, int):
                loc += f"[{part}]"
            else:
                loc += f".{part}" if loc else str(part)
        message = str(item.get("msg") or item.get("type") or "invalid")
        errors.append(f"{loc}: {message}" if loc else message)
    return errors


def validate_storyboard_payload(payload: Any) -> ValidationResult:
    """确定性结构校验：先于任何语义/模型检查运行，失败时给出可修复的错误路径。"""
    if not isinstance(payload, dict):
        return ValidationResult(ok=False, errors=["分镜输出必须是 JSON 对象"])
    try:
        parsed = StoryboardPayloadModel.model_validate(payload)
    except ValidationError as exc:
        return ValidationResult(ok=False, errors=_format_validation_error(exc))
    errors: list[str] = []
    if not str(parsed.title or "").strip():
        errors.append("title: 不能为空")
    if not str(parsed.summary or "").strip():
        errors.append("summary: 不能为空")
    if not parsed.shots:
        errors.append("shots: 不能为空")
    for index, shot in enumerate(parsed.shots):
        prefix = f"shots[{index}]"
        if shot.shot_no <= 0:
            errors.append(f"{prefix}.shot_no: 必须为正整数")
        if not str(shot.visual_prompt or "").strip():
            errors.append(f"{prefix}.visual_prompt: 不能为空")
    return ValidationResult(ok=not errors, errors=errors)