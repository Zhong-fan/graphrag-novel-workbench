from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.capabilities import AdapterError, AdapterErrorCategory, CapabilityDeclaration, CapabilityRole, ImageGenerationResult
from app.db import Base
from app.models import CharacterCard, GenerationAttempt, MediaAsset, Project, User
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


class RaisingImageCapability(FakeImageCapability):
    def generate(self, request):
        raise AdapterError(
            AdapterErrorCategory.RATE_LIMIT_OR_QUOTA,
            safe_message="限流",
            provider_code="429",
        )


class VisualAssetEvidenceTests(unittest.TestCase):
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

    def test_turnaround_success_records_evidence_with_adopted_asset(self) -> None:
        service = VisualAssetService(self.settings)
        with self.SessionLocal() as session, tempfile.TemporaryDirectory() as tmpdir:
            project = self._project(session)
            character = self._character(session, project, name="阳菜")
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
                asset = service.generate_character_turnaround(db=session, project=project, character=character)
                session.commit()

            attempt = session.scalar(select(GenerationAttempt))
            self.assertIsNotNone(attempt)
            self.assertEqual(attempt.stage, "image_turnaround")
            self.assertEqual(attempt.status, "succeeded")
            self.assertEqual(attempt.provider, "jimeng")
            self.assertEqual(attempt.model, "req")
            self.assertEqual(attempt.project_id, project.id)
            self.assertEqual(attempt.adopted_asset_id, asset.id)
            self.assertEqual(attempt.quality_outcome, "candidate_created")
            self.assertEqual(attempt.provider_ref, "task-1")
            self.assertEqual(attempt.shot_id, None)

    def test_turnaround_failure_records_failed_evidence_and_reraises(self) -> None:
        service = VisualAssetService(self.settings)
        with self.SessionLocal() as session, tempfile.TemporaryDirectory() as tmpdir:
            project = self._project(session)
            character = self._character(session, project, name="阳菜")
            with patch("app.visual_asset_service.build_image_capability", return_value=RaisingImageCapability()):
                with self.assertRaises(AdapterError) as raised:
                    service.generate_character_turnaround(db=session, project=project, character=character)
                self.assertEqual(raised.exception.category, AdapterErrorCategory.RATE_LIMIT_OR_QUOTA)
                session.commit()

            attempt = session.scalar(select(GenerationAttempt))
            self.assertIsNotNone(attempt)
            self.assertEqual(attempt.stage, "image_turnaround")
            self.assertEqual(attempt.status, "failed")
            self.assertEqual(attempt.error_category, "AdapterError")
            self.assertEqual(attempt.project_id, project.id)
            self.assertEqual(attempt.adopted_asset_id, None)

    def _project(self, session) -> Project:
        user = User(email="evidence@example.com", display_name="证据用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
        project = Project(owner=user, title="天空与海", genre="青春", reference_work="天气之子")
        session.add(project)
        session.commit()
        return project

    def _character(self, session, project: Project, *, name: str) -> CharacterCard:
        card = CharacterCard(project_id=project.id, name=name)
        session.add(card)
        session.commit()
        return card


if __name__ == "__main__":
    unittest.main()
