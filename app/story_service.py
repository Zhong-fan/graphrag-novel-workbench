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
        style_profile: str,
        punctuation_rule: str,
        user_prompt: str,
        scene_card: str,
        memories: list[dict[str, str]],
        use_refiner: bool,
    ) -> tuple[str, str, str]:
        memory_lines = "\n".join(
            f"- {item['title']}：{item['content']}" for item in memories[:10]
        ) or "- 暂无额外长期设定。"

        style_instructions = self._style_instructions(style_profile)
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

            当前文风预设：
            {style_instructions}

            项目风格规则：
            {punctuation_rule}
            {writing_rules or "保持轻盈、自然、叙事连续，以人物互动推动场景。"}
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

            用户长期设定：
            {memory_lines}

            写作上下文卡：
            {scene_card}

            任务：
            1. 先写一个简洁标题。
            2. 再写一段 60 字以内的摘要。
            3. 再写完整正文。

            正文额外要求：
            - 对白要自然，避免每句都带重情绪说明。
            - 一章里允许有空气感，但不要连续三段都在抒情。
            - 少解释“他很难过”，多写“他怎么停顿、怎么移开视线、怎么没把话说完”。
            - 不要把人物情绪写成厚重散文。

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
        draft_content = str(payload.get("content", "")).strip() or response.text.strip()
        refined_content = draft_content
        if use_refiner:
            refined_content = self._refine_light_novel_prose(
                project_title=project_title,
                genre=genre,
                style_profile=style_profile,
                title=title,
                summary=summary,
                user_prompt=user_prompt,
                draft_content=draft_content,
            )
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
        # Replace alternating fallback quotes with Japanese-style nested quotes when possible.
        normalized = normalized.replace("『「", "『").replace("」』", "』")
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
    ) -> str:
        system_prompt = dedent(
            """
            你是中文轻小说润色编辑。
            你的任务不是重写剧情，而是在保持事件、人物关系、先后顺序完全不变的前提下，
            把初稿润色得更轻、更顺、更自然、更适合现代轻小说阅读。

            强制规则：
            - 不改变剧情事实。
            - 不新增不存在的重要设定。
            - 不删掉关键事件。
            - 对话继续使用「」。
            - 所有内容使用简体中文。

            润色目标：
            - 降低抒情密度。
            - 减少连续的抽象意象和“像、仿佛、似乎”类堆叠。
            - 增加人物动作、对白、停顿带来的情绪表达。
            - 保持空气感，但不要沉重。
            - 让句子更轻、更好读、更像轻小说。
            """
        ).strip()

        if style_profile == "lyrical_restrained":
            system_prompt = dedent(
                """
                你是中文小说润色编辑。
                你的任务不是重写剧情，而是在保持事件、人物关系、先后顺序完全不变的前提下，
                把初稿润色得更细腻、克制、带有轻微抒情感，但不能过度沉重。

                强制规则：
                - 不改变剧情事实。
                - 不新增不存在的重要设定。
                - 不删掉关键事件。
                - 对话继续使用「」。
                - 所有内容使用简体中文。

                润色目标：
                - 保留细微情绪潜流。
                - 保留适量意象，但避免堆叠。
                - 让语言更顺，更有呼吸感。
                - 不要把文本写成厚重散文。
                """
            ).strip()

        prompt = dedent(
            f"""
            项目：{project_title}
            类型：{genre}
            本章标题：{title}
            本章摘要：{summary}
            用户目标：{user_prompt}

            下面是初稿，请进行“轻量减重润色”：

            {draft_content}

            输出要求：
            - 只输出润色后的正文
            - 不要解释修改思路
            - 不要加额外标题
            """
        ).strip()

        response = self.llm.generate(
            model=self.settings.writer_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
        )
        return response.text.strip() or draft_content

    def _style_instructions(self, style_profile: str) -> str:
        if style_profile == "lyrical_restrained":
            return dedent(
                """
                - 允许保留细微意象和情绪潜流。
                - 优先通过环境与动作折射情绪，但不要堆叠抽象比喻。
                - 语言要克制、透明、细腻，不要写成沉重散文。
                - 场景推进仍然要清楚，不能只有氛围没有动作。
                """
            ).strip()

        return dedent(
            """
            - 优先通过人物动作、对白、停顿和场景推进表现情绪。
            - 不要过度抒情，不要连续堆叠抽象意象。
            - 情感要轻、准、自然，不要写成沉重散文化 prose。
            - 句子尽量轻，少用过长复句。
            - 每一段都要推动场景、关系或信息，而不是只营造氛围。
            - 优先写人物之间的互动，再补环境细节。
            - 允许保留青春感、透明感和轻微口语节奏，但不要油腻。
            """
        ).strip()
