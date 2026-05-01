from __future__ import annotations

from datetime import datetime

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
    premise: str = Field(..., min_length=12)
    world_brief: str = Field(default="")
    writing_rules: str = Field(default="")


class ProjectOut(BaseModel):
    id: int
    title: str
    genre: str
    premise: str
    world_brief: str
    writing_rules: str
    punctuation_rule: str
    indexing_status: str
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


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=12)
    search_method: str = Field(default="local")
    response_type: str = Field(default="Multiple Paragraphs")


class GenerationOut(BaseModel):
    id: int
    title: str
    content: str
    summary: str
    retrieval_context: str
    search_method: str
    response_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(BaseModel):
    project: ProjectOut
    memories: list[MemoryOut]
    sources: list[SourceOut]
    generations: list[GenerationOut]


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
    generation_id: int
    title: str = Field(..., min_length=2, max_length=255)
    author_name: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(default="", max_length=5000)
    tagline: str = Field(default="", max_length=255)
    visibility: str = Field(default="public", pattern="^(public|private)$")


class UpdateNovelRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    author_name: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(default="", max_length=5000)
    tagline: str = Field(default="", max_length=255)
    visibility: str = Field(default="public", pattern="^(public|private)$")


class AppendNovelChapterRequest(BaseModel):
    project_id: int
    generation_id: int
    title: str = Field(default="", max_length=255)


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
