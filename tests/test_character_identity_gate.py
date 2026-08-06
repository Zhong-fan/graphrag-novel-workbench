from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.video_preflight_service import video_quality_gate_failures
from app.character_identity_service import CharacterIdentityService
from app.config import load_settings
from app.db import Base
from app.json_utils import json_dumps
from app.models import CharacterCard, CharacterIdentityVersion, MediaAsset, Project, Storyboard, StoryboardShot, User
from app.visual_asset_service import VisualAssetService


class CharacterIdentityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.turnaround_path = Path(self.tmpdir.name) / "turnaround.png"
        self.turnaround_path.write_bytes(b"fake-turnaround" * 40)
        with self.SessionLocal() as session:
            user = User(email="idgate@example.com", display_name="身份门禁", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="门禁项目", genre="都市")
            character = CharacterCard(project=project, name="阿离")
            storyboard = Storyboard(project=project, title="短片", source_chapter_ids_json="[]", status="draft")
            session.add_all([user, project, character, storyboard])
            session.flush()
            first_shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="开场。",
                visual_prompt="雨夜街口。",
                character_refs_json="[]",
                scene_refs_json="[]",
                meta_json=json_dumps(
                    {"continuity": {"requires_i2v": False, "first_frame_source": "generated", "shot_type": "new"}}
                ),
                status="draft",
            )
            session.add(first_shot)
            session.flush()
            tail = MediaAsset(
                project_id=project.id,
                storyboard=storyboard,
                shot=first_shot,
                asset_type="shot_last_frame",
                uri="tail.png",
                prompt="tail",
                status="completed",
                meta_json=json_dumps({"shot_no": 1}),
            )
            continuation = StoryboardShot(
                storyboard=storyboard,
                shot_no=2,
                narration_text="镜头继续。",
                visual_prompt="沿雨夜街道继续前行。",
                character_refs_json=json_dumps([{"character_card_id": character.id, "name": "阿离"}]),
                scene_refs_json="[]",
                meta_json=json_dumps(
                    {
                        "continuity": {
                            "requires_i2v": True,
                            "first_frame_source": "previous_last_frame",
                            "shot_type": "continuation",
                            "depends_on_shot_no": 1,
                        },
                        "source_mode": "image_first_reference",
                    }
                ),
                status="draft",
            )
            session.add_all([tail, continuation])
            session.commit()
            self.project_id = project.id
            self.character_id = character.id
            self.storyboard_id = storyboard.id

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _turnaround(self, session) -> MediaAsset:
        asset = MediaAsset(
            project_id=self.project_id,
            asset_type="character_turnaround",
            uri=str(self.turnaround_path),
            prompt="三视图",
            status="completed",
            meta_json=json_dumps({"character_card_id": self.character_id, "character_name": "阿离"}),
        )
        session.add(asset)
        session.flush()
        return asset

    def test_continuation_shot_without_identity_binding_is_blocked(self) -> None:
        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            failures = video_quality_gate_failures(
                session, settings=load_settings(), project=storyboard.project, storyboard=storyboard
            )
        self.assertTrue(any("规范身份绑定" in failure for failure in failures))

    def test_locking_turnaround_creates_identity_version(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            asset = self._turnaround(session)
            VisualAssetService(load_settings()).apply_turnaround_lock(db=session, project=project, asset=asset, locked=True)
            version = session.query(CharacterIdentityVersion).one()
            self.assertEqual(version.status, "confirmed")
            self.assertEqual(version.turnaround_asset_id, asset.id)
            self.assertEqual(version.version_no, 1)

    def test_continuation_shot_with_binding_and_tail_passes_gate(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            storyboard = session.get(Storyboard, self.storyboard_id)
            asset = self._turnaround(session)
            VisualAssetService(load_settings()).apply_turnaround_lock(db=session, project=project, asset=asset, locked=True)
            continuation = next(shot for shot in storyboard.shots if shot.shot_no == 2)
            CharacterIdentityService(load_settings()).bind_all_shot_characters(
                db=session, project=project, shot=continuation
            )
            failures = video_quality_gate_failures(
                session, settings=load_settings(), project=project, storyboard=storyboard
            )
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()