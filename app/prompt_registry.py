from __future__ import annotations

import json
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Callable

from .prompt_builders import build_image_first_storyboard_prompt, build_storyboard_shots_prompt
from .prompt_validation import ValidationResult, validate_storyboard_payload

PromptBuilder = Callable[..., tuple[str, str]]
PromptValidator = Callable[[dict[str, Any]], ValidationResult]


@dataclass(frozen=True)
class PromptContract:
    """已注册提示词契约：标识、版本、角色、输出契约、构建器、校验器与修复指引。"""

    prompt_id: str
    version: str
    role: str
    model_contract: str
    builder: PromptBuilder
    validator: PromptValidator
    repair_instruction: str


PROMPT_REGISTRY: dict[str, PromptContract] = {}


def register_prompt(contract: PromptContract) -> PromptContract:
    if contract.prompt_id in PROMPT_REGISTRY:
        raise RuntimeError(f"提示词契约重复注册：{contract.prompt_id}")
    PROMPT_REGISTRY[contract.prompt_id] = contract
    return contract


def get_prompt_contract(prompt_id: str) -> PromptContract:
    try:
        return PROMPT_REGISTRY[prompt_id]
    except KeyError as exc:
        raise RuntimeError(f"未注册的提示词契约：{prompt_id}") from exc


STORYBOARD_SHOTS_CONTRACT = register_prompt(
    PromptContract(
        prompt_id="storyboard.shots.v1",
        version="v1",
        role="storyboard_director",
        model_contract="strict-json-object",
        builder=build_storyboard_shots_prompt,
        validator=validate_storyboard_payload,
        repair_instruction=(
            "只修复结构错误和缺失/空白的必填字段（title、summary、shots、shot_no、visual_prompt、"
            "continuity.requires_i2v），保持镜头数量、顺序和所有创意内容不变。"
        ),
    )
)

STORYBOARD_IMAGE_FIRST_CONTRACT = register_prompt(
    PromptContract(
        prompt_id="storyboard.image_first.v1",
        version="v1",
        role="image_first_storyboard_director",
        model_contract="strict-json-object",
        builder=build_image_first_storyboard_prompt,
        validator=validate_storyboard_payload,
        repair_instruction=(
            "只修复结构错误和缺失/空白的必填字段（title、summary、shots、shot_no、visual_prompt、"
            "continuity.requires_i2v），并确保每个镜头的 continuity.requires_i2v 为 true；"
            "保持镜头数量、顺序和所有创意内容不变。"
        ),
    )
)


def build_repair_prompt(
    *,
    contract: PromptContract,
    payload: dict[str, Any],
    result: ValidationResult,
) -> tuple[str, str]:
    """按契约修复指引构造单次定向修复提示词。"""
    system_prompt = (
        "你是严格的分镜 JSON 修复器。只修复结构或必填字段问题，不要改动镜头创意内容，"
        "保持镜头数量和顺序，只输出修复后的完整 JSON。"
    )
    prompt = dedent(
        f"""
        上一次生成的分镜 JSON 未通过校验，错误如下：
        {result.error_text}

        修复要求：{contract.repair_instruction}

        原始 JSON（可能包含格式问题，请以结构为准重新整理）：
        {json.dumps(payload, ensure_ascii=False)}
        """
    ).strip()
    return system_prompt, prompt