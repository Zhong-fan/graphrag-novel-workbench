from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    password_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    owned_novels: Mapped[list["Novel"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    novel_likes: Mapped[list["NovelLike"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    novel_favorites: Mapped[list["NovelFavorite"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    novel_comments: Mapped[list["NovelComment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    world_brief: Mapped[str] = mapped_column(Text, default="", nullable=False)
    writing_rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
    style_profile: Mapped[str] = mapped_column(String(40), default="light_novel", nullable=False)
    punctuation_rule: Mapped[str] = mapped_column(
        String(120),
        default="对话使用「」，嵌套引号使用『』。",
        nullable=False,
    )
    indexing_status: Mapped[str] = mapped_column(String(40), default="idle", nullable=False)

    owner: Mapped["User"] = relationship(back_populates="projects")
    memories: Mapped[list["Memory"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    graph_workspace: Mapped["GraphWorkspace"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    generations: Mapped[list["GenerationRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    character_state_updates: Mapped[list["CharacterStateUpdate"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    relationship_state_updates: Mapped[list["RelationshipStateUpdate"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    story_events: Mapped[list["StoryEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    world_perception_updates: Mapped[list["WorldPerceptionUpdate"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_scope: Mapped[str] = mapped_column(String(60), default="story", nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="memories")


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(60), default="reference", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="source_documents")


class GraphWorkspace(Base, TimestampMixin):
    __tablename__ = "graph_workspaces"
    __table_args__ = (UniqueConstraint("project_id", name="uq_graph_workspaces_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    workspace_path: Mapped[str] = mapped_column(String(500), nullable=False)
    neo4j_sync_status: Mapped[str] = mapped_column(String(40), default="idle", nullable=False)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="graph_workspace")


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    search_method: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    response_type: Mapped[str] = mapped_column(String(120), default="Multiple Paragraphs", nullable=False)
    retrieval_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scene_card: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evolution_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="generations")
    character_state_updates: Mapped[list["CharacterStateUpdate"]] = relationship(
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )
    relationship_state_updates: Mapped[list["RelationshipStateUpdate"]] = relationship(
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )
    story_events: Mapped[list["StoryEvent"]] = relationship(
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )
    world_perception_updates: Mapped[list["WorldPerceptionUpdate"]] = relationship(
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")


class Novel(Base, TimestampMixin):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    visibility: Mapped[str] = mapped_column(String(40), default="private", nullable=False)

    owner: Mapped["User"] = relationship(back_populates="owned_novels")
    chapters: Mapped[list["NovelChapter"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    likes: Mapped[list["NovelLike"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    favorites: Mapped[list["NovelFavorite"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    comments: Mapped[list["NovelComment"]] = relationship(back_populates="novel", cascade="all, delete-orphan")


class NovelChapter(Base, TimestampMixin):
    __tablename__ = "novel_chapters"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_no", name="uq_novel_chapters_novel_chapter_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)

    novel: Mapped["Novel"] = relationship(back_populates="chapters")


class NovelLike(Base, TimestampMixin):
    __tablename__ = "novel_likes"
    __table_args__ = (UniqueConstraint("novel_id", "user_id", name="uq_novel_likes_novel_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    novel: Mapped["Novel"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship(back_populates="novel_likes")


class NovelFavorite(Base, TimestampMixin):
    __tablename__ = "novel_favorites"
    __table_args__ = (UniqueConstraint("novel_id", "user_id", name="uq_novel_favorites_novel_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    novel: Mapped["Novel"] = relationship(back_populates="favorites")
    user: Mapped["User"] = relationship(back_populates="novel_favorites")


class NovelComment(Base, TimestampMixin):
    __tablename__ = "novel_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    novel: Mapped["Novel"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="novel_comments")


class CharacterStateUpdate(Base, TimestampMixin):
    __tablename__ = "character_state_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    generation_run_id: Mapped[int] = mapped_column(ForeignKey("generation_runs.id"), nullable=False)
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    emotion_state: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    current_goal: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    self_view_shift: Mapped[str] = mapped_column(Text, default="", nullable=False)
    public_perception: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="character_state_updates")
    generation_run: Mapped["GenerationRun"] = relationship(back_populates="character_state_updates")


class RelationshipStateUpdate(Base, TimestampMixin):
    __tablename__ = "relationship_state_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    generation_run_id: Mapped[int] = mapped_column(ForeignKey("generation_runs.id"), nullable=False)
    source_character: Mapped[str] = mapped_column(String(100), nullable=False)
    target_character: Mapped[str] = mapped_column(String(100), nullable=False)
    change_type: Mapped[str] = mapped_column(String(60), default="relationship_shift", nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="stable", nullable=False)
    intensity: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="relationship_state_updates")
    generation_run: Mapped["GenerationRun"] = relationship(back_populates="relationship_state_updates")


class StoryEvent(Base, TimestampMixin):
    __tablename__ = "story_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    generation_run_id: Mapped[int] = mapped_column(ForeignKey("generation_runs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    impact_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    participants_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    location_hint: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="story_events")
    generation_run: Mapped["GenerationRun"] = relationship(back_populates="story_events")


class WorldPerceptionUpdate(Base, TimestampMixin):
    __tablename__ = "world_perception_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    generation_run_id: Mapped[int] = mapped_column(ForeignKey("generation_runs.id"), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(100), nullable=False)
    observer_group: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="stable", nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="world_perception_updates")
    generation_run: Mapped["GenerationRun"] = relationship(back_populates="world_perception_updates")
