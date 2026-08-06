from __future__ import annotations

from textwrap import dedent
from typing import Any

from .config import Settings
from .json_utils import ensure_list, parse_json_object
from .llm import OpenAICompatibleTextLLM
from .capabilities import CapabilityRole
from .text_capability import text_model_for_role
from .models import Project
from .reference_policy_service import ReferencePolicyService
from .story_boundary_service import StoryBoundaryService
from .violation_check_service import ViolationCheckService


class SeriesPlanningService:
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
        self.reference_policy_service = ReferencePolicyService()
        self.story_boundary_service = StoryBoundaryService()
        self.violation_check_service = ViolationCheckService()

    def generate_plan(
        self,
        *,
        project: Project,
        target_chapter_count: int,
        user_brief: str,
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        story_feed = context_pack_inputs.get("story_feed", {}) if isinstance(context_pack_inputs, dict) else {}
        character_snapshot = context_pack_inputs.get("character_snapshot", []) if isinstance(context_pack_inputs, dict) else []
        project_snapshot = context_pack_inputs.get("project_snapshot", {}) if isinstance(context_pack_inputs, dict) else {}
        reference_snapshot = context_pack_inputs.get("reference_snapshot", {}) if isinstance(context_pack_inputs, dict) else {}
        hard_constraints = context_pack_inputs.get("hard_constraints", []) if isinstance(context_pack_inputs, dict) else []
        story_boundary_rules = context_pack_inputs.get("story_boundary_rules", []) if isinstance(context_pack_inputs, dict) else []

        memory_items = story_feed.get("supporting_memories") if isinstance(story_feed, dict) else None
        source_items = story_feed.get("supporting_sources") if isinstance(story_feed, dict) else None
        memory_lines = "\n".join(
            f"- {item.get('title', '')}：{item.get('content', '')}" for item in (memory_items or [])[:12] if isinstance(item, dict)
        ) or "\n".join(
            f"- {item.title}：{item.content}" for item in sorted(project.memories, key=lambda item: item.importance, reverse=True)[:12]
        ) or "- 暂无长期资料。"
        character_lines = "\n".join(
            f"- {item.get('name', '')} / {item.get('story_role', '')}：{item.get('personality', '')} {item.get('background', '')}"
            for item in character_snapshot[:20]
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ) or "\n".join(
            f"- {item.name} / {item.story_role}：{item.personality} {item.background}"
            for item in project.character_cards
            if item.deleted_at is None
        ) or "- 暂无人物卡。"
        source_lines = "\n".join(
            f"- {item.get('title', '')}：{str(item.get('content', ''))[:700]}" for item in (source_items or [])[:6] if isinstance(item, dict)
        ) or "\n".join(f"- {item.title}：{item.content[:700]}" for item in project.source_documents[:6]) or "- 暂无参考资料。"

        system_prompt = dedent(
            """
            你是长篇中文小说规划师。请生成可控写作系统使用的结构化长篇规划。
            参考作品只是可选风格/世界观辅助，不能复刻原作角色、剧情、专有名词，也不能作为硬前置。
            输出必须是严格 JSON，不要输出 Markdown。
            """
        ).strip()
        prompt = f"""
项目标题：{project_snapshot.get("title") or project.title}
类型：{project_snapshot.get("genre") or project.genre}
目标章节数：{target_chapter_count}

参考作品结构化约束：
{self._reference_block(project, reference_snapshot=reference_snapshot)}

世界设定：
{project_snapshot.get("world_brief") or project.world_brief or "暂无"}

写作规则：
{project_snapshot.get("writing_rules") or project.writing_rules or "暂无"}

人物卡：
{character_lines}

故事边界硬约束：
{chr(10).join(f"- {item}" for item in self.story_boundary_service.prompt_lines(story_boundary_rules)) or "- 无"}

参考作品继承策略：
{self.reference_policy_service.prompt_block(reference_snapshot) or "无"}

长期资料：
{memory_lines}

参考资料：
{source_lines}

用户额外要求：
{user_brief or "无"}

必须严格遵守的硬约束：
{chr(10).join(f"- {item}" for item in hard_constraints) or "- 已确认人物姓名、身份和世界规则不得漂移。"}

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
- 如果某章处在故事边界硬约束区间内，`must_not_happen` 必须显式体现对应禁区。
""".strip()
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.CREATIVE_TEXT),
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        payload = parse_json_object(response.text)
        self._validate_payload(payload, target_chapter_count=target_chapter_count)
        self._attach_constraint_snapshots(
            payload,
            story_boundary_rules=story_boundary_rules,
            reference_facts=ensure_list(reference_snapshot.get("reference_facts")),
            authorized_overrides=ensure_list(reference_snapshot.get("authorized_overrides")),
        )
        self._validate_story_boundaries(payload, story_boundary_rules)
        return payload

    def _reference_block(self, project: Project, *, reference_snapshot: dict[str, Any] | None = None) -> str:
        snapshot = reference_snapshot or {}
        reference_work = str(snapshot.get("reference_work") or project.reference_work).strip()
        if not reference_work:
            return "无"
        parts = [
            f"- 作品名：{reference_work}",
            f"- 作品概况：{snapshot.get('synopsis') or project.reference_work_synopsis or '无'}",
            f"- 写作风格线索：{'；'.join(snapshot.get('style_traits') or project.reference_work_style_traits) or '无'}",
            f"- 世界特征：{'；'.join(snapshot.get('world_traits') or project.reference_work_world_traits) or '无'}",
            f"- 写作与改编约束：{'；'.join(snapshot.get('narrative_constraints') or project.reference_work_narrative_constraints) or '无'}",
        ]
        return "\n".join(parts)

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

    def _attach_constraint_snapshots(
        self,
        payload: dict[str, Any],
        *,
        story_boundary_rules: list[dict[str, Any]],
        reference_facts: list[Any] | None = None,
        authorized_overrides: list[Any] | None = None,
    ) -> None:
        for chapter_payload in ensure_list(payload.get("chapters")):
            if not isinstance(chapter_payload, dict):
                continue
            chapter_no = self._coerce_int(chapter_payload.get("chapter_no"))
            if chapter_no is None:
                continue
            active_rules = self.story_boundary_service.active_rules_for_chapter(story_boundary_rules, chapter_no)
            chapter_payload["constraint_snapshot"] = {
                "hard_constraints": active_rules,
                "reference_facts": [item for item in ensure_list(reference_facts) if isinstance(item, dict)],
                "authorized_overrides": [str(item) for item in ensure_list(authorized_overrides) if str(item).strip()],
                "forbidden_events": [
                    item
                    for item in active_rules
                    if item.get("rule_type") == "forbid_event" and str(item.get("predicate") or "").strip()
                ],
            }
            self._merge_forbidden_rules_into_must_not_happen(chapter_payload, active_rules)

    def _merge_forbidden_rules_into_must_not_happen(
        self,
        chapter_payload: dict[str, Any],
        active_rules: list[dict[str, Any]],
    ) -> None:
        must_not_happen = ensure_list(chapter_payload.get("must_not_happen"))
        normalized_existing = {str(item).strip() for item in must_not_happen}
        for rule in active_rules:
            if rule.get("rule_type") != "forbid_event":
                continue
            line = self.story_boundary_service.summary_line(rule)
            if line and line not in normalized_existing:
                must_not_happen.append(line)
                normalized_existing.add(line)
        chapter_payload["must_not_happen"] = must_not_happen

    def _validate_story_boundaries(self, payload: dict[str, Any], story_boundary_rules: list[dict[str, Any]]) -> None:
        if not story_boundary_rules:
            return
        for chapter_payload in ensure_list(payload.get("chapters")):
            if not isinstance(chapter_payload, dict):
                continue
            chapter_no = int(chapter_payload.get("chapter_no") or 0)
            if chapter_no <= 0:
                continue
            active_rules = self.story_boundary_service.active_rules_for_chapter(story_boundary_rules, chapter_no)
            if not active_rules:
                continue
            violations = self.violation_check_service.check_outline(chapter_payload, active_rules)
            if violations:
                details = "；".join(str(item.get("message") or "违反故事边界。") for item in violations)
                raise RuntimeError(f"第 {chapter_no} 章概要违反故事边界：{details}")

    def _coerce_int(self, value: Any) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
