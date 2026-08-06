from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import parse_json_object
from .llm import OpenAICompatibleTextLLM
from .capabilities import CapabilityRole
from .text_capability import text_model_for_role
from .story_boundary_service import StoryBoundaryService


class OutlineRevisionService:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.llm = OpenAICompatibleTextLLM(
            settings.openai_api_key,
            settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=settings.llm_stream_responses,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )
        self.story_boundary_service = StoryBoundaryService()

    def revise_plan(
        self,
        *,
        current_plan: dict[str, Any],
        feedback_text: str,
        target_type: str,
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        character_snapshot = context_pack_inputs.get("character_snapshot", []) if isinstance(context_pack_inputs, dict) else []
        hard_constraints = context_pack_inputs.get("hard_constraints", []) if isinstance(context_pack_inputs, dict) else []
        story_boundary_rules = context_pack_inputs.get("story_boundary_rules", []) if isinstance(context_pack_inputs, dict) else []
        user_decisions = (
            context_pack_inputs.get("story_feed", {}).get("user_decisions")
            if isinstance(context_pack_inputs, dict) and isinstance(context_pack_inputs.get("story_feed"), dict)
            else {}
        )
        system_prompt = dedent(
            """
            你是长篇小说概要反馈解析与修订助手。
            先把用户意见转成结构化修订计划，再给出应用后的新概要。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
反馈目标层级：{target_type}

当前概要 JSON：
{current_plan}

用户反馈：
{feedback_text}

当前已确认人物：
{character_snapshot}

当前硬约束：
{hard_constraints}

故事边界硬约束：
{chr(10).join(f"- {item}" for item in self.story_boundary_service.prompt_lines(story_boundary_rules)) or "- 无"}

当前用户已确认选择：
{user_decisions}

请输出：
{{
  "revision_plan": {{
    "target_type": "series|arc|chapter",
    "affected_chapters": [1, 2],
    "relationship_lines": ["..."],
    "pace_changes": ["..."],
    "must_add": ["..."],
    "must_remove": ["..."],
    "risk_notes": ["..."]
  }},
  "revised_plan": {{
    "series": {{...}},
    "arcs": [...],
    "chapters": [...]
  }},
  "change_note": "简短说明这次改了什么",
  "feedback_covered": true
}}

要求：
- 保留未受反馈影响的稳定设定。
- 不要把反馈原样塞进正文提示，要体现在概要结构里。
- revised_plan 必须仍包含 series、arcs、chapters 三层。
- 已确认人物姓名、身份、关系和用户已选择的版本方向不得漂移。
- 已确认故事边界硬约束不得被反馈静默移除或违反。
""".strip()
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        if not isinstance(payload.get("revision_plan"), dict) or not isinstance(payload.get("revised_plan"), dict):
            raise RuntimeError("修订模型没有返回 revision_plan 和 revised_plan。")
        return payload
