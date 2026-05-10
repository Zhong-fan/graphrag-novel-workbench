from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import load_settings
from .contracts import (
    CharacterCardOut,
    CharacterStateUpdateOut,
    GraphReviewFileOut,
    GraphReviewOut,
    MemoryOut,
    ProjectChapterOut,
    ProjectFolderOut,
    ProjectOut,
    RelationshipStateUpdateOut,
    SourceOut,
    StoryEventOut,
    TrashItemOut,
    WorldPerceptionUpdateOut,
)
from .graphrag_service import GraphRAGService
from .models import (
    CharacterCard,
    CharacterStateUpdate,
    GenerationRun,
    GraphWorkspace,
    Novel,
    Project,
    ProjectChapter,
    ProjectFolder,
    RelationshipStateUpdate,
    StoryEvent,
    User,
    WorldPerceptionUpdate,
)


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
        project.graph_workspace.last_error = ""


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
            last_error=record.last_error,
            last_indexed_at=record.last_indexed_at,
        )
    payload = service.review_payload(workspace)
    return GraphReviewOut(
        workspace_path=record.workspace_path,
        input_files=payload["input_files"],
        files=[GraphReviewFileOut(**item) for item in payload["files"]],
        preview_text=payload["preview_text"],
        neo4j_sync_status=record.neo4j_sync_status,
        last_error=record.last_error,
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

    dirty_character_updates = db.scalars(
        select(CharacterStateUpdate)
        .join(Project, CharacterStateUpdate.project_id == Project.id)
        .join(GenerationRun, CharacterStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            Project.owner_id == user_id,
            CharacterStateUpdate.deleted_at.is_not(None),
            GenerationRun.canonicalized_at.is_(None),
        )
        .order_by(CharacterStateUpdate.deleted_at.desc())
    ).all()
    for item in dirty_character_updates:
        items.append(
            TrashItemOut(
                item_type="dirty_evolution",
                item_id=item.id,
                title=f"脏角色演化：{item.character_name}",
                subtitle="character_state_updates",
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.project_id,
            )
        )

    dirty_relationship_updates = db.scalars(
        select(RelationshipStateUpdate)
        .join(Project, RelationshipStateUpdate.project_id == Project.id)
        .join(GenerationRun, RelationshipStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            Project.owner_id == user_id,
            RelationshipStateUpdate.deleted_at.is_not(None),
            GenerationRun.canonicalized_at.is_(None),
        )
        .order_by(RelationshipStateUpdate.deleted_at.desc())
    ).all()
    for item in dirty_relationship_updates:
        items.append(
            TrashItemOut(
                item_type="dirty_evolution",
                item_id=1_000_000 + item.id,
                title=f"脏关系演化：{item.source_character} -> {item.target_character}",
                subtitle="relationship_state_updates",
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.project_id,
            )
        )

    dirty_story_events = db.scalars(
        select(StoryEvent)
        .join(Project, StoryEvent.project_id == Project.id)
        .join(GenerationRun, StoryEvent.generation_run_id == GenerationRun.id)
        .where(
            Project.owner_id == user_id,
            StoryEvent.deleted_at.is_not(None),
            GenerationRun.canonicalized_at.is_(None),
        )
        .order_by(StoryEvent.deleted_at.desc())
    ).all()
    for item in dirty_story_events:
        items.append(
            TrashItemOut(
                item_type="dirty_evolution",
                item_id=2_000_000 + item.id,
                title=f"脏事件演化：{item.title}",
                subtitle="story_events",
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.project_id,
            )
        )

    dirty_world_updates = db.scalars(
        select(WorldPerceptionUpdate)
        .join(Project, WorldPerceptionUpdate.project_id == Project.id)
        .join(GenerationRun, WorldPerceptionUpdate.generation_run_id == GenerationRun.id)
        .where(
            Project.owner_id == user_id,
            WorldPerceptionUpdate.deleted_at.is_not(None),
            GenerationRun.canonicalized_at.is_(None),
        )
        .order_by(WorldPerceptionUpdate.deleted_at.desc())
    ).all()
    for item in dirty_world_updates:
        items.append(
            TrashItemOut(
                item_type="dirty_evolution",
                item_id=3_000_000 + item.id,
                title=f"脏世界认知：{item.subject_name}",
                subtitle="world_perception_updates",
                deleted_at=item.deleted_at or item.updated_at,
                project_id=item.project_id,
            )
        )

    items.sort(key=lambda item: item.deleted_at, reverse=True)
    return items


def _soft_delete_dirty_evolution_for_project(db: Session, project: Project) -> dict[str, int]:
    deleted_at = datetime.utcnow()
    stats = {"character": 0, "relationship": 0, "event": 0, "world": 0}

    character_updates = db.scalars(
        select(CharacterStateUpdate)
        .join(GenerationRun, CharacterStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            CharacterStateUpdate.project_id == project.id,
            CharacterStateUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_(None),
        )
    ).all()
    for item in character_updates:
        item.deleted_at = deleted_at
        stats["character"] += 1

    relationship_updates = db.scalars(
        select(RelationshipStateUpdate)
        .join(GenerationRun, RelationshipStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            RelationshipStateUpdate.project_id == project.id,
            RelationshipStateUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_(None),
        )
    ).all()
    for item in relationship_updates:
        item.deleted_at = deleted_at
        stats["relationship"] += 1

    story_events = db.scalars(
        select(StoryEvent)
        .join(GenerationRun, StoryEvent.generation_run_id == GenerationRun.id)
        .where(
            StoryEvent.project_id == project.id,
            StoryEvent.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_(None),
        )
    ).all()
    for item in story_events:
        item.deleted_at = deleted_at
        stats["event"] += 1

    world_updates = db.scalars(
        select(WorldPerceptionUpdate)
        .join(GenerationRun, WorldPerceptionUpdate.generation_run_id == GenerationRun.id)
        .where(
            WorldPerceptionUpdate.project_id == project.id,
            WorldPerceptionUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_(None),
        )
    ).all()
    for item in world_updates:
        item.deleted_at = deleted_at
        stats["world"] += 1

    return stats


def _canonical_project_evolution(
    db: Session,
    project: Project,
) -> tuple[list[CharacterStateUpdate], list[RelationshipStateUpdate], list[StoryEvent], list[WorldPerceptionUpdate]]:
    character_updates = db.scalars(
        select(CharacterStateUpdate)
        .join(GenerationRun, CharacterStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            CharacterStateUpdate.project_id == project.id,
            CharacterStateUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_not(None),
        )
        .order_by(CharacterStateUpdate.created_at.desc())
    ).all()
    relationship_updates = db.scalars(
        select(RelationshipStateUpdate)
        .join(GenerationRun, RelationshipStateUpdate.generation_run_id == GenerationRun.id)
        .where(
            RelationshipStateUpdate.project_id == project.id,
            RelationshipStateUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_not(None),
        )
        .order_by(RelationshipStateUpdate.created_at.desc())
    ).all()
    story_events = db.scalars(
        select(StoryEvent)
        .join(GenerationRun, StoryEvent.generation_run_id == GenerationRun.id)
        .where(
            StoryEvent.project_id == project.id,
            StoryEvent.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_not(None),
        )
        .order_by(StoryEvent.created_at.desc())
    ).all()
    world_updates = db.scalars(
        select(WorldPerceptionUpdate)
        .join(GenerationRun, WorldPerceptionUpdate.generation_run_id == GenerationRun.id)
        .where(
            WorldPerceptionUpdate.project_id == project.id,
            WorldPerceptionUpdate.deleted_at.is_(None),
            GenerationRun.canonicalized_at.is_not(None),
        )
        .order_by(WorldPerceptionUpdate.created_at.desc())
    ).all()
    return character_updates, relationship_updates, story_events, world_updates


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
    import json

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
