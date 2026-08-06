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
from app.models import CharacterCard, Project, ReferenceImageAsset, User
from app.reference_asset_service import _remote_url_hash
from app.visual_asset_service import VisualAssetService


class CapturingImageCapability:
    calls: list = []

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=CapabilityRole.IMAGE,
            provider="jimeng",
            model="req",
            supports_reference_images=True,
        )

    def generate(self, request):
        self.calls.append(request)
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


class TurnaroundReferenceAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        CapturingImageCapability.calls = []
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

    def test_character_turnaround_uses_approved_reference_images_for_character(self) -> None:
        capability = CapturingImageCapability()
        service = VisualAssetService(self.settings)
        with self.SessionLocal() as session, tempfile.TemporaryDirectory() as tmpdir:
            user = User(email="ref-turn@example.com", display_name="视觉用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="天空项目", genre="青春", reference_work="上传参考")
            character = CharacterCard(project=project, name="阳菜")
            session.add_all([project, character])
            session.flush()
            ref = ReferenceImageAsset(
                project=project,
                source_work="上传参考",
                asset_kind="character_reference",
                remote_url="/output/projects/0001/reference_assets/hina.png",
                remote_url_hash=_remote_url_hash("/output/projects/0001/reference_assets/hina.png"),
                provider="upload",
                source_page="upload:hina.png",
                mapped_character_name="阳菜",
                status="approved",
                meta_json=json_dumps({"classification_status": "confirmed"}),
            )
            session.add(ref)
            session.commit()

            with patch("app.visual_asset_service.build_image_capability", return_value=capability), patch.object(
                service, "_save_image_payload", return_value=None
            ), patch.object(
                service, "_write_provider_debug_sidecar", return_value=None
            ), patch.object(
                service, "_visual_output_dir", return_value=Path(tmpdir)
            ), patch.object(
                service, "_provider_debug_path", side_effect=lambda path: path.with_suffix(".provider.json")
            ):
                asset = service.generate_character_turnaround(db=session, project=project, character=character)

            self.assertEqual(capability.calls[0].reference_images, (ref.remote_url,))
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["visual_reference_asset_ids"], [ref.id])


if __name__ == "__main__":
    unittest.main()