from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
    DeleteCharacterCardRequest,
    DeleteNovelRequest,
    DeleteProjectRequest,
    FavoriteToggleResponse,
    GenerateRequest,
    GenerationOut,
    GenerationProgressOut,
    GraphReviewFileOut,
    GraphReviewFileUpdateRequest,
    GraphReviewOut,
    IndexRequest,
    IndexResponse,
    LikeToggleResponse,
    LoginRequest,
    MoveProjectFolderRequest,
    MyWorkspaceOut,
    NovelCardOut,
    NovelChapterOut,
    NovelDetailOut,
    MemoryCreateRequest,
    MemoryOut,
    AppendNovelChapterRequest,
    NovelCommentCreateRequest,
    NovelCommentOut,
    ProjectFolderCreateRequest,
    ProjectFolderOut,
    CharacterCardOut,
    CharacterCardUpdateRequest,
    PublishNovelRequest,
    ProjectChapterCreateRequest,
    ProjectChapterOut,
    ProjectChapterUpdateRequest,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectOut,
    ProjectUpdateRequest,
    RegisterRequest,
    RestoreTrashItemRequest,
    SourceCreateRequest,
    SourceOut,
    StoryEventOut,
    TrashItemOut,
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
    ProjectChapter,
    ProjectFolder,
    RelationshipStateUpdate,
    SourceDocument,
    StoryEvent,
    User,
    UserProfile,
    WorldPerceptionUpdate,
)
from .story_service import StoryGenerationService

logger = logging.getLogger(__name__)
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def _china_timestamp() -> str:
    return datetime.now(CHINA_TZ).isoformat(timespec="seconds")


GENERATION_PROGRESS: dict[int, dict[str, object]] = {}


def _username_to_internal_email(username: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    suffix = abs(hash((username, timestamp))) % 100000
    return f"user-{timestamp}-{suffix}@local.invalid"


def _project_or_404(db: Session, user_id: int, project_id: int) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    return project


def _project_chapter_or_404(db: Session, project_id: int, chapter_id: int) -> ProjectChapter:
    chapter = db.scalar(
        select(ProjectChapter).where(
            ProjectChapter.project_id == project_id,
            ProjectChapter.id == chapter_id,
        )
    )
    if chapter is None:
        raise HTTPException(status_code=404, detail="章节不存在。")
    return chapter


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


def _graph_review_out(project: Project) -> GraphReviewOut | None:
    record = project.graph_workspace
    if record is None:
        return None
    workspace = Path(record.workspace_path)
    settings = load_settings()
    service = GraphRAGService(settings)
    if not (workspace / "input").exists():
        return GraphReviewOut(
            workspace_path=record.workspace_path,
            input_files=[],
            files=[],
            preview_text="",
            neo4j_sync_status=record.neo4j_sync_status,
            last_indexed_at=record.last_indexed_at,
        )
    payload = service.review_payload(workspace)
    return GraphReviewOut(
        workspace_path=record.workspace_path,
        input_files=payload["input_files"],
        files=[GraphReviewFileOut(**item) for item in payload["files"]],
        preview_text=payload["preview_text"],
        neo4j_sync_status=record.neo4j_sync_status,
        last_indexed_at=record.last_indexed_at,
    )


def _character_card_or_404(db: Session, project_id: int, card_id: int) -> CharacterCard:
    card = db.scalar(
        select(CharacterCard).where(
            CharacterCard.project_id == project_id,
            CharacterCard.id == card_id,
            CharacterCard.deleted_at.is_(None),
        )
    )
    if card is None:
        raise HTTPException(status_code=404, detail="人物卡不存在。")
    return card


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.display_name, email=user.email)


def _ensure_default_folder(db: Session, user: User) -> ProjectFolder:
    folder = db.scalar(
        select(ProjectFolder).where(ProjectFolder.user_id == user.id, ProjectFolder.is_default.is_(True)).limit(1)
    )
    if folder is not None:
        return folder

    folder = ProjectFolder(user=user, name="默认文件夹", sort_order=0, is_default=True)
    db.add(folder)
    db.flush()
    return folder


def _folder_out(folder: ProjectFolder) -> ProjectFolderOut:
    return ProjectFolderOut(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        is_default=folder.is_default,
        project_count=sum(1 for item in folder.projects if item.deleted_at is None),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _trash_items_for_user(db: Session, user_id: int) -> list[TrashItemOut]:
    items: list[TrashItemOut] = []

    deleted_projects = db.scalars(
        select(Project).where(Project.owner_id == user_id, Project.deleted_at.is_not(None)).order_by(Project.deleted_at.desc())
    ).all()
    for item in deleted_projects:
        items.append(
            TrashItemOut(
                item_type="project",
                item_id=item.id,
                title=item.title,
                subtitle=item.genre,
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.id,
            )
        )

    deleted_novels = db.scalars(
        select(Novel).where(Novel.owner_id == user_id, Novel.deleted_at.is_not(None)).order_by(Novel.deleted_at.desc())
    ).all()
    for item in deleted_novels:
        items.append(
            TrashItemOut(
                item_type="novel",
                item_id=item.id,
                title=item.title,
                subtitle=item.genre,
                deleted_at=item.deleted_at or item.updated_at,
            )
        )

    deleted_cards = db.scalars(
        select(CharacterCard)
        .join(Project, CharacterCard.project_id == Project.id)
        .where(Project.owner_id == user_id, CharacterCard.deleted_at.is_not(None))
        .order_by(CharacterCard.deleted_at.desc())
    ).all()
    for item in deleted_cards:
        items.append(
            TrashItemOut(
                item_type="character_card",
                item_id=item.id,
                title=item.name,
                subtitle=item.story_role,
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.project_id,
            )
        )

    items.sort(key=lambda item: item.deleted_at, reverse=True)
    return items


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
        project_id=novel.project_id,
        source_generation_id=novel.source_generation_id,
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


def _snapshot_with_process(evolution_payload, process: dict) -> str:
    return json.dumps(
        {
            "process": process,
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


def _build_generation_trace(
    *,
    project: Project,
    project_chapter: ProjectChapter,
    payload: GenerateRequest,
) -> dict[str, object]:
    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "genre": project.genre,
        },
        "chapter": {
            "id": project_chapter.id,
            "chapter_no": project_chapter.chapter_no,
            "title": project_chapter.title,
            "premise": project_chapter.premise,
        },
        "request": {
            "prompt": payload.prompt,
            "search_method": payload.search_method,
            "response_type": payload.response_type,
            "use_global_search": payload.use_global_search,
            "use_scene_card": payload.use_scene_card,
            "use_refiner": payload.use_refiner,
            "write_evolution": payload.write_evolution,
        },
        "context": {},
        "steps": {},
    }


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
        .where(Novel.id == novel_id, Novel.deleted_at.is_(None))
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
        .where(Novel.id == novel_id, Novel.owner_id == user_id, Novel.deleted_at.is_(None))
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="作品不存在或无权限。")
    return novel


def _ensure_seed_novels(db: Session) -> None:
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
            "title": "晚一点下雨的城市",
            "genre": "都市情感",
            "tagline": "天气预报总在推迟，很多没说出口的话也是。",
            "summary": "回到旧城后的那个夏天，她在反复延后的雨里，再次遇见多年未见的人。",
            "content": "傍晚的风先一步穿过高架桥底，把便利店门口的塑料帘吹得轻轻作响。她站在檐下等雨，看见街对面有人沿着亮起来的斑马线慢慢走近，像从很久以前那段并不清晰的夏天里重新显影出来。",
        },
        {
            "title": "海雾停在末班车后",
            "genre": "轻科幻",
            "tagline": "有些记忆不像闪回，更像列车进站前玻璃上的一层雾。",
            "summary": "深夜地铁停进终点站时，一个总在同一节车厢出现的陌生人，开始把她带回一段被自己主动忘掉的过去。",
            "content": "列车减速时，车窗外的灯光被潮湿空气晕开，远远看去像浮在海面上。广播报出终点站名，她抬起头，正好看见对面玻璃里那个人的倒影，安静得像已经在那里等了很多天。",
        },
        {
            "title": "春天先落在阳台上",
            "genre": "治愈日常",
            "tagline": "生活没有一下子变好，只是光重新照进了房间。",
            "summary": "搬进旧公寓后，她和隔壁安静的住户因为轮流照看一排植物，慢慢把各自散乱的生活重新扶正。",
            "content": "清晨六点多，阳光先落在阳台边缘，再慢慢移到洗净的玻璃杯上。她给土有些发硬的栀子浇水时，隔壁窗户正好被推开，风带来一点潮湿的青草味，整栋楼像因此轻了一些。",
        },
        {
            "title": "夏夜失物招领处",
            "genre": "青春悬疑",
            "tagline": "没有署名的信，比大声说出口的话更让人无法回避。",
            "summary": "暑假在车站做值班志愿者时，他收到一封存放在失物招领处、却没有收件人的信，信里的线索把几个熟悉的人重新连到了一起。",
            "content": "他把那只浅灰色信封拿起来时，纸面还带着一点夜风留下的潮气。候车厅已经没有多少人，顶灯把地砖照得发白，只有信封背面那行很轻的字在灯下显得格外清楚: 如果你今晚看见月亮，请先不要告诉别人。",
        },
    ]

    for idx, item in enumerate(seed_payloads, start=1):
        novel = db.scalar(
            select(Novel).where(
                Novel.owner_id == seed_user.id,
                Novel.title == item["title"],
                Novel.visibility == "public",
                Novel.deleted_at.is_(None),
            )
        )
        if novel is None:
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
        else:
            novel.author_name = seed_user.display_name
            novel.summary = item["summary"]
            novel.genre = item["genre"]
            novel.tagline = item["tagline"]
            novel.status = "published"
            novel.visibility = "public"
            novel.deleted_at = None

        chapter = db.scalar(
            select(NovelChapter).where(
                NovelChapter.novel_id == novel.id,
                NovelChapter.chapter_no == 1,
            )
        )
        if chapter is None:
            db.add(
                NovelChapter(
                    novel=novel,
                    title=f"第{idx}章",
                    summary=item["summary"],
                    content=item["content"],
                    chapter_no=1,
                )
            )
        else:
            chapter.title = f"第{idx}章"
            chapter.summary = item["summary"]
            chapter.content = item["content"]
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
        _ensure_default_folder(db, current_user)
        db.commit()
        projects = db.scalars(
            select(Project)
            .where(Project.owner_id == current_user.id, Project.deleted_at.is_(None))
            .order_by(Project.updated_at.desc())
        ).all()
        return [ProjectOut.model_validate(item) for item in projects]

    @app.get("/api/me/workspace", response_model=MyWorkspaceOut)
    def my_workspace(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> MyWorkspaceOut:
        default_folder = _ensure_default_folder(db, current_user)
        projects = db.scalars(
            select(Project)
            .where(Project.owner_id == current_user.id, Project.deleted_at.is_(None))
            .order_by(Project.updated_at.desc())
        ).all()
        folders = db.scalars(
            select(ProjectFolder).where(ProjectFolder.user_id == current_user.id).order_by(ProjectFolder.sort_order.asc(), ProjectFolder.created_at.asc())
        ).all()
        for project in projects:
            if project.folder_id is None:
                project.folder = default_folder
        db.commit()
        return MyWorkspaceOut(
            folders=[_folder_out(item) for item in folders],
            projects=[ProjectOut.model_validate(item) for item in projects],
            trash=_trash_items_for_user(db, current_user.id),
        )

    @app.post("/api/me/folders", response_model=ProjectFolderOut)
    def create_project_folder(
        payload: ProjectFolderCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectFolderOut:
        _ensure_default_folder(db, current_user)
        name = payload.name.strip()
        exists = db.scalar(select(ProjectFolder).where(ProjectFolder.user_id == current_user.id, ProjectFolder.name == name))
        if exists is not None:
            raise HTTPException(status_code=409, detail="文件夹名称已存在。")
        max_order = db.scalar(select(ProjectFolder.sort_order).where(ProjectFolder.user_id == current_user.id).order_by(ProjectFolder.sort_order.desc()).limit(1))
        folder = ProjectFolder(user=current_user, name=name, sort_order=(max_order or 0) + 1, is_default=False)
        db.add(folder)
        db.commit()
        db.refresh(folder)
        return _folder_out(folder)

    @app.post("/api/projects", response_model=ProjectOut)
    def create_project(
        payload: ProjectCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectOut:
        default_folder = _ensure_default_folder(db, current_user)
        project = Project(
            owner_id=current_user.id,
            folder=default_folder,
            title=payload.title,
            genre=payload.genre,
            world_brief=payload.world_brief,
            writing_rules=payload.writing_rules,
            style_profile=payload.style_profile,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return ProjectOut.model_validate(project)

    @app.put("/api/projects/{project_id}/folder", response_model=ProjectOut)
    def move_project_to_folder(
        project_id: int,
        payload: MoveProjectFolderRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectOut:
        project = _project_or_404(db, current_user.id, project_id)
        folder = None
        if payload.folder_id is None:
            folder = _ensure_default_folder(db, current_user)
        else:
            folder = db.scalar(
                select(ProjectFolder).where(ProjectFolder.user_id == current_user.id, ProjectFolder.id == payload.folder_id)
            )
            if folder is None:
                raise HTTPException(status_code=404, detail="文件夹不存在。")
        project.folder = folder
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
        project.world_brief = payload.world_brief.strip()
        project.writing_rules = payload.writing_rules.strip()
        project.style_profile = payload.style_profile
        _mark_project_stale(project)
        db.commit()
        db.refresh(project)
        return ProjectOut.model_validate(project)

    @app.post("/api/projects/{project_id}/chapters", response_model=ProjectChapterOut)
    def create_project_chapter(
        project_id: int,
        payload: ProjectChapterCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectChapterOut:
        project = _project_or_404(db, current_user.id, project_id)
        chapter_no = payload.chapter_no or (max((item.chapter_no for item in project.project_chapters), default=0) + 1)
        if any(item.chapter_no == chapter_no for item in project.project_chapters):
            raise HTTPException(status_code=409, detail=f"第 {chapter_no} 章已经存在。")
        chapter = ProjectChapter(
            project=project,
            title=payload.title.strip(),
            premise=payload.premise.strip(),
            chapter_no=chapter_no,
        )
        db.add(chapter)
        _mark_project_stale(project)
        db.commit()
        db.refresh(chapter)
        return ProjectChapterOut.model_validate(chapter)

    @app.put("/api/projects/{project_id}/chapters/{chapter_id}", response_model=ProjectChapterOut)
    def update_project_chapter(
        project_id: int,
        chapter_id: int,
        payload: ProjectChapterUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectChapterOut:
        project = _project_or_404(db, current_user.id, project_id)
        chapter = _project_chapter_or_404(db, project.id, chapter_id)
        if any(item.id != chapter.id and item.chapter_no == payload.chapter_no for item in project.project_chapters):
            raise HTTPException(status_code=409, detail=f"第 {payload.chapter_no} 章已经存在。")
        chapter.title = payload.title.strip()
        chapter.premise = payload.premise.strip()
        chapter.chapter_no = payload.chapter_no
        _mark_project_stale(project)
        db.commit()
        db.refresh(chapter)
        return ProjectChapterOut.model_validate(chapter)

    @app.delete("/api/projects/{project_id}", response_model=ProjectOut)
    def delete_project(
        project_id: int,
        payload: DeleteProjectRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ProjectOut:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == current_user.id))
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        if payload.hard_delete:
            db.delete(project)
            db.commit()
            return ProjectOut.model_validate(project)
        project.deleted_at = datetime.utcnow()
        db.commit()
        db.refresh(project)
        return ProjectOut.model_validate(project)

    @app.post("/api/trash/{item_id}/restore")
    def restore_trash_item(
        item_id: int,
        payload: RestoreTrashItemRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict[str, object]:
        if payload.item_type == "project":
            item = db.scalar(select(Project).where(Project.id == item_id, Project.owner_id == current_user.id))
            if item is None:
                raise HTTPException(status_code=404, detail="项目不存在。")
            item.deleted_at = None
            if item.folder_id is None:
                item.folder = _ensure_default_folder(db, current_user)
        elif payload.item_type == "novel":
            item = db.scalar(select(Novel).where(Novel.id == item_id, Novel.owner_id == current_user.id))
            if item is None:
                raise HTTPException(status_code=404, detail="作品不存在。")
            item.deleted_at = None
        else:
            item = db.scalar(
                select(CharacterCard)
                .join(Project, CharacterCard.project_id == Project.id)
                .where(CharacterCard.id == item_id, Project.owner_id == current_user.id)
            )
            if item is None:
                raise HTTPException(status_code=404, detail="人物卡不存在。")
            item.deleted_at = None
        db.commit()
        return {"status": "restored"}

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
            project_chapters=[
                ProjectChapterOut.model_validate(item) for item in sorted(project.project_chapters, key=lambda chapter: chapter.chapter_no)
            ],
            memories=[MemoryOut.model_validate(item) for item in project.memories],
            character_cards=[
                CharacterCardOut.model_validate(item) for item in project.character_cards if item.deleted_at is None
            ],
            sources=[SourceOut.model_validate(item) for item in project.source_documents],
            generations=[GenerationOut.model_validate(item) for item in generations],
            graphrag_review=_graph_review_out(project),
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
            .where(Novel.visibility == "public", Novel.deleted_at.is_(None))
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
        novels = [item.novel for item in favorites if item.novel.visibility == "public" and item.novel.deleted_at is None]
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
            .where(Novel.owner_id == current_user.id, Novel.deleted_at.is_(None))
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
        project_chapter = _project_chapter_or_404(db, project.id, payload.project_chapter_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)
        if generation.project_chapter_id != project_chapter.id:
            raise HTTPException(status_code=409, detail="Generation does not belong to the selected project chapter.")

        novel = Novel(
            owner=current_user,
            project=project,
            source_generation=generation,
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

    @app.delete("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def delete_novel(
        novel_id: int,
        payload: DeleteNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = db.scalar(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.id == novel_id, Novel.owner_id == current_user.id)
        )
        if novel is None:
            raise HTTPException(status_code=404, detail="作品不存在。")
        if payload.hard_delete:
            result = _novel_detail_out(novel, current_user_id=current_user.id)
            db.delete(novel)
            db.commit()
            return result
        novel.deleted_at = datetime.utcnow()
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
        if novel.project_id is not None and novel.project_id != project.id:
            raise HTTPException(status_code=409, detail="Novel does not belong to the selected project.")
        project_chapter = _project_chapter_or_404(db, project.id, payload.project_chapter_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)
        if generation.project_chapter_id != project_chapter.id:
            raise HTTPException(status_code=409, detail="Generation does not belong to the selected project chapter.")
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

    @app.delete("/api/projects/{project_id}/character-cards/{card_id}", response_model=CharacterCardOut)
    def delete_character_card(
        project_id: int,
        card_id: int,
        payload: DeleteCharacterCardRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> CharacterCardOut:
        project = _project_or_404(db, current_user.id, project_id)
        card = db.scalar(select(CharacterCard).where(CharacterCard.project_id == project.id, CharacterCard.id == card_id))
        if card is None:
            raise HTTPException(status_code=404, detail="人物卡不存在。")
        if payload.hard_delete:
            result = CharacterCardOut.model_validate(card)
            db.delete(card)
            _mark_project_stale(project)
            db.commit()
            return result
        card.deleted_at = datetime.utcnow()
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

    @app.post("/api/projects/{project_id}/graphrag/prepare-review", response_model=GraphReviewOut)
    def prepare_graphrag_review(
        project_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> GraphReviewOut:
        project = _project_or_404(db, current_user.id, project_id)
        graphrag = GraphRAGService(settings)
        workspace = graphrag.prepare_project_inputs(
            project,
            list(project.memories),
            list(project.source_documents),
            character_cards=[item for item in project.character_cards if item.deleted_at is None],
            character_updates=list(project.character_state_updates),
            relationship_updates=list(project.relationship_state_updates),
            story_events=list(project.story_events),
            world_updates=list(project.world_perception_updates),
        )
        record = _workspace_record(db, project, workspace)
        record.workspace_path = str(workspace)
        if record.neo4j_sync_status == "idle":
            record.neo4j_sync_status = "stale"
        db.commit()
        db.refresh(project)
        review = _graph_review_out(project)
        if review is None:
            raise HTTPException(status_code=500, detail="GraphRAG 预览生成失败。")
        return review

    @app.put("/api/projects/{project_id}/graphrag/files/{filename}", response_model=GraphReviewOut)
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
        project.indexing_status = "stale"
        db.commit()
        db.refresh(project)
        review = _graph_review_out(project)
        if review is None:
            raise HTTPException(status_code=500, detail="GraphRAG 预览刷新失败。")
        return review

    @app.post("/api/projects/{project_id}/generate", response_model=GenerationOut)
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
        logger.info(
            "Generate retrieval completed: project=%s chapter=%s retrieval=%s global=%s",
            project.id,
            project_chapter.id,
            "graphrag" if can_use_retrieval else "direct",
            bool(global_result),
        )
        set_progress("retrieval", "参考资料已处理" if can_use_retrieval else "资料库未就绪，直接生成")
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
        try:
            logger.info("Generate draft writing started: project=%s chapter=%s", project.id, project_chapter.id)
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
            logger.info("Generate draft writing completed: project=%s chapter=%s", project.id, project_chapter.id)
        except RuntimeError as exc:
            detail = str(exc)
            set_progress("failed", detail, level="error")
            logger.warning(
                "Draft generation failed for project %s chapter %s: %s",
                project.id,
                project_chapter.id,
                detail,
            )
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
                        "refine": {"status": "done" if payload.use_refiner else "skipped", "message": "润色已完成" if payload.use_refiner else "未启用润色"},
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
        logger.info("Generate draft saved: project=%s chapter=%s generation=%s", project.id, project_chapter.id, generation.id)

        if payload.write_evolution:
            try:
                set_progress("evolution", "正在抽取人物、关系和事件变化")
                logger.info("Generate evolution extraction started: generation=%s", generation.id)
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
                logger.info("Generate evolution extraction completed: generation=%s", generation.id)
            except RuntimeError:
                set_progress("evolution_failed", "变化抽取失败，草稿已保留")
                logger.warning("Evolution extraction failed for generation %s.", generation.id)
                evolution_payload = evolution.empty_payload()
                generation.evolution_snapshot = _snapshot_with_process(
                    evolution_payload,
                    {
                        "draft": {"status": "done", "message": "初稿已保存"},
                        "refine": {"status": "done" if payload.use_refiner else "skipped", "message": "润色已完成" if payload.use_refiner else "未启用润色"},
                        "evolution": {"status": "failed", "message": "变化抽取失败，可继续处理"},
                    },
                )
                db.commit()
                return GenerationOut.model_validate(generation)
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

        generation.evolution_snapshot = _snapshot_with_process(
            evolution_payload,
            {
                "draft": {"status": "done", "message": "初稿已保存"},
                "refine": {"status": "done" if payload.use_refiner else "skipped", "message": "润色已完成" if payload.use_refiner else "未启用润色"},
                "evolution": {"status": "done" if payload.write_evolution else "skipped", "message": "变化抽取已完成" if payload.write_evolution else "未启用变化抽取"},
            },
        )
        db.commit()
        set_progress("done", "生成流程完成")
        return GenerationOut.model_validate(generation)

    @app.get("/api/projects/{project_id}/generate/progress", response_model=GenerationProgressOut)
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

    @app.post("/api/projects/{project_id}/generations/{generation_id}/continue", response_model=GenerationOut)
    def continue_generation(
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
            logger.info("Continue generation evolution started: generation=%s", generation.id)
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
            logger.warning("Continue generation failed: generation=%s error=%s", generation.id, exc)
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

        for item in evolution_payload.characters:
            if item.character_name:
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
            if item.source_character and item.target_character:
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
            if item.title:
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
            if item.subject_name and item.observer_group:
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
        logger.info("Continue generation completed: generation=%s", generation.id)
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
