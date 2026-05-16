from __future__ import annotations

import json
from dataclasses import dataclass

from .config import Settings
from .llm import OpenAIResponsesLLM
from .prompts import evolution_system_prompt, evolution_user_prompt


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
                (
                    f"- {item['character_name']}："
                    f"当前情绪 {item['emotion_state'] or '未记录'}；"
                    f"当前目标 {item['current_goal'] or '未记录'}；"
                    f"状态变化 {item['summary'] or '未记录'}"
                )
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
                f"- {item['observer_group']} 看待 {item['subject_name']}：{item['change_summary'] or '未记录'}"
                for item in recent_world_updates[:4]
            )

        return (
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
            - 如果最近事件已经带来后果，下一章应体现这种后果，而不是直接跳过。

            七、直接创作上下文
            {local_context}

            八、补充上下文
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
        trace: dict | None = None,
    ) -> EvolutionPayload:
        system_prompt = evolution_system_prompt()
        prompt = evolution_user_prompt(
            project_title=project_title,
            genre=genre,
            premise=premise,
            user_prompt=user_prompt,
            title=title,
            summary=summary,
            content=content,
        )

        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        if trace is not None:
            trace["evolution"] = {
                "status": "succeeded",
                "model": self.settings.utility_model,
                "system_prompt": system_prompt,
                "user_prompt": prompt,
                "raw_output": response.text,
            }
        data = self._parse_json(response.text)
        if trace is not None:
            trace["evolution"]["parsed"] = data
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
