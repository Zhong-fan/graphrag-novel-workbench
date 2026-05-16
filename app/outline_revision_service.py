from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import parse_json_object
from .llm import OpenAIResponsesLLM


class OutlineRevisionService:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.llm = OpenAIResponsesLLM(
            settings.openai_api_key,
            settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=settings.llm_stream_responses,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )

    def revise_plan(
        self,
        *,
        current_plan: dict[str, Any],
        feedback_text: str,
        target_type: str,
    ) -> dict[str, Any]:
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
""".strip()
        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        if not isinstance(payload.get("revision_plan"), dict) or not isinstance(payload.get("revised_plan"), dict):
            raise RuntimeError("修订模型没有返回 revision_plan 和 revised_plan。")
        return payload
