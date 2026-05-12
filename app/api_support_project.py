from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .contracts import (
    CharacterCardOut,
    CharacterStateUpdateOut,
    ProjectChapterOut,
    ProjectFolderOut,
    ProjectOut,
    RelationshipStateUpdateOut,
    SourceOut,
    StoryEventOut,
    TrashItemOut,
    WorldPerceptionUpdateOut,
)
from .models import (
    CharacterCard,
    CharacterStateUpdate,
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


def _mark_project_stale(project: Project) -> None:
    _ = project


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

    dirty_sources = [
        ("character_state_updates", CharacterStateUpdate, 0),
        ("relationship_state_updates", RelationshipStateUpdate, 1_000_000),
        ("story_events", StoryEvent, 2_000_000),
        ("world_perception_updates", WorldPerceptionUpdate, 3_000_000),
    ]
    for _, model, prefix in dirty_sources:
        rows = db.scalars(
            select(model)
            .join(Project, model.project_id == Project.id)
            .where(Project.owner_id == user_id, model.deleted_at.is_not(None))
            .order_by(model.deleted_at.desc())
        ).all()
        for item in rows:
            title = getattr(item, "summary", "") or getattr(item, "title", "") or getattr(item, "subject_name", "")
            subtitle = getattr(item, "character_name", "") or getattr(item, "source_character", "") or getattr(item, "observer_group", "")
            items.append(
                TrashItemOut(
                    item_type="dirty_evolution",
                    item_id=prefix + item.id,
                    title=title or "演化记录",
                    subtitle=subtitle,
                    deleted_at=item.deleted_at or item.updated_at,
                    project_id=item.project_id,
                )
            )

    items.sort(key=lambda item: item.deleted_at, reverse=True)
    return items


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
        participants = json.loads(item.participants_json or "[]")
    except json.JSONDecodeError:
        participants = []
    if not isinstance(participants, list):
        participants = []
    return StoryEventOut(
        id=item.id,
        title=item.title,
        summary=item.summary,
        impact_summary=item.impact_summary,
        participants=[str(value).strip() for value in participants if str(value).strip()],
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


def _soft_delete_dirty_evolution_for_project(db: Session, project: Project) -> dict[str, int]:
    stats = {"characters": 0, "relationships": 0, "events": 0, "world_updates": 0}

    for item in project.character_state_updates:
        if item.deleted_at is None:
            item.deleted_at = datetime.utcnow()
            stats["characters"] += 1
    for item in project.relationship_state_updates:
        if item.deleted_at is None:
            item.deleted_at = datetime.utcnow()
            stats["relationships"] += 1
    for item in project.story_events:
        if item.deleted_at is None:
            item.deleted_at = datetime.utcnow()
            stats["events"] += 1
    for item in project.world_perception_updates:
        if item.deleted_at is None:
            item.deleted_at = datetime.utcnow()
            stats["world_updates"] += 1

    return stats


def _canonical_project_evolution(
    db: Session,
    project: Project,
) -> tuple[list[CharacterStateUpdate], list[RelationshipStateUpdate], list[StoryEvent], list[WorldPerceptionUpdate]]:
    character_updates = db.scalars(
        select(CharacterStateUpdate)
        .where(CharacterStateUpdate.project_id == project.id, CharacterStateUpdate.deleted_at.is_(None))
        .order_by(CharacterStateUpdate.created_at.desc())
    ).all()
    relationship_updates = db.scalars(
        select(RelationshipStateUpdate)
        .where(RelationshipStateUpdate.project_id == project.id, RelationshipStateUpdate.deleted_at.is_(None))
        .order_by(RelationshipStateUpdate.created_at.desc())
    ).all()
    story_events = db.scalars(
        select(StoryEvent)
        .where(StoryEvent.project_id == project.id, StoryEvent.deleted_at.is_(None))
        .order_by(StoryEvent.created_at.desc())
    ).all()
    world_updates = db.scalars(
        select(WorldPerceptionUpdate)
        .where(WorldPerceptionUpdate.project_id == project.id, WorldPerceptionUpdate.deleted_at.is_(None))
        .order_by(WorldPerceptionUpdate.created_at.desc())
    ).all()
    return character_updates, relationship_updates, story_events, world_updates
