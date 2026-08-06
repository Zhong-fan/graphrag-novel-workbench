from __future__ import annotations

import base64
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.capabilities import AdapterError
from app.config import load_settings
from app.db import Base
from app.json_utils import json_dumps, json_loads_object
from app.models import CharacterCard, MediaAsset, Project, Storyboard, StoryboardShot, User
from app.voice_design_service import VoiceDesignService
from app.voice_service import VoiceService


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def _audio_response(content: bytes) -> bytes:
    return json.dumps({"code": 0, "data": base64.b64encode(content).decode("ascii")}).encode("utf-8")


class VoiceDesignServiceTests(unittest.TestCase):
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
        self.settings = replace(
            load_settings(),
            output_dir=Path(self.tmpdir.name),
            tts_provider="volcengine_doubao",
            volcengine_tts_app_id="app-1",
            volcengine_tts_access_key="key-1",
            volcengine_tts_api_key="",
            volcengine_tts_resource_id="seed-tts-2.0",
            volcengine_tts_endpoint="https://example.test/tts",
            volcengine_tts_speaker="preset_default",
            volcengine_tts_model="",
            volcengine_tts_sample_rate=24000,
            volcengine_tts_preset_speakers="",
        )
        with self.SessionLocal() as session:
            user = User(email="voice@example.com", display_name="配音用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="配音项目", genre="都市")
            character = CharacterCard(project=project, name="阿离", voice_speaker="char_speaker")
            storyboard = Storyboard(project=project, title="短片", source_chapter_ids_json="[]", status="draft")
            session.add_all([user, project, character, storyboard])
            session.flush()
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="雨夜独白。",
                visual_prompt="雨夜街口。",
                character_refs_json="[]",
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

    def test_submit_preset_design_binds_character_and_stays_pending(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            design = VoiceDesignService(self.settings).submit_preset_design(
                db=session, project=project, character=character, preset_speaker="preset_a"
            )
            session.commit()
            self.assertEqual(design.status, "pending_approval")
            self.assertEqual(design.voice_ref, "preset_a")
            self.assertEqual(design.provider, "volcengine_doubao")
            self.assertEqual(character.voice_design_id, design.id)
            with self.assertRaises(RuntimeError) as ctx:
                VoiceDesignService(self.settings).approved_voice_ref(db=session, character=character)
            self.assertIn("审批", str(ctx.exception))

    def test_approve_design_unblocks_synthesis_reference(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            service = VoiceDesignService(self.settings)
            design = service.submit_preset_design(
                db=session, project=project, character=character, preset_speaker="preset_a"
            )
            service.approve_design(db=session, design_id=design.id)
            session.commit()
            self.assertEqual(design.status, "approved")
            self.assertIsNotNone(design.approved_at)
            self.assertEqual(service.approved_voice_ref(db=session, character=character), "preset_a")

    def test_reject_design_records_reason_and_stays_blocked(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            service = VoiceDesignService(self.settings)
            design = service.submit_preset_design(
                db=session, project=project, character=character, preset_speaker="preset_a"
            )
            service.reject_design(db=session, design_id=design.id, reason="音色不符")
            session.commit()
            self.assertEqual(design.status, "rejected")
            self.assertEqual(design.reason, "音色不符")
            self.assertIsNotNone(design.rejected_at)
            with self.assertRaises(RuntimeError):
                service.approved_voice_ref(db=session, character=character)
            with self.assertRaises(RuntimeError):
                service.approve_design(db=session, design_id=design.id)

    def test_gate_passes_without_design_binding(self) -> None:
        with self.SessionLocal() as session:
            character = self._character(session)
            self.assertIsNone(
                VoiceDesignService(self.settings).approved_voice_ref(db=session, character=character)
            )

    def test_gate_raises_when_bound_design_missing(self) -> None:
        with self.SessionLocal() as session:
            character = self._character(session)
            character.voice_design_id = 9999
            session.commit()
            with self.assertRaises(RuntimeError) as ctx:
                VoiceDesignService(self.settings).approved_voice_ref(db=session, character=character)
            self.assertIn("已不存在", str(ctx.exception))

    def test_gate_rejects_design_bound_to_another_character(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            other = CharacterCard(project=project, name="路人甲", voice_speaker="other_speaker")
            session.add(other)
            session.flush()
            service = VoiceDesignService(self.settings)
            design = service.submit_preset_design(
                db=session, project=project, character=other, preset_speaker="preset_a"
            )
            service.approve_design(db=session, design_id=design.id)
            character.voice_design_id = design.id
            session.commit()
            with self.assertRaises(RuntimeError) as ctx:
                service.approved_voice_ref(db=session, character=character)
            self.assertIn("其他角色", str(ctx.exception))

    def test_submit_unknown_preset_raises_actionable_error(self) -> None:
        settings = replace(self.settings, volcengine_tts_preset_speakers="preset_a,preset_b")
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            character = self._character(session)
            with self.assertRaises(AdapterError) as ctx:
                VoiceDesignService(settings).submit_preset_design(
                    db=session, project=project, character=character, preset_speaker="unknown"
                )
            self.assertEqual(ctx.exception.provider_code, "preset_not_in_library")

    def test_synthesis_blocked_for_pending_design(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            storyboard = session.get(Storyboard, self.storyboard_id)
            character = self._character(session)
            VoiceDesignService(self.settings).submit_preset_design(
                db=session, project=project, character=character, preset_speaker="preset_a"
            )
            session.commit()
            with self.assertRaises(RuntimeError) as ctx:
                VoiceService(self.settings).generate_shot_voice(
                    db=session,
                    project=project,
                    storyboard=storyboard,
                    shot=storyboard.shots[0],
                    provider="volcengine_doubao",
                    voice_role="narrator",
                    character=character,
                )
            self.assertIn("审批", str(ctx.exception))
            self.assertIsNone(session.scalar(select(MediaAsset).limit(1)))

    def test_synthesis_uses_approved_design_voice_ref(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            storyboard = session.get(Storyboard, self.storyboard_id)
            character = self._character(session)
            service = VoiceDesignService(self.settings)
            design = service.submit_preset_design(
                db=session, project=project, character=character, preset_speaker="preset_a"
            )
            service.approve_design(db=session, design_id=design.id)
            session.commit()
            with patch(
                "app.voice_capability.urllib.request.urlopen",
                return_value=_FakeResponse(_audio_response(b"\x10approved-audio")),
            ):
                asset = VoiceService(self.settings).generate_shot_voice(
                    db=session,
                    project=project,
                    storyboard=storyboard,
                    shot=storyboard.shots[0],
                    provider="volcengine_doubao",
                    voice_role="narrator",
                    character=character,
                )
            session.commit()
            self.assertEqual(asset.status, "completed")
            self.assertTrue(Path(asset.uri).exists())
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["voice_profile"], "preset_a")
            self.assertEqual(meta["provider"], "volcengine_doubao")
            self.assertEqual(meta["model"], "seed-tts-2.0")
            self.assertEqual(Path(asset.uri).read_bytes(), b"\x10approved-audio")

    def test_preset_speaker_without_design_synthesizes_directly(self) -> None:
        with self.SessionLocal() as session:
            project = session.get(Project, self.project_id)
            storyboard = session.get(Storyboard, self.storyboard_id)
            character = self._character(session)
            with patch(
                "app.voice_capability.urllib.request.urlopen",
                return_value=_FakeResponse(_audio_response(b"\x11preset-audio")),
            ):
                asset = VoiceService(self.settings).generate_shot_voice(
                    db=session,
                    project=project,
                    storyboard=storyboard,
                    shot=storyboard.shots[0],
                    provider="volcengine_doubao",
                    voice_role="narrator",
                    character=character,
                )
            session.commit()
            self.assertEqual(asset.status, "completed")
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["voice_profile"], "char_speaker")


if __name__ == "__main__":
    unittest.main()
