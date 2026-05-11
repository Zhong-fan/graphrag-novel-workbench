from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import load_settings


SCHEMA_MIGRATIONS_TABLE = "schema_migrations"
WORKSPACE_SCHEMA_MIGRATION = "20260507_0001_workspace_schema"
NOVEL_PROJECT_TITLE_MIGRATION = "20260510_0002_novel_project_titles"
PROJECT_REFERENCE_WORK_FIELDS_MIGRATION = "20260511_0003_project_reference_work_fields"


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

    if "graph_workspaces" in _table_names():
        graph_columns = _column_names("graph_workspaces")
        if "last_error" not in graph_columns:
            connection.execute(text("ALTER TABLE graph_workspaces ADD COLUMN last_error TEXT NULL"))
            connection.execute(text("UPDATE graph_workspaces SET last_error = '' WHERE last_error IS NULL"))

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


def db_session() -> Session:
    return SessionLocal()
