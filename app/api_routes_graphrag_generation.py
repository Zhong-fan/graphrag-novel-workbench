from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from .api_support import (
    GENERATION_PROGRESS,
    _canonical_project_evolution,
    _china_timestamp,
    _generation_or_404,
    _graph_review_out,
    _project_chapter_or_404,
    _project_or_404,
    _snapshot_with_process,
    _workspace_record,
)
from .auth import get_current_user
from .config import Settings
from .contracts import (
    GenerateRequest,
    GenerationOut,
    GenerationProgressOut,
    GraphReviewFileUpdateRequest,
    GraphReviewOut,
    IndexRequest,
    IndexResponse,
)
from .db import get_db
from .evolution_service import EvolutionService
from .graphrag_service import GraphRAGService
from .models import GenerationRun, User
from .story_service import StoryGenerationService

logger = logging.getLogger(__name__)


def register_graphrag_generation_routes(
    router: APIRouter,
    *,
    settings: Settings,
    run_index_job,
) -> None:
    @router.post("/api/projects/{project_id}/index", response_model=IndexResponse)
    def index_project(
        project_id: int,
        payload: IndexRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> IndexResponse:
        project = _project_or_404(db, current_user.id, project_id)
        graphrag = GraphRAGService(settings)
        workspace_path = graphrag.workspace_path(project)
        record = _workspace_record(db, project, workspace_path)
        if project.indexing_status != "indexing" or payload.force_rebuild:
            project.indexing_status = "indexing"
            record.neo4j_sync_status = "indexing"
            record.last_error = ""
            db.commit()
            background_tasks.add_task(run_index_job, project.id)

        return IndexResponse(
            status=project.indexing_status,
            workspace_path=record.workspace_path,
            neo4j_sync_status=record.neo4j_sync_status,
            last_error=record.last_error,
        )

    @router.post("/api/projects/{project_id}/graphrag/prepare-review", response_model=GraphReviewOut)
    def prepare_graphrag_review(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GraphReviewOut:
        project = _project_or_404(db, current_user.id, project_id)
        graphrag = GraphRAGService(settings)
        character_updates, relationship_updates, story_events, world_updates = _canonical_project_evolution(db, project)
        workspace = graphrag.prepare_project_inputs(
            project,
            list(project.memories),
            list(project.source_documents),
            character_cards=[item for item in project.character_cards if item.deleted_at is None],
            character_updates=character_updates,
            relationship_updates=relationship_updates,
            story_events=story_events,
            world_updates=world_updates,
        )
        record = _workspace_record(db, project, workspace)
        record.workspace_path = str(workspace)
        if record.neo4j_sync_status == "idle":
            record.neo4j_sync_status = "stale"
        record.last_error = ""
        db.commit()
        db.refresh(project)
        review = _graph_review_out(project)
        if review is None:
            raise HTTPException(status_code=500, detail="GraphRAG 预览生成失败。")
        return review

    @router.put("/api/projects/{project_id}/graphrag/files/{filename}", response_model=GraphReviewOut)
    def update_graphrag_review_file(
        project_id: int,
        filename: str,
        payload: GraphReviewFileUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GraphReviewOut:
        project = _project_or_404(db, current_user.id, project_id)
        record = project.graph_workspace
        if record is None:
            raise HTTPException(status_code=404, detail="GraphRAG 工作区不存在，请先准备预览。")
        workspace = Path(record.workspace_path)
        target = workspace / "input" / filename
        if not target.exists() or target.suffix != ".txt":
            raise HTTPException(status_code=404, detail="目标输入文件不存在。")
        target.write_text(payload.content.strip() + "\n", encoding="utf-8")
        record.neo4j_sync_status = "stale"
        record.last_error = ""
        project.indexing_status = "stale"
        db.commit()
        db.refresh(project)
        review = _graph_review_out(project)
        if review is None:
            raise HTTPException(status_code=500, detail="GraphRAG 预览刷新失败。")
        return review

    @router.post("/api/projects/{project_id}/generate", response_model=GenerationOut)
    def generate(
        project_id: int,
        payload: GenerateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationOut:
        trace: dict[str, object] = {}
        logs: list[dict[str, object]] = []

        def set_progress(
            stage: str,
            message: str,
            *,
            level: str = "info",
            details: dict[str, object] | None = None,
        ) -> None:
            entry = {
                "timestamp": _china_timestamp(),
                "stage": stage,
                "level": level,
                "message": message,
                "details": details or {},
            }
            logs.append(entry)
            GENERATION_PROGRESS[current_user.id] = {"stage": stage, "message": message, "trace": trace, "logs": logs}
            log_method = logger.warning if level == "warning" else logger.error if level == "error" else logger.info
            log_method(
                "Generate progress updated: project=%s chapter=%s user=%s stage=%s message=%s",
                project_id,
                payload.chapter_id,
                current_user.id,
                stage,
                message,
            )

        project = _project_or_404(db, current_user.id, project_id)
        project_chapter = _project_chapter_or_404(db, project.id, payload.chapter_id)
        set_progress("start", "开始生成")
        logger.info("Generate started: project=%s chapter=%s", project.id, project_chapter.id)

        graphrag = GraphRAGService(settings)
        if project.indexing_status != "ready" or project.graph_workspace is None:
            detail = "请先准备并完成 GraphRAG 索引，索引就绪后才能生成草稿。"
            set_progress("failed", detail, level="error")
            raise HTTPException(status_code=409, detail=detail)

        local_result = graphrag.query(project, payload.prompt, payload.search_method, payload.response_type)
        global_result = None
        if payload.use_global_search:
            global_result = graphrag.query(project, payload.prompt, "global", payload.response_type)
        set_progress("retrieval", "参考资料已处理")

        recent_character_updates, recent_relationship_updates, recent_story_events, recent_world_updates = _canonical_project_evolution(
            db,
            project,
        )

        evolution = EvolutionService(settings)
        scene_card = ""
        if payload.use_scene_card:
            scene_card = evolution.build_scene_card(
                user_prompt=payload.prompt,
                local_context=local_result.text,
                global_context=global_result.text if global_result is not None else "未启用全局检索。",
                recent_character_updates=[
                    {
                        "character_name": item.character_name,
                        "emotion_state": item.emotion_state,
                        "current_goal": item.current_goal,
                        "summary": item.summary,
                    }
                    for item in recent_character_updates[:8]
                ],
                recent_relationship_updates=[
                    {
                        "source_character": item.source_character,
                        "target_character": item.target_character,
                        "summary": item.summary,
                    }
                    for item in recent_relationship_updates[:8]
                ],
                recent_events=[
                    {"title": item.title, "impact_summary": item.impact_summary}
                    for item in recent_story_events[:6]
                ],
                recent_world_updates=[
                    {
                        "observer_group": item.observer_group,
                        "subject_name": item.subject_name,
                        "change_summary": item.change_summary,
                    }
                    for item in recent_world_updates[:6]
                ],
            )

        writer = StoryGenerationService(settings)
        try:
            title, summary, content = writer.generate(
                project_title=project.title,
                genre=project.genre,
                premise=project_chapter.premise,
                world_brief=project.world_brief,
                writing_rules=project.writing_rules,
                style_profile=project.style_profile,
                user_prompt=payload.prompt,
                response_type=payload.response_type,
                scene_card=scene_card,
                memories=[
                    {"title": memory.title, "content": memory.content}
                    for memory in sorted(project.memories, key=lambda item: item.importance, reverse=True)
                ],
                use_refiner=payload.use_refiner,
                progress=set_progress,
                trace=trace,
            )
        except RuntimeError as exc:
            detail = str(exc)
            set_progress("failed", detail, level="error")
            raise HTTPException(status_code=502, detail=detail) from exc

        generation = GenerationRun(
            project=project,
            project_chapter=project_chapter,
            prompt=payload.prompt,
            search_method=payload.search_method,
            response_type=payload.response_type,
            retrieval_context=(
                f"[Local]\n{local_result.text}\n\n[Global]\n{global_result.text}"
                if global_result is not None
                else f"[Local]\n{local_result.text}\n\n[Global]\n未启用全局检索。"
            ),
            scene_card=scene_card,
            evolution_snapshot=json.dumps(
                {
                    "process": {
                        "draft": {"status": "done", "message": "初稿已保存"},
                        "refine": {
                            "status": "done" if payload.use_refiner else "skipped",
                            "message": "润色已完成" if payload.use_refiner else "未启用润色",
                        },
                        "evolution": {"status": "pending", "message": "等待抽取变化"},
                    },
                    "characters": [],
                    "relationships": [],
                    "events": [],
                    "world_updates": [],
                },
                ensure_ascii=False,
            ),
            generation_trace=json.dumps(trace, ensure_ascii=False),
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)
        set_progress("saved", f"草稿已保存，编号 {generation.id}")

        if payload.write_evolution:
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
                    trace=trace,
                )
                set_progress("evolution_done", "变化抽取已完成")
            except RuntimeError:
                set_progress("evolution_failed", "变化抽取失败，草稿已保留")
                evolution_payload = evolution.empty_payload()
                generation.evolution_snapshot = _snapshot_with_process(
                    evolution_payload,
                    {
                        "draft": {"status": "done", "message": "初稿已保存"},
                        "refine": {
                            "status": "done" if payload.use_refiner else "skipped",
                            "message": "润色已完成" if payload.use_refiner else "未启用润色",
                        },
                        "evolution": {"status": "failed", "message": "变化抽取失败，可继续处理"},
                    },
                )
                db.commit()
                return GenerationOut.model_validate(generation)
        else:
            evolution_payload = evolution.empty_payload()

        generation.evolution_snapshot = _snapshot_with_process(
            evolution_payload,
            {
                "draft": {"status": "done", "message": "初稿已保存"},
                "refine": {
                    "status": "done" if payload.use_refiner else "skipped",
                    "message": "润色已完成" if payload.use_refiner else "未启用润色",
                },
                "evolution": {
                    "status": "done" if payload.write_evolution else "skipped",
                    "message": "变化抽取已完成" if payload.write_evolution else "未启用变化抽取",
                },
            },
        )
        db.commit()
        set_progress("done", "生成流程完成")
        return GenerationOut.model_validate(generation)

    @router.get("/api/projects/{project_id}/generate/progress", response_model=GenerationProgressOut)
    def generation_progress(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationProgressOut:
        _project_or_404(db, current_user.id, project_id)
        payload = GENERATION_PROGRESS.get(current_user.id, {"stage": "idle", "message": "暂无生成任务", "trace": {}})
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
        project_chapter = _project_chapter_or_404(db, project.id, generation.project_chapter_id) if generation.project_chapter_id else None
        evolution = EvolutionService(settings)
        try:
            evolution_payload = evolution.extract_evolution(
                project_title=project.title,
                genre=project.genre,
                premise=project_chapter.premise if project_chapter is not None else "",
                user_prompt=generation.prompt,
                title=generation.title,
                summary=generation.summary,
                content=generation.content,
            )
        except RuntimeError as exc:
            generation.evolution_snapshot = _snapshot_with_process(
                evolution.empty_payload(),
                {
                    "draft": {"status": "done", "message": "初稿已保存"},
                    "refine": {"status": "done", "message": "正文可用"},
                    "evolution": {"status": "failed", "message": str(exc)},
                },
            )
            db.commit()
            db.refresh(generation)
            return GenerationOut.model_validate(generation)

        generation.evolution_snapshot = _snapshot_with_process(
            evolution_payload,
            {
                "draft": {"status": "done", "message": "初稿已保存"},
                "refine": {"status": "done", "message": "正文可用"},
                "evolution": {"status": "done", "message": "变化抽取已完成"},
            },
        )
        db.commit()
        db.refresh(generation)
        return GenerationOut.model_validate(generation)
