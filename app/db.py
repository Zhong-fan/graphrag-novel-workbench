from __future__ import annotations

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


settings = load_settings()
engine = create_engine(
    settings.sqlalchemy_database_url,
    future=True,
    pool_pre_ping=True,
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
                    meta_json TEXT NOT NULL,
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


def db_session() -> Session:
    return SessionLocal()
