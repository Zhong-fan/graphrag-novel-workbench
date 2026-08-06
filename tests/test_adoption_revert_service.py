from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adoption_revert_service import AdoptionRevertService
from app.character_identity_service import CharacterIdentityService
from app.config import load_settings
from app.db import Base
from app.json_utils import json_dumps, json_loads_object
from app.models import (
    CharacterCard,
    CharacterIdentityVersion,
    CharacterReferenceProfile,
    MediaAsset,
    MediaAssetVersion,
    Project,
    Storyboard,
    StoryboardShot,
    TaskEvent,
    User,
)
from app.visual_asset_service import VisualAssetService


class AdoptionRevertServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.settings = replace(load_settings(), output_dir=Path(self.tmpdir.name))
        with self.SessionLocal() as session:
            user = User(email="revert@example.com", display_name="回退用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="回退项目", genre="都市")
            character = CharacterCard(project=project, name="阿离")
            storyboard = Storyboard(project=project, title="短片", source_chapter_ids_json="[]", status="draft")
            session.add_all([user, project, character, storyboard])
            session.flush()
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="开场。",
                visual_prompt="雨夜街口。",
                character_refs_json=json_dumps([{"character_card_id": character.id, "name": "阿离"}]),
                scene_refs_json="[]",
                meta_json="{}",
                status="draft",
            )
            session.add(shot)
            session.commit()
            self.project_id = project.id
            self.character_id = character.id
            self.storyboard_id = storyboard.id

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _character(self, session) -> CharacterCard:
        return session.get(CharacterCard, self.character_id)

    def _shot(self, session) -> StoryboardShot:
        return session.get(Storyboard, self.storyboard_id).shots[0]

    def _turnaround(self, session, name: str, payload: bytes) -> MediaAsset:
        path = Path(self.tmpdir.name) / f"{name}.png"
        path.write_bytes(payload)
        asset = MediaAsset(
            project_id=self.project_id,
            asset_type="character_turnaround",
            uri=str(path),
            prompt=name,
            status="completed",
            meta_json=json_dumps(
                {"character_card_id": self.character_id, "character_name": "阿离", "locked": False}
            ),
        )
        session.add(asset)
        session.flush()
        return asset

    def _first_frame(self, session, payload: bytes) -> MediaAsset:
        path = Path(self.tmpdir.name) / "first-frame.png"
        path.write_bytes(payload)
        asset = MediaAsset(
            project_id=self.project_id,
            storyboard_id=self.storyboard_id,
            shot_id=self._shot(session).id,
            asset_type="shot_first_frame",
            uri=str(path),
            prompt="旧提示词",
            status="completed",
            meta_json=json_dumps({"shot_no": 1, "provider": "jimeng", "locked": False}),
        )
        session.add(asset)
        session.flush()
        return asset

    def test_snapshot_and_restore_first_frame_are_reversible(self) -> None:
        with self.SessionLocal() as session:
            asset = self._first_frame(session, b"v1-bytes")
            service = AdoptionRevertService(self.settings)
            snapshot = service.snapshot_before_overwrite(db=session, asset=asset, reason="shot_first_frame_regeneration")
            session.commit()
            self.assertEqual(snapshot.version_no, 1)
            self.assertEqual(Path(snapshot.uri).read_bytes(), b"v1-bytes")

            # Overwrite the canonical file with a new generation.
            Path(asset.uri).write_bytes(b"v2-bytes")
            asset.meta_json = json_dumps(json_loads_object(asset.meta_json) | {"provider": "ark_seedream"})

            restored = service.restore_asset_version(db=session, asset=asset, version_no=1)
            session.commit()
            self.assertEqual(restored.version_no, 1)
            self.assertEqual(Path(asset.uri).read_bytes(), b"v1-bytes")
            self.assertEqual(asset.prompt, "旧提示词")
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["restored_from_version"], 1)
            # The restore itself snapshotted the v2 state, so history keeps growing.
            versions = service.list_versions(db=session, asset=asset)
            self.assertEqual([item.version_no for item in versions], [1, 2])
            self.assertEqual(Path(versions[1].uri).read_bytes(), b"v2-bytes")

    def test_snapshot_skips_incomplete_assets(self) -> None:
        with self.SessionLocal() as session:
            asset = MediaAsset(
                project_id=self.project_id,
                asset_type="shot_first_frame",
                uri="",
                prompt="p",
                status="processing",
                meta_json="{}",
            )
            session.add(asset)
            session.flush()
            self.assertIsNone(
                AdoptionRevertService(self.settings).snapshot_before_overwrite(
                    db=session, asset=asset, reason="shot_first_frame_regeneration"
                )
            )

    def test_restore_unknown_version_raises(self) -> None:
        with self.SessionLocal() as session:
            asset = self._first_frame(session, b"x")
            with self.assertRaises(LookupError):
                AdoptionRevertService(self.settings).restore_asset_version(
                    db=session, asset=asset, version_no=9
                )

    def test_restore_missing_snapshot_file_raises(self) -> None:
        with self.SessionLocal() as session:
            asset = self._first_frame(session, b"x")
            service = AdoptionRevertService(self.settings)
            snapshot = service.snapshot_before_overwrite(db=session, asset=asset, reason="r")
            session.commit()
            Path(snapshot.uri).unlink()
            with self.assertRaises(RuntimeError):
                service.restore_asset_version(db=session, asset=asset, version_no=1)

    def test_revert_identity_adoption_restores_previous_version(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            turnaround_a = self._turnaround(session, "turnaround-a", b"a-bytes")
            VisualAssetService(self.settings).apply_turnaround_lock(
                db=session, project=project, asset=turnaround_a, locked=True
            )
            session.commit()
            turnaround_b = self._turnaround(session, "turnaround-b", b"b-bytes")
            VisualAssetService(self.settings).apply_turnaround_lock(
                db=session, project=project, asset=turnaround_b, locked=True
            )
            CharacterIdentityService(self.settings).bind_all_shot_characters(
                db=session, project=project, shot=self._shot(session)
            )
            session.commit()

            versions = session.scalars(
                select(CharacterIdentityVersion)
                .where(CharacterIdentityVersion.character_card_id == character.id)
                .order_by(CharacterIdentityVersion.version_no.asc())
            ).all()
            self.assertEqual([item.version_no for item in versions], [1, 2])
            first_version = versions[0]

            target = AdoptionRevertService(self.settings).revert_identity_adoption(
                db=session, project=project, character=character, target_version_id=first_version.id
            )
            session.commit()
            self.assertEqual(target.id, first_version.id)

            current = CharacterIdentityService(self.settings).current_identity_version(
                db=session, character_id=character.id
            )
            self.assertEqual(current.id, first_version.id)
            self.assertEqual(current.status, "confirmed")
            self.assertEqual(versions[1].status, "superseded")

            profile = session.scalar(
                select(CharacterReferenceProfile).where(
                    CharacterReferenceProfile.character_card_id == character.id
                )
            )
            self.assertEqual(profile.locked_turnaround_asset_id, turnaround_a.id)
            self.assertEqual(profile.status, "turnaround_locked")

            self.assertTrue(json_loads_object(turnaround_a.meta_json)["locked"])
            self.assertFalse(json_loads_object(turnaround_b.meta_json)["locked"])

            bindings = CharacterIdentityService(self.settings).shot_identity_bindings(shot=self._shot(session))
            self.assertEqual(bindings[0]["identity_version_id"], first_version.id)

            event = session.scalar(select(TaskEvent).where(TaskEvent.event_type == "identity_adoption_reverted"))
            self.assertIsNotNone(event)
            self.assertIn("回退", event.message)

    def test_revert_rejects_foreign_version(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            other = CharacterCard(project=project, name="路人甲")
            session.add(other)
            session.flush()
            asset = self._turnaround(session, "turnaround-a", b"a")
            VisualAssetService(self.settings).apply_turnaround_lock(
                db=session, project=project, asset=asset, locked=True
            )
            other_asset = MediaAsset(
                project_id=self.project_id,
                asset_type="character_turnaround",
                uri=str(Path(self.tmpdir.name) / "other.png"),
                prompt="other",
                status="completed",
                meta_json=json_dumps({"character_card_id": other.id}),
            )
            session.add(other_asset)
            session.flush()
            CharacterIdentityService(self.settings).approve_turnaround(
                db=session, project=project, character=other, asset=other_asset
            )
            foreign_version = session.scalar(
                select(CharacterIdentityVersion).where(
                    CharacterIdentityVersion.character_card_id == other.id
                )
            )
            session.commit()
            with self.assertRaises(RuntimeError):
                AdoptionRevertService(self.settings).revert_identity_adoption(
                    db=session, project=project, character=character, target_version_id=foreign_version.id
                )

    def test_revert_unknown_version_raises(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            with self.assertRaises(RuntimeError):
                AdoptionRevertService(self.settings).revert_identity_adoption(
                    db=session, project=project, character=character, target_version_id=12345
                )

    def test_revert_to_current_version_is_noop(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            asset = self._turnaround(session, "turnaround-a", b"a")
            VisualAssetService(self.settings).apply_turnaround_lock(
                db=session, project=project, asset=asset, locked=True
            )
            session.commit()
            current = CharacterIdentityService(self.settings).current_identity_version(
                db=session, character_id=character.id
            )
            target = AdoptionRevertService(self.settings).revert_identity_adoption(
                db=session, project=project, character=character, target_version_id=current.id
            )
            session.commit()
            self.assertEqual(target.id, current.id)
            self.assertIsNone(
                session.scalar(select(TaskEvent).where(TaskEvent.event_type == "identity_adoption_reverted"))
            )


if __name__ == "__main__":
    unittest.main()
