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
    reference_work: str = Field(default="", max_length=255)
    reference_work_creator: str = Field(default="", max_length=255)
    reference_work_medium: str = Field(default="", max_length=120)
    reference_work_synopsis: str = Field(default="", max_length=4000)
    reference_work_style_traits: list[str] = []
    reference_work_world_traits: list[str] = []
    reference_work_narrative_constraints: list[str] = []
    reference_work_confidence_note: str = Field(default="", max_length=1000)
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
    reference_work: str
    reference_work_creator: str
    reference_work_medium: str
    reference_work_synopsis: str
    reference_work_style_traits: list[str] = []
    reference_work_world_traits: list[str] = []
    reference_work_narrative_constraints: list[str] = []
    reference_work_confidence_note: str
    world_brief: str
    writing_rules: str
    style_profile: str
    punctuation_rule: str
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


class GenerateRequest(BaseModel):
    chapter_id: int
    prompt: str = Field(..., min_length=12)
    search_method: str = Field(default="direct")
    response_type: str = Field(default="Multiple Paragraphs")
    use_global_search: bool = False
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
    character_state_updates: list[CharacterStateUpdateOut] = []
    relationship_state_updates: list[RelationshipStateUpdateOut] = []
    story_events: list[StoryEventOut] = []
    world_perception_updates: list[WorldPerceptionUpdateOut] = []


class ProjectFolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class ProjectBriefingSuggestionRequest(BaseModel):
    kind: str = Field(..., pattern="^(world_brief|writing_rules)$")
    title: str = Field(default="", max_length=255)
    genre: str = Field(default="", max_length=100)
    reference_work: str = Field(default="", max_length=255)
    seed_text: str = Field(..., min_length=4, max_length=600)


class ProjectBriefingSuggestionResponse(BaseModel):
    kind: str
    suggestions: list[str]


class ReferenceWorkResolveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=255)
    genre: str = Field(default="", max_length=100)


class ReferenceWorkResolvedOut(BaseModel):
    canonical_title: str
    creator: str
    medium: str
    synopsis: str
    style_traits: list[str]
    world_traits: list[str]
    narrative_constraints: list[str]
    confidence_note: str


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
    item_type: str = Field(..., pattern="^(project|novel|character_card|dirty_evolution)$")


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


class NovelCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class NovelCommentOut(BaseModel):
    id: int
    user_id: int
    username: str
    content: str
    created_at: datetime


class FavoriteToggleResponse(BaseModel):
    favorited: bool
    novel_id: int
    favorites_count: int


class LikeToggleResponse(BaseModel):
    liked: bool
    novel_id: int
    likes_count: int


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


class GenerateSeriesPlanRequest(BaseModel):
    target_chapter_count: int = Field(default=12, ge=3, le=80)
    user_brief: str = Field(default="", max_length=4000)


class SeriesPlanVersionOut(BaseModel):
    id: int
    series_plan_id: int
    version_no: int
    summary: dict[str, Any]
    change_note: str
    source_feedback_snapshot: str
    created_by: str
    created_at: datetime


class ArcPlanOut(BaseModel):
    id: int
    series_plan_id: int
    version_id: int
    arc_no: int
    start_chapter_no: int
    end_chapter_no: int
    title: str
    goal: str
    conflict: str
    turning_points: list[Any]
    status: str


class ChapterOutlineOut(BaseModel):
    id: int
    project_id: int
    series_plan_id: int
    arc_plan_id: int | None = None
    chapter_no: int
    title: str
    outline: dict[str, Any]
    status: str
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UpdateChapterOutlineRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    outline: dict[str, Any]
    status: str = Field(default="outline_draft", max_length=40)


class DraftVersionOut(BaseModel):
    id: int
    project_id: int
    chapter_outline_id: int
    generation_run_id: int | None = None
    parent_version_id: int | None = None
    version_no: int
    title: str
    summary: str
    content: str
    status: str
    revision_reason: str
    created_at: datetime


class ReviseDraftVersionRequest(BaseModel):
    feedback_text: str = Field(..., min_length=2, max_length=8000)


class CanonicalizeDraftVersionRequest(BaseModel):
    novel_id: int | None = Field(default=None, ge=1)
    author_name: str = Field(default="", max_length=100)
    visibility: str = Field(default="private", pattern="^(public|private)$")
    tagline: str = Field(default="", max_length=255)


class SeriesPlanOut(BaseModel):
    id: int
    project_id: int
    title: str
    target_chapter_count: int
    theme: str
    main_conflict: str
    ending_direction: str
    status: str
    current_version_id: int | None = None
    created_at: datetime
    updated_at: datetime
    current_version: SeriesPlanVersionOut | None = None
    versions: list[SeriesPlanVersionOut] = []
    arcs: list[ArcPlanOut] = []
    chapters: list[ChapterOutlineOut] = []


class SeriesPlanningStateOut(BaseModel):
    series_plans: list[SeriesPlanOut]
    draft_versions: list[DraftVersionOut] = []
    batch_jobs: list["BatchGenerationJobOut"] = []
    storyboards: list["StoryboardOut"] = []
    media_assets: list["MediaAssetOut"] = []
    video_tasks: list["VideoTaskOut"] = []


class SubmitOutlineFeedbackRequest(BaseModel):
    target_type: str = Field(..., pattern="^(series|arc|chapter)$")
    target_id: int = Field(..., ge=1)
    feedback_text: str = Field(..., min_length=2, max_length=8000)
    feedback_type: str = Field(default="general", max_length=60)
    priority: int = Field(default=3, ge=1, le=5)


class OutlineFeedbackItemOut(BaseModel):
    id: int
    project_id: int
    target_type: str
    target_id: int
    feedback_text: str
    feedback_type: str
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutlineRevisionPlanOut(BaseModel):
    id: int
    feedback_item_id: int
    target_type: str
    target_id: int
    plan: dict[str, Any]
    applied: bool
    created_at: datetime


class OutlineRevisionResponse(BaseModel):
    feedback: OutlineFeedbackItemOut
    revision_plan: OutlineRevisionPlanOut
    series_plan: SeriesPlanOut


class LockChapterOutlinesRequest(BaseModel):
    chapter_outline_ids: list[int] = Field(default_factory=list)


class BatchGenerationRequest(BaseModel):
    series_plan_id: int = Field(..., ge=1)
    start_chapter_no: int = Field(..., ge=1, le=10000)
    end_chapter_no: int = Field(..., ge=1, le=10000)


class BatchGenerationChapterTaskOut(BaseModel):
    id: int
    job_id: int
    chapter_outline_id: int
    chapter_no: int
    status: str
    draft_version_id: int | None = None
    generation_run_id: int | None = None
    error_message: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskEventOut(BaseModel):
    id: int
    project_id: int
    job_id: int | None = None
    storyboard_id: int | None = None
    video_task_id: int | None = None
    chapter_task_id: int | None = None
    event_type: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class BatchGenerationJobOut(BaseModel):
    id: int
    project_id: int
    series_plan_id: int
    start_chapter_no: int
    end_chapter_no: int
    job_status: str
    current_chapter_no: int | None = None
    result_summary: dict[str, Any]
    worker_id: str = ""
    worker_started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    chapter_tasks: list[BatchGenerationChapterTaskOut] = []
    events: list[TaskEventOut] = []
    created_at: datetime
    updated_at: datetime


class CreateStoryboardRequest(BaseModel):
    novel_chapter_ids: list[int] = Field(..., min_length=1, max_length=12)
    title: str = Field(default="", max_length=255)


class StoryboardShotOut(BaseModel):
    id: int
    storyboard_id: int
    shot_no: int
    narration_text: str
    visual_prompt: str
    character_refs: list[Any]
    scene_refs: list[Any]
    duration_seconds: float
    status: str


class StoryboardOut(BaseModel):
    id: int
    project_id: int
    title: str
    source_chapter_ids: list[Any]
    status: str
    summary: str
    worker_id: str = ""
    worker_started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    error_message: str = ""
    shots: list[StoryboardShotOut] = []
    events: list[TaskEventOut] = []
    created_at: datetime
    updated_at: datetime


class UpdateStoryboardShotRequest(BaseModel):
    narration_text: str = Field(default="", max_length=8000)
    visual_prompt: str = Field(default="", max_length=8000)
    character_refs: list[Any] = []
    scene_refs: list[Any] = []
    duration_seconds: float = Field(default=4, ge=0.5, le=60)
    status: str = Field(default="draft", max_length=40)


class CreateStoryboardShotRequest(UpdateStoryboardShotRequest):
    shot_no: int | None = Field(default=None, ge=1, le=10000)


class ReorderStoryboardShotsRequest(BaseModel):
    shot_ids: list[int] = Field(..., min_length=1)


class MediaAssetOut(BaseModel):
    id: int
    project_id: int
    storyboard_id: int | None = None
    shot_id: int | None = None
    asset_type: str
    uri: str
    prompt: str
    status: str
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UpdateMediaAssetRequest(BaseModel):
    uri: str = Field(default="", max_length=500)
    status: str = Field(default="pending", max_length=40)
    meta: dict[str, Any] = {}


class VideoTaskOut(BaseModel):
    id: int
    project_id: int
    storyboard_id: int
    task_status: str
    output_uri: str
    progress: dict[str, Any]
    error_message: str
    events: list[TaskEventOut] = []
    created_at: datetime
    updated_at: datetime


class UpdateVideoTaskRequest(BaseModel):
    task_status: str = Field(default="queued", max_length=40)
    output_uri: str = Field(default="", max_length=500)
    progress: dict[str, Any] = {}
    error_message: str = Field(default="", max_length=8000)


class DeleteProjectRequest(BaseModel):
    hard_delete: bool = False


class DeleteCharacterCardRequest(BaseModel):
    hard_delete: bool = False


class BootstrapResponse(BaseModel):
    service_name: str
    auth_enabled: bool
    writer_model: str
    utility_model: str
    embedding_model: str
    embedding_provider: str
    embedding_base_url: str
    punctuation_rule: str


AuthResponse.model_rebuild()
SeriesPlanningStateOut.model_rebuild()
