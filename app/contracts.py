from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=120)


class AuthResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str

    class Config:
        from_attributes = True


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


class BootstrapResponse(BaseModel):
    service_name: str
    graph_engine: str
    auth_enabled: bool
    writer_model: str
    utility_model: str
    punctuation_rule: str
    query_methods: list[str]


AuthResponse.model_rebuild()
