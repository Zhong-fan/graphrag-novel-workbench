from __future__ import annotations

import unittest

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
from app.exception_inbox_service import create_inbox_item
from app.json_utils import json_dumps
from app.models import Project, Storyboard, StoryboardShot, User, VideoTask
from app.workflow_guidance_service import recommend_next_action


class WorkflowGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="guidance@example.com", display_name="引导用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="引导项目", genre="青春")
            session.add_all([user, project])
            session.flush()
            ContextPackService().build(
                session, project=project, reference_mode="style_reference", user_notes="", confirm_after_build=True
            )
            session.commit()
            self.user_id = user.id
            self.project_id = project.id

        self.settings = load_settings()
        app = FastAPI()
        router = APIRouter()
        register_longform_routes(router, settings=self.settings)
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

    def _draft_storyboard(self, session, *, character_refs: str = "[]", requires_i2v: bool = False) -> Storyboard:
        storyboard = Storyboard(project_id=self.project_id, title="引导短片", source_chapter_ids_json="[]", status="draft", summary="单镜头。")
        session.add(storyboard)
        session.flush()
        session.add(
            StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="雨夜街口。",
                visual_prompt="日系动画，雨夜街口。",
                character_refs_json=character_refs,
                scene_refs_json="[]",
                meta_json=json_dumps(
                    {
                        "source_mode": "user_brief",
                        "continuity": {"requires_i2v": requires_i2v, "first_frame_source": "generated"},
                        "audio_script": {},
                    }
                ),
                duration_seconds=5,
                status="draft",
            )
        )
        session.commit()
        return storyboard

    def _guidance(self, session) -> dict:
        project = session.get(Project, self.project_id)
        return recommend_next_action(session, project=project, settings=self.settings)

    def test_no_storyboard_recommends_storyboard(self) -> None:
        with self.SessionLocal() as session:
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "needs_storyboard")
            self.assertIn("生成分镜稿", guidance.next_action)
            self.assertEqual(guidance.defaults["video_provider"], "ark_seedance")

    def test_ready_to_render_uses_defaults(self) -> None:
        with self.SessionLocal() as session:
            self._draft_storyboard(session)
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "ready_to_render")
            self.assertIn("创建视频任务", guidance.next_action)
            self.assertEqual(guidance.defaults["video_model"], self.settings.ark_video_model)
            self.assertIn("storyboard.shots.v1", guidance.defaults["prompt_contracts"])

    def test_first_frame_blocked_reports_blockers(self) -> None:
        with self.SessionLocal() as session:
            self._draft_storyboard(session, character_refs='[{"character_card_id": 1, "name": "阿离"}]', requires_i2v=True)
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "first_frame_blocked")
            self.assertTrue(guidance.blockers)
            self.assertIn("锁定三视图", guidance.blockers[0])

    def test_budget_approval_state(self) -> None:
        with self.SessionLocal() as session:
            self._draft_storyboard(session)
            project = session.get(Project, self.project_id)
            create_inbox_item(
                db=session,
                project=project,
                item_type="budget_approval",
                title="视频生成成本需要确认",
                reason="估算成本超阈值。",
                recommended_action="确认预算后继续。",
            )
            session.commit()
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "budget_approval")
            self.assertIn("预算", guidance.next_action)

    def test_rendering_state(self) -> None:
        with self.SessionLocal() as session:
            storyboard = self._draft_storyboard(session)
            session.add(
                VideoTask(
                    project_id=self.project_id,
                    storyboard_id=storyboard.id,
                    task_status="running",
                    output_uri="",
                    progress_json="{}",
                    error_message="",
                )
            )
            session.commit()
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "rendering")

    def test_needs_review_state(self) -> None:
        with self.SessionLocal() as session:
            storyboard = self._draft_storyboard(session)
            session.add(
                VideoTask(
                    project_id=self.project_id,
                    storyboard_id=storyboard.id,
                    task_status="completed",
                    output_uri="",
                    progress_json=json_dumps({"video_quality_result": {"status": "requires_review"}}),
                    error_message="",
                )
            )
            session.commit()
            guidance = self._guidance(session)
            self.assertEqual(guidance.state, "needs_review")
            self.assertIn("验收", guidance.next_action)

    def test_next_action_endpoint(self) -> None:
        response = self.client.get(f"/api/projects/{self.project_id}/next-action")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["state"], "needs_storyboard")
        self.assertIn("next_action", payload)
        self.assertIn("defaults", payload)


if __name__ == "__main__":
    unittest.main()
