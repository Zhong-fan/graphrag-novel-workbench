from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import parse_json_object
from .llm import OpenAIResponsesLLM
from .models import ChapterOutline, DraftVersion, Project


class DraftRevisionService:
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

    def revise(
        self,
        *,
        project: Project,
        outline: ChapterOutline,
        draft: DraftVersion,
        feedback_text: str,
        outline_payload: dict[str, Any],
    ) -> dict[str, str]:
        system_prompt = dedent(
            """
            你是中文长篇小说章节重写助手。
            根据用户反馈重写整章正文，同时保持项目设定、章节概要和前后连续性。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
项目：{project.title}
类型：{project.genre}

世界设定：
{project.world_brief or "暂无"}

写作规则：
{project.writing_rules or "暂无"}

章节概要：
{outline_payload}

当前章节：第 {outline.chapter_no} 章《{draft.title}》

当前摘要：
{draft.summary}

当前正文：
{draft.content}

用户反馈：
{feedback_text}

任务：
1. 全章重写，优先覆盖用户反馈。
2. 不改变已锁定概要中的核心事实，除非用户反馈明确要求且不破坏连续性。
3. 保持正文可直接作为章节版本保存。

输出格式：
{{
  "title": "...",
  "summary": "...",
  "content": "...",
  "change_note": "这次重写主要调整了什么"
}}
""".strip()
        response = self.llm.generate(
            model=self.settings.writer_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        title = str(payload.get("title") or draft.title).strip()
        summary = str(payload.get("summary") or draft.summary).strip()
        content = str(payload.get("content") or draft.content).strip()
        change_note = str(payload.get("change_note") or feedback_text).strip()
        if not content:
            raise RuntimeError("正文重写模型没有返回 content。")
        return {
            "title": title,
            "summary": summary,
            "content": content,
            "change_note": change_note,
        }
