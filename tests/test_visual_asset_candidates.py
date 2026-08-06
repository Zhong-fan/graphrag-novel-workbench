from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.capabilities import CapabilityDeclaration, CapabilityRole, ImageGenerationResult
from app.db import Base
from app.json_utils import json_dumps, json_loads_object
from app.models import CharacterCard, CharacterReferenceProfile, MediaAsset, Project, User
from app.visual_asset_service import VisualAssetService


class FakeImageCapability:
    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=CapabilityRole.IMAGE,
            provider="jimeng",
            model="req",
            supports_reference_images=True,
        )

    def generate(self, request):
        return ImageGenerationResult(
            provider="jimeng",
            model="req",
            kind="url",
            value="https://example.com/generated.png",
            provider_ref="task-1",
            submit_summary={},
            result_summary={},
            parameters={"req_key": "req", "width": 1024, "height": 1024},
        )


class VisualAssetCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.settings = SimpleNamespace(
            jimeng_access_key="ak",
            jimeng_secret_key="sk",
            jimeng_endpoint="https://example.com",
            jimeng_region="cn",
            jimeng_service="image",
            jimeng_image_req_key="req",
            jimeng_image_width=1024,
            jimeng_image_height=1024,
            jimeng_poll_timeout_seconds=1,
        )

    def test_repeated_generation_uses_incremented_candidate_version_and_path(self) -> None:
        service = VisualAssetService(self.settings)
        with self.SessionLocal() as session, tempfile.TemporaryDirectory() as tmpdir:
            project = self._project(session)
            character = self._character(session, project, name="阳菜")
            existing = self._asset(session, project, character, version=1, locked=False)

            saved_paths: list[Path] = []
            with patch("app.visual_asset_service.build_image_capability", return_value=FakeImageCapability()), patch.object(
                service,
                "_save_image_payload",
                side_effect=lambda payload, path: saved_paths.append(path),
            ), patch.object(
                service,
                "_write_provider_debug_sidecar",
                return_value=None,
            ), patch.object(
                service,
                "_visual_output_dir",
                return_value=Path(tmpdir) / "turnarounds",
            ), patch.object(
                service,
                "_provider_debug_path",
                side_effect=lambda path: path.with_name(path.name + ".debug.json"),
            ):
                asset = service.generate_character_turnaround(
                    db=session,
                    project=project,
                    character=character,
                    chapter_no=12,
                    prompt_note="new candidate",
                )
                session.commit()

            meta = json_loads_object(asset.meta_json)
            self.assertEqual(asset.uri, str(saved_paths[0]))
            self.assertTrue(asset.uri.endswith("turnaround-v002.png"))
            self.assertEqual(meta["version"], 2)
            self.assertEqual(meta["candidate_version"], 2)
            self.assertEqual(meta["candidate_status"], "candidate")
            self.assertFalse(meta["locked"])
            self.assertEqual(existing.uri, "output/characters/yangcai/turnaround-v001.png")

    def test_locked_candidate_remains_selected_when_new_candidate_is_generated(self) -> None:
        service = VisualAssetService(self.settings)
        with self.SessionLocal() as session, tempfile.TemporaryDirectory() as tmpdir:
            project = self._project(session)
            character = self._character(session, project, name="阳菜")
            locked = self._asset(session, project, character, version=1, locked=True)
            service.character_reference_profiles.apply_turnaround_lock(session, project, locked, True)
            session.commit()

            with patch("app.visual_asset_service.build_image_capability", return_value=FakeImageCapability()), patch.object(
                service,
                "_save_image_payload",
                return_value=None,
            ), patch.object(
                service,
                "_write_provider_debug_sidecar",
                return_value=None,
            ), patch.object(
                service,
                "_visual_output_dir",
                return_value=Path(tmpdir) / "turnarounds",
            ), patch.object(
                service,
                "_provider_debug_path",
                side_effect=lambda path: path.with_name(path.name + ".debug.json"),
            ):
                new_asset = service.generate_character_turnaround(
                    db=session,
                    project=project,
                    character=character,
                    chapter_no=12,
                    prompt_note="new candidate",
                )
                session.commit()

            profile = session.query(CharacterReferenceProfile).filter(CharacterReferenceProfile.project_id == project.id).one()
            self.assertEqual(profile.locked_turnaround_asset_id, locked.id)
            self.assertNotEqual(new_asset.id, locked.id)
            self.assertEqual(session.query(MediaAsset).filter(MediaAsset.project_id == project.id).count(), 2)
            self.assertTrue(new_asset.uri.endswith("turnaround-v002.png"))

    def test_workspace_panel_mentions_candidate_actions(self) -> None:
        panel_source = Path("frontend/src/components/workspace/ToonflowWorkbench.vue").read_text(encoding="utf-8")

        self.assertIn("候选 v", panel_source)
        self.assertIn("设为采用", panel_source)
        self.assertIn("取消采用", panel_source)
        self.assertIn("删除候选", panel_source)

    def _project(self, session) -> Project:
        user = User(email="asset@example.com", display_name="素材用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
        project = Project(owner=user, title="天空与海", genre="青春", reference_work="天气之子")
        session.add(project)
        session.commit()
        return project

    def _character(self, session, project: Project, *, name: str) -> CharacterCard:
        card = CharacterCard(project_id=project.id, name=name)
        session.add(card)
        session.commit()
        return card

    def _asset(self, session, project: Project, character: CharacterCard, *, version: int, locked: bool) -> MediaAsset:
        asset = MediaAsset(
            project_id=project.id,
            asset_type="character_turnaround",
            uri=f"output/characters/yangcai/turnaround-v{version:03d}.png",
            prompt="prompt",
            status="completed",
            meta_json=json_dumps(
                {
                    "character_card_id": character.id,
                    "character_name": character.name,
                    "version": version,
                    "candidate_version": version,
                    "candidate_status": "locked" if locked else "candidate",
                    "locked": locked,
                    "views": ["front", "side", "back"],
                }
            ),
        )
        session.add(asset)
        session.commit()
        return asset


if __name__ == "__main__":
    unittest.main()