from __future__ import annotations

import json
from dataclasses import asdict
from textwrap import dedent

from .config import Settings
from .llm import BaseLLM, parse_json_response
from .schema import (
    ChapterPlan,
    ChapterRequest,
    ChapterUpdate,
    ExtractedEdge,
    RetrievalResult,
    SceneBeat,
)


def _compact_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


class PlannerAgent:
    def __init__(self, *, settings: Settings, llm: BaseLLM) -> None:
        self.settings = settings
        self.llm = llm

    def plan(
        self,
        *,
        project: dict,
        request: ChapterRequest,
        retrieval: RetrievalResult,
    ) -> tuple[ChapterPlan, str]:
        system_prompt = dedent(
            """
            你是 GraphRAG 轻小说系统里的规划代理。
            你的任务是生成简洁的场景简报，保证连续性，并推动章节向前。
            所有说明内容都应服务于中文小说写作。
            只返回 JSON。
            """
        ).strip()
        payload = {
            "project_title": project.get("title"),
            "theme": project.get("theme"),
            "request": asdict(request),
            "focus_nodes": [asdict(node) for node in retrieval.focus_nodes],
            "related_nodes": [asdict(node) for node in retrieval.related_nodes[:8]],
            "recent_chapters": [asdict(record) for record in retrieval.recent_chapters],
        }
        user_prompt = dedent(
            """
            为下一章生成简洁的规划简报。

            JSON 结构必须如下：
            {
              "chapter_goal": "...",
              "emotional_shift": "...",
              "motif_image": "...",
              "scene_beats": [
                {"label": "...", "focus": "...", "tension": "...", "turn": "..."}
              ],
              "continuity_notes": ["..."]
            }

            约束：
            - 生成 3 到 5 个场景节点。
            - 保留图谱里已经存在的事实。
            - 情绪推进要克制、连续、偏细微。
            - 所有自然语言内容使用简体中文。

            INPUT_PAYLOAD:
            """
        ).strip() + "\n" + _compact_json(payload)

        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
        )
        try:
            data = parse_json_response(response.text)
            plan = self._from_payload(data, request)
        except RuntimeError:
            plan = self._fallback_plan(request)
        return plan, response.model

    def _from_payload(self, payload: dict, request: ChapterRequest) -> ChapterPlan:
        scene_beats = [
            SceneBeat(
                label=str(item.get("label", "场景")).strip() or "场景",
                focus=str(item.get("focus", request.premise)).strip() or request.premise,
                tension=str(item.get("tension", "旧日的张力仍在。")).strip()
                or "旧日的张力仍在。",
                turn=str(item.get("turn", "一个细小变化改变了场面。")).strip()
                or "一个细小变化改变了场面。",
            )
            for item in payload.get("scene_beats", [])[:5]
            if isinstance(item, dict)
        ]
        if not scene_beats:
            scene_beats = self._fallback_plan(request).scene_beats

        continuity_notes = [
            str(item).strip()
            for item in payload.get("continuity_notes", [])
            if str(item).strip()
        ]

        return ChapterPlan(
            chapter_goal=str(payload.get("chapter_goal", request.premise)).strip()
            or request.premise,
            emotional_shift=str(
                payload.get("emotional_shift", "距离感有所松动，但没有真正消失")
            ).strip()
            or "距离感有所松动，但没有真正消失",
            motif_image=str(payload.get("motif_image", request.motif)).strip() or request.motif,
            scene_beats=scene_beats,
            continuity_notes=continuity_notes,
        )

    def _fallback_plan(self, request: ChapterRequest) -> ChapterPlan:
        return ChapterPlan(
            chapter_goal=request.premise,
            emotional_shift="距离略有缓和，但仍未被真正解决",
            motif_image=request.motif,
            scene_beats=[
                SceneBeat(
                    label="相遇",
                    focus="主要角色以明显的克制进入同一空间。",
                    tension="过去还没被说出口，就已经先一步抵达现场。",
                    turn="一个共同注意到的小细节让双方都没有立刻离开。",
                ),
                SceneBeat(
                    label="交谈",
                    focus="越是普通的对话，越显出两人之间没有说开的部分。",
                    tension="真正重要的话仍停留在暗处。",
                    turn="一个被记起的细节改变了这场对话的温度。",
                ),
                SceneBeat(
                    label="余波",
                    focus="章节在微小但真实的前进一步里收束。",
                    tension="坦白与和解都还没有真正到来。",
                    turn="一句轻微的邀约或约定取代了沉默。",
                ),
            ],
            continuity_notes=["保持既有事件历史与意象连续，不要强行跳跃推进。"],
        )


class WriterAgent:
    def __init__(self, *, settings: Settings, llm: BaseLLM) -> None:
        self.settings = settings
        self.llm = llm

    def write(
        self,
        *,
        project: dict,
        request: ChapterRequest,
        retrieval: RetrievalResult,
        plan: ChapterPlan,
    ) -> tuple[str, str]:
        style = project.get("style_guide", {})
        system_prompt = dedent(
            f"""
            你是负责正文写作的代理，要写出克制、意象先行的中文轻小说章节。
            文风必须原创，不模仿任何在世作者。
            优先级：
            - 用情绪潜流代替直白说明
            - 感官细节要落在天气与场所上
            - 保持与已有故事事实连续
            - 以场景推进为主，段落紧凑

            风格约束：
            - 每章包含自然意象：{style.get('natural_motif_per_chapter', True)}
            - 对话比例上限：{style.get('dialogue_ratio_max', 0.25)}
            - 必须有感官锚点：{style.get('sensory_anchor_required', True)}
            - 优先通过环境映射情绪：{style.get('emotion_via_environment_first', True)}
            - 全文使用简体中文
            """
        ).strip()
        payload = {
            "project_title": project.get("title"),
            "theme": project.get("theme"),
            "request": asdict(request),
            "plan": asdict(plan),
            "focus_nodes": [asdict(node) for node in retrieval.focus_nodes],
            "related_nodes": [asdict(node) for node in retrieval.related_nodes[:8]],
            "recent_chapters": [asdict(record) for record in retrieval.recent_chapters],
        }
        scene_lines = "\n".join(
            f"- {beat.label}：{beat.focus} 张力：{beat.tension} 转折：{beat.turn}"
            for beat in plan.scene_beats
        )
        user_prompt = dedent(
            f"""
            项目：{project["title"]}
            主题：{project["theme"]}

            写作目标：第 {request.chapter_number} 章
            前提：{request.premise}
            章节目标：{plan.chapter_goal}
            情绪变化：{plan.emotional_shift}
            核心意象：{plan.motif_image}

            场景简报：
            {scene_lines or "- 暂无场景简报。"}

            连续性备注：
            {chr(10).join(f"- {item}" for item in plan.continuity_notes) or "- 无"}

            产出要求：
            - 3 到 5 个紧凑场景
            - 人物关系有细微推进
            - 与检索出的图谱事实保持一致
            - 不要输出元说明，不要加 markdown 标题
            - 正文全部使用简体中文

            INPUT_PAYLOAD:
            """
        ).strip() + "\n" + _compact_json(payload)

        response = self.llm.generate(
            model=self.settings.writer_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="text",
        )
        return response.text.strip(), response.model


class UpdaterAgent:
    def __init__(self, *, settings: Settings, llm: BaseLLM) -> None:
        self.settings = settings
        self.llm = llm

    def extract(
        self,
        *,
        request: ChapterRequest,
        retrieval: RetrievalResult,
        plan: ChapterPlan,
        title: str,
        chapter_text: str,
    ) -> tuple[ChapterUpdate, str]:
        system_prompt = dedent(
            """
            你是负责故事状态回写的代理。
            你的任务是从章节草稿中提取可持续存在的状态变化。
            只返回 JSON，且在创建边时只使用现有节点 id。
            所有自然语言内容使用简体中文。
            """
        ).strip()
        payload = {
            "title": title,
            "request": asdict(request),
            "plan": asdict(plan),
            "focus_nodes": [asdict(node) for node in retrieval.focus_nodes],
            "related_nodes": [asdict(node) for node in retrieval.related_nodes[:8]],
            "recent_chapters": [asdict(record) for record in retrieval.recent_chapters],
            "chapter_text": chapter_text,
        }
        user_prompt = dedent(
            """
            从章节草稿里提取紧凑的结构化更新。

            JSON 结构必须如下：
            {
              "event_name": "...",
              "event_summary": "...",
              "event_attributes": {"key": "value"},
              "continuity_notes": ["..."],
              "edges": [
                {"source": "existing_node_id", "target": "existing_node_id", "type": "...", "attributes": {}}
              ]
            }

            约束：
            - 摘要只写一句话。
            - 只保留会持续影响后文的人物关系或记忆状态。
            - 只有当边代表稳定的状态信号时才输出。
            - 所有自然语言内容使用简体中文。

            INPUT_PAYLOAD:
            """
        ).strip() + "\n" + _compact_json(payload)

        response = self.llm.generate(
            model=self.settings.utility_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
        )
        try:
            data = parse_json_response(response.text)
            update = self._from_payload(data, title, request, plan)
        except RuntimeError:
            update = self._fallback_update(title, request, plan)
        return update, response.model

    def _from_payload(
        self,
        payload: dict,
        title: str,
        request: ChapterRequest,
        plan: ChapterPlan,
    ) -> ChapterUpdate:
        edges = [
            ExtractedEdge(
                source=str(item.get("source", "")).strip(),
                target=str(item.get("target", "")).strip(),
                type=str(item.get("type", "")).strip(),
                attributes=item.get("attributes", {}) if isinstance(item.get("attributes"), dict) else {},
            )
            for item in payload.get("edges", [])
            if isinstance(item, dict)
        ]
        return ChapterUpdate(
            event_name=str(payload.get("event_name", title)).strip() or title,
            event_summary=str(payload.get("event_summary", request.premise)).strip()
            or request.premise,
            event_attributes=payload.get("event_attributes", {})
            if isinstance(payload.get("event_attributes"), dict)
            else {},
            continuity_notes=[
                str(item).strip()
                for item in payload.get("continuity_notes", [])
                if str(item).strip()
            ],
            edges=[edge for edge in edges if edge.source and edge.target and edge.type],
        )

    def _fallback_update(
        self,
        title: str,
        request: ChapterRequest,
        plan: ChapterPlan,
    ) -> ChapterUpdate:
        return ChapterUpdate(
            event_name=title,
            event_summary=request.premise,
            event_attributes={
                "chapter_number": request.chapter_number,
                "emotional_shift": plan.emotional_shift,
                "motif_image": plan.motif_image,
            },
            continuity_notes=plan.continuity_notes,
        )
