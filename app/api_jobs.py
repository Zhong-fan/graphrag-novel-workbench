from __future__ import annotations

import logging
from datetime import datetime

from .api_support_project import _canonical_project_evolution, _workspace_record
from .config import Settings
from .db import db_session
from .graphrag_service import GraphRAGService
from .models import Project

logger = logging.getLogger(__name__)


def create_run_index_job(settings: Settings):
    def run_index_job(project_id: int) -> None:
        with db_session() as db:
            project = db.get(Project, project_id)
            if project is None:
                return

            graphrag = GraphRAGService(settings)
            workspace_path = graphrag.workspace_path(project)
            record = _workspace_record(db, project, workspace_path)
            canonical_character_updates, canonical_relationship_updates, canonical_story_events, canonical_world_updates = _canonical_project_evolution(
                db,
                project,
            )
            project.indexing_status = "indexing"
            record.neo4j_sync_status = "indexing"
            db.commit()

            try:
                graphrag.index_project(
                    project,
                    list(project.memories),
                    list(project.source_documents),
                    record,
                    character_cards=list(project.character_cards),
                    character_updates=canonical_character_updates,
                    relationship_updates=canonical_relationship_updates,
                    story_events=canonical_story_events,
                    world_updates=canonical_world_updates,
                )
                project.indexing_status = "ready"
                record.neo4j_sync_status = "synced"
                record.last_indexed_at = datetime.utcnow()
                db.commit()
            except Exception:
                logger.exception("Background GraphRAG index failed for project_id=%s", project_id)
                db.rollback()
                project = db.get(Project, project_id)
                if project is None:
                    return
                record = project.graph_workspace
                project.indexing_status = "failed"
                if record is not None:
                    record.neo4j_sync_status = "failed"
                db.commit()

    return run_index_job
