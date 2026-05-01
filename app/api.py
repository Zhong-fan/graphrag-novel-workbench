from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .auth import (
    create_captcha,
    get_current_user,
    get_optional_user,
    hash_password,
    issue_token,
    verify_captcha,
    verify_password,
)
from .config import load_settings
from .contracts import (
    AuthResponse,
    BootstrapResponse,
    CaptchaChallenge,
    CharacterCardCreateRequest,
    CharacterCardOut,
    CharacterCardUpdateRequest,
    CharacterStateUpdateOut,
    FavoriteToggleResponse,
    GenerateRequest,
    GenerationOut,
    IndexRequest,
    IndexResponse,
    LikeToggleResponse,
    LoginRequest,
    NovelCardOut,
    NovelChapterOut,
    NovelDetailOut,
    MemoryCreateRequest,
    MemoryOut,
    AppendNovelChapterRequest,
    NovelCommentCreateRequest,
    NovelCommentOut,
    PublishNovelRequest,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectOut,
    ProjectUpdateRequest,
    RegisterRequest,
    SourceCreateRequest,
    SourceOut,
    StoryEventOut,
    UpdateNovelChapterRequest,
    UpdateNovelRequest,
    UserOut,
    UserProfileOut,
    UserProfileUpdateRequest,
    WorldPerceptionUpdateOut,
    RelationshipStateUpdateOut,
)
from .db import db_session, get_db, init_db
from .evolution_service import EvolutionService
from .graphrag_service import GraphRAGService, QueryResult
from .models import (
    CharacterCard,
    CharacterStateUpdate,
    GenerationRun,
    GraphWorkspace,
    Memory,
    Novel,
    NovelChapter,
    NovelComment,
    NovelFavorite,
    NovelLike,
    Project,
    RelationshipStateUpdate,
    SourceDocument,
    StoryEvent,
    User,
    UserProfile,
    WorldPerceptionUpdate,
)
from .story_service import StoryGenerationService

logger = logging.getLogger(__name__)


def _username_to_internal_email(username: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    suffix = abs(hash((username, timestamp))) % 100000
    return f"user-{timestamp}-{suffix}@local.invalid"


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


def _mark_project_stale(project: Project) -> None:
    project.indexing_status = "stale"
    if project.graph_workspace is not None:
        project.graph_workspace.neo4j_sync_status = "stale"


def _character_card_or_404(db: Session, project_id: int, card_id: int) -> CharacterCard:
    card = db.scalar(select(CharacterCard).where(CharacterCard.project_id == project_id, CharacterCard.id == card_id))
    if card is None:
        raise HTTPException(status_code=404, detail="人物卡不存在。")
    return card


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.display_name, email=user.email)


def _novel_excerpt(novel: Novel) -> str:
    chapter = sorted(novel.chapters, key=lambda item: item.chapter_no)[0] if novel.chapters else None
    if chapter is not None and chapter.content.strip():
        return chapter.content.strip()[:160]
    if chapter is not None and chapter.summary.strip():
        return chapter.summary.strip()[:160]
    return novel.summary.strip()[:160]


def _novel_card_out(novel: Novel, current_user_id: int | None = None) -> NovelCardOut:
    favorite_user_ids = {item.user_id for item in novel.favorites}
    like_user_ids = {item.user_id for item in novel.likes}
    return NovelCardOut(
        id=novel.id,
        title=novel.title,
        author=novel.author_name,
        summary=novel.summary,
        genre=novel.genre,
        tagline=novel.tagline,
        cover_url=novel.cover_url,
        status=novel.status,
        visibility=novel.visibility,
        likes_count=len(novel.likes),
        favorites_count=len(novel.favorites),
        comments_count=len(novel.comments),
        chapters_count=len(novel.chapters),
        latest_excerpt=_novel_excerpt(novel),
        is_liked=current_user_id in like_user_ids if current_user_id is not None else False,
        is_favorited=current_user_id in favorite_user_ids if current_user_id is not None else False,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
    )


def _novel_detail_out(novel: Novel, current_user_id: int | None = None) -> NovelDetailOut:
    return NovelDetailOut(
        **_novel_card_out(novel, current_user_id=current_user_id).model_dump(),
        chapters=[
            NovelChapterOut.model_validate(chapter)
            for chapter in sorted(novel.chapters, key=lambda item: item.chapter_no)
        ],
    )


def _novel_comment_out(comment: NovelComment) -> NovelCommentOut:
    return NovelCommentOut(
        id=comment.id,
        user_id=comment.user_id,
        username=comment.user.display_name,
        content=comment.content,
        created_at=comment.created_at,
    )


def _character_state_out(item: CharacterStateUpdate) -> CharacterStateUpdateOut:
    return CharacterStateUpdateOut(
        id=item.id,
        character_name=item.character_name,
        emotion_state=item.emotion_state,
        current_goal=item.current_goal,
        self_view_shift=item.self_view_shift,
        public_perception=item.public_perception,
        summary=item.summary,
        created_at=item.created_at,
    )


def _relationship_state_out(item: RelationshipStateUpdate) -> RelationshipStateUpdateOut:
    return RelationshipStateUpdateOut(
        id=item.id,
        source_character=item.source_character,
        target_character=item.target_character,
        change_type=item.change_type,
        direction=item.direction,
        intensity=item.intensity,
        summary=item.summary,
        created_at=item.created_at,
    )


def _story_event_out(item: StoryEvent) -> StoryEventOut:
    try:
        participants = json.loads(item.participants_json)
    except json.JSONDecodeError:
        participants = []
    if not isinstance(participants, list):
        participants = []
    return StoryEventOut(
        id=item.id,
        title=item.title,
        summary=item.summary,
        impact_summary=item.impact_summary,
        participants=[str(participant) for participant in participants],
        location_hint=item.location_hint,
        created_at=item.created_at,
    )


def _world_perception_out(item: WorldPerceptionUpdate) -> WorldPerceptionUpdateOut:
    return WorldPerceptionUpdateOut(
        id=item.id,
        subject_name=item.subject_name,
        observer_group=item.observer_group,
        direction=item.direction,
        change_summary=item.change_summary,
        created_at=item.created_at,
    )


def _generation_or_404(db: Session, project_id: int, generation_id: int) -> GenerationRun:
    generation = db.scalar(
        select(GenerationRun).where(GenerationRun.project_id == project_id, GenerationRun.id == generation_id)
    )
    if generation is None:
        raise HTTPException(status_code=404, detail="生成结果不存在。")
    return generation


def _novel_viewable_or_404(db: Session, novel_id: int, current_user_id: int | None = None) -> Novel:
    novel = db.scalar(
        select(Novel)
        .options(
            selectinload(Novel.owner),
            selectinload(Novel.chapters),
            selectinload(Novel.likes),
            selectinload(Novel.favorites),
            selectinload(Novel.comments),
        )
        .where(Novel.id == novel_id)
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="作品不存在。")
    if novel.visibility != "public" and novel.owner_id != current_user_id:
        raise HTTPException(status_code=404, detail="作品不存在。")
    return novel


def _novel_owned_or_404(db: Session, user_id: int, novel_id: int) -> Novel:
    novel = db.scalar(
        select(Novel)
        .options(
            selectinload(Novel.owner),
            selectinload(Novel.chapters),
            selectinload(Novel.likes),
            selectinload(Novel.favorites),
            selectinload(Novel.comments),
        )
        .where(Novel.id == novel_id, Novel.owner_id == user_id)
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="作品不存在或无权限。")
    return novel


def _ensure_seed_novels(db: Session) -> None:
    published_exists = db.scalar(select(Novel.id).where(Novel.visibility == "public").limit(1))
    if published_exists is not None:
        return

    seed_user = db.scalar(select(User).where(User.display_name == "书城编辑部"))
    if seed_user is None:
        password_hash, password_salt = hash_password("SeedUser123")
        seed_user = User(
            email="seed-bookstore@local.invalid",
            display_name="书城编辑部",
            password_hash=password_hash,
            password_salt=password_salt,
        )
        db.add(seed_user)
        db.flush()

    seed_payloads = [
        {
            "title": "雨停之前的十分钟",
            "genre": "都市情感",
            "tagline": "高架桥下的重逢，像一场迟来的告白。",
            "summary": "一场暴雨把多年未见的两个人重新推回同一片屋檐下。",
            "content": "雨水从广告牌边缘一滴一滴落下来，她撑着伞站在便利店门口，看见那个人从街对面跑来，像从很多年前的傍晚里穿出来。",
        },
        {
            "title": "深蓝地铁终点站",
            "genre": "轻科幻",
            "tagline": "所有错过的人，都在最后一站留下回声。",
            "summary": "一列地铁在城市深夜尽头缓缓停下，把遗失的记忆推回现实。",
            "content": "列车驶入终点站时，车窗外的城市灯光像浸在海里。她听见广播报站，却突然觉得这声音像在叫很久以前的自己。",
        },
        {
            "title": "春天先路过阳台",
            "genre": "治愈日常",
            "tagline": "两个人和一盆快要枯萎的栀子花，慢慢学会重新生活。",
            "summary": "一次普通的照料，让两个人重新学会把生活扶正。",
            "content": "清晨六点，阳光落在洗净的玻璃杯上，像把整个房间擦亮了一遍。她忽然想起，已经很久没有认真看过窗外。",
        },
        {
            "title": "夏夜失物招领",
            "genre": "青春悬疑",
            "tagline": "有人在失物招领处寄存了一封没有收件人的信。",
            "summary": "一封没有署名的信，把平静夏夜撕开了一道口子。",
            "content": "他把信封翻过来时，封口处还带着一点潮湿，像刚从河边的风里带回来。没有名字，没有地址，只有一句手写的『如果你看见月亮，请替我保密。』",
        },
    ]

    for idx, item in enumerate(seed_payloads, start=1):
        novel = Novel(
            owner=seed_user,
            author_name=seed_user.display_name,
            title=item["title"],
            summary=item["summary"],
            genre=item["genre"],
            tagline=item["tagline"],
            status="published",
            visibility="public",
        )
        db.add(novel)
        db.flush()
        db.add(
            NovelChapter(
                novel=novel,
                title=f"第{idx}章",
                summary=item["summary"],
                content=item["content"],
                chapter_no=1,
            )
        )
    db.commit()


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="晨流写作台",
        version="1.0.0",
        description="ChenFlow Workbench：基于 GraphRAG + MySQL + Neo4j + Vue 的中文小说创作工作台。",
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
        with db_session() as db:
            _ensure_seed_novels(db)

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
                graphrag.index_project(
                    project,
                    list(project.memories),
                    list(project.source_documents),
                    record,
                    character_cards=list(project.character_cards),
                    character_updates=list(project.character_state_updates),
                    relationship_updates=list(project.relationship_state_updates),
                    story_events=list(project.story_events),
                    world_updates=list(project.world_perception_updates),
                )
                project.indexing_status = "ready"
                record.neo4j_sync_status = "synced"
                record.last_indexed_at = datetime.utcnow()
                db.commit()
            except Exception:
                logger.exception("Background GraphRAG index failed for project_id=%s", project_id)
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
            service_name="晨流写作台",
            graph_engine="GraphRAG + Neo4j",
            auth_enabled=True,
            writer_model=settings.writer_model,
            utility_model=settings.utility_model,
            embedding_model=settings.embedding_model,
            embedding_provider=settings.embedding_provider_label,
            embedding_base_url=settings.embedding_base_url,
            punctuation_rule="普通对话使用「」，嵌套引号使用『』。",
            query_methods=["local", "global", "drift", "basic"],
        )

    @app.get("/api/auth/captcha", response_model=CaptchaChallenge)
    def auth_captcha() -> CaptchaChallenge:
        return CaptchaChallenge(**create_captcha())

    @app.post("/api/auth/register", response_model=AuthResponse)
    def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
        if not verify_captcha(payload.captcha_answer, payload.captcha_token):
            raise HTTPException(status_code=400, detail="验证码错误或已过期。")

        username = payload.username.strip()
        exists = db.scalar(select(User).where(User.display_name == username))
        if exists is not None:
            raise HTTPException(status_code=409, detail="用户名已存在。")

        password_hash, password_salt = hash_password(payload.password)
        user = User(
            email=_username_to_internal_email(username),
            display_name=username,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return AuthResponse(token=issue_token(user.id), user=_user_out(user))

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
        username = payload.username.strip()
        user = db.scalar(select(User).where(User.display_name == username))
        if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
            raise HTTPException(status_code=401, detail="用户名或密码错误。")
        return AuthResponse(token=issue_token(user.id), user=_user_out(user))

    @app.get("/api/auth/me", response_model=UserOut)
    def me(current_user: User = Depends(get_current_user)) -> UserOut:
        return _user_out(current_user)

    @app.get("/api/me/profile", response_model=UserProfileOut)
    def my_profile(current_user: User = Depends(get_current_user)) -> UserProfileOut:
        profile = current_user.profile
        if profile is None:
            return UserProfileOut(bio="", email=None, phone=None)
        return UserProfileOut(bio=profile.bio, email=profile.email, phone=profile.phone)

    @app.put("/api/me/profile", response_model=UserProfileOut)
    def update_my_profile(
        payload: UserProfileUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> UserProfileOut:
        profile = current_user.profile
        if profile is None:
            profile = UserProfile(user=current_user, bio="", email=None, phone=None)
            db.add(profile)

        profile.bio = payload.bio.strip()
        profile.email = payload.email.strip() if payload.email and payload.email.strip() else None
        profile.phone = payload.phone.strip() if payload.phone and payload.phone.strip() else None
        db.commit()
        db.refresh(profile)
        return UserProfileOut(bio=profile.bio, email=profile.email, phone=profile.phone)

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
            style_profile=payload.style_profile,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return ProjectOut.model_validate(project)

    @app.put("/api/projects/{project_id}", response_model=ProjectOut)
    def update_project(
        project_id: int,
        payload: ProjectUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectOut:
        project = _project_or_404(db, current_user.id, project_id)
        project.title = payload.title.strip()
        project.genre = payload.genre.strip()
        project.premise = payload.premise.strip()
        project.world_brief = payload.world_brief.strip()
        project.writing_rules = payload.writing_rules.strip()
        project.style_profile = payload.style_profile
        _mark_project_stale(project)
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
            select(GenerationRun).where(GenerationRun.project_id == project.id).order_by(GenerationRun.created_at.desc())
        ).all()
        character_updates = db.scalars(
            select(CharacterStateUpdate)
            .where(CharacterStateUpdate.project_id == project.id)
            .order_by(CharacterStateUpdate.created_at.desc())
        ).all()
        relationship_updates = db.scalars(
            select(RelationshipStateUpdate)
            .where(RelationshipStateUpdate.project_id == project.id)
            .order_by(RelationshipStateUpdate.created_at.desc())
        ).all()
        story_events = db.scalars(
            select(StoryEvent).where(StoryEvent.project_id == project.id).order_by(StoryEvent.created_at.desc())
        ).all()
        world_updates = db.scalars(
            select(WorldPerceptionUpdate)
            .where(WorldPerceptionUpdate.project_id == project.id)
            .order_by(WorldPerceptionUpdate.created_at.desc())
        ).all()
        return ProjectDetailResponse(
            project=ProjectOut.model_validate(project),
            memories=[MemoryOut.model_validate(item) for item in project.memories],
            character_cards=[CharacterCardOut.model_validate(item) for item in project.character_cards],
            sources=[SourceOut.model_validate(item) for item in project.source_documents],
            generations=[GenerationOut.model_validate(item) for item in generations],
            character_state_updates=[_character_state_out(item) for item in character_updates[:20]],
            relationship_state_updates=[_relationship_state_out(item) for item in relationship_updates[:20]],
            story_events=[_story_event_out(item) for item in story_events[:20]],
            world_perception_updates=[_world_perception_out(item) for item in world_updates[:20]],
        )

    @app.get("/api/novels", response_model=list[NovelCardOut])
    def list_novels(
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> list[NovelCardOut]:
        novels = db.scalars(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.visibility == "public")
            .order_by(Novel.updated_at.desc())
        ).unique().all()
        current_user_id = current_user.id if current_user is not None else None
        return [_novel_card_out(item, current_user_id=current_user_id) for item in novels]

    @app.get("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def novel_detail(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> NovelDetailOut:
        current_user_id = current_user.id if current_user is not None else None
        novel = _novel_viewable_or_404(db, novel_id, current_user_id=current_user_id)
        return _novel_detail_out(novel, current_user_id=current_user_id)

    @app.get("/api/me/favorites", response_model=list[NovelCardOut])
    def my_favorites(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[NovelCardOut]:
        favorites = db.scalars(
            select(NovelFavorite)
            .options(
                selectinload(NovelFavorite.novel).selectinload(Novel.owner),
                selectinload(NovelFavorite.novel).selectinload(Novel.chapters),
                selectinload(NovelFavorite.novel).selectinload(Novel.likes),
                selectinload(NovelFavorite.novel).selectinload(Novel.favorites),
                selectinload(NovelFavorite.novel).selectinload(Novel.comments),
            )
            .where(NovelFavorite.user_id == current_user.id)
            .order_by(NovelFavorite.created_at.desc())
        ).all()
        novels = [item.novel for item in favorites if item.novel.visibility == "public"]
        return [_novel_card_out(item, current_user_id=current_user.id) for item in novels]

    @app.get("/api/me/novels", response_model=list[NovelCardOut])
    def my_novels(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[NovelCardOut]:
        novels = db.scalars(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.owner_id == current_user.id)
            .order_by(Novel.updated_at.desc())
        ).unique().all()
        return [_novel_card_out(item, current_user_id=current_user.id) for item in novels]

    @app.post("/api/novels/{novel_id}/favorite", response_model=FavoriteToggleResponse)
    def create_favorite(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> FavoriteToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        exists = db.scalar(
            select(NovelFavorite).where(NovelFavorite.novel_id == novel_id, NovelFavorite.user_id == current_user.id)
        )
        if exists is None:
            db.add(NovelFavorite(novel=novel, user=current_user))
            db.commit()
            db.refresh(novel)
        return FavoriteToggleResponse(
            favorited=True,
            novel_id=novel.id,
            favorites_count=len(novel.favorites),
        )

    @app.delete("/api/novels/{novel_id}/favorite", response_model=FavoriteToggleResponse)
    def delete_favorite(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> FavoriteToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        favorite = db.scalar(
            select(NovelFavorite).where(NovelFavorite.novel_id == novel_id, NovelFavorite.user_id == current_user.id)
        )
        if favorite is not None:
            db.delete(favorite)
            db.commit()
            db.refresh(novel)
        return FavoriteToggleResponse(
            favorited=False,
            novel_id=novel.id,
            favorites_count=len(novel.favorites),
        )

    @app.post("/api/novels/{novel_id}/like", response_model=LikeToggleResponse)
    def create_like(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> LikeToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        exists = db.scalar(select(NovelLike).where(NovelLike.novel_id == novel_id, NovelLike.user_id == current_user.id))
        if exists is None:
            db.add(NovelLike(novel=novel, user=current_user))
            db.commit()
            db.refresh(novel)
        return LikeToggleResponse(
            liked=True,
            novel_id=novel.id,
            likes_count=len(novel.likes),
        )

    @app.delete("/api/novels/{novel_id}/like", response_model=LikeToggleResponse)
    def delete_like(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> LikeToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        like = db.scalar(select(NovelLike).where(NovelLike.novel_id == novel_id, NovelLike.user_id == current_user.id))
        if like is not None:
            db.delete(like)
            db.commit()
            db.refresh(novel)
        return LikeToggleResponse(
            liked=False,
            novel_id=novel.id,
            likes_count=len(novel.likes),
        )

    @app.get("/api/novels/{novel_id}/comments", response_model=list[NovelCommentOut])
    def list_novel_comments(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> list[NovelCommentOut]:
        current_user_id = current_user.id if current_user is not None else None
        _novel_viewable_or_404(db, novel_id, current_user_id=current_user_id)
        comments = db.scalars(
            select(NovelComment)
            .options(selectinload(NovelComment.user))
            .where(NovelComment.novel_id == novel_id)
            .order_by(NovelComment.created_at.desc())
        ).all()
        return [_novel_comment_out(item) for item in comments]

    @app.post("/api/novels/{novel_id}/comments", response_model=NovelCommentOut)
    def create_novel_comment(
        novel_id: int,
        payload: NovelCommentCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelCommentOut:
        novel = _novel_viewable_or_404(db, novel_id, current_user_id=current_user.id)
        comment = NovelComment(
            novel=novel,
            user=current_user,
            content=payload.content.strip(),
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)
        db.refresh(novel)
        return _novel_comment_out(comment)

    @app.post("/api/novels/from-generation", response_model=NovelDetailOut)
    def publish_novel_from_generation(
        payload: PublishNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        project = _project_or_404(db, current_user.id, payload.project_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)

        novel = Novel(
            owner=current_user,
            author_name=payload.author_name.strip(),
            title=payload.title.strip(),
            summary=payload.summary.strip() or generation.summary,
            genre=project.genre,
            tagline=payload.tagline.strip(),
            status="published",
            visibility=payload.visibility,
        )
        db.add(novel)
        db.flush()

        chapter_title = payload.chapter_title.strip() or generation.title.strip() or "第一章"
        chapter_summary = payload.chapter_summary.strip() or generation.summary
        chapter_content = payload.chapter_content.strip() or generation.content
        db.add(
            NovelChapter(
                novel=novel,
                title=chapter_title,
                summary=chapter_summary,
                content=chapter_content,
                chapter_no=payload.chapter_no,
            )
        )
        db.commit()

        created = db.scalar(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.id == novel.id)
        )
        if created is None:
            raise HTTPException(status_code=500, detail="作品发布失败。")
        return _novel_detail_out(created, current_user_id=current_user.id)

    @app.put("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def update_novel(
        novel_id: int,
        payload: UpdateNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        novel.title = payload.title.strip()
        novel.author_name = payload.author_name.strip()
        novel.summary = payload.summary.strip()
        novel.tagline = payload.tagline.strip()
        novel.visibility = payload.visibility
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

    @app.post("/api/novels/{novel_id}/chapters/from-generation", response_model=NovelDetailOut)
    def append_novel_chapter_from_generation(
        novel_id: int,
        payload: AppendNovelChapterRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        project = _project_or_404(db, current_user.id, payload.project_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)
        next_chapter_no = payload.chapter_no or max((item.chapter_no for item in novel.chapters), default=0) + 1
        if any(item.chapter_no == next_chapter_no for item in novel.chapters):
            raise HTTPException(status_code=409, detail=f"第 {next_chapter_no} 章已经存在。")

        db.add(
            NovelChapter(
                novel=novel,
                title=payload.title.strip() or generation.title.strip() or f"第{next_chapter_no}章",
                summary=payload.summary.strip() or generation.summary,
                content=payload.content.strip() or generation.content,
                chapter_no=next_chapter_no,
            )
        )
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

    @app.put("/api/novels/{novel_id}/chapters/{chapter_id}", response_model=NovelDetailOut)
    def update_novel_chapter(
        novel_id: int,
        chapter_id: int,
        payload: UpdateNovelChapterRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        chapter = next((item for item in novel.chapters if item.id == chapter_id), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        if any(item.id != chapter_id and item.chapter_no == payload.chapter_no for item in novel.chapters):
            raise HTTPException(status_code=409, detail=f"第 {payload.chapter_no} 章已经存在。")

        chapter.title = payload.title.strip()
        chapter.summary = payload.summary.strip()
        chapter.content = payload.content.strip()
        chapter.chapter_no = payload.chapter_no
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

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
        _mark_project_stale(project)
        db.commit()
        db.refresh(memory)
        return MemoryOut.model_validate(memory)

    @app.post("/api/projects/{project_id}/character-cards", response_model=CharacterCardOut)
    def create_character_card(
        project_id: int,
        payload: CharacterCardCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> CharacterCardOut:
        project = _project_or_404(db, current_user.id, project_id)
        card = CharacterCard(
            project=project,
            name=payload.name.strip(),
            age=payload.age.strip(),
            gender=payload.gender.strip(),
            personality=payload.personality.strip(),
            story_role=payload.story_role.strip(),
            background=payload.background.strip(),
        )
        db.add(card)
        _mark_project_stale(project)
        db.commit()
        db.refresh(card)
        return CharacterCardOut.model_validate(card)

    @app.put("/api/projects/{project_id}/character-cards/{card_id}", response_model=CharacterCardOut)
    def update_character_card(
        project_id: int,
        card_id: int,
        payload: CharacterCardUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> CharacterCardOut:
        project = _project_or_404(db, current_user.id, project_id)
        card = _character_card_or_404(db, project.id, card_id)
        card.name = payload.name.strip()
        card.age = payload.age.strip()
        card.gender = payload.gender.strip()
        card.personality = payload.personality.strip()
        card.story_role = payload.story_role.strip()
        card.background = payload.background.strip()
        _mark_project_stale(project)
        db.commit()
        db.refresh(card)
        return CharacterCardOut.model_validate(card)

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
        _mark_project_stale(project)
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

        graphrag = GraphRAGService(settings)
        can_use_retrieval = project.indexing_status == "ready"
        local_result = (
            graphrag.query(project, payload.prompt, payload.search_method, payload.response_type)
            if can_use_retrieval
            else QueryResult(
                method="direct",
                response_type=payload.response_type,
                text="资料库尚未整理，本次仅根据项目设定和用户输入直接创作。",
            )
        )
        global_result = None
        if payload.use_global_search and can_use_retrieval:
            global_result = graphrag.query(project, payload.prompt, "global", payload.response_type)
        recent_character_updates = db.scalars(
            select(CharacterStateUpdate)
            .where(CharacterStateUpdate.project_id == project.id)
            .order_by(CharacterStateUpdate.created_at.desc())
        ).all()
        recent_relationship_updates = db.scalars(
            select(RelationshipStateUpdate)
            .where(RelationshipStateUpdate.project_id == project.id)
            .order_by(RelationshipStateUpdate.created_at.desc())
        ).all()
        recent_story_events = db.scalars(
            select(StoryEvent).where(StoryEvent.project_id == project.id).order_by(StoryEvent.created_at.desc())
        ).all()
        recent_world_updates = db.scalars(
            select(WorldPerceptionUpdate)
            .where(WorldPerceptionUpdate.project_id == project.id)
            .order_by(WorldPerceptionUpdate.created_at.desc())
        ).all()

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
                    {
                        "title": item.title,
                        "impact_summary": item.impact_summary,
                    }
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
        title, summary, content = writer.generate(
            project_title=project.title,
            genre=project.genre,
            premise=project.premise,
            world_brief=project.world_brief,
            writing_rules=project.writing_rules,
            style_profile=project.style_profile,
            user_prompt=payload.prompt,
            scene_card=scene_card,
            memories=[
                {"title": memory.title, "content": memory.content}
                for memory in sorted(project.memories, key=lambda item: item.importance, reverse=True)
            ],
            use_refiner=payload.use_refiner,
        )

        generation = GenerationRun(
            project=project,
            prompt=payload.prompt,
            search_method=payload.search_method,
            response_type=payload.response_type,
            retrieval_context=(
                f"[Local]\n{local_result.text}\n\n[Global]\n{global_result.text}"
                if global_result is not None
                else f"[Local]\n{local_result.text}\n\n[Global]\n未启用全局检索。"
            ),
            scene_card=scene_card,
            evolution_snapshot="",
            title=title,
            summary=summary,
            content=content,
        )
        db.add(generation)
        db.commit()
        db.refresh(generation)

        if payload.write_evolution:
            evolution_payload = evolution.extract_evolution(
                project_title=project.title,
                genre=project.genre,
                premise=project.premise,
                user_prompt=payload.prompt,
                title=title,
                summary=summary,
                content=content,
            )
        else:
            evolution_payload = evolution.empty_payload()

        for item in evolution_payload.characters:
            if not item.character_name:
                continue
            db.add(
                CharacterStateUpdate(
                    project=project,
                    generation_run=generation,
                    character_name=item.character_name,
                    emotion_state=item.emotion_state,
                    current_goal=item.current_goal,
                    self_view_shift=item.self_view_shift,
                    public_perception=item.public_perception,
                    summary=item.summary,
                )
            )

        for item in evolution_payload.relationships:
            if not item.source_character or not item.target_character:
                continue
            db.add(
                RelationshipStateUpdate(
                    project=project,
                    generation_run=generation,
                    source_character=item.source_character,
                    target_character=item.target_character,
                    change_type=item.change_type,
                    direction=item.direction,
                    intensity=item.intensity,
                    summary=item.summary,
                )
            )

        for item in evolution_payload.events:
            if not item.title:
                continue
            db.add(
                StoryEvent(
                    project=project,
                    generation_run=generation,
                    title=item.title,
                    summary=item.summary,
                    impact_summary=item.impact_summary,
                    participants_json=json.dumps(item.participants, ensure_ascii=False),
                    location_hint=item.location_hint,
                )
            )

        for item in evolution_payload.world_updates:
            if not item.subject_name or not item.observer_group:
                continue
            db.add(
                WorldPerceptionUpdate(
                    project=project,
                    generation_run=generation,
                    subject_name=item.subject_name,
                    observer_group=item.observer_group,
                    direction=item.direction,
                    change_summary=item.change_summary,
                )
            )

        generation.evolution_snapshot = json.dumps(
            {
                "characters": [
                    {
                        "character_name": item.character_name,
                        "emotion_state": item.emotion_state,
                        "current_goal": item.current_goal,
                        "self_view_shift": item.self_view_shift,
                        "public_perception": item.public_perception,
                        "summary": item.summary,
                    }
                    for item in evolution_payload.characters
                ],
                "relationships": [
                    {
                        "source_character": item.source_character,
                        "target_character": item.target_character,
                        "change_type": item.change_type,
                        "direction": item.direction,
                        "intensity": item.intensity,
                        "summary": item.summary,
                    }
                    for item in evolution_payload.relationships
                ],
                "events": [
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "impact_summary": item.impact_summary,
                        "participants": item.participants,
                        "location_hint": item.location_hint,
                    }
                    for item in evolution_payload.events
                ],
                "world_updates": [
                    {
                        "subject_name": item.subject_name,
                        "observer_group": item.observer_group,
                        "direction": item.direction,
                        "change_summary": item.change_summary,
                    }
                    for item in evolution_payload.world_updates
                ],
            },
            ensure_ascii=False,
        )
        db.commit()
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
