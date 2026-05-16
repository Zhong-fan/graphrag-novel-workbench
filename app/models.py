from __future__ import annotations
import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
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
    project_folders: Mapped[list["ProjectFolder"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
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
    reference_work: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    reference_work_creator: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    reference_work_medium: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    reference_work_synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reference_work_style_traits_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    reference_work_world_traits_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    reference_work_narrative_constraints_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    reference_work_confidence_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    premise: Mapped[str] = mapped_column(Text, default="", nullable=False)
    world_brief: Mapped[str] = mapped_column(Text, default="", nullable=False)
    writing_rules: Mapped[str] = mapped_column(Text, default="", nullable=False)
    style_profile: Mapped[str] = mapped_column(String(40), default="light_novel", nullable=False)
    indexing_status: Mapped[str] = mapped_column(String(40), default="stale", nullable=False)
    punctuation_rule: Mapped[str] = mapped_column(
        String(120),
        default="对话使用「」，嵌套引号使用『』。",
        nullable=False,
    )
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("project_folders.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="projects")
    folder: Mapped["ProjectFolder | None"] = relationship(back_populates="projects")
    memories: Mapped[list["Memory"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    character_cards: Mapped[list["CharacterCard"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    project_chapters: Mapped[list["ProjectChapter"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    generations: Mapped[list["GenerationRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    published_novels: Mapped[list["Novel"]] = relationship(back_populates="project")
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
    series_plans: Mapped[list["SeriesPlan"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    chapter_outlines: Mapped[list["ChapterOutline"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    outline_feedback_items: Mapped[list["OutlineFeedbackItem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    draft_versions: Mapped[list["DraftVersion"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    batch_generation_jobs: Mapped[list["BatchGenerationJob"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    task_events: Mapped[list["TaskEvent"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    storyboards: Mapped[list["Storyboard"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    @property
    def reference_work_style_traits(self) -> list[str]:
        return _json_text_list(self.reference_work_style_traits_json)

    @reference_work_style_traits.setter
    def reference_work_style_traits(self, value: list[str]) -> None:
        self.reference_work_style_traits_json = json.dumps(_normalize_text_list(value), ensure_ascii=False)

    @property
    def reference_work_world_traits(self) -> list[str]:
        return _json_text_list(self.reference_work_world_traits_json)

    @reference_work_world_traits.setter
    def reference_work_world_traits(self, value: list[str]) -> None:
        self.reference_work_world_traits_json = json.dumps(_normalize_text_list(value), ensure_ascii=False)

    @property
    def reference_work_narrative_constraints(self) -> list[str]:
        return _json_text_list(self.reference_work_narrative_constraints_json)

    @reference_work_narrative_constraints.setter
    def reference_work_narrative_constraints(self, value: list[str]) -> None:
        self.reference_work_narrative_constraints_json = json.dumps(_normalize_text_list(value), ensure_ascii=False)


def _json_text_list(value: str) -> list[str]:
    try:
        payload = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _normalize_text_list(value: list[str]) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()]


class ProjectFolder(Base, TimestampMixin):
    __tablename__ = "project_folders"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_project_folders_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="project_folders")
    projects: Mapped[list["Project"]] = relationship(back_populates="folder")


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_scope: Mapped[str] = mapped_column(String(60), default="story", nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="memories")


class CharacterCard(Base, TimestampMixin):
    __tablename__ = "character_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    gender: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    personality: Mapped[str] = mapped_column(Text, default="", nullable=False)
    story_role: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    background: Mapped[str] = mapped_column(Text, default="", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="character_cards")


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(60), default="reference", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="source_documents")


class ProjectChapter(Base, TimestampMixin):
    __tablename__ = "project_chapters"
    __table_args__ = (UniqueConstraint("project_id", "chapter_no", name="uq_project_chapters_project_chapter_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    premise: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="project_chapters")
    generations: Mapped[list["GenerationRun"]] = relationship(back_populates="project_chapter")


class SeriesPlan(Base, TimestampMixin):
    __tablename__ = "series_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_chapter_count: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    theme: Mapped[str] = mapped_column(Text, default="", nullable=False)
    main_conflict: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ending_direction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    current_version_id: Mapped[int | None] = mapped_column(ForeignKey("series_plan_versions.id"), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="series_plans")
    versions: Mapped[list["SeriesPlanVersion"]] = relationship(
        back_populates="series_plan",
        cascade="all, delete-orphan",
        foreign_keys="SeriesPlanVersion.series_plan_id",
    )
    current_version: Mapped["SeriesPlanVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )
    arc_plans: Mapped[list["ArcPlan"]] = relationship(back_populates="series_plan", cascade="all, delete-orphan")
    chapter_outlines: Mapped[list["ChapterOutline"]] = relationship(back_populates="series_plan", cascade="all, delete-orphan")
    batch_generation_jobs: Mapped[list["BatchGenerationJob"]] = relationship(back_populates="series_plan")


class SeriesPlanVersion(Base):
    __tablename__ = "series_plan_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_plan_id: Mapped[int] = mapped_column(ForeignKey("series_plans.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    change_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_feedback_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(40), default="planner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    series_plan: Mapped["SeriesPlan"] = relationship(
        back_populates="versions",
        foreign_keys=[series_plan_id],
    )
    arc_plans: Mapped[list["ArcPlan"]] = relationship(back_populates="version")


class ArcPlan(Base):
    __tablename__ = "arc_plans"
    __table_args__ = (UniqueConstraint("series_plan_id", "version_id", "arc_no", name="uq_arc_plans_series_version_arc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_plan_id: Mapped[int] = mapped_column(ForeignKey("series_plans.id"), nullable=False)
    version_id: Mapped[int] = mapped_column(ForeignKey("series_plan_versions.id"), nullable=False)
    arc_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    end_chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    conflict: Mapped[str] = mapped_column(Text, default="", nullable=False)
    turning_points_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)

    series_plan: Mapped["SeriesPlan"] = relationship(back_populates="arc_plans")
    version: Mapped["SeriesPlanVersion"] = relationship(back_populates="arc_plans")
    chapter_outlines: Mapped[list["ChapterOutline"]] = relationship(back_populates="arc_plan")


class ChapterOutline(Base, TimestampMixin):
    __tablename__ = "chapter_outlines"
    __table_args__ = (UniqueConstraint("series_plan_id", "chapter_no", name="uq_chapter_outlines_series_chapter_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    series_plan_id: Mapped[int] = mapped_column(ForeignKey("series_plans.id"), nullable=False)
    arc_plan_id: Mapped[int | None] = mapped_column(ForeignKey("arc_plans.id"), nullable=True)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    outline_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="outline_draft", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="chapter_outlines")
    series_plan: Mapped["SeriesPlan"] = relationship(back_populates="chapter_outlines")
    arc_plan: Mapped["ArcPlan | None"] = relationship(back_populates="chapter_outlines")
    draft_versions: Mapped[list["DraftVersion"]] = relationship(back_populates="chapter_outline")


class OutlineFeedbackItem(Base, TimestampMixin):
    __tablename__ = "outline_feedback_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(60), default="general", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="outline_feedback_items")
    revision_plans: Mapped[list["OutlineRevisionPlan"]] = relationship(
        back_populates="feedback_item",
        cascade="all, delete-orphan",
    )


class OutlineRevisionPlan(Base):
    __tablename__ = "outline_revision_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_item_id: Mapped[int] = mapped_column(ForeignKey("outline_feedback_items.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    feedback_item: Mapped["OutlineFeedbackItem"] = relationship(back_populates="revision_plans")


class DraftVersion(Base):
    __tablename__ = "draft_versions"
    __table_args__ = (UniqueConstraint("chapter_outline_id", "version_no", name="uq_draft_versions_outline_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    chapter_outline_id: Mapped[int] = mapped_column(ForeignKey("chapter_outlines.id"), nullable=False)
    generation_run_id: Mapped[int | None] = mapped_column(ForeignKey("generation_runs.id"), nullable=True)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft_generated", nullable=False)
    revision_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="draft_versions")
    chapter_outline: Mapped["ChapterOutline"] = relationship(back_populates="draft_versions")
    generation_run: Mapped["GenerationRun | None"] = relationship()
    parent_version: Mapped["DraftVersion | None"] = relationship(remote_side=[id])


class BatchGenerationJob(Base, TimestampMixin):
    __tablename__ = "batch_generation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    series_plan_id: Mapped[int] = mapped_column(ForeignKey("series_plans.id"), nullable=False)
    start_chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    end_chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    job_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    current_chapter_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    worker_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="batch_generation_jobs")
    series_plan: Mapped["SeriesPlan"] = relationship(back_populates="batch_generation_jobs")
    chapter_tasks: Mapped[list["BatchGenerationChapterTask"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class BatchGenerationChapterTask(Base, TimestampMixin):
    __tablename__ = "batch_generation_chapter_tasks"
    __table_args__ = (UniqueConstraint("job_id", "chapter_no", name="uq_batch_generation_task_job_chapter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("batch_generation_jobs.id"), nullable=True)
    storyboard_id: Mapped[int | None] = mapped_column(ForeignKey("storyboards.id"), nullable=True)
    chapter_outline_id: Mapped[int] = mapped_column(ForeignKey("chapter_outlines.id"), nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    draft_version_id: Mapped[int | None] = mapped_column(ForeignKey("draft_versions.id"), nullable=True)
    generation_run_id: Mapped[int | None] = mapped_column(ForeignKey("generation_runs.id"), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped["BatchGenerationJob"] = relationship(back_populates="chapter_tasks")
    chapter_outline: Mapped["ChapterOutline"] = relationship()
    draft_version: Mapped["DraftVersion | None"] = relationship()
    generation_run: Mapped["GenerationRun | None"] = relationship()
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="chapter_task")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("batch_generation_jobs.id"), nullable=True)
    storyboard_id: Mapped[int | None] = mapped_column(ForeignKey("storyboards.id"), nullable=True)
    video_task_id: Mapped[int | None] = mapped_column(ForeignKey("video_tasks.id"), nullable=True)
    chapter_task_id: Mapped[int | None] = mapped_column(ForeignKey("batch_generation_chapter_tasks.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="task_events")
    job: Mapped["BatchGenerationJob | None"] = relationship(back_populates="events")
    storyboard: Mapped["Storyboard | None"] = relationship(back_populates="events")
    video_task: Mapped["VideoTask | None"] = relationship(back_populates="events")
    chapter_task: Mapped["BatchGenerationChapterTask | None"] = relationship(back_populates="events")


class Storyboard(Base, TimestampMixin):
    __tablename__ = "storyboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_chapter_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    worker_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="storyboards")
    shots: Mapped[list["StoryboardShot"]] = relationship(back_populates="storyboard", cascade="all, delete-orphan")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="storyboard")
    video_tasks: Mapped[list["VideoTask"]] = relationship(back_populates="storyboard")
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="storyboard")


class StoryboardShot(Base):
    __tablename__ = "storyboard_shots"
    __table_args__ = (UniqueConstraint("storyboard_id", "shot_no", name="uq_storyboard_shots_storyboard_shot_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("storyboards.id"), nullable=False)
    shot_no: Mapped[int] = mapped_column(Integer, nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visual_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    character_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    scene_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)

    storyboard: Mapped["Storyboard"] = relationship(back_populates="shots")


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    storyboard_id: Mapped[int | None] = mapped_column(ForeignKey("storyboards.id"), nullable=True)
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("storyboard_shots.id"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    uri: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    meta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    project: Mapped["Project"] = relationship()
    storyboard: Mapped["Storyboard | None"] = relationship(back_populates="media_assets")
    shot: Mapped["StoryboardShot | None"] = relationship()


class VideoTask(Base, TimestampMixin):
    __tablename__ = "video_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("storyboards.id"), nullable=False)
    task_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    output_uri: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    progress_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["Project"] = relationship()
    storyboard: Mapped["Storyboard"] = relationship(back_populates="video_tasks")
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="video_task")


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    project_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("project_chapters.id"), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    search_method: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    response_type: Mapped[str] = mapped_column(String(120), default="Multiple Paragraphs", nullable=False)
    retrieval_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scene_card: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evolution_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generation_trace: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    canonicalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="generations")
    project_chapter: Mapped["ProjectChapter | None"] = relationship(back_populates="generations")
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
    published_novels: Mapped[list["Novel"]] = relationship(back_populates="source_generation")


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
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    source_generation_id: Mapped[int | None] = mapped_column(ForeignKey("generation_runs.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    visibility: Mapped[str] = mapped_column(String(40), default="private", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="owned_novels")
    project: Mapped["Project | None"] = relationship(back_populates="published_novels")
    source_generation: Mapped["GenerationRun | None"] = relationship(back_populates="published_novels")
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="world_perception_updates")
    generation_run: Mapped["GenerationRun"] = relationship(back_populates="world_perception_updates")
