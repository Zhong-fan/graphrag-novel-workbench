from __future__ import annotations

import json
from textwrap import dedent

from .config import Settings
from .llm import OpenAIResponsesLLM


class StoryGenerationService:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.llm = OpenAIResponsesLLM(settings.openai_api_key, settings.openai_base_url)

    def generate(
        self,
        *,
        project_title: str,
        genre: str,
        premise: str,
        world_brief: str,
        writing_rules: str,
        punctuation_rule: str,
        user_prompt: str,
        local_context: str,
        global_context: str,
        memories: list[dict[str, str]],
    ) -> tuple[str, str, str]:
        memory_lines = "\n".join(
            f"- {item['title']}：{item['content']}" for item in memories[:10]
        ) or "- 暂无额外记忆。"

        system_prompt = dedent(
            f"""
            你是一名中文小说写作者。
            你要根据 GraphRAG 检索结果、项目设定和用户目标，写出原创中文小说正文。

            强制规则：
            - 普通对话必须使用「」。
            - 引号内嵌套引号必须使用『』。
            - 不要输出英文双引号，不要输出中文弯引号。
            - 不要模仿任何在世作者。
            - 不要解释你是如何写作的。
            - 正文必须自然、连续、可直接阅读。

            项目风格规则：
            {punctuation_rule}
            {writing_rules or "保持克制、意象明确、叙事连续。"}
            """
        ).strip()

        prompt = dedent(
            f"""
            项目：{project_title}
            类型：{genre}
            项目前提：{premise}
            世界设定：{world_brief}

            用户当前写作目标：
            {user_prompt}

            用户长期记忆：
            {memory_lines}

            GraphRAG Local Search 结果：
            {local_context}

            GraphRAG Global Search 结果：
            {global_context}

            任务：
            1. 先写一个简洁标题。
            2. 再写一段 60 字以内的摘要。
            3. 再写完整正文。

            输出格式必须严格是 JSON：
            {{
              "title": "...",
              "summary": "...",
              "content": "..."
            }}
            """
        ).strip()

        response = self.llm.generate(
            model=self.settings.writer_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
        )
        payload = self._parse_json(response.text)
        title = str(payload.get("title", "")).strip() or "未命名章节"
        summary = str(payload.get("summary", "")).strip() or user_prompt[:80]
        content = str(payload.get("content", "")).strip() or response.text.strip()
        content = self._normalize_dialogue(content)
        return title, summary, content

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
        # Replace alternating fallback quotes with Japanese-style nested quotes when possible.
        normalized = normalized.replace("『「", "『").replace("」』", "』")
        return normalized
