from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import ensure_list, parse_json_object
from .llm import OpenAIResponsesLLM
from .models import Project


class SeriesPlanningService:
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

    def generate_plan(
        self,
        *,
        project: Project,
        target_chapter_count: int,
        user_brief: str,
    ) -> dict[str, Any]:
        memory_lines = "\n".join(
            f"- {item.title}：{item.content}" for item in sorted(project.memories, key=lambda item: item.importance, reverse=True)[:12]
        ) or "- 暂无长期资料。"
        character_lines = "\n".join(
            f"- {item.name} / {item.story_role}：{item.personality} {item.background}"
            for item in project.character_cards
            if item.deleted_at is None
        ) or "- 暂无人物卡。"
        source_lines = "\n".join(f"- {item.title}：{item.content[:700]}" for item in project.source_documents[:6]) or "- 暂无参考资料。"

        system_prompt = dedent(
            """
            你是长篇中文小说规划师。请生成可控写作系统使用的结构化长篇规划。
            参考作品只是可选风格/世界观辅助，不能复刻原作角色、剧情、专有名词，也不能作为硬前置。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
项目标题：{project.title}
类型：{project.genre}
目标章节数：{target_chapter_count}

参考作品：
{project.reference_work or "无"}

世界设定：
{project.world_brief or "暂无"}

写作规则：
{project.writing_rules or "暂无"}

人物卡：
{character_lines}

长期资料：
{memory_lines}

参考资料：
{source_lines}

用户额外要求：
{user_brief or "无"}

请按三层规划输出 JSON：
{{
  "series": {{
    "title": "...",
    "target_chapter_count": 12,
    "theme": "...",
    "main_conflict": "...",
    "main_goal": "...",
    "character_arcs": ["..."],
    "foreshadowing_plan": ["..."],
    "ending_direction": "..."
  }},
  "arcs": [
    {{
      "arc_no": 1,
      "start_chapter_no": 1,
      "end_chapter_no": 5,
      "title": "...",
      "goal": "...",
      "conflict": "...",
      "turning_points": ["..."],
      "ending_state": "..."
    }}
  ],
  "chapters": [
    {{
      "chapter_no": 1,
      "title": "...",
      "chapter_goal": "...",
      "conflict": "...",
      "emotion_tone": "...",
      "must_happen": ["..."],
      "must_not_happen": ["..."],
      "character_progress": ["..."],
      "ending_hook": "...",
      "estimated_length": "2500-3500字"
    }}
  ],
  "change_note": "初版规划说明"
}}

约束：
- chapters 数量必须等于目标章节数。
- Arc 建议每 5 到 10 章一段，覆盖所有章节且不重叠。
- 每章概要必须能直接驱动正文生成，避免空泛。
""".strip()
        response = self.llm.generate(model=self.settings.writer_model, system_prompt=system_prompt, user_prompt=prompt)
        payload = parse_json_object(response.text)
        self._validate_payload(payload, target_chapter_count=target_chapter_count)
        return payload

    def _validate_payload(self, payload: dict[str, Any], *, target_chapter_count: int) -> None:
        series = payload.get("series")
        if not isinstance(series, dict):
            raise RuntimeError("规划模型没有返回 series 对象。")
        arcs = ensure_list(payload.get("arcs"))
        chapters = ensure_list(payload.get("chapters"))
        if not arcs:
            raise RuntimeError("规划模型没有返回阶段概要。")
        if len(chapters) != target_chapter_count:
            raise RuntimeError(f"规划模型返回了 {len(chapters)} 章概要，目标是 {target_chapter_count} 章。")
