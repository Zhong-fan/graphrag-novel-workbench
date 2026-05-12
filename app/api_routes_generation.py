from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .api_support import (
    GENERATION_PROGRESS,
    _build_generation_trace,
    _china_timestamp,
    _generation_or_404,
    _project_chapter_or_404,
    _project_or_404,
    _snapshot_with_process,
)
from .api_support_project import _canonical_project_evolution
from .auth import get_current_user
from .config import Settings
from .contracts import GenerateRequest, GenerationOut, GenerationProgressOut
from .db import get_db
from .evolution_service import EvolutionService
from .models import GenerationRun, Project, ProjectChapter, User
from .story_service import StoryGenerationService

logger = logging.getLogger(__name__)


def _trim_lines(items: list[str], *, limit: int) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned[:limit]


def _build_scene_card(
    *,
    project: Project,
    project_chapter: ProjectChapter,
    payload: GenerateRequest,
    memory_titles: list[str],
    source_titles: list[str],
    recent_character_updates,
    recent_relationship_updates,
    recent_story_events,
    recent_world_updates,
) -> str:
    character_lines = _trim_lines(
        [
            f"- {item.character_name}: {item.summary or item.current_goal or item.emotion_state}"
            for item in recent_character_updates[:6]
            if item.character_name
        ],
        limit=6,
    ) or ["- 暂无最近人物变化"]
    relationship_lines = _trim_lines(
        [
            f"- {item.source_character} -> {item.target_character}: {item.summary}"
            for item in recent_relationship_updates[:6]
            if item.source_character and item.target_character
        ],
        limit=6,
    ) or ["- 暂无最近关系变化"]
    event_lines = _trim_lines(
        [
            f"- {item.title}: {item.impact_summary or item.summary}"
            for item in recent_story_events[:6]
            if item.title
        ],
        limit=6,
    ) or ["- 暂无最近关键事件"]
    world_lines = _trim_lines(
        [
            f"- {item.observer_group} 眼中的 {item.subject_name}: {item.change_summary}"
            for item in recent_world_updates[:6]
            if item.observer_group and item.subject_name
        ],
        limit=6,
    ) or ["- 暂无最近世界认知变化"]

    memory_summary = "\n".join(f"- {title}" for title in memory_titles[:8]) if memory_titles else "- 暂无长期记忆条目"
    source_summary = "\n".join(f"- {title}" for title in source_titles[:8]) if source_titles else "- 暂无参考资料"

    return (
        "\n".join(
            [
                "当前场景卡",
                f"项目：{project.title}",
                f"章节：第 {project_chapter.chapter_no} 章 / {project_chapter.title}",
                "",
                "本章目标",
                payload.prompt.strip(),
                "",
                "章节前提",
                project_chapter.premise.strip() or "暂无章节前提",
                "",
                "长期记忆",
                memory_summary,
                "",
                "参考资料",
                source_summary,
                "",
                "最近人物变化",
                "\n".join(character_lines),
                "",
                "最近关系变化",
                "\n".join(relationship_lines),
                "",
                "最近关键事件",
                "\n".join(event_lines),
                "",
                "最近世界认知变化",
                "\n".join(world_lines),
            ]
        )
    ).strip()


def _summarize_trace_step(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    summary: dict[str, object] = {}
    for key in ("status", "model", "reason", "error"):
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            summary[key] = raw.strip()

    parsed = value.get("parsed")
    if isinstance(parsed, dict):
        title = parsed.get("title")
        if isinstance(title, str) and title.strip():
            summary["title"] = title.strip()
        text_summary = parsed.get("summary")
        if isinstance(text_summary, str):
            summary["summary_length"] = len(text_summary.strip())
        content = parsed.get("content")
        if isinstance(content, str):
            summary["content_length"] = len(content.strip())
        covered = parsed.get("covered")
        if isinstance(covered, bool):
            summary["covered"] = covered

    output = value.get("output")
    if isinstance(output, str):
        summary["output_length"] = len(output.strip())
    raw_output = value.get("raw_output")
    if isinstance(raw_output, str):
        summary["raw_output_length"] = len(raw_output.strip())

    return summary or None


def _refresh_runtime_trace_steps(trace: dict[str, object]) -> None:
    steps: dict[str, object] = {}
    for name in ("draft", "refine", "intent_check", "evolution"):
        summary = _summarize_trace_step(trace.get(name))
        if summary is not None:
            steps[name] = summary
    trace["steps"] = steps


def _build_persisted_trace(
    runtime_trace: dict[str, object],
    *,
    title: str,
    summary: str,
    content: str,
) -> dict[str, object]:
    _refresh_runtime_trace_steps(runtime_trace)
    return {
        "project": runtime_trace.get("project", {}),
        "chapter": runtime_trace.get("chapter", {}),
        "request": runtime_trace.get("request", {}),
        "context": runtime_trace.get("context", {}),
        "steps": runtime_trace.get("steps", {}),
        "result": {
            "title": title.strip(),
            "summary_length": len(summary.strip()),
            "content_length": len(content.strip()),
        },
    }


def register_generation_routes(
    router: APIRouter,
    *,
    settings: Settings,
) -> None:
    @router.post("/api/projects/{project_id}/generate", response_model=GenerationOut)
    def generate(
        project_id: int,
        payload: GenerateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationOut:
        project = _project_or_404(db, current_user.id, project_id)
        project_chapter = _project_chapter_or_404(db, project.id, payload.chapter_id)
        runtime_trace = _build_generation_trace(project=project, project_chapter=project_chapter, payload=payload)
        logs: list[dict[str, object]] = []

        def set_progress(
            stage: str,
            message: str,
            *,
            level: str = "info",
            details: dict[str, object] | None = None,
        ) -> None:
            _refresh_runtime_trace_steps(runtime_trace)
            entry = {
                "timestamp": _china_timestamp(),
                "stage": stage,
                "level": level,
                "message": message,
                "details": details or {},
            }
            logs.append(entry)
            GENERATION_PROGRESS[current_user.id] = {
                "stage": stage,
                "message": message,
                "trace": runtime_trace,
                "logs": logs,
            }
            log_method = logger.warning if level == "warning" else logger.error if level == "error" else logger.info
            log_method(
                "Generate progress updated: project=%s chapter=%s user=%s stage=%s message=%s",
                project_id,
                payload.chapter_id,
                current_user.id,
                stage,
                message,
            )

        set_progress("start", "开始生成")

        memories = sorted(project.memories, key=lambda item: item.importance, reverse=True)
        memory_payload = [{"title": memory.title, "content": memory.content} for memory in memories]
        memory_titles = [memory.title for memory in memories if memory.title.strip()]
        source_titles = [item.title for item in project.source_documents if item.title.strip()]

        (
            recent_character_updates,
            recent_relationship_updates,
            recent_story_events,
            recent_world_updates,
        ) = _canonical_project_evolution(db, project)

        context_info = runtime_trace.get("context")
        if isinstance(context_info, dict):
            context_info.update(
                {
                    "mode": "creator_workbench_direct",
                    "memory_count": len(memory_payload),
                    "source_count": len(project.source_documents),
                    "recent_character_update_count": len(recent_character_updates),
                    "recent_relationship_update_count": len(recent_relationship_updates),
                    "recent_event_count": len(recent_story_events),
                    "recent_world_update_count": len(recent_world_updates),
                    "reference_work_enabled": bool(project.reference_work.strip()),
                }
            )

        scene_card = ""
        if payload.use_scene_card:
            scene_card = _build_scene_card(
                project=project,
                project_chapter=project_chapter,
                payload=payload,
                memory_titles=memory_titles,
                source_titles=source_titles,
                recent_character_updates=recent_character_updates,
                recent_relationship_updates=recent_relationship_updates,
                recent_story_events=recent_story_events,
                recent_world_updates=recent_world_updates,
            )
            if isinstance(context_info, dict):
                context_info["scene_card_length"] = len(scene_card)

        writer = StoryGenerationService(settings)
        try:
            title, summary, content = writer.generate(
                project_title=project.title,
                genre=project.genre,
                reference_work=project.reference_work,
                premise=project_chapter.premise,
                world_brief=project.world_brief,
                writing_rules=project.writing_rules,
                style_profile=project.style_profile,
                user_prompt=payload.prompt,
                response_type=payload.response_type,
                scene_card=scene_card,
                memories=memory_payload,
                use_refiner=payload.use_refiner,
                progress=set_progress,
                trace=runtime_trace,
            )
        except RuntimeError as exc:
            detail = str(exc)
            set_progress("failed", detail, level="error")
            raise HTTPException(status_code=502, detail=detail) from exc

        retrieval_snapshot = {
            "mode": "creator_workbench_direct",
            "world_brief_length": len(project.world_brief.strip()),
            "writing_rules_length": len(project.writing_rules.strip()),
            "memory_count": len(memory_payload),
            "memory_titles": memory_titles[:8],
            "source_count": len(project.source_documents),
            "source_titles": source_titles[:8],
            "recent_character_update_count": len(recent_character_updates),
            "recent_relationship_update_count": len(recent_relationship_updates),
            "recent_event_count": len(recent_story_events),
            "recent_world_update_count": len(recent_world_updates),
        }
        generation = GenerationRun(
            project=project,
            project_chapter=project_chapter,
            prompt=payload.prompt,
            search_method=payload.search_method,
            response_type=payload.response_type,
            retrieval_context=json.dumps(retrieval_snapshot, ensure_ascii=False),
            scene_card=scene_card,
            evolution_snapshot=json.dumps(
                {
                    "process": {
                        "draft": {"status": "done", "message": "初稿已生成"},
                        "refine": {
                            "status": "done" if payload.use_refiner else "skipped",
                            "message": "润色已完成" if payload.use_refiner else "未启用润色",
                        },
                        "evolution": {
                            "status": "pending" if payload.write_evolution else "skipped",
                            "message": "等待抽取变化" if payload.write_evolution else "未启用变化抽取",
                        },
                    },
                    "characters": [],
                    "relationships": [],
                    "events": [],
                    "world_updates": [],
                },
                ensure_ascii=False,
            ),
            generation_trace=json.dumps(
                _build_persisted_trace(runtime_trace, title=title, summary=summary, content=content),
                ensure_ascii=False,
            ),
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)
        set_progress("saved", f"草稿已保存，编号 {generation.id}")

        if not payload.write_evolution:
            set_progress("done", "生成流程完成")
            return GenerationOut.model_validate(generation)

        evolution = EvolutionService(settings)
        try:
            set_progress("evolution", "正在抽取人物、关系和事件变化")
            evolution_payload = evolution.extract_evolution(
                project_title=project.title,
                genre=project.genre,
                premise=project_chapter.premise,
                user_prompt=payload.prompt,
                title=title,
                summary=summary,
                content=content,
                trace=runtime_trace,
            )
            generation.evolution_snapshot = _snapshot_with_process(
                evolution_payload,
                {
                    "draft": {"status": "done", "message": "初稿已生成"},
                    "refine": {
                        "status": "done" if payload.use_refiner else "skipped",
                        "message": "润色已完成" if payload.use_refiner else "未启用润色",
                    },
                    "evolution": {"status": "done", "message": "变化抽取已完成"},
                },
            )
            generation.generation_trace = json.dumps(
                _build_persisted_trace(runtime_trace, title=title, summary=summary, content=content),
                ensure_ascii=False,
            )
            db.commit()
            db.refresh(generation)
            set_progress("done", "生成流程完成")
            return GenerationOut.model_validate(generation)
        except RuntimeError as exc:
            generation.evolution_snapshot = _snapshot_with_process(
                evolution.empty_payload(),
                {
                    "draft": {"status": "done", "message": "初稿已生成"},
                    "refine": {
                        "status": "done" if payload.use_refiner else "skipped",
                        "message": "润色已完成" if payload.use_refiner else "未启用润色",
                    },
                    "evolution": {"status": "failed", "message": str(exc)},
                },
            )
            runtime_trace["evolution"] = {
                "status": "failed",
                "model": settings.utility_model,
                "error": str(exc),
            }
            generation.generation_trace = json.dumps(
                _build_persisted_trace(runtime_trace, title=title, summary=summary, content=content),
                ensure_ascii=False,
            )
            db.commit()
            db.refresh(generation)
            set_progress("evolution_failed", "变化抽取失败，草稿已保留", level="warning")
            return GenerationOut.model_validate(generation)

    @router.get("/api/projects/{project_id}/generate/progress", response_model=GenerationProgressOut)
    def generation_progress(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationProgressOut:
        _project_or_404(db, current_user.id, project_id)
        payload = GENERATION_PROGRESS.get(
            current_user.id,
            {"stage": "idle", "message": "暂无生成任务", "trace": {}, "logs": []},
        )
        payload.setdefault("trace", {})
        payload.setdefault("logs", [])
        return GenerationProgressOut.model_validate(payload)

    @router.post("/api/projects/{project_id}/generations/{generation_id}/refresh-evolution", response_model=GenerationOut)
    def refresh_generation_evolution(
        project_id: int,
        generation_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationOut:
        project = _project_or_404(db, current_user.id, project_id)
        generation = _generation_or_404(db, project.id, generation_id)
        project_chapter = (
            _project_chapter_or_404(db, project.id, generation.project_chapter_id)
            if generation.project_chapter_id is not None
            else None
        )
        evolution = EvolutionService(settings)
        runtime_trace: dict[str, object] = {}
        try:
            evolution_payload = evolution.extract_evolution(
                project_title=project.title,
                genre=project.genre,
                premise=project_chapter.premise if project_chapter is not None else "",
                user_prompt=generation.prompt,
                title=generation.title,
                summary=generation.summary,
                content=generation.content,
                trace=runtime_trace,
            )
            generation.evolution_snapshot = _snapshot_with_process(
                evolution_payload,
                {
                    "draft": {"status": "done", "message": "初稿已生成"},
                    "refine": {"status": "done", "message": "正文可用"},
                    "evolution": {"status": "done", "message": "变化抽取已完成"},
                },
            )
        except RuntimeError as exc:
            generation.evolution_snapshot = _snapshot_with_process(
                evolution.empty_payload(),
                {
                    "draft": {"status": "done", "message": "初稿已生成"},
                    "refine": {"status": "done", "message": "正文可用"},
                    "evolution": {"status": "failed", "message": str(exc)},
                },
            )
            runtime_trace["evolution"] = {
                "status": "failed",
                "model": settings.utility_model,
                "error": str(exc),
            }

        try:
            persisted_trace = json.loads(generation.generation_trace or "{}")
        except json.JSONDecodeError:
            persisted_trace = {}
        if not isinstance(persisted_trace, dict):
            persisted_trace = {}
        persisted_steps = persisted_trace.get("steps")
        if not isinstance(persisted_steps, dict):
            persisted_steps = {}
        step_summary = _summarize_trace_step(runtime_trace.get("evolution"))
        if step_summary is not None:
            persisted_steps["evolution"] = step_summary
        persisted_trace["steps"] = persisted_steps
        generation.generation_trace = json.dumps(persisted_trace, ensure_ascii=False)
        db.commit()
        db.refresh(generation)
        return GenerationOut.model_validate(generation)
