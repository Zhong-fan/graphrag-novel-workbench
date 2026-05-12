from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import Settings
from .contracts import GenerateRequest
from .evolution_service import EvolutionService
from .models import (
    CharacterStateUpdate,
    GenerationRun,
    Project,
    ProjectChapter,
    RelationshipStateUpdate,
    StoryEvent,
    WorldPerceptionUpdate,
)


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


def _replace_canonical_evolution(
    db: Session,
    project: Project,
    generation: GenerationRun,
    evolution_payload,
) -> None:
    for item in list(generation.character_state_updates):
        db.delete(item)
    for item in list(generation.relationship_state_updates):
        db.delete(item)
    for item in list(generation.story_events):
        db.delete(item)
    for item in list(generation.world_perception_updates):
        db.delete(item)
    db.flush()

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


def _canonicalize_generation(
    db: Session,
    settings: Settings,
    project: Project,
    project_chapter: ProjectChapter,
    generation: GenerationRun,
    *,
    adopted_title: str,
    adopted_summary: str,
    adopted_content: str,
) -> None:
    if generation.canonicalized_at is not None:
        return

    evolution = EvolutionService(settings)
    try:
        evolution_payload = evolution.extract_evolution(
            project_title=project.title,
            genre=project.genre,
            premise=project_chapter.premise,
            user_prompt=generation.prompt,
            title=adopted_title,
            summary=adopted_summary,
            content=adopted_content,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="正式章节演化抽取失败：" + str(exc)) from exc

    _replace_canonical_evolution(db, project, generation, evolution_payload)
    generation.canonicalized_at = datetime.utcnow()


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
        },
        "request": {
            "prompt_length": len(payload.prompt.strip()),
            "search_method": payload.search_method,
            "response_type": payload.response_type,
            "use_global_search": payload.use_global_search,
            "use_scene_card": payload.use_scene_card,
            "use_refiner": payload.use_refiner,
            "write_evolution": payload.write_evolution,
        },
        "context": {
            "premise_length": len(project_chapter.premise.strip()),
            "world_brief_length": len(project.world_brief.strip()),
            "writing_rules_length": len(project.writing_rules.strip()),
        },
        "steps": {},
    }
