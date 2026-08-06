from __future__ import annotations

import unittest

from sqlalchemy import create_engine, inspect, select, text

from app.db import (
    _ensure_schema_migrations_table,
    _migrate_character_identity_versions_schema,
    _migrate_exception_inbox_schema,
    _migrate_generation_evidence_schema,
    _migrate_asset_version_schema,
    _migrate_media_publication_schema,
    _migrate_voice_design_schema,
    _run_schema_migration,
)
from app.models import GenerationAttempt


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)

    def _apply(self, migrate, version: str) -> None:
        with self.engine.begin() as connection:
            _ensure_schema_migrations_table(connection)
            _run_schema_migration(connection, version, "roundtrip", migrate)

    def test_new_tables_created_by_migrations(self) -> None:
        self._apply(_migrate_media_publication_schema, "20260806_0021_media_publication_schema")
        self._apply(_migrate_character_identity_versions_schema, "20260806_0022_character_identity_versions_schema")
        self._apply(_migrate_generation_evidence_schema, "20260806_0023_generation_evidence_schema")
        self._apply(_migrate_exception_inbox_schema, "20260806_0024_exception_inbox_schema")
        self._apply(_migrate_voice_design_schema, "20260806_0025_voice_design_schema")
        self._apply(_migrate_asset_version_schema, "20260806_0026_asset_version_schema")

        with self.engine.connect() as connection:
            names = set(inspect(connection).get_table_names())
        for table in (
            "media_publications",
            "character_identity_versions",
            "character_appearance_versions",
            "generation_attempts",
            "exception_inbox_items",
            "voice_designs",
            "media_asset_versions",
        ):
            self.assertIn(table, names, table)

    def test_migrations_are_idempotent(self) -> None:
        self._apply(_migrate_generation_evidence_schema, "20260806_0023_generation_evidence_schema")
        # Re-run the same DDL under a new version: existing tables are skipped, no error.
        self._apply(_migrate_generation_evidence_schema, "20260806_0023_generation_evidence_schema-rerun")
        self._apply(_migrate_media_publication_schema, "20260806_0021_media_publication_schema")
        self._apply(_migrate_media_publication_schema, "20260806_0021_media_publication_schema-rerun")
        self._apply(_migrate_voice_design_schema, "20260806_0025_voice_design_schema")
        self._apply(_migrate_voice_design_schema, "20260806_0025_voice_design_schema-rerun")
        self._apply(_migrate_asset_version_schema, "20260806_0026_asset_version_schema")
        self._apply(_migrate_asset_version_schema, "20260806_0026_asset_version_schema-rerun")

    def test_migrated_generation_attempts_round_trip(self) -> None:
        self._apply(_migrate_generation_evidence_schema, "20260806_0023_generation_evidence_schema")
        from sqlalchemy.orm import Session

        with Session(self.engine) as session:
            attempt = GenerationAttempt(stage="image_first_frame", status="succeeded", provider="jimeng", model="req")
            session.add(attempt)
            session.commit()
            row = session.scalar(select(GenerationAttempt))
            self.assertEqual(row.provider, "jimeng")
            self.assertEqual(row.stage, "image_first_frame")



    def test_voice_design_binding_column_added_to_character_cards(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE character_cards (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL)")
            )
        self._apply(_migrate_voice_design_schema, "20260806_0025_voice_design_schema")
        with self.engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("character_cards")}
        self.assertIn("voice_design_id", columns)



if __name__ == "__main__":
    unittest.main()

