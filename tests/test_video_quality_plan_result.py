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
from app.json_utils import json_dumps, json_loads_object
from app.models import MediaAsset, Project, Storyboard, StoryboardShot, User, VideoTask


class VideoQualityPlanResultTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(
                email="quality@example.com",
                display_name="Quality User",
                password_hash=b"0" * 32,
                password_salt=b"1" * 16,
            )
            project = Project(
                owner=user,
                title="Quality Short",
                genre="urban fantasy",
                premise="A beam of light changes a rainy city.",
            )
            storyboard = Storyboard(
                project=project,
                title="Quality Short",
                source_chapter_ids_json="[]",
                status="draft",
                summary="A three-shot short.",
            )
            session.add_all([user, project, storyboard])
            session.flush()
            ContextPackService().build(
                session,
                project=project,
                reference_mode="style_reference",
                user_notes="",
                confirm_after_build=True,
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="A light appears on a rainy street.",
                visual_prompt="Animated film frame, rainy city street, blue green light beam.",
                character_refs_json="[]",
                scene_refs_json="[]",
                meta_json=(
                    '{"source_mode":"user_brief",'
                    '"source_trace":{"source_mode":"user_brief","reference_video_brief":"A three-shot short."},'
                    '"continuity":{"requires_i2v":false,"first_frame_source":"generated"},'
                    '"audio_script":{"subtitle_text":"A light appears on a rainy street."}}'
                ),
                duration_seconds=5,
                status="draft",
            )
            session.add(shot)
            session.commit()
            self.user_id = user.id
            self.project_id = project.id
            self.storyboard_id = storyboard.id

        app = FastAPI()
        router = APIRouter()
        register_longform_routes(router, settings=load_settings())
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

    def test_video_task_stores_quality_plan(self) -> None:
        response = self.client.post(f"/api/projects/{self.project_id}/storyboards/{self.storyboard_id}/video-tasks")

        self.assertEqual(response.status_code, 200, response.text)
        with self.SessionLocal() as session:
            task = session.query(VideoTask).one()
            progress = json_loads_object(task.progress_json)
            quality_plan = progress["video_quality_plan"]
            self.assertEqual(quality_plan["source_mode"], "user_brief")
            self.assertEqual(quality_plan["shot_count"], 1)
            self.assertEqual(quality_plan["structure"]["opening"], "Shot 1 establishes the scene.")
            self.assertEqual(quality_plan["shots"][0]["shot_no"], 1)
            self.assertEqual(quality_plan["shots"][0]["purpose"], "A light appears on a rainy street.")

    def test_video_quality_result_separates_render_from_acceptance(self) -> None:
        from app.json_utils import json_dumps
        from app.video_quality_service import VideoQualityService

        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            task = VideoTask(
                project_id=self.project_id,
                storyboard=storyboard,
                task_status="completed",
                output_uri="output/video_tasks/1/final.mp4",
                progress_json=json_dumps({"video_quality_plan": VideoQualityService().build_quality_plan(storyboard)}),
                error_message="",
            )
            session.add(task)
            session.flush()

            result = VideoQualityService().build_result(task=task, status="completed", message="Video generation completed.")

            self.assertEqual(result["status"], "requires_review")
            self.assertEqual(result["render_status"], "completed")
            self.assertFalse(result["quality_accepted"])
            self.assertTrue(result["checked_against_plan"])
            self.assertEqual(result["short_film_structure"], "requires_review")

            accepted = VideoQualityService().build_result(
                task=task, status="completed", message="accepted", quality_accepted=True
            )
            self.assertEqual(accepted["status"], "passed")
            self.assertTrue(accepted["quality_accepted"])
            self.assertEqual(accepted["short_film_structure"], "passed")

    def test_video_render_service_records_quality_result(self) -> None:
        from app.video_quality_service import VideoQualityService
        from app.video_render_service import VideoRenderService

        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            task = VideoTask(
                project_id=self.project_id,
                storyboard=storyboard,
                task_status="completed",
                output_uri="output/video_tasks/1/final.mp4",
                progress_json=json_dumps({"video_quality_plan": VideoQualityService().build_quality_plan(storyboard)}),
                error_message="",
            )
            session.add(task)
            session.flush()

            VideoRenderService(load_settings()).record_quality_result(
                task,
                status="completed",
                message="Video generation completed.",
            )

            progress = json_loads_object(task.progress_json)
            self.assertEqual(progress["video_quality_result"]["status"], "requires_review")
            self.assertFalse(progress["video_quality_result"]["quality_accepted"])
            self.assertEqual(progress["video_quality_result"]["render_status"], "completed")
            self.assertTrue(progress["video_quality_result"]["checked_against_plan"])

    def test_longform_state_render_trace_exposes_render_prompt_sources(self) -> None:
        from app.video_quality_service import VideoQualityService

        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            task = VideoTask(
                project_id=self.project_id,
                storyboard=storyboard,
                task_status="running",
                output_uri="",
                progress_json=json_dumps(
                    {
                        "current_step": "ark_seedance_submit",
                        "provider": "ark_seedance",
                        "video_quality_plan": VideoQualityService().build_quality_plan(storyboard),
                        "shots": [{"shot_id": storyboard.shots[0].id, "shot_no": 1, "used_first_frame": True, "image_status": "running"}],
                    }
                ),
                error_message="",
            )
            session.add(task)
            session.flush()
            session.add(
                MediaAsset(
                    project_id=self.project_id,
                    storyboard=storyboard,
                    shot=storyboard.shots[0],
                    asset_type="video",
                    uri="output/video_tasks/1/segment-001.mp4",
                    prompt="final render video prompt",
                    status="running",
                    meta_json=json_dumps({"provider": "ark_seedance"}),
                )
            )
            session.commit()

        state_response = self.client.get(f"/api/projects/{self.project_id}/longform")
        self.assertEqual(state_response.status_code, 200, state_response.text)
        trace = state_response.json()["storyboards"][0]["progress"]["generation_trace"]
        render_step = next(item for item in trace if item["step_key"] == "render")
        self.assertTrue(render_step["prompt_text"])
        self.assertIn("render_prompt_sources", render_step["parameters"])
        self.assertEqual(render_step["parameters"]["render_prompt_sources"][0]["prompt"], "final render video prompt")

    def test_video_render_service_persists_render_prompt_context(self) -> None:
        from app.video_render_service import VideoRenderService

        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            shot = storyboard.shots[0]
            task = VideoTask(
                project_id=self.project_id,
                storyboard=storyboard,
                task_status="running",
                output_uri="",
                progress_json=json_dumps({"shots": [{"shot_id": shot.id, "shot_no": shot.shot_no}]}),
                error_message="",
            )
            session.add(task)
            session.flush()

            first_frame = MediaAsset(
                project_id=self.project_id,
                storyboard=storyboard,
                shot=shot,
                asset_type="shot_first_frame",
                uri="output/projects/test/shot-001.png",
                prompt="locked first frame prompt",
                status="completed",
                meta_json=json_dumps({"locked": True}),
            )
            session.add(first_frame)
            session.flush()

            service = VideoRenderService(load_settings())
            prompt = service._build_ark_seedance_prompt(task, shot, first_frame_asset=first_frame)
            service._persist_render_context(
                task,
                provider="ark_seedance",
                shot=shot,
                prompt=prompt,
                first_frame_asset=first_frame,
            )
            service._set_progress(
                task,
                stage="ark_seedance_submit",
                message="提交 Ark Seedance 镜头 1 视频任务。",
                extra={"provider": "ark_seedance", "shot_no": shot.shot_no, "used_first_frame": True},
            )
            session.flush()

            progress = json_loads_object(task.progress_json)
            self.assertEqual(progress["provider"], "ark_seedance")
            self.assertTrue(progress["used_first_frame"])
            self.assertEqual(progress["shot_no"], shot.shot_no)
            self.assertEqual(progress["render_prompt"], prompt)
            self.assertEqual(progress["render_first_frame_asset_id"], first_frame.id)


if __name__ == "__main__":
    unittest.main()
