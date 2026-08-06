from __future__ import annotations

import json
import logging
from textwrap import dedent
from typing import Any, Callable

from .config import Settings
from .llm import OpenAICompatibleTextLLM
from .capabilities import CapabilityRole
from .text_capability import text_model_for_role
from .prompts import (
    light_refine_system_prompt,
    light_refine_user_prompt,
    story_generation_system_prompt,
    story_generation_user_prompt,
    style_instructions,
)
from .reference_policy_service import ReferencePolicyService
from .story_boundary_service import StoryBoundaryService
from .violation_check_service import ViolationCheckService

logger = logging.getLogger(__name__)


class StoryGenerationService:
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

    def generate(
        self,
        *,
        project_title: str,
        genre: str,
        reference_work: str,
        reference_work_synopsis: str = "",
        reference_work_style_traits: list[str] | None = None,
        reference_work_world_traits: list[str] | None = None,
        reference_work_narrative_constraints: list[str] | None = None,
        premise: str,
        world_brief: str,
        writing_rules: str,
        style_profile: str,
        user_prompt: str,
        response_type: str,
        scene_card: str,
        memories: list[dict[str, str]],
        use_refiner: bool,
        context_pack_inputs: dict[str, Any] | None = None,
        progress: Callable[..., None] | None = None,
        trace: dict | None = None,
    ) -> tuple[str, str, str]:
        story_feed = context_pack_inputs.get("story_feed", {}) if isinstance(context_pack_inputs, dict) else {}
        project_core = story_feed.get("project_core", {}) if isinstance(story_feed, dict) else {}
        character_constraints = story_feed.get("character_constraints", []) if isinstance(story_feed, dict) else []
        reference_constraints = story_feed.get("reference_constraints", {}) if isinstance(story_feed, dict) else {}
        user_decisions = story_feed.get("user_decisions", {}) if isinstance(story_feed, dict) else {}
        hard_constraints = story_feed.get("hard_constraints", []) if isinstance(story_feed, dict) else []
        active_story_boundary_rules = (
            context_pack_inputs.get("active_story_boundary_rules", [])
            if isinstance(context_pack_inputs, dict)
            else []
        )
        memory_source = story_feed.get("supporting_memories") if isinstance(story_feed, dict) else None
        memory_lines = "\n".join(
            f"- {item.get('title', '')}：{item.get('content', '')}" for item in (memory_source or [])[:10] if isinstance(item, dict)
        ) or "\n".join(
            f"- {item['title']}：{item['content']}" for item in memories[:10]
        ) or "- 暂无额外长期设定。"
        reference_guidance = self._reference_guidance(
            reference_work=str(reference_constraints.get("reference_work") or reference_work),
            reference_work_synopsis=str(reference_constraints.get("synopsis") or reference_work_synopsis),
            reference_work_style_traits=list(reference_constraints.get("style_traits") or reference_work_style_traits or []),
            reference_work_world_traits=list(reference_constraints.get("world_traits") or reference_work_world_traits or []),
            reference_work_narrative_constraints=list(reference_constraints.get("narrative_constraints") or reference_work_narrative_constraints or []),
        )

        system_prompt = story_generation_system_prompt(style_instructions(style_profile), writing_rules)
        prompt = story_generation_user_prompt(
            project_title=str(project_core.get("title") or project_title),
            genre=str(project_core.get("genre") or genre),
            reference_work=str(reference_constraints.get("reference_work") or reference_work),
            premise=premise,
            world_brief=str(project_core.get("world_brief") or world_brief),
            user_prompt="\n".join(
                [
                    user_prompt,
                    "",
                    "已确认人物约束：",
                    *[
                        f"- {item.get('name', '')} / {item.get('story_role', '')} / {item.get('gender', '')} / {item.get('background', '')}"
                        for item in character_constraints[:12]
                        if isinstance(item, dict)
                    ],
                    "",
                    "已确认硬约束：",
                    *[f"- {item}" for item in hard_constraints],
                    "",
                    "参考作品继承策略：",
                    self.reference_policy_service.prompt_block(reference_constraints) or "- 无",
                    "",
                    "当前章节故事边界：",
                    *[f"- {item}" for item in self.story_boundary_service.prompt_lines(active_story_boundary_rules)],
                    "",
                    "用户已确认的版本选择：",
                    *[f"- {key}: {value}" for key, value in user_decisions.items()],
                ]
            ).strip(),
            response_type=response_type,
            memory_lines=memory_lines,
            reference_guidance=reference_guidance,
            scene_card=scene_card,
        )

        if progress:
            progress(
                "draft",
                f"正在调用写作模型 {self.settings.writer_model} 生成初稿",
                details={"model": self.settings.writer_model, "phase": "draft"},
            )
        logger.info("Draft base generation started: project=%s response_type=%s", project_title, response_type)
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.CREATIVE_TEXT),
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
            event_callback=self._model_event_callback(progress, "draft"),
        )
        if trace is not None:
            trace["draft"] = {
                "status": "succeeded",
                "model": self.settings.writer_model,
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "raw_output": response.text,
            }
        payload = self._parse_json(response.text)
        title = str(payload.get("title", "")).strip() or "未命名章节"
        summary = str(payload.get("summary", "")).strip() or user_prompt[:80]
        draft_content = str(payload.get("content", "")).strip() or response.text.strip()
        if trace is not None:
            trace["draft"]["parsed"] = {
                "title": title,
                "summary": summary,
                "content": draft_content,
            }
        if progress:
            progress("draft_saved", "初稿已生成，准备保存")
        logger.info("Draft base generation completed: title=%s chars=%s", title, len(draft_content))

        refined_content = draft_content
        if use_refiner:
            try:
                if progress:
                    progress("refine", "正在润色正文")
                logger.info("Draft refinement started: title=%s", title)
                refined_content = self._refine_light_novel_prose(
                    project_title=project_title,
                    genre=genre,
                    style_profile=style_profile,
                    title=title,
                    summary=summary,
                    user_prompt=user_prompt,
                    draft_content=draft_content,
                    trace=trace,
                    progress=progress,
                )
                logger.info("Draft refinement completed: title=%s chars=%s", title, len(refined_content))
            except RuntimeError as exc:
                if trace is not None:
                    trace["refine"] = {
                        "status": "failed",
                        "model": self.settings.writer_model,
                        "error": str(exc),
                    }
                if progress:
                    progress("refine_failed", "润色失败，将保留初稿")
                logger.warning("Draft refinement failed; saving unrefined draft instead: %s", exc)
        elif trace is not None:
            trace["refine"] = {
                "status": "skipped",
                "model": self.settings.writer_model,
                "reason": "disabled",
            }

        refined_content = self._normalize_dialogue(refined_content)
        title, summary, refined_content = self._enforce_user_intent_coverage(
            project_title=project_title,
            genre=genre,
            premise=premise,
            world_brief=world_brief,
            writing_rules=writing_rules,
            style_profile=style_profile,
            user_prompt=user_prompt,
            response_type=response_type,
            memory_lines=memory_lines,
            reference_work=reference_work,
            reference_guidance=reference_guidance,
            scene_card=scene_card,
            title=title,
            summary=summary,
            content=refined_content,
            trace=trace,
            progress=progress,
        )
        title, summary, refined_content = self._enforce_story_boundary_rules(
            project_title=project_title,
            genre=genre,
            premise=premise,
            world_brief=world_brief,
            writing_rules=writing_rules,
            user_prompt=user_prompt,
            scene_card=scene_card,
            title=title,
            summary=summary,
            content=refined_content,
            active_story_boundary_rules=active_story_boundary_rules,
            trace=trace,
            progress=progress,
        )
        return title, summary, refined_content

    def _parse_json(self, text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                stripped = "\n".join(lines[1:-1]).strip()

        decoder = json.JSONDecoder()
        for index, char in enumerate(stripped):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(stripped[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise RuntimeError("写作模型没有返回可解析的 JSON。")

    def _normalize_dialogue(self, text: str) -> str:
        normalized = text.replace("“", "「").replace("”", "」")
        normalized = normalized.replace('"', "「")
        normalized = normalized.replace("『「", "『").replace("』」", "』")
        return normalized

    def _refine_light_novel_prose(
        self,
        *,
        project_title: str,
        genre: str,
        style_profile: str,
        title: str,
        summary: str,
        user_prompt: str,
        draft_content: str,
        trace: dict | None = None,
        progress: Callable[..., None] | None = None,
    ) -> str:
        system_prompt = light_refine_system_prompt(style_profile)
        prompt = light_refine_user_prompt(
            project_title=project_title,
            genre=genre,
            title=title,
            summary=summary,
            user_prompt=user_prompt,
            draft_content=draft_content,
        )

        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.CREATIVE_TEXT),
            system_prompt=system_prompt,
            user_prompt=prompt,
            event_callback=self._model_event_callback(progress, "refine"),
        )
        refined = response.text.strip() or draft_content
        if trace is not None:
            trace["refine"] = {
                "status": "succeeded",
                "model": self.settings.writer_model,
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "raw_output": response.text,
                "output": refined,
            }
        return refined

    def _enforce_user_intent_coverage(
        self,
        *,
        project_title: str,
        genre: str,
        premise: str,
        world_brief: str,
        writing_rules: str,
        style_profile: str,
        user_prompt: str,
        response_type: str,
        memory_lines: str,
        reference_work: str,
        reference_guidance: str,
        scene_card: str,
        title: str,
        summary: str,
        content: str,
        trace: dict | None = None,
        progress: Callable[..., None] | None = None,
    ) -> tuple[str, str, str]:
        system_prompt = (
            "你是中文小说草稿质检与修订助手。"
            "你的任务是检查草稿正文是否真正覆盖了用户要求这一章发生的内容。"
            "如果没有覆盖，就在不偏离项目设定和章节前提的前提下重写为更贴合要求的版本。"
            "输出必须是严格 JSON，字段只包含 title、summary、content、covered、reason。"
        )
        user_prompt_text = f"""
项目：{project_title}
类型：{genre}
章节前提：
{premise}

参考作品：
{reference_work or "无"}

世界设定：
{world_brief or "暂无额外世界设定。"}

项目自定义偏好：
{writing_rules or "保持轻盈、自然、叙事连续，以人物互动推动场景。"}

用户明确希望这一章发生什么：
{user_prompt}

长期设定与资料：
{memory_lines}

参考作品可迁移特征：
{reference_guidance or "无"}

写作上下文卡：
{scene_card}

当前草稿标题：
{title}

当前草稿摘要：
{summary}

当前草稿正文：
{content}

任务：
1. 判断当前草稿是否真正覆盖了用户要求这一章发生的关键内容。
2. 如果已经覆盖，保留并返回等价内容。
3. 如果没有覆盖，就重写标题、摘要、正文，让用户要求的关键推进点在正文里真实发生。

判定标准：
- “覆盖”指正文里实际发生了相关行动、冲突、对话、决定或结果。
- 不能只写成计划、暗示、回忆、旁白说明或未来伏笔。
- 不要为了补覆盖而脱离章节前提或项目资料。

输出格式：
{{
  "title": "...",
  "summary": "...",
  "content": "...",
  "covered": true,
  "reason": "..."
}}
""".strip()

        if progress:
            progress("intent_check", "正在检查草稿是否覆盖本章要求")
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
            system_prompt=system_prompt,
            user_prompt=user_prompt_text,
            json_mode=True,
            event_callback=self._model_event_callback(progress, "intent_check"),
        )
        payload = self._parse_json(response.text)
        next_title = str(payload.get("title", "")).strip() or title
        next_summary = str(payload.get("summary", "")).strip() or summary
        next_content = self._normalize_dialogue(str(payload.get("content", "")).strip() or content)
        covered = bool(payload.get("covered", False))
        reason = str(payload.get("reason", "")).strip()

        if trace is not None:
            trace["intent_check"] = {
                "status": "succeeded",
                "model": self.settings.utility_model,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt_text,
                "raw_output": response.text,
                "parsed": {
                    "title": next_title,
                    "summary": next_summary,
                    "content": next_content,
                    "covered": covered,
                    "reason": reason,
                },
            }

        if progress:
            progress(
                "intent_check_done",
                "本章要求已覆盖" if covered else "已按本章要求补写草稿",
                details={"covered": covered, "reason": reason},
            )
        return next_title, next_summary, next_content

    def _reference_guidance(
        self,
        reference_work: str,
        *,
        reference_work_synopsis: str = "",
        reference_work_style_traits: list[str] | None = None,
        reference_work_world_traits: list[str] | None = None,
        reference_work_narrative_constraints: list[str] | None = None,
    ) -> str:
        if not reference_work.strip():
            return ""
        structured_parts: list[str] = []
        if reference_work_synopsis.strip():
            structured_parts.append(f"- 作品概况：{reference_work_synopsis.strip()}")
        style_traits = [item.strip() for item in (reference_work_style_traits or []) if item and item.strip()]
        if style_traits:
            structured_parts.append(f"- 文风线索：{'；'.join(style_traits[:8])}")
        world_traits = [item.strip() for item in (reference_work_world_traits or []) if item and item.strip()]
        if world_traits:
            structured_parts.append(f"- 世界特征：{'；'.join(world_traits[:8])}")
        constraints = [item.strip() for item in (reference_work_narrative_constraints or []) if item and item.strip()]
        if constraints:
            structured_parts.append(f"- 写作与改编约束：{'；'.join(constraints[:8])}")
        if structured_parts:
            structured_parts.append("- 这些内容用于提炼可迁移约束，不允许直接照搬原作角色、剧情节点、专有名词和关键设定。")
            return "\n".join(structured_parts)
        system_prompt = dedent(
            """
            你是小说参考作品分析助手。
            请把用户给出的参考作品，转换为原创写作时可以借鉴的指导语。
            输出要求：
            - 只输出纯文本
            - 4 到 7 行
            - 每行以 `- ` 开头
            - 包含气质、节奏、世界构成、情绪推进和边界提醒
            - 明确不要直接复刻原作角色、剧情和专有名词
            """
        ).strip()
        user_prompt = f"参考作品：{reference_work}\n请提炼原创写作可迁移指导语。"
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return response.text.strip()

    def _enforce_story_boundary_rules(
        self,
        *,
        project_title: str,
        genre: str,
        premise: str,
        world_brief: str,
        writing_rules: str,
        user_prompt: str,
        scene_card: str,
        title: str,
        summary: str,
        content: str,
        active_story_boundary_rules: list[dict[str, Any]],
        trace: dict | None = None,
        progress: Callable[..., None] | None = None,
    ) -> tuple[str, str, str]:
        if not active_story_boundary_rules:
            return title, summary, content
        violations = self.violation_check_service.check_content(content, active_story_boundary_rules)
        if not violations:
            return title, summary, content

        violation_messages = [str(item.get("message") or "违反故事边界。") for item in violations]
        if progress:
            progress("boundary_violation", "检测到故事边界违规，正在尝试修正", details={"violations": violation_messages})

        system_prompt = (
            "你是中文小说硬约束修订助手。"
            "你的任务是在不偏离章节前提和已有写作目标的前提下，修正正文中违反故事边界硬约束的部分。"
            "输出必须是严格 JSON，字段只包含 title、summary、content、fixed、reason。"
        )
        user_prompt_text = f"""
项目：{project_title}
类型：{genre}
章节前提：
{premise}

世界设定：
{world_brief or "暂无额外世界设定。"}

项目自定义偏好：
{writing_rules or "保持轻盈、自然、叙事连续，以人物互动推动场景。"}

本章目标：
{user_prompt}

写作上下文卡：
{scene_card}

当前生效的故事边界硬约束：
{chr(10).join(f"- {item}" for item in self.story_boundary_service.prompt_lines(active_story_boundary_rules))}

检测到的违规：
{chr(10).join(f"- {item}" for item in violation_messages)}

当前标题：
{title}

当前摘要：
{summary}

当前正文：
{content}

任务：
1. 修掉违反故事边界硬约束的内容。
2. 不要把违规事件改写成含糊擦边的“几乎发生了”。
3. 保留章节目标、情绪和推进方向。

输出格式：
{{
  "title": "...",
  "summary": "...",
  "content": "...",
  "fixed": true,
  "reason": "..."
}}
""".strip()
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
            system_prompt=system_prompt,
            user_prompt=user_prompt_text,
            json_mode=True,
            event_callback=self._model_event_callback(progress, "boundary_repair"),
        )
        payload = self._parse_json(response.text)
        next_title = str(payload.get("title", "")).strip() or title
        next_summary = str(payload.get("summary", "")).strip() or summary
        next_content = self._normalize_dialogue(str(payload.get("content", "")).strip() or content)
        next_violations = self.violation_check_service.check_content(next_content, active_story_boundary_rules)
        if trace is not None:
            trace["boundary_repair"] = {
                "status": "succeeded" if not next_violations else "failed",
                "model": self.settings.utility_model,
                "violations_before": violation_messages,
                "violations_after": next_violations,
                "raw_output": response.text,
            }
        if next_violations:
            messages = "；".join(str(item.get("message") or "违反故事边界。") for item in next_violations)
            raise RuntimeError(f"草稿违反故事边界且修正失败：{messages}")
        if progress:
            progress("boundary_repair_done", "故事边界违规已修正", details={"violations": violation_messages})
        return next_title, next_summary, next_content

    def _model_event_callback(
        self,
        progress: Callable[..., None] | None,
        phase: str,
    ) -> Callable[[dict[str, Any]], None] | None:
        if progress is None:
            return None

        def emit(event: dict[str, Any]) -> None:
            endpoint = event.get("endpoint") or "unknown"
            attempt = event.get("attempt")
            message = str(event.get("message") or "模型调用事件")
            if attempt:
                message = f"{message}：{endpoint} / 第 {attempt} 次"
            progress(
                f"{phase}_model",
                message,
                level=str(event.get("level") or "info"),
                details={"phase": phase, **event},
            )

        return emit
