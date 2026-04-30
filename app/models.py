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


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    world_brief: Mapped[str] = mapped_column(Text, default="", nullable=False)
    writing_rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
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
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="generations")
