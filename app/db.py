from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import load_settings


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
    inspector = inspect(engine)
    if "novels" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("novels")}
    with engine.begin() as connection:
        project_columns = {column["name"] for column in inspector.get_columns("projects")} if "projects" in inspector.get_table_names() else set()
        if "project_folders" not in inspector.get_table_names():
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
        if "folder_id" not in project_columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN folder_id INTEGER NULL"))
        if "deleted_at" not in project_columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN deleted_at DATETIME NULL"))
        if "premise" in project_columns:
            connection.execute(text("UPDATE projects SET premise = '' WHERE premise IS NULL"))

        if "project_chapters" not in inspector.get_table_names():
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

        if "author_name" not in columns:
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

        refreshed = inspect(engine)
        refreshed_columns = {column["name"] for column in refreshed.get_columns("novels")}
        if "owner_id" not in refreshed_columns and "author_id" in refreshed_columns:
            connection.execute(text("ALTER TABLE novels ADD COLUMN owner_id INTEGER NULL"))
            connection.execute(text("UPDATE novels SET owner_id = author_id WHERE owner_id IS NULL"))
        if "project_id" not in refreshed_columns:
            connection.execute(text("ALTER TABLE novels ADD COLUMN project_id INTEGER NULL"))
        if "source_generation_id" not in refreshed_columns:
            connection.execute(text("ALTER TABLE novels ADD COLUMN source_generation_id INTEGER NULL"))
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
        if "deleted_at" not in refreshed_columns:
            connection.execute(text("ALTER TABLE novels ADD COLUMN deleted_at DATETIME NULL"))

        generation_columns = {column["name"] for column in inspector.get_columns("generation_runs")} if "generation_runs" in inspector.get_table_names() else set()
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

        if "character_cards" in inspector.get_table_names():
            character_columns = {column["name"] for column in inspector.get_columns("character_cards")}
            if "deleted_at" not in character_columns:
                connection.execute(text("ALTER TABLE character_cards ADD COLUMN deleted_at DATETIME NULL"))


def db_session() -> Session:
    return SessionLocal()
