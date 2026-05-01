from __future__ import annotations

import json
from dataclasses import dataclass
from textwrap import dedent

from .config import Settings
from .llm import OpenAIResponsesLLM


@dataclass
class CharacterEvolution:
    character_name: str
    emotion_state: str
    current_goal: str
    self_view_shift: str
    public_perception: str
    summary: str


@dataclass
class RelationshipEvolution:
    source_character: str
    target_character: str
    change_type: str
    direction: str
    intensity: int
    summary: str


@dataclass
class StoryEventEvolution:
    title: str
    summary: str
    impact_summary: str
    participants: list[str]
    location_hint: str


@dataclass
class WorldPerceptionEvolution:
    subject_name: str
    observer_group: str
    direction: str
    change_summary: str


@dataclass
class EvolutionPayload:
    characters: list[CharacterEvolution]
    relationships: list[RelationshipEvolution]
    events: list[StoryEventEvolution]
    world_updates: list[WorldPerceptionEvolution]


class EvolutionService:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.llm = OpenAIResponsesLLM(settings.openai_api_key, settings.openai_base_url)

    def build_scene_card(
        self,
        *,
        user_prompt: str,
        local_context: str,
        global_context: str,
        recent_character_updates: list[dict[str, str]],
        recent_relationship_updates: list[dict[str, str]],
        recent_events: list[dict[str, str]],
        recent_world_updates: list[dict[str, str]],
    ) -> str:
        character_section = "暂无最近角色状态变化。"
        relationship_section = "暂无最近关系变化。"
        event_section = "暂无最近关键事件。"
        world_section = "暂无最近外界看法变化。"

        if recent_character_updates:
            character_section = "\n".join(
                f"- {item['character_name']}：当前情绪={item['emotion_state'] or '未记录'}；当前目标={item['current_goal'] or '未记录'}；状态变化={item['summary'] or '未记录'}"
                for item in recent_character_updates[:6]
            )

        if recent_relationship_updates:
            relationship_section = "\n".join(
                f"- {item['source_character']} -> {item['target_character']}：{item['summary'] or '未记录'}"
                for item in recent_relationship_updates[:6]
            )

        if recent_events:
            event_section = "\n".join(
                f"- {item['title']}：{item['impact_summary'] or item.get('summary', '未记录')}"
                for item in recent_events[:5]
            )

        if recent_world_updates:
            world_section = "\n".join(
                f"- {item['observer_group']} 对 {item['subject_name']}：{item['change_summary'] or '未记录'}"
                for item in recent_world_updates[:4]
            )

        return dedent(
            f"""
            当前场景写作卡

            一、最近角色状态变化
            {character_section}

            二、最近关系变化
            {relationship_section}

            三、最近关键事件
            {event_section}

            四、最近外界看法变化
            {world_section}

            五、本次场景目标
            {user_prompt}

            六、连续性提醒
            - 优先沿用最近状态变化，不要把角色重新写回初始设定。
            - 如果关系已经发生变化，优先承接这种变化，不要假装什么都没发生。
            - 如果最近事件已经带来后果，下一章应体现这种后果，而不是跳过。

            七、GraphRAG Local Search
            {local_context}

            八、GraphRAG Global Search
            {global_context}
            """
        ).strip()

    def empty_payload(self) -> EvolutionPayload:
        return EvolutionPayload(characters=[], relationships=[], events=[], world_updates=[])

    def extract_evolution(
        self,
        *,
        project_title: str,
        genre: str,
        premise: str,
        user_prompt: str,
        title: str,
        summary: str,
        content: str,
    ) -> EvolutionPayload:
        system_prompt = dedent(
            """
            你是中文小说系统里的状态演化分析器。
            你的任务不是润色正文，而是从本章内容里提取会持续影响后文的变化。
            只返回 JSON。
            """
        ).strip()

        prompt = dedent(
            f"""
            项目：{project_title}
            类型：{genre}
            项目前提：{premise}
            用户本次目标：{user_prompt}

            本章标题：
            {title}

            本章摘要：
            {summary}

            本章正文：
            {content}

            请提取“持续影响后文”的变化，输出 JSON：
            {{
              "characters": [
                {{
                  "character_name": "...",
                  "emotion_state": "...",
                  "current_goal": "...",
                  "self_view_shift": "...",
                  "public_perception": "...",
                  "summary": "..."
                }}
              ],
              "relationships": [
                {{
                  "source_character": "...",
                  "target_character": "...",
                  "change_type": "...",
                  "direction": "up/down/stable",
                  "intensity": 1,
                  "summary": "..."
                }}
              ],
              "events": [
                {{
                  "title": "...",
                  "summary": "...",
                  "impact_summary": "...",
                  "participants": ["..."],
                  "location_hint": "..."
                }}
              ],
              "world_updates": [
                {{
                  "subject_name": "...",
                  "observer_group": "...",
                  "direction": "positive/negative/stable",
                  "change_summary": "..."
                }}
              ]
            }}

            约束：
            - 每类最多输出 5 条
            - 只保留会持续影响后文的变化
            - 角色变化优先输出“状态变化”，不要重写基础人设
            - 不要写空泛总结，例如“情绪有变化”“关系更复杂了”。
            - 要写成下一章真的能继续用的信息，例如“开始回避对方”“不再完全信任”“第一次意识到自己做错了”。
            - 如果没有明确变化，就不要硬造。
            - 所有自然语言内容使用简体中文
            """
        ).strip()

        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
        )
        data = self._parse_json(response.text)
        return EvolutionPayload(
            characters=[self._character(item) for item in data.get("characters", [])[:5] if isinstance(item, dict)],
            relationships=[self._relationship(item) for item in data.get("relationships", [])[:5] if isinstance(item, dict)],
            events=[self._event(item) for item in data.get("events", [])[:5] if isinstance(item, dict)],
            world_updates=[self._world(item) for item in data.get("world_updates", [])[:5] if isinstance(item, dict)],
        )

    def _character(self, payload: dict) -> CharacterEvolution:
        return CharacterEvolution(
            character_name=str(payload.get("character_name", "")).strip(),
            emotion_state=str(payload.get("emotion_state", "")).strip(),
            current_goal=str(payload.get("current_goal", "")).strip(),
            self_view_shift=str(payload.get("self_view_shift", "")).strip(),
            public_perception=str(payload.get("public_perception", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
        )

    def _relationship(self, payload: dict) -> RelationshipEvolution:
        intensity = payload.get("intensity", 3)
        try:
            intensity_value = max(1, min(5, int(intensity)))
        except (TypeError, ValueError):
            intensity_value = 3
        return RelationshipEvolution(
            source_character=str(payload.get("source_character", "")).strip(),
            target_character=str(payload.get("target_character", "")).strip(),
            change_type=str(payload.get("change_type", "relationship_shift")).strip() or "relationship_shift",
            direction=str(payload.get("direction", "stable")).strip() or "stable",
            intensity=intensity_value,
            summary=str(payload.get("summary", "")).strip(),
        )

    def _event(self, payload: dict) -> StoryEventEvolution:
        participants = [str(item).strip() for item in payload.get("participants", []) if str(item).strip()]
        return StoryEventEvolution(
            title=str(payload.get("title", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
            impact_summary=str(payload.get("impact_summary", "")).strip(),
            participants=participants[:8],
            location_hint=str(payload.get("location_hint", "")).strip(),
        )

    def _world(self, payload: dict) -> WorldPerceptionEvolution:
        return WorldPerceptionEvolution(
            subject_name=str(payload.get("subject_name", "")).strip(),
            observer_group=str(payload.get("observer_group", "")).strip(),
            direction=str(payload.get("direction", "stable")).strip() or "stable",
            change_summary=str(payload.get("change_summary", "")).strip(),
        )

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
        raise RuntimeError("演化分析器没有返回可解析的 JSON。")
