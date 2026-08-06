from __future__ import annotations

import hashlib

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import load_settings


SCHEMA_MIGRATIONS_TABLE = "schema_migrations"
WORKSPACE_SCHEMA_MIGRATION = "20260507_0001_workspace_schema"
NOVEL_PROJECT_TITLE_MIGRATION = "20260510_0002_novel_project_titles"
PROJECT_REFERENCE_WORK_FIELDS_MIGRATION = "20260511_0003_project_reference_work_fields"
GENERATION_RUN_MEDIUMTEXT_MIGRATION = "20260512_0004_generation_run_mediumtext"
LONGFORM_PIPELINE_SCHEMA_MIGRATION = "20260515_0005_longform_pipeline_schema"
LONGFORM_BATCH_QUEUE_SCHEMA_MIGRATION = "20260516_0006_longform_batch_queue_schema"
LONGFORM_ASYNC_METADATA_SCHEMA_MIGRATION = "20260516_0007_longform_async_metadata_schema"
PROJECT_VISUAL_STYLE_FIELDS_MIGRATION = "20260517_0008_project_visual_style_fields"
CHARACTER_CARD_VOICE_FIELDS_MIGRATION = "20260517_0009_character_card_voice_fields"
LONGFORM_SCHEMA_PARITY_MIGRATION = "20260518_0010_longform_schema_parity"
CONTEXT_PACK_SCHEMA_MIGRATION = "20260518_0011_context_pack_schema"
MEDIA_ASSET_META_MEDIUMTEXT_MIGRATION = "20260519_0012_media_asset_meta_mediumtext"
STORY_BOUNDARY_SCHEMA_MIGRATION = "20260519_0013_story_boundary_schema"
REFERENCE_POLICY_SCHEMA_MIGRATION = "20260519_0014_reference_policy_schema"
REFERENCE_FACT_SCHEMA_MIGRATION = "20260519_0015_reference_fact_schema"
REFERENCE_IMAGE_ASSET_SCHEMA_MIGRATION = "20260519_0016_reference_image_asset_schema"
CHARACTER_REFERENCE_PROFILE_SCHEMA_MIGRATION = "20260520_0017_character_reference_profile_schema"
REFERENCE_IMAGE_ASSET_URL_HASH_MIGRATION = "20260520_0018_reference_image_asset_url_hash"
REFERENCE_IMAGE_ASSET_META_MIGRATION = "20260523_0019_reference_image_asset_meta"
MEDIA_ASSET_DELETED_AT_MIGRATION = "20260603_0020_media_asset_deleted_at"
MEDIA_PUBLICATION_SCHEMA_MIGRATION = "20260806_0021_media_publication_schema"
CHARACTER_IDENTITY_VERSIONS_SCHEMA_MIGRATION = "20260806_0022_character_identity_versions_schema"
GENERATION_EVIDENCE_SCHEMA_MIGRATION = "20260806_0023_generation_evidence_schema"
EXCEPTION_INBOX_SCHEMA_MIGRATION = "20260806_0024_exception_inbox_schema"
VOICE_DESIGN_SCHEMA_MIGRATION = "20260806_0025_voice_design_schema"
ASSET_VERSION_SCHEMA_MIGRATION = "20260806_0026_asset_version_schema"


settings = load_settings()
engine = create_engine(
    settings.sqlalchemy_database_url,
    future=True,
    pool_pre_ping=True,
    connect_args={"charset": "utf8mb4", "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema() -> None:
    with engine.begin() as connection:
        _ensure_schema_migrations_table(connection)
        _run_schema_migration(
            connection,
            WORKSPACE_SCHEMA_MIGRATION,
            "Workspace folders, project chapters, published novel links, and soft-delete fields",
            _migrate_workspace_schema,
        )
        _run_schema_migration(
            connection,
            NOVEL_PROJECT_TITLE_MIGRATION,
            "Use project titles as published novel titles",
            _migrate_novel_project_titles,
        )
        _run_schema_migration(
            connection,
            PROJECT_REFERENCE_WORK_FIELDS_MIGRATION,
            "Backfill missing project reference-work fields in older workspace schemas",
            _migrate_project_reference_work_fields,
        )
        _run_schema_migration(
            connection,
            GENERATION_RUN_MEDIUMTEXT_MIGRATION,
            "Upgrade generation_runs large text columns to MEDIUMTEXT for workbench draft persistence",
            _migrate_generation_run_mediumtext,
        )
        _run_schema_migration(
            connection,
            LONGFORM_PIPELINE_SCHEMA_MIGRATION,
            "Longform planning, revision, batch generation, and storyboard pipeline tables",
            _migrate_longform_pipeline_schema,
        )
        _run_schema_migration(
            connection,
            LONGFORM_BATCH_QUEUE_SCHEMA_MIGRATION,
            "Longform DB-backed batch generation chapter tasks and task events",
            _migrate_longform_batch_queue_schema,
        )
        _run_schema_migration(
            connection,
            LONGFORM_ASYNC_METADATA_SCHEMA_MIGRATION,
            "Longform async worker metadata for batch and storyboard jobs",
            _migrate_longform_async_metadata_schema,
        )
        _run_schema_migration(
            connection,
            PROJECT_VISUAL_STYLE_FIELDS_MIGRATION,
            "Project-level visual style lock fields for image and video generation",
            _migrate_project_visual_style_fields,
        )
        _run_schema_migration(
            connection,
            CHARACTER_CARD_VOICE_FIELDS_MIGRATION,
            "Character-card voice provider, speaker, style, speed, and pitch fields",
            _migrate_character_card_voice_fields,
        )
        _run_schema_migration(
            connection,
            LONGFORM_SCHEMA_PARITY_MIGRATION,
            "Backfill missing longform columns and enforce utf8mb4 defaults on current pipeline tables",
            _migrate_longform_schema_parity,
        )
        _run_schema_migration(
            connection,
            CONTEXT_PACK_SCHEMA_MIGRATION,
            "Context Pack snapshots and feed previews for pre-generation review",
            _migrate_context_pack_schema,
        )
        _run_schema_migration(
            connection,
            MEDIA_ASSET_META_MEDIUMTEXT_MIGRATION,
            "Upgrade media_assets.meta_json to MEDIUMTEXT for local media metadata",
            _migrate_media_asset_meta_mediumtext,
        )
        _run_schema_migration(
            connection,
            STORY_BOUNDARY_SCHEMA_MIGRATION,
            "Project-level story boundary text and structured rule storage",
            _migrate_story_boundary_schema,
        )
        _run_schema_migration(
            connection,
            REFERENCE_POLICY_SCHEMA_MIGRATION,
            "Project-level reference inheritance policy and rewrite-start fields",
            _migrate_reference_policy_schema,
        )
        _run_schema_migration(
            connection,
            REFERENCE_FACT_SCHEMA_MIGRATION,
            "Derived reference facts for inherited reference-work constraints",
            _migrate_reference_fact_schema,
        )
        _run_schema_migration(
            connection,
            REFERENCE_IMAGE_ASSET_SCHEMA_MIGRATION,
            "Reference image candidates and approval state",
            _migrate_reference_image_asset_schema,
        )
        _run_schema_migration(
            connection,
            CHARACTER_REFERENCE_PROFILE_SCHEMA_MIGRATION,
            "Character visual identity profile state",
            _migrate_character_reference_profile_schema,
        )
        _run_schema_migration(
            connection,
            REFERENCE_IMAGE_ASSET_URL_HASH_MIGRATION,
            "Use a fixed-width URL hash for reference image asset uniqueness",
            _migrate_reference_image_asset_url_hash_schema,
        )
        _run_schema_migration(
            connection,
            REFERENCE_IMAGE_ASSET_META_MIGRATION,
            "Reference image asset metadata for uploaded assets and AI classification state",
            _migrate_reference_image_asset_meta_schema,
        )
        _run_schema_migration(
            connection,
            MEDIA_ASSET_DELETED_AT_MIGRATION,
            "Soft-delete media assets for recycle bin restore",
            _migrate_media_asset_deleted_at_schema,
        )
        _run_schema_migration(
            connection,
            MEDIA_PUBLICATION_SCHEMA_MIGRATION,
            "Provider-readable expiring media publication records",
            _migrate_media_publication_schema,
        )
        _run_schema_migration(
            connection,
            CHARACTER_IDENTITY_VERSIONS_SCHEMA_MIGRATION,
            "Immutable character identity and appearance version tables",
            _migrate_character_identity_versions_schema,
        )
        _run_schema_migration(
            connection,
            GENERATION_EVIDENCE_SCHEMA_MIGRATION,
            "Append-only generation attempts with redacted trace evidence",
            _migrate_generation_evidence_schema,
        )
        _run_schema_migration(
            connection,
            EXCEPTION_INBOX_SCHEMA_MIGRATION,
            "Exception inbox items with recommended action and bounded options",
            _migrate_exception_inbox_schema,
        )
        _run_schema_migration(
            connection,
            VOICE_DESIGN_SCHEMA_MIGRATION,
            "Approval-gated voice design records and character-card binding",
            _migrate_voice_design_schema,
        )
        _run_schema_migration(
            connection,
            ASSET_VERSION_SCHEMA_MIGRATION,
            "Version snapshots for reversible auto-adopted asset changes",
            _migrate_asset_version_schema,
        )
    _backfill_character_reference_profiles()


def _ensure_schema_migrations_table(connection) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA_MIGRATIONS_TABLE} (
                version VARCHAR(80) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _run_schema_migration(connection, version: str, name: str, migrate) -> None:
    already_applied = connection.execute(
        text(f"SELECT version FROM {SCHEMA_MIGRATIONS_TABLE} WHERE version = :version"),
        {"version": version},
    ).first()
    if already_applied is not None:
        return

    migrate(connection)
    connection.execute(
        text(f"INSERT INTO {SCHEMA_MIGRATIONS_TABLE} (version, name) VALUES (:version, :name)"),
        {"version": version, "name": name},
    )


def _table_names() -> set[str]:
    return set(inspect(engine).get_table_names())


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _column_specs(table_name: str) -> dict[str, dict]:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return {}
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _migrate_workspace_schema(connection) -> None:
    tables = _table_names()
    if "projects" not in tables or "novels" not in tables:
        return

    project_columns = _column_names("projects")
    if "project_folders" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE project_folders (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    user_id INTEGER NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_project_folders_user_name UNIQUE (user_id, name)
                )
                """
            )
        )

    if "style_profile" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN style_profile VARCHAR(40) NULL"))
        connection.execute(text("UPDATE projects SET style_profile = 'light_novel' WHERE style_profile IS NULL OR style_profile = ''"))
    if "indexing_status" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN indexing_status VARCHAR(40) NULL"))
        connection.execute(text("UPDATE projects SET indexing_status = 'stale' WHERE indexing_status IS NULL OR indexing_status = ''"))
    if "reference_work" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work VARCHAR(255) NULL"))
        connection.execute(text("UPDATE projects SET reference_work = '' WHERE reference_work IS NULL"))
    if "reference_work_creator" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_creator VARCHAR(255) NULL"))
        connection.execute(text("UPDATE projects SET reference_work_creator = '' WHERE reference_work_creator IS NULL"))
    if "reference_work_medium" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_medium VARCHAR(120) NULL"))
        connection.execute(text("UPDATE projects SET reference_work_medium = '' WHERE reference_work_medium IS NULL"))
    if "reference_work_synopsis" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_synopsis TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_synopsis = '' WHERE reference_work_synopsis IS NULL"))
    if "reference_work_style_traits_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_style_traits_json TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_style_traits_json = '[]' WHERE reference_work_style_traits_json IS NULL"))
    if "reference_work_world_traits_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_world_traits_json TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_world_traits_json = '[]' WHERE reference_work_world_traits_json IS NULL"))
    if "reference_work_narrative_constraints_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_narrative_constraints_json TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_narrative_constraints_json = '[]' WHERE reference_work_narrative_constraints_json IS NULL"))
    if "reference_work_confidence_note" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_confidence_note TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_confidence_note = '' WHERE reference_work_confidence_note IS NULL"))
    if "folder_id" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN folder_id INTEGER NULL"))
    if "deleted_at" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN deleted_at DATETIME NULL"))
    if "premise" in project_columns:
        connection.execute(text("UPDATE projects SET premise = '' WHERE premise IS NULL"))
    if "indexing_status" in _column_names("projects"):
        connection.execute(text("UPDATE projects SET indexing_status = 'stale' WHERE indexing_status IS NULL OR indexing_status = ''"))

    if "project_chapters" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE project_chapters (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    premise TEXT NOT NULL,
                    chapter_no INTEGER NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_project_chapters_project_chapter_no UNIQUE (project_id, chapter_no)
                )
                """
            )
        )

    novel_columns = _column_names("novels")
    if "author_name" not in novel_columns:
        connection.execute(text("ALTER TABLE novels ADD COLUMN author_name VARCHAR(100) NULL"))
        connection.execute(
            text(
                """
                UPDATE novels n
                JOIN users u ON u.id = n.author_id
                SET n.author_name = u.display_name
                WHERE n.author_name IS NULL OR n.author_name = ''
                """
            )
        )
        connection.execute(text("UPDATE novels SET author_name = '佚名' WHERE author_name IS NULL OR author_name = ''"))

    novel_columns = _column_names("novels")
    if "owner_id" not in novel_columns and "author_id" in novel_columns:
        connection.execute(text("ALTER TABLE novels ADD COLUMN owner_id INTEGER NULL"))
        connection.execute(text("UPDATE novels SET owner_id = author_id WHERE owner_id IS NULL"))
    if "project_id" not in novel_columns:
        connection.execute(text("ALTER TABLE novels ADD COLUMN project_id INTEGER NULL"))
    if "source_generation_id" not in novel_columns:
        connection.execute(text("ALTER TABLE novels ADD COLUMN source_generation_id INTEGER NULL"))
    if {"novel_chapters", "generation_runs"}.issubset(_table_names()):
        connection.execute(
            text(
                """
                UPDATE novels n
                JOIN novel_chapters c ON c.novel_id = n.id AND c.chapter_no = 1
                JOIN generation_runs g
                  ON g.title = c.title
                 AND (g.summary = c.summary OR c.summary = '' OR g.summary = '')
                SET
                  n.project_id = COALESCE(n.project_id, g.project_id),
                  n.source_generation_id = COALESCE(n.source_generation_id, g.id)
                WHERE n.project_id IS NULL OR n.source_generation_id IS NULL
                """
            )
        )
    novel_columns = _column_names("novels")
    if "deleted_at" not in novel_columns:
        connection.execute(text("ALTER TABLE novels ADD COLUMN deleted_at DATETIME NULL"))

    if "generation_runs" in _table_names():
        generation_columns = _column_names("generation_runs")
        if "project_chapter_id" not in generation_columns:
            connection.execute(text("ALTER TABLE generation_runs ADD COLUMN project_chapter_id INTEGER NULL"))
        if "scene_card" not in generation_columns:
            connection.execute(text("ALTER TABLE generation_runs ADD COLUMN scene_card TEXT NULL"))
            connection.execute(text("UPDATE generation_runs SET scene_card = '' WHERE scene_card IS NULL"))
        if "evolution_snapshot" not in generation_columns:
            connection.execute(text("ALTER TABLE generation_runs ADD COLUMN evolution_snapshot TEXT NULL"))
            connection.execute(text("UPDATE generation_runs SET evolution_snapshot = '' WHERE evolution_snapshot IS NULL"))
        if "generation_trace" not in generation_columns:
            connection.execute(text("ALTER TABLE generation_runs ADD COLUMN generation_trace TEXT NULL"))
            connection.execute(text("UPDATE generation_runs SET generation_trace = '' WHERE generation_trace IS NULL"))
        if "canonicalized_at" not in generation_columns:
            connection.execute(text("ALTER TABLE generation_runs ADD COLUMN canonicalized_at DATETIME NULL"))

    if "character_cards" in _table_names():
        character_columns = _column_names("character_cards")
        if "deleted_at" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN deleted_at DATETIME NULL"))
        if "voice_provider" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_provider VARCHAR(80) NULL"))
            connection.execute(text("UPDATE character_cards SET voice_provider = '' WHERE voice_provider IS NULL"))
        if "voice_speaker" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_speaker VARCHAR(120) NULL"))
            connection.execute(text("UPDATE character_cards SET voice_speaker = '' WHERE voice_speaker IS NULL"))
        if "voice_style" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_style VARCHAR(120) NULL"))
            connection.execute(text("UPDATE character_cards SET voice_style = '' WHERE voice_style IS NULL"))
        if "voice_speed" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_speed FLOAT NULL"))
            connection.execute(text("UPDATE character_cards SET voice_speed = 1.0 WHERE voice_speed IS NULL"))
        if "voice_pitch" not in character_columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_pitch FLOAT NULL"))
            connection.execute(text("UPDATE character_cards SET voice_pitch = 0.0 WHERE voice_pitch IS NULL"))

    for table_name in (
        "character_state_updates",
        "relationship_state_updates",
        "story_events",
        "world_perception_updates",
    ):
        if table_name in _table_names():
            table_columns = _column_names(table_name)
            if "deleted_at" not in table_columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN deleted_at DATETIME NULL"))


def _migrate_novel_project_titles(connection) -> None:
    if not {"novels", "projects", "novel_chapters"}.issubset(_table_names()):
        return
    novel_columns = _column_names("novels")
    if "project_id" not in novel_columns:
        return
    connection.execute(
        text(
            """
            UPDATE novels n
            JOIN projects p ON p.id = n.project_id
            JOIN novel_chapters c ON c.novel_id = n.id AND c.chapter_no = 1
            SET n.title = p.title
            WHERE n.project_id IS NOT NULL
              AND n.title = c.title
              AND p.title <> ''
            """
        )
    )


def _migrate_project_reference_work_fields(connection) -> None:
    if "projects" not in _table_names():
        return

    project_columns = _column_names("projects")
    if "indexing_status" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN indexing_status VARCHAR(40) NULL"))
        connection.execute(text("UPDATE projects SET indexing_status = 'stale' WHERE indexing_status IS NULL OR indexing_status = ''"))
    if "reference_work" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work VARCHAR(255) NULL"))
        connection.execute(text("UPDATE projects SET reference_work = '' WHERE reference_work IS NULL"))
    if "reference_work_creator" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_creator VARCHAR(255) NULL"))
        connection.execute(text("UPDATE projects SET reference_work_creator = '' WHERE reference_work_creator IS NULL"))
    if "reference_work_medium" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_medium VARCHAR(120) NULL"))
        connection.execute(text("UPDATE projects SET reference_work_medium = '' WHERE reference_work_medium IS NULL"))
    if "reference_work_synopsis" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_synopsis TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_synopsis = '' WHERE reference_work_synopsis IS NULL"))
    if "reference_work_style_traits_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_style_traits_json TEXT NULL"))
        connection.execute(
            text("UPDATE projects SET reference_work_style_traits_json = '[]' WHERE reference_work_style_traits_json IS NULL")
        )
    if "reference_work_world_traits_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_world_traits_json TEXT NULL"))
        connection.execute(
            text("UPDATE projects SET reference_work_world_traits_json = '[]' WHERE reference_work_world_traits_json IS NULL")
        )
    if "reference_work_narrative_constraints_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_narrative_constraints_json TEXT NULL"))
        connection.execute(
            text(
                "UPDATE projects SET reference_work_narrative_constraints_json = '[]' "
                "WHERE reference_work_narrative_constraints_json IS NULL"
            )
        )
    if "reference_work_confidence_note" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_work_confidence_note TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_work_confidence_note = '' WHERE reference_work_confidence_note IS NULL"))
    if "indexing_status" in _column_names("projects"):
        connection.execute(text("UPDATE projects SET indexing_status = 'stale' WHERE indexing_status IS NULL OR indexing_status = ''"))


def _migrate_project_visual_style_fields(connection) -> None:
    if "projects" not in _table_names():
        return
    project_columns = _column_names("projects")
    if "visual_style_locked" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_locked BOOLEAN NULL"))
        connection.execute(text("UPDATE projects SET visual_style_locked = TRUE WHERE visual_style_locked IS NULL"))
    if "visual_style_medium" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_medium VARCHAR(80) NULL"))
        connection.execute(text("UPDATE projects SET visual_style_medium = '' WHERE visual_style_medium IS NULL"))
    if "visual_style_artists_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_artists_json TEXT NULL"))
        connection.execute(text("UPDATE projects SET visual_style_artists_json = '[]' WHERE visual_style_artists_json IS NULL"))
    if "visual_style_positive_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_positive_json TEXT NULL"))
        connection.execute(
            text("UPDATE projects SET visual_style_positive_json = reference_work_style_traits_json WHERE visual_style_positive_json IS NULL")
        )
    if "visual_style_negative_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_negative_json TEXT NULL"))
        connection.execute(
            text(
                "UPDATE projects SET visual_style_negative_json = "
                "'[]' "
                "WHERE visual_style_negative_json IS NULL"
            )
        )
    if "visual_style_notes" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN visual_style_notes TEXT NULL"))
        connection.execute(text("UPDATE projects SET visual_style_notes = '' WHERE visual_style_notes IS NULL"))


def _migrate_character_card_voice_fields(connection) -> None:
    if "character_cards" not in _table_names():
        return
    character_columns = _column_names("character_cards")
    if "voice_provider" not in character_columns:
        connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_provider VARCHAR(80) NULL"))
        connection.execute(text("UPDATE character_cards SET voice_provider = '' WHERE voice_provider IS NULL"))
    if "voice_speaker" not in character_columns:
        connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_speaker VARCHAR(120) NULL"))
        connection.execute(text("UPDATE character_cards SET voice_speaker = '' WHERE voice_speaker IS NULL"))
    if "voice_style" not in character_columns:
        connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_style VARCHAR(120) NULL"))
        connection.execute(text("UPDATE character_cards SET voice_style = '' WHERE voice_style IS NULL"))
    if "voice_speed" not in character_columns:
        connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_speed FLOAT NULL"))
        connection.execute(text("UPDATE character_cards SET voice_speed = 1.0 WHERE voice_speed IS NULL"))
    if "voice_pitch" not in character_columns:
        connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_pitch FLOAT NULL"))
        connection.execute(text("UPDATE character_cards SET voice_pitch = 0.0 WHERE voice_pitch IS NULL"))


def _migrate_longform_schema_parity(connection) -> None:
    tables = _table_names()

    connection.execute(text("ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    for table_name in (
        "projects",
        "storyboards",
        "storyboard_shots",
        "media_assets",
        "video_tasks",
        "task_events",
        "series_plans",
        "series_plan_versions",
        "arc_plans",
        "chapter_outlines",
        "outline_feedback_items",
        "outline_revision_plans",
        "draft_versions",
        "batch_generation_jobs",
        "batch_generation_chapter_tasks",
        "novels",
        "novel_chapters",
        "generation_runs",
    ):
        if table_name in tables:
            connection.execute(text(f"ALTER TABLE {table_name} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    if "storyboard_shots" in tables:
        shot_columns = _column_names("storyboard_shots")
        if "meta_json" not in shot_columns:
            connection.execute(text("ALTER TABLE storyboard_shots ADD COLUMN meta_json TEXT NULL"))
            connection.execute(text("UPDATE storyboard_shots SET meta_json = '{}' WHERE meta_json IS NULL"))
            connection.execute(text("ALTER TABLE storyboard_shots MODIFY COLUMN meta_json TEXT NOT NULL"))

    if "storyboards" in tables:
        storyboard_columns = _column_names("storyboards")
        if "worker_id" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
        if "worker_started_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_started_at DATETIME NULL"))
        if "last_heartbeat_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN last_heartbeat_at DATETIME NULL"))
        if "error_message" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN error_message TEXT NULL"))
            connection.execute(text("UPDATE storyboards SET error_message = '' WHERE error_message IS NULL"))
            connection.execute(text("ALTER TABLE storyboards MODIFY COLUMN error_message TEXT NOT NULL"))

    if "task_events" in tables:
        event_columns = _column_names("task_events")
        if "storyboard_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN storyboard_id INTEGER NULL"))
        if "video_task_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN video_task_id INTEGER NULL"))
        if "chapter_task_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN chapter_task_id INTEGER NULL"))
        job_column = _column_specs("task_events").get("job_id")
        if job_column is not None and not job_column.get("nullable", True):
            connection.execute(text("ALTER TABLE task_events MODIFY COLUMN job_id INTEGER NULL"))

    if "batch_generation_jobs" in tables:
        job_columns = _column_names("batch_generation_jobs")
        if "worker_id" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
        if "worker_started_at" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_started_at DATETIME NULL"))
        if "last_heartbeat_at" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN last_heartbeat_at DATETIME NULL"))

    if "batch_generation_chapter_tasks" in tables:
        chapter_task_columns = _column_names("batch_generation_chapter_tasks")
        if "storyboard_id" not in chapter_task_columns:
            connection.execute(text("ALTER TABLE batch_generation_chapter_tasks ADD COLUMN storyboard_id INTEGER NULL"))


def _migrate_context_pack_schema(connection) -> None:
    tables = _table_names()
    if "context_packs" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE context_packs (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    version_no INTEGER NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft',
                    reference_mode VARCHAR(40) NOT NULL DEFAULT 'hybrid_reference',
                    user_notes TEXT NOT NULL,
                    source_fingerprint VARCHAR(64) NOT NULL DEFAULT '',
                    project_snapshot_json MEDIUMTEXT NOT NULL,
                    character_snapshot_json MEDIUMTEXT NOT NULL,
                    reference_snapshot_json MEDIUMTEXT NOT NULL,
                    source_snapshot_json MEDIUMTEXT NOT NULL,
                    conflict_report_json MEDIUMTEXT NOT NULL,
                    user_decisions_json MEDIUMTEXT NOT NULL,
                    derived_constraints_json MEDIUMTEXT NOT NULL,
                    feed_preview_json MEDIUMTEXT NOT NULL,
                    confirmed_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_context_packs_project_version UNIQUE (project_id, version_no)
                )
                """
            )
        )
        return
    context_columns = _column_names("context_packs")
    if "user_decisions_json" not in context_columns:
        connection.execute(text("ALTER TABLE context_packs ADD COLUMN user_decisions_json MEDIUMTEXT NULL"))
        connection.execute(text("UPDATE context_packs SET user_decisions_json = '{}' WHERE user_decisions_json IS NULL"))
        connection.execute(text("ALTER TABLE context_packs MODIFY COLUMN user_decisions_json MEDIUMTEXT NOT NULL"))


def _migrate_media_asset_meta_mediumtext(connection) -> None:
    column_specs = _column_specs("media_assets")
    if not column_specs:
        return
    column = column_specs.get("meta_json")
    if column is None:
        return
    column_type = str(column["type"]).upper()
    if "MEDIUMTEXT" in column_type:
        return
    connection.execute(text("UPDATE media_assets SET meta_json = '{}' WHERE meta_json IS NULL"))
    connection.execute(text("ALTER TABLE media_assets MODIFY COLUMN meta_json MEDIUMTEXT NOT NULL"))


def _migrate_media_asset_deleted_at_schema(connection) -> None:
    if "media_assets" not in _table_names():
        return
    media_asset_columns = _column_names("media_assets")
    if "deleted_at" not in media_asset_columns:
        connection.execute(text("ALTER TABLE media_assets ADD COLUMN deleted_at DATETIME NULL"))


def _migrate_story_boundary_schema(connection) -> None:
    if "projects" not in _table_names():
        return
    project_columns = _column_names("projects")
    if "story_boundary_text" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN story_boundary_text MEDIUMTEXT NULL"))
        connection.execute(text("UPDATE projects SET story_boundary_text = '' WHERE story_boundary_text IS NULL"))
        connection.execute(text("ALTER TABLE projects MODIFY COLUMN story_boundary_text MEDIUMTEXT NOT NULL"))
    if "story_boundary_rules_json" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN story_boundary_rules_json MEDIUMTEXT NULL"))
        connection.execute(text("UPDATE projects SET story_boundary_rules_json = '[]' WHERE story_boundary_rules_json IS NULL"))
        connection.execute(text("ALTER TABLE projects MODIFY COLUMN story_boundary_rules_json MEDIUMTEXT NOT NULL"))


def _migrate_reference_policy_schema(connection) -> None:
    if "projects" not in _table_names():
        return
    project_columns = _column_names("projects")
    if "reference_inheritance_mode" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_inheritance_mode VARCHAR(40) NULL"))
        connection.execute(text("UPDATE projects SET reference_inheritance_mode = 'style_only' WHERE reference_inheritance_mode IS NULL OR reference_inheritance_mode = ''"))
        connection.execute(text("ALTER TABLE projects MODIFY COLUMN reference_inheritance_mode VARCHAR(40) NOT NULL"))
    if "reference_rewrite_start" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_rewrite_start TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_rewrite_start = '' WHERE reference_rewrite_start IS NULL"))
        connection.execute(text("ALTER TABLE projects MODIFY COLUMN reference_rewrite_start TEXT NOT NULL"))
    if "reference_authorized_changes" not in project_columns:
        connection.execute(text("ALTER TABLE projects ADD COLUMN reference_authorized_changes TEXT NULL"))
        connection.execute(text("UPDATE projects SET reference_authorized_changes = '' WHERE reference_authorized_changes IS NULL"))
        connection.execute(text("ALTER TABLE projects MODIFY COLUMN reference_authorized_changes TEXT NOT NULL"))


def _migrate_reference_fact_schema(connection) -> None:
    if "reference_facts" in _table_names():
        return
    connection.execute(
        text(
            """
            CREATE TABLE reference_facts (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                project_id INTEGER NOT NULL,
                fact_type VARCHAR(80) NOT NULL,
                reference_key VARCHAR(255) NOT NULL,
                chapter_effective_until INTEGER NULL,
                payload_json MEDIUMTEXT NOT NULL,
                status VARCHAR(40) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_reference_facts_project_key_type (project_id, reference_key, fact_type)
            )
            """
        )
    )


def _migrate_reference_image_asset_schema(connection) -> None:
    if "reference_image_assets" in _table_names():
        return
    connection.execute(
        text(
            """
            CREATE TABLE reference_image_assets (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                project_id INTEGER NOT NULL,
                source_work VARCHAR(255) NOT NULL,
                asset_kind VARCHAR(80) NOT NULL DEFAULT 'stills',
                remote_url VARCHAR(1000) NOT NULL,
                remote_url_hash VARCHAR(64) NOT NULL,
                provider VARCHAR(80) NOT NULL DEFAULT 'manual',
                source_page VARCHAR(1000) NOT NULL DEFAULT '',
                mapped_character_name VARCHAR(120) NOT NULL DEFAULT '',
                status VARCHAR(40) NOT NULL DEFAULT 'candidate',
                meta_json TEXT NOT NULL DEFAULT ('{}'),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_reference_image_assets_project_url_hash (project_id, remote_url_hash)
            )
            """
        )
    )


def _migrate_reference_image_asset_url_hash_schema(connection) -> None:
    if "reference_image_assets" not in _table_names():
        return

    columns = _column_names("reference_image_assets")
    if "remote_url_hash" not in columns:
        connection.execute(text("ALTER TABLE reference_image_assets ADD COLUMN remote_url_hash VARCHAR(64) NULL"))

    rows = connection.execute(
        text(
            """
            SELECT id, remote_url
            FROM reference_image_assets
            WHERE remote_url_hash IS NULL OR remote_url_hash = ''
            """
        )
    ).mappings()
    for row in rows:
        connection.execute(
            text("UPDATE reference_image_assets SET remote_url_hash = :remote_url_hash WHERE id = :id"),
            {"id": row["id"], "remote_url_hash": _reference_url_hash(row["remote_url"])},
        )

    if connection.dialect.name == "mysql":
        connection.execute(text("ALTER TABLE reference_image_assets MODIFY COLUMN remote_url_hash VARCHAR(64) NOT NULL"))

    index_names = _schema_index_names(connection, "reference_image_assets")
    if "uq_reference_image_assets_project_url" in index_names:
        if connection.dialect.name == "mysql":
            connection.execute(text("ALTER TABLE reference_image_assets DROP INDEX uq_reference_image_assets_project_url"))
        else:
            connection.execute(text("DROP INDEX IF EXISTS uq_reference_image_assets_project_url"))

    index_names = _schema_index_names(connection, "reference_image_assets")
    if "uq_reference_image_assets_project_url_hash" not in index_names:
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_reference_image_assets_project_url_hash
                ON reference_image_assets (project_id, remote_url_hash)
                """
            )
        )


def _migrate_reference_image_asset_meta_schema(connection) -> None:
    if "reference_image_assets" not in _table_names():
        return
    columns = _column_names("reference_image_assets")
    if "meta_json" not in columns:
        connection.execute(text("ALTER TABLE reference_image_assets ADD COLUMN meta_json TEXT NOT NULL DEFAULT ('{}')"))


def _schema_index_names(connection, table_name: str) -> set[str]:
    inspector = inspect(connection)
    names = {item["name"] for item in inspector.get_indexes(table_name) if item.get("name")}
    names.update(item["name"] for item in inspector.get_unique_constraints(table_name) if item.get("name"))
    return names


def _reference_url_hash(remote_url: str) -> str:
    return hashlib.sha256(str(remote_url or "").encode("utf-8")).hexdigest()


def _migrate_generation_run_mediumtext(connection) -> None:
    column_specs = _column_specs("generation_runs")
    if not column_specs:
        return

    def upgrade(column_name: str, *, nullable: bool) -> None:
        column = column_specs.get(column_name)
        if column is None:
            return
        column_type = str(column["type"]).upper()
        if "MEDIUMTEXT" in column_type:
            return
        if nullable:
            connection.execute(text(f"ALTER TABLE generation_runs MODIFY COLUMN {column_name} MEDIUMTEXT NULL"))
            return
        connection.execute(text(f"UPDATE generation_runs SET {column_name} = '' WHERE {column_name} IS NULL"))
        connection.execute(text(f"ALTER TABLE generation_runs MODIFY COLUMN {column_name} MEDIUMTEXT NOT NULL"))

    upgrade("content", nullable=False)
    upgrade("retrieval_context", nullable=False)
    upgrade("scene_card", nullable=False)
    upgrade("generation_trace", nullable=False)
    upgrade("evolution_snapshot", nullable=False)


def _migrate_longform_pipeline_schema(connection) -> None:
    tables = _table_names()
    if "projects" not in tables:
        return

    if "series_plans" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE series_plans (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    target_chapter_count INTEGER NOT NULL DEFAULT 12,
                    theme TEXT NOT NULL,
                    main_conflict TEXT NOT NULL,
                    ending_direction TEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft',
                    current_version_id INTEGER NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "series_plan_versions" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE series_plan_versions (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    series_plan_id INTEGER NOT NULL,
                    version_no INTEGER NOT NULL,
                    summary_json MEDIUMTEXT NOT NULL,
                    change_note TEXT NOT NULL,
                    source_feedback_snapshot TEXT NOT NULL,
                    created_by VARCHAR(40) NOT NULL DEFAULT 'planner',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "arc_plans" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE arc_plans (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    series_plan_id INTEGER NOT NULL,
                    version_id INTEGER NOT NULL,
                    arc_no INTEGER NOT NULL,
                    start_chapter_no INTEGER NOT NULL,
                    end_chapter_no INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    goal TEXT NOT NULL,
                    conflict TEXT NOT NULL,
                    turning_points_json TEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft',
                    CONSTRAINT uq_arc_plans_series_version_arc UNIQUE (series_plan_id, version_id, arc_no)
                )
                """
            )
        )

    if "chapter_outlines" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE chapter_outlines (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    series_plan_id INTEGER NOT NULL,
                    arc_plan_id INTEGER NULL,
                    chapter_no INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    outline_json MEDIUMTEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'outline_draft',
                    locked_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_chapter_outlines_series_chapter_no UNIQUE (series_plan_id, chapter_no)
                )
                """
            )
        )

    if "outline_feedback_items" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE outline_feedback_items (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    target_type VARCHAR(40) NOT NULL,
                    target_id INTEGER NOT NULL,
                    feedback_text TEXT NOT NULL,
                    feedback_type VARCHAR(60) NOT NULL DEFAULT 'general',
                    priority INTEGER NOT NULL DEFAULT 3,
                    status VARCHAR(40) NOT NULL DEFAULT 'pending',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "outline_revision_plans" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE outline_revision_plans (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    feedback_item_id INTEGER NOT NULL,
                    target_type VARCHAR(40) NOT NULL,
                    target_id INTEGER NOT NULL,
                    plan_json MEDIUMTEXT NOT NULL,
                    applied BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "draft_versions" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE draft_versions (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    chapter_outline_id INTEGER NOT NULL,
                    generation_run_id INTEGER NULL,
                    parent_version_id INTEGER NULL,
                    version_no INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    summary TEXT NOT NULL,
                    content MEDIUMTEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft_generated',
                    revision_reason TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_draft_versions_outline_version UNIQUE (chapter_outline_id, version_no)
                )
                """
            )
        )

    if "batch_generation_jobs" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE batch_generation_jobs (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    series_plan_id INTEGER NOT NULL,
                    start_chapter_no INTEGER NOT NULL,
                    end_chapter_no INTEGER NOT NULL,
                    job_status VARCHAR(40) NOT NULL DEFAULT 'pending',
                    current_chapter_no INTEGER NULL,
                    result_summary_json MEDIUMTEXT NOT NULL,
                    worker_id VARCHAR(120) NOT NULL DEFAULT '',
                    worker_started_at DATETIME NULL,
                    last_heartbeat_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "storyboards" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE storyboards (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    source_chapter_ids_json TEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft',
                    summary TEXT NOT NULL,
                    worker_id VARCHAR(120) NOT NULL DEFAULT '',
                    worker_started_at DATETIME NULL,
                    last_heartbeat_at DATETIME NULL,
                    error_message TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "storyboard_shots" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE storyboard_shots (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    storyboard_id INTEGER NOT NULL,
                    shot_no INTEGER NOT NULL,
                    narration_text TEXT NOT NULL,
                    visual_prompt TEXT NOT NULL,
                    character_refs_json TEXT NOT NULL,
                    scene_refs_json TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    duration_seconds FLOAT NOT NULL DEFAULT 4,
                    status VARCHAR(40) NOT NULL DEFAULT 'draft',
                    CONSTRAINT uq_storyboard_shots_storyboard_shot_no UNIQUE (storyboard_id, shot_no)
                )
                """
            )
        )

    if "media_assets" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE media_assets (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    storyboard_id INTEGER NULL,
                    shot_id INTEGER NULL,
                    asset_type VARCHAR(40) NOT NULL,
                    uri VARCHAR(500) NOT NULL DEFAULT '',
                    prompt TEXT NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'pending',
                    meta_json MEDIUMTEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    if "video_tasks" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE video_tasks (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    storyboard_id INTEGER NOT NULL,
                    task_status VARCHAR(40) NOT NULL DEFAULT 'pending',
                    output_uri VARCHAR(500) NOT NULL DEFAULT '',
                    progress_json TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def _migrate_longform_batch_queue_schema(connection) -> None:
    tables = _table_names()
    if "batch_generation_jobs" not in tables:
        return

    job_columns = _column_names("batch_generation_jobs")
    if "worker_id" not in job_columns:
        connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
    if "worker_started_at" not in job_columns:
        connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_started_at DATETIME NULL"))
    if "last_heartbeat_at" not in job_columns:
        connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN last_heartbeat_at DATETIME NULL"))

    if "batch_generation_chapter_tasks" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE batch_generation_chapter_tasks (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    job_id INTEGER NOT NULL,
                    chapter_outline_id INTEGER NOT NULL,
                    chapter_no INTEGER NOT NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'queued',
                    draft_version_id INTEGER NULL,
                    generation_run_id INTEGER NULL,
                    error_message TEXT NOT NULL,
                    started_at DATETIME NULL,
                    finished_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_batch_generation_task_job_chapter UNIQUE (job_id, chapter_no)
                )
                """
            )
        )

    if "task_events" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    job_id INTEGER NULL,
                    storyboard_id INTEGER NULL,
                    video_task_id INTEGER NULL,
                    chapter_task_id INTEGER NULL,
                    event_type VARCHAR(60) NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    else:
        event_columns = _column_names("task_events")
        if "storyboard_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN storyboard_id INTEGER NULL"))
        if "video_task_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN video_task_id INTEGER NULL"))
        job_column = _column_specs("task_events").get("job_id")
        if job_column is not None and not job_column.get("nullable", True):
            connection.execute(text("ALTER TABLE task_events MODIFY COLUMN job_id INTEGER NULL"))

    if "storyboards" in tables:
        storyboard_columns = _column_names("storyboards")
        if "worker_id" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
        if "worker_started_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_started_at DATETIME NULL"))
        if "last_heartbeat_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN last_heartbeat_at DATETIME NULL"))
        if "error_message" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN error_message TEXT NULL"))
            connection.execute(text("UPDATE storyboards SET error_message = '' WHERE error_message IS NULL"))
            connection.execute(text("ALTER TABLE storyboards MODIFY COLUMN error_message TEXT NOT NULL"))

    if "storyboard_shots" in tables:
        shot_columns = _column_names("storyboard_shots")
        if "meta_json" not in shot_columns:
            connection.execute(text("ALTER TABLE storyboard_shots ADD COLUMN meta_json TEXT NULL"))
            connection.execute(text("UPDATE storyboard_shots SET meta_json = '{}' WHERE meta_json IS NULL"))
            connection.execute(text("ALTER TABLE storyboard_shots MODIFY COLUMN meta_json TEXT NOT NULL"))


def _migrate_longform_async_metadata_schema(connection) -> None:
    tables = _table_names()
    if "batch_generation_jobs" in tables:
        job_columns = _column_names("batch_generation_jobs")
        if "worker_id" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
        if "worker_started_at" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN worker_started_at DATETIME NULL"))
        if "last_heartbeat_at" not in job_columns:
            connection.execute(text("ALTER TABLE batch_generation_jobs ADD COLUMN last_heartbeat_at DATETIME NULL"))

    if "task_events" in tables:
        event_columns = _column_names("task_events")
        if "storyboard_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN storyboard_id INTEGER NULL"))
        if "video_task_id" not in event_columns:
            connection.execute(text("ALTER TABLE task_events ADD COLUMN video_task_id INTEGER NULL"))
        job_column = _column_specs("task_events").get("job_id")
        if job_column is not None and not job_column.get("nullable", True):
            connection.execute(text("ALTER TABLE task_events MODIFY COLUMN job_id INTEGER NULL"))

    if "storyboards" in tables:
        storyboard_columns = _column_names("storyboards")
        if "worker_id" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_id VARCHAR(120) NOT NULL DEFAULT ''"))
        if "worker_started_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN worker_started_at DATETIME NULL"))
        if "last_heartbeat_at" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN last_heartbeat_at DATETIME NULL"))
        if "error_message" not in storyboard_columns:
            connection.execute(text("ALTER TABLE storyboards ADD COLUMN error_message TEXT NULL"))
            connection.execute(text("UPDATE storyboards SET error_message = '' WHERE error_message IS NULL"))
            connection.execute(text("ALTER TABLE storyboards MODIFY COLUMN error_message TEXT NOT NULL"))

    if "storyboard_shots" in tables:
        shot_columns = _column_names("storyboard_shots")
        if "meta_json" not in shot_columns:
            connection.execute(text("ALTER TABLE storyboard_shots ADD COLUMN meta_json TEXT NULL"))
            connection.execute(text("UPDATE storyboard_shots SET meta_json = '{}' WHERE meta_json IS NULL"))
            connection.execute(text("ALTER TABLE storyboard_shots MODIFY COLUMN meta_json TEXT NOT NULL"))


def _migrate_character_reference_profile_schema(connection) -> None:
    tables = _table_names()
    if "character_reference_profiles" not in tables:
        connection.execute(
            text(
                """
                CREATE TABLE character_reference_profiles (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    project_id INTEGER NOT NULL,
                    character_card_id INTEGER NOT NULL,
                    reference_character_name VARCHAR(120) NOT NULL DEFAULT '',
                    visual_reference_asset_ids_json TEXT NOT NULL,
                    locked_turnaround_asset_id INTEGER NULL,
                    status VARCHAR(40) NOT NULL DEFAULT 'unmapped',
                    notes TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_character_reference_profiles_project_character UNIQUE (project_id, character_card_id)
                )
                """
            )
        )


def _backfill_character_reference_profiles() -> None:
    from .models import Project
    from .visual_asset_service import CharacterReferenceProfileService

    service = CharacterReferenceProfileService()
    with SessionLocal() as session:
        projects = session.query(Project).filter(Project.deleted_at.is_(None)).all()
        for project in projects:
            service.ensure_profiles(session, project)
        session.commit()


def db_session() -> Session:
    return SessionLocal()


def _create_table_if_missing(connection, table_name: str) -> None:
    """Create an ORM-declared table only when it is absent.

    Uses the ORM metadata (dialect-correct DDL) and is idempotent, so the same
    migration is safe on fresh and existing databases.
    """
    if table_name in inspect(connection).get_table_names():
        return
    Base.metadata.tables[table_name].create(bind=connection)


def _migrate_media_publication_schema(connection) -> None:
    _create_table_if_missing(connection, "media_publications")


def _migrate_character_identity_versions_schema(connection) -> None:
    _create_table_if_missing(connection, "character_identity_versions")
    _create_table_if_missing(connection, "character_appearance_versions")


def _migrate_generation_evidence_schema(connection) -> None:
    _create_table_if_missing(connection, "generation_attempts")


def _migrate_exception_inbox_schema(connection) -> None:
    _create_table_if_missing(connection, "exception_inbox_items")


def _migrate_voice_design_schema(connection) -> None:
    _create_table_if_missing(connection, "voice_designs")
    if "character_cards" in inspect(connection).get_table_names():
        columns = {column["name"] for column in inspect(connection).get_columns("character_cards")}
        if "voice_design_id" not in columns:
            connection.execute(text("ALTER TABLE character_cards ADD COLUMN voice_design_id INTEGER NULL"))


def _migrate_asset_version_schema(connection) -> None:
    _create_table_if_missing(connection, "media_asset_versions")
