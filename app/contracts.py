from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=120)
    captcha_answer: str = Field(..., min_length=1, max_length=40)
    captcha_token: str = Field(..., min_length=16)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=120)


class AuthResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileOut(BaseModel):
    bio: str
    email: str | None = None
    phone: str | None = None


class UserProfileUpdateRequest(BaseModel):
    bio: str = Field(default="", max_length=5000)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=60)


class CaptchaChallenge(BaseModel):
    challenge: str
    token: str
    expires_in: int


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    genre: str = Field(..., min_length=2, max_length=100)
    world_brief: str = Field(default="", max_length=4000)
    writing_rules: str = Field(default="", max_length=2000)
    style_profile: str = Field(
        default="light_novel",
        pattern="^(light_novel|lyrical_restrained|dialogue_driven|cinematic_tense|warm_healing|epic_serious)$",
    )


class ProjectUpdateRequest(ProjectCreateRequest):
    pass


class ProjectOut(BaseModel):
    id: int
    title: str
    genre: str
    world_brief: str
    writing_rules: str
    style_profile: str
    punctuation_rule: str
    indexing_status: str
    folder_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=4)
    memory_scope: str = Field(default="story", min_length=2, max_length=60)
    importance: int = Field(default=3, ge=1, le=5)


class MemoryOut(BaseModel):
    id: int
    title: str
    content: str
    memory_scope: str
    importance: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharacterCardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    age: str = Field(default="", max_length=60)
    gender: str = Field(default="", max_length=60)
    personality: str = Field(default="", max_length=2000)
    story_role: str = Field(default="", max_length=120)
    background: str = Field(default="", max_length=4000)


class CharacterCardUpdateRequest(CharacterCardCreateRequest):
    pass


class CharacterCardOut(BaseModel):
    id: int
    name: str
    age: str
    gender: str
    personality: str
    story_role: str
    background: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=8)
    source_kind: str = Field(default="reference", min_length=2, max_length=60)


class SourceOut(BaseModel):
    id: int
    title: str
    content: str
    source_kind: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IndexRequest(BaseModel):
    force_rebuild: bool = True


class IndexResponse(BaseModel):
    status: str
    workspace_path: str
    neo4j_sync_status: str


class GraphReviewOut(BaseModel):
    workspace_path: str
    input_files: list[str]
    files: list["GraphReviewFileOut"] = []
    preview_text: str
    neo4j_sync_status: str
    last_indexed_at: datetime | None = None


class GraphReviewFileOut(BaseModel):
    filename: str
    title: str
    category: str
    content: str


class GraphReviewFileUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=200000)


class GenerateRequest(BaseModel):
    chapter_id: int
    prompt: str = Field(..., min_length=12)
    search_method: str = Field(default="local")
    response_type: str = Field(default="Multiple Paragraphs")
    use_global_search: bool = True
    use_scene_card: bool = True
    use_refiner: bool = True
    write_evolution: bool = True


class GenerationOut(BaseModel):
    id: int
    project_chapter_id: int | None = None
    title: str
    content: str
    summary: str
    retrieval_context: str
    scene_card: str
    evolution_snapshot: str
    generation_trace: str
    search_method: str
    response_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class GenerationProgressOut(BaseModel):
    stage: str
    message: str
    trace: dict[str, Any] = Field(default_factory=dict)
    logs: list[dict[str, Any]] = Field(default_factory=list)


class CharacterStateUpdateOut(BaseModel):
    id: int
    character_name: str
    emotion_state: str
    current_goal: str
    self_view_shift: str
    public_perception: str
    summary: str
    created_at: datetime


class RelationshipStateUpdateOut(BaseModel):
    id: int
    source_character: str
    target_character: str
    change_type: str
    direction: str
    intensity: int
    summary: str
    created_at: datetime


class StoryEventOut(BaseModel):
    id: int
    title: str
    summary: str
    impact_summary: str
    participants: list[str]
    location_hint: str
    created_at: datetime


class WorldPerceptionUpdateOut(BaseModel):
    id: int
    subject_name: str
    observer_group: str
    direction: str
    change_summary: str
    created_at: datetime


class ProjectDetailResponse(BaseModel):
    project: ProjectOut
    project_chapters: list["ProjectChapterOut"] = []
    memories: list[MemoryOut]
    character_cards: list[CharacterCardOut] = []
    sources: list[SourceOut]
    generations: list[GenerationOut]
    graphrag_review: GraphReviewOut | None = None
    character_state_updates: list[CharacterStateUpdateOut] = []
    relationship_state_updates: list[RelationshipStateUpdateOut] = []
    story_events: list[StoryEventOut] = []
    world_perception_updates: list[WorldPerceptionUpdateOut] = []


class ProjectFolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class ProjectFolderOut(BaseModel):
    id: int
    name: str
    sort_order: int
    is_default: bool
    project_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MoveProjectFolderRequest(BaseModel):
    folder_id: int | None = None


class TrashItemOut(BaseModel):
    item_type: str
    item_id: int
    title: str
    subtitle: str = ""
    deleted_at: datetime
    project_id: int | None = None


class RestoreTrashItemRequest(BaseModel):
    item_type: str = Field(..., pattern="^(project|novel|character_card)$")


class MyWorkspaceOut(BaseModel):
    folders: list[ProjectFolderOut]
    projects: list[ProjectOut]
    trash: list[TrashItemOut]


class ProjectChapterCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    premise: str = Field(..., min_length=12, max_length=2000)
    chapter_no: int | None = Field(default=None, ge=1, le=10000)


class ProjectChapterUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    premise: str = Field(..., min_length=12, max_length=2000)
    chapter_no: int = Field(..., ge=1, le=10000)


class ProjectChapterOut(BaseModel):
    id: int
    project_id: int
    title: str
    premise: str
    chapter_no: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NovelChapterOut(BaseModel):
    id: int
    title: str
    summary: str
    content: str
    chapter_no: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NovelCardOut(BaseModel):
    id: int
    project_id: int | None = None
    source_generation_id: int | None = None
    title: str
    author: str
    summary: str
    genre: str
    tagline: str
    cover_url: str | None = None
    status: str
    visibility: str
    likes_count: int
    favorites_count: int
    comments_count: int
    chapters_count: int
    latest_excerpt: str
    is_liked: bool
    is_favorited: bool
    created_at: datetime
    updated_at: datetime


class NovelDetailOut(NovelCardOut):
    chapters: list[NovelChapterOut]


class FavoriteToggleResponse(BaseModel):
    favorited: bool
    novel_id: int
    favorites_count: int


class LikeToggleResponse(BaseModel):
    liked: bool
    novel_id: int
    likes_count: int


class NovelCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class NovelCommentOut(BaseModel):
    id: int
    user_id: int
    username: str
    content: str
    created_at: datetime


class PublishNovelRequest(BaseModel):
    project_id: int
    project_chapter_id: int
    generation_id: int
    title: str = Field(..., min_length=2, max_length=255)
    author_name: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(default="", max_length=5000)
    tagline: str = Field(default="", max_length=255)
    visibility: str = Field(default="public", pattern="^(public|private)$")
    chapter_title: str = Field(default="", max_length=255)
    chapter_summary: str = Field(default="", max_length=5000)
    chapter_content: str = Field(default="", max_length=200000)
    chapter_no: int = Field(default=1, ge=1, le=10000)


class UpdateNovelRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    author_name: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(default="", max_length=5000)
    tagline: str = Field(default="", max_length=255)
    visibility: str = Field(default="public", pattern="^(public|private)$")


class DeleteNovelRequest(BaseModel):
    hard_delete: bool = False


class AppendNovelChapterRequest(BaseModel):
    project_id: int
    project_chapter_id: int
    generation_id: int
    title: str = Field(default="", max_length=255)
    summary: str = Field(default="", max_length=5000)
    content: str = Field(default="", max_length=200000)
    chapter_no: int | None = Field(default=None, ge=1, le=10000)


class UpdateNovelChapterRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(default="", max_length=5000)
    content: str = Field(..., min_length=1, max_length=200000)
    chapter_no: int = Field(..., ge=1, le=10000)


class DeleteProjectRequest(BaseModel):
    hard_delete: bool = False


class DeleteCharacterCardRequest(BaseModel):
    hard_delete: bool = False


class BootstrapResponse(BaseModel):
    service_name: str
    graph_engine: str
    auth_enabled: bool
    writer_model: str
    utility_model: str
    embedding_model: str
    embedding_provider: str
    embedding_base_url: str
    punctuation_rule: str
    query_methods: list[str]


AuthResponse.model_rebuild()
