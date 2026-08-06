from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.character_identity_service import CharacterIdentityService
from app.db import Base
from app.json_utils import json_dumps, json_loads_object
from app.models import (
    CharacterAppearanceVersion,
    CharacterCard,
    CharacterIdentityVersion,
    MediaAsset,
    Project,
    Storyboard,
    StoryboardShot,
    User,
)


class CharacterIdentityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.tmpdir.name) / "turnaround.png"
        self.file_path.write_bytes(b"fake-turnaround" * 50)
        self.settings = SimpleNamespace()
        with self.SessionLocal() as session:
            user = User(email="identity@example.com", display_name="身份用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="身份项目", genre="古风")
            character = CharacterCard(project=project, name="阿离")
            storyboard = Storyboard(project=project, title="短片", source_chapter_ids_json="[]")
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
            self.user_id = user.id
            self.project_id = project.id
            self.character_id = character.id
            self.shot_id = shot.id

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _turnaround(self, session, *, completed: bool = True) -> MediaAsset:
        asset = MediaAsset(
            project_id=self.project_id,
            asset_type="character_turnaround",
            uri=str(self.file_path),
            prompt="三视图",
            status="completed" if completed else "pending",
            meta_json=json_dumps({"character_card_id": self.character_id, "character_name": "阿离"}),
        )
        session.add(asset)
        session.flush()
        return asset

    def test_approve_turnaround_creates_confirmed_version(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            version = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            self.assertEqual(version.version_no, 1)
            self.assertEqual(version.status, "confirmed")
            self.assertEqual(version.turnaround_asset_id, asset.id)
            self.assertTrue(version.checksum)
            self.assertEqual(version.reason, "creator_approval")

    def test_approve_same_asset_is_idempotent(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            first = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            second = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            self.assertEqual(first.id, second.id)
            count = session.query(CharacterIdentityVersion).count()
            self.assertEqual(count, 1)

    def test_new_turnaround_supersedes_previous_version(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            first_asset = self._turnaround(session)
            first = service.approve_turnaround(db=session, project=project, character=character, asset=first_asset)
            second_file = Path(self.tmpdir.name) / "turnaround-v2.png"
            second_file.write_bytes(b"fake-turnaround-v2")
            second_asset = self._turnaround(session)
            second_asset.uri = str(second_file)
            second = service.approve_turnaround(db=session, project=project, character=character, asset=second_asset)
            session.refresh(first)
            self.assertEqual(second.version_no, 2)
            self.assertEqual(first.status, "superseded")
            self.assertEqual(second.status, "confirmed")

    def test_approve_rejects_non_completed_asset(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session, completed=False)
            with self.assertRaises(RuntimeError):
                service.approve_turnaround(db=session, project=project, character=character, asset=asset)

    def test_approve_rejects_wrong_character(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            other = CharacterCard(project=project, name="别人")
            session.add(other)
            session.flush()
            asset = self._turnaround(session)
            asset.meta_json = json_dumps({"character_card_id": other.id})
            with self.assertRaises(RuntimeError):
                service.approve_turnaround(db=session, project=project, character=character, asset=asset)

    def test_current_identity_version_returns_latest_confirmed(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            first_asset = self._turnaround(session)
            service.approve_turnaround(db=session, project=project, character=character, asset=first_asset)
            current = service.current_identity_version(db=session, character_id=self.character_id)
            self.assertIsNotNone(current)
            self.assertEqual(current.version_no, 1)

    def test_bind_shot_identity_and_read_back(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            version = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            shot = session.get(StoryboardShot, self.shot_id)
            service.bind_shot_identity(db=session, shot=shot, character_id=self.character_id, identity_version_id=version.id)
            bindings = service.shot_identity_bindings(shot=shot)
            self.assertEqual(len(bindings), 1)
            self.assertEqual(bindings[0]["character_card_id"], self.character_id)
            self.assertEqual(bindings[0]["identity_version_id"], version.id)

    def test_bind_all_shot_characters_binds_existing_identities(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            version = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            shot = session.get(StoryboardShot, self.shot_id)
            bound = service.bind_all_shot_characters(db=session, project=project, shot=shot)
            self.assertEqual(len(bound), 1)
            self.assertEqual(bound[0]["identity_version_id"], version.id)
            meta = json_loads_object(shot.meta_json)
            self.assertEqual(meta["identity_bindings"][0]["character_card_id"], self.character_id)

    def test_appearance_version_sequence_and_current(self) -> None:
        service = CharacterIdentityService(self.settings)
        with self.SessionLocal() as session:
            character = session.get(CharacterCard, self.character_id)
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            version = service.approve_turnaround(db=session, project=project, character=character, asset=asset)
            first = service.create_appearance_version(db=session, identity_version_id=version.id, costume_name="日常装")
            second = service.create_appearance_version(
                db=session, identity_version_id=version.id, costume_name="雨衣", costume_details="透明雨衣"
            )
            session.refresh(first)
            self.assertEqual(first.status, "superseded")
            self.assertEqual(second.version_no, 2)
            self.assertEqual(second.status, "active")
            current = service.current_appearance_version(db=session, identity_version_id=version.id)
            self.assertEqual(current.id, second.id)
            self.assertEqual(current.costume_name, "雨衣")


if __name__ == "__main__":
    unittest.main()