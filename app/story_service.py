from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .config import Settings
from .llm import OpenAIResponsesLLM
from .prompts import (
    light_refine_system_prompt,
    light_refine_user_prompt,
    story_generation_system_prompt,
    story_generation_user_prompt,
    style_instructions,
)

logger = logging.getLogger(__name__)


class StoryGenerationService:
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

    def generate(
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
        scene_card: str,
        memories: list[dict[str, str]],
        use_refiner: bool,
        progress: Callable[..., None] | None = None,
        trace: dict | None = None,
    ) -> tuple[str, str, str]:
        memory_lines = "\n".join(
            f"- {item['title']}：{item['content']}" for item in memories[:10]
        ) or "- 暂无额外长期设定。"

        system_prompt = story_generation_system_prompt(style_instructions(style_profile), writing_rules)
        prompt = story_generation_user_prompt(
            project_title=project_title,
            genre=genre,
            premise=premise,
            world_brief=world_brief,
            user_prompt=user_prompt,
            response_type=response_type,
            memory_lines=memory_lines,
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
            model=self.settings.writer_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
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
            model=self.settings.writer_model,
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
