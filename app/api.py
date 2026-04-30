from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, hash_password, issue_token, verify_password
from .config import load_settings
from .contracts import (
    AuthResponse,
    BootstrapResponse,
    GenerateRequest,
    GenerationOut,
    IndexRequest,
    IndexResponse,
    LoginRequest,
    MemoryCreateRequest,
    MemoryOut,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectOut,
    RegisterRequest,
    SourceCreateRequest,
    SourceOut,
    UserOut,
)
from .db import db_session, get_db, init_db
from .graphrag_service import GraphRAGService
from .models import GenerationRun, GraphWorkspace, Memory, Project, SourceDocument, User
from .story_service import StoryGenerationService


def _project_or_404(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user_id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    return project


def _workspace_record(db: Session, project: Project, workspace_path: Path) -> GraphWorkspace:
    if project.graph_workspace is not None:
        return project.graph_workspace
    record = GraphWorkspace(project=project, workspace_path=str(workspace_path))
    db.add(record)
    db.flush()
    return record


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="GraphRAG 小说工作台",
        version="1.0.0",
        description="GraphRAG + MySQL + Neo4j + Vue 的中文小说工作台。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup() -> None:
        init_db()

    def run_index_job(project_id: int) -> None:
        with db_session() as db:
            project = db.get(Project, project_id)
            if project is None:
                return

            graphrag = GraphRAGService(settings)
            workspace_path = graphrag.workspace_path(project)
            record = _workspace_record(db, project, workspace_path)
            project.indexing_status = "indexing"
            record.neo4j_sync_status = "indexing"
            db.commit()

            try:
                graphrag.index_project(project, list(project.memories), list(project.source_documents), record)
                project.indexing_status = "ready"
                record.neo4j_sync_status = "synced"
                record.last_indexed_at = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
                project = db.get(Project, project_id)
                if project is None:
                    return
                record = project.graph_workspace
                project.indexing_status = "failed"
                if record is not None:
                    record.neo4j_sync_status = "failed"
                db.commit()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/bootstrap", response_model=BootstrapResponse)
    def bootstrap() -> BootstrapResponse:
        return BootstrapResponse(
            service_name="GraphRAG 中文小说工作台",
            graph_engine="GraphRAG + Neo4j",
            auth_enabled=True,
            writer_model=settings.writer_model,
            utility_model=settings.utility_model,
            punctuation_rule="普通对话使用「」，嵌套引号使用『』。",
            query_methods=["local", "global", "drift", "basic"],
        )

    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
        exists = db.scalar(select(User).where(User.email == payload.email))
        if exists is not None:
            raise HTTPException(status_code=409, detail="该邮箱已注册。")
        password_hash, password_salt = hash_password(payload.password)
        user = User(
            email=payload.email,
            display_name=payload.display_name,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return AuthResponse(token=issue_token(user.id), user=UserOut.model_validate(user))

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
        user = db.scalar(select(User).where(User.email == payload.email))
        if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
            raise HTTPException(status_code=401, detail="邮箱或密码错误。")
        return AuthResponse(token=issue_token(user.id), user=UserOut.model_validate(user))

    @app.get("/api/auth/me", response_model=UserOut)
    def me(current_user: User = Depends(get_current_user)) -> UserOut:
        return UserOut.model_validate(current_user)

    @app.get("/api/projects", response_model=list[ProjectOut])
    def list_projects(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[ProjectOut]:
        projects = db.scalars(
            select(Project).where(Project.owner_id == current_user.id).order_by(Project.updated_at.desc())
        ).all()
        return [ProjectOut.model_validate(item) for item in projects]

    @app.post("/api/projects", response_model=ProjectOut)
    def create_project(
        payload: ProjectCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectOut:
        project = Project(
            owner_id=current_user.id,
            title=payload.title,
            genre=payload.genre,
            premise=payload.premise,
            world_brief=payload.world_brief,
            writing_rules=payload.writing_rules,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return ProjectOut.model_validate(project)

    @app.get("/api/projects/{project_id}", response_model=ProjectDetailResponse)
    def project_detail(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectDetailResponse:
        project = _project_or_404(db, current_user.id, project_id)
        generations = db.scalars(
            select(GenerationRun)
            .where(GenerationRun.project_id == project.id)
            .order_by(GenerationRun.created_at.desc())
        ).all()
        return ProjectDetailResponse(
            project=ProjectOut.model_validate(project),
            memories=[MemoryOut.model_validate(item) for item in project.memories],
            sources=[SourceOut.model_validate(item) for item in project.source_documents],
            generations=[GenerationOut.model_validate(item) for item in generations],
        )

    @app.post("/api/projects/{project_id}/memories", response_model=MemoryOut)
    def create_memory(
        project_id: int,
        payload: MemoryCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> MemoryOut:
        project = _project_or_404(db, current_user.id, project_id)
        memory = Memory(
            project=project,
            title=payload.title,
            content=payload.content,
            memory_scope=payload.memory_scope,
            importance=payload.importance,
        )
        db.add(memory)
        project.indexing_status = "stale"
        db.commit()
        db.refresh(memory)
        return MemoryOut.model_validate(memory)

    @app.post("/api/projects/{project_id}/sources", response_model=SourceOut)
    def create_source(
        project_id: int,
        payload: SourceCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> SourceOut:
        project = _project_or_404(db, current_user.id, project_id)
        source = SourceDocument(
            project=project,
            title=payload.title,
            content=payload.content,
            source_kind=payload.source_kind,
        )
        db.add(source)
        project.indexing_status = "stale"
        db.commit()
        db.refresh(source)
        return SourceOut.model_validate(source)

    @app.post("/api/projects/{project_id}/index", response_model=IndexResponse)
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
            db.commit()
            background_tasks.add_task(run_index_job, project.id)

        return IndexResponse(
            status=project.indexing_status,
            workspace_path=record.workspace_path,
            neo4j_sync_status=record.neo4j_sync_status,
        )

    @app.post("/api/projects/{project_id}/generate", response_model=GenerationOut)
    def generate(
        project_id: int,
        payload: GenerateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GenerationOut:
        project = _project_or_404(db, current_user.id, project_id)
        if project.indexing_status != "ready":
            raise HTTPException(status_code=400, detail="项目尚未完成 GraphRAG 索引。")

        graphrag = GraphRAGService(settings)
        local_result = graphrag.query(project, payload.prompt, payload.search_method, payload.response_type)
        global_result = graphrag.query(project, payload.prompt, "global", payload.response_type)

        writer = StoryGenerationService(settings)
        title, summary, content = writer.generate(
            project_title=project.title,
            genre=project.genre,
            premise=project.premise,
            world_brief=project.world_brief,
            writing_rules=project.writing_rules,
            punctuation_rule=project.punctuation_rule,
            user_prompt=payload.prompt,
            local_context=local_result.text,
            global_context=global_result.text,
            memories=[
                {"title": memory.title, "content": memory.content}
                for memory in sorted(project.memories, key=lambda item: item.importance, reverse=True)
            ],
        )

        generation = GenerationRun(
            project=project,
            prompt=payload.prompt,
            search_method=payload.search_method,
            response_type=payload.response_type,
            retrieval_context=f"[Local]\n{local_result.text}\n\n[Global]\n{global_result.text}",
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)
        return GenerationOut.model_validate(generation)

    dist_dir = settings.root_dir / "frontend" / "dist"
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if dist_dir.exists() and (dist_dir / "index.html").exists():

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            requested = dist_dir / full_path
            if full_path and requested.exists() and requested.is_file():
                return FileResponse(requested)
            return FileResponse(dist_dir / "index.html")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
