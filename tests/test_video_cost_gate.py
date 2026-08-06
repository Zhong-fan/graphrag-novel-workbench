from __future__ import annotations

import unittest
from dataclasses import replace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_routes_longform import register_longform_routes
from app.auth import get_current_user
from app.config import load_settings
from app.context_pack_service import ContextPackService
from app.db import Base, get_db
from app.json_utils import json_loads_object
from app.models import ExceptionInboxItem, GenerationAttempt, Project, Storyboard, StoryboardShot, User, VideoTask


class VideoCostGateTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="cost@example.com", display_name="成本用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="成本项目", genre="青春", premise="一束光改变雨夜城市。")
            storyboard = Storyboard(project=project, title="成本短片", source_chapter_ids_json="[]", status="draft", summary="单镜头短片。")
            session.add_all([user, project, storyboard])
            session.flush()
            ContextPackService().build(
                session, project=project, reference_mode="style_reference", user_notes="", confirm_after_build=True
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="雨夜街口。",
                visual_prompt="日系动画，雨夜街口，蓝绿色光束。",
                character_refs_json="[]",
                scene_refs_json="[]",
                meta_json=(
                    '{"source_mode":"user_brief",'
                    '"continuity":{"requires_i2v":false,"first_frame_source":"generated"},'
                    '"audio_script":{}}'
                ),
                duration_seconds=5,
                status="draft",
            )
            session.add(shot)
            session.commit()
            self.user_id = user.id
            self.project_id = project.id
            self.storyboard_id = storyboard.id

        settings = replace(load_settings(), video_cost_confirmation_threshold_usd=0.05)
        app = FastAPI()
        router = APIRouter()
        register_longform_routes(router, settings=settings)
        app.include_router(router)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_current_user():
            with self.SessionLocal() as session:
                return session.get(User, self.user_id)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        self.client = TestClient(app)

    def _post(self, payload: dict | None = None):
        return self.client.post(
            f"/api/projects/{self.project_id}/storyboards/{self.storyboard_id}/video-tasks",
            json=payload,
        )

    def test_blocks_when_estimate_exceeds_threshold_without_confirmation(self) -> None:
        response = self._post(None)
        self.assertEqual(response.status_code, 409, response.text)
        detail = response.json()["detail"]
        self.assertIn("估算成本", detail)
        self.assertIn("budget_confirmed", detail)
        with self.SessionLocal() as session:
            attempt = session.query(GenerationAttempt).one()
            self.assertEqual(attempt.stage, "cost_gate")
            self.assertEqual(attempt.status, "blocked")
            self.assertEqual(attempt.error_category, "budget_confirmation_required")
            self.assertGreater(attempt.cost_estimate_usd, 0)
            inbox_item = session.query(ExceptionInboxItem).one()
            self.assertEqual(inbox_item.item_type, "budget_approval")
            self.assertEqual(inbox_item.status, "open")
            self.assertEqual(inbox_item.severity, "high")
            self.assertEqual(json_loads_object(inbox_item.evidence_json)["generation_attempt_id"], attempt.id)

    def test_passes_when_budget_confirmed(self) -> None:
        response = self._post({"budget_confirmed": True})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["progress"]["quality_status"], "unknown")
        with self.SessionLocal() as session:
            task = session.query(VideoTask).one()
            progress = json_loads_object(task.progress_json)
            self.assertGreater(progress["estimated_cost"]["estimated_cost_usd"], 0)
            self.assertEqual(progress["estimated_cost"]["currency"], "USD")


    def test_preview_mode_records_preview_resolution(self) -> None:
        response = self._post({"budget_confirmed": True, "preview": True})
        self.assertEqual(response.status_code, 200, response.text)
        with self.SessionLocal() as session:
            task = session.query(VideoTask).one()
            progress = json_loads_object(task.progress_json)
            self.assertTrue(progress["preview_mode"])
            self.assertEqual(progress["video_resolution"], "720p")

    def test_render_service_resolves_preview_resolution(self) -> None:
        from types import SimpleNamespace

        from app.video_render_service import VideoRenderService

        service = VideoRenderService(SimpleNamespace(ark_video_resolution="1080p"))
        preview_task = SimpleNamespace(progress_json='{"video_resolution": "720p"}')
        default_task = SimpleNamespace(progress_json="{}")
        self.assertEqual(service._video_resolution(preview_task), "720p")
        self.assertEqual(service._video_resolution(default_task), "1080p")


if __name__ == "__main__":
    unittest.main()