from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.video_preflight_service import video_quality_gate_failures
from app.api_routes_longform import register_longform_routes
from app.auth import get_current_user
from app.config import load_settings
from app.context_pack_service import ContextPackService
from app.db import Base, get_db
from app.json_utils import json_dumps, json_loads_object
from app.models import MediaAsset, Project, Storyboard, StoryboardShot, User, VideoTask


class ImageFirstVideoGateTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="image-gate@example.com", display_name="图片门禁用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="图片先行", genre="动画短片", reference_work="参考作品")
            storyboard = Storyboard(
                project=project,
                title="图片先行测试",
                source_chapter_ids_json="[]",
                status="draft",
                summary="从参考作品直接生成关键图再生成视频。",
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=1,
                narration_text="雨光落下。",
                visual_prompt="雨夜城市，一束光穿过云层。",
                character_refs_json="[]",
                scene_refs_json="[]",
                meta_json=json_dumps(
                    {
                        "continuity": {
                            "requires_i2v": True,
                            "first_frame_source": "generated",
                            "shot_type": "new",
                        },
                        "source_mode": "image_first_reference",
                    }
                ),
                duration_seconds=5,
                status="draft",
            )
            session.add_all([user, project, storyboard, shot])
            session.flush()
            ContextPackService().build(
                session,
                project=project,
                reference_mode="style_reference",
                user_notes="",
                confirm_after_build=True,
            )
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

    def test_image_first_video_task_requires_completed_first_frame(self) -> None:
        response = self.client.post(f"/api/projects/{self.project_id}/storyboards/{self.storyboard_id}/video-tasks")

        self.assertEqual(response.status_code, 409)
        self.assertIn("图片先行镜头缺少已完成首帧", response.json()["detail"])

    def test_render_service_marks_image_first_shot_as_i2v_required(self) -> None:
        from app.video_render_service import VideoRenderService

        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            shot = storyboard.shots[0]

            self.assertTrue(VideoRenderService(load_settings())._shot_requires_i2v(shot))

    def test_previous_last_frame_video_task_requires_dependency_tail_frame(self) -> None:
        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            first_shot = storyboard.shots[0]
            session.add(
                MediaAsset(
                    project_id=self.project_id,
                    storyboard=storyboard,
                    shot=first_shot,
                    asset_type="shot_first_frame",
                    uri="first.png",
                    prompt="first",
                    status="completed",
                    meta_json=json_dumps({"shot_no": 1}),
                )
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=2,
                narration_text="镜头继续推进。",
                visual_prompt="沿着上一镜头的雨夜街道继续前行。",
                character_refs_json="[]",
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
                duration_seconds=5,
                status="draft",
            )
            session.add(shot)
            session.commit()

        response = self.client.post(f"/api/projects/{self.project_id}/storyboards/{self.storyboard_id}/video-tasks")

        self.assertEqual(response.status_code, 409)
        self.assertIn("依赖镜头 1 缺少已完成尾帧", response.json()["detail"])

    def test_previous_last_frame_video_task_accepts_dependency_tail_frame(self) -> None:
        with self.SessionLocal() as session:
            storyboard = session.get(Storyboard, self.storyboard_id)
            first_shot = storyboard.shots[0]
            first_frame = MediaAsset(
                project_id=self.project_id,
                storyboard=storyboard,
                shot=first_shot,
                asset_type="shot_first_frame",
                uri="first.png",
                prompt="first",
                status="completed",
                meta_json=json_dumps({"shot_no": 1}),
            )
            tail = MediaAsset(
                project_id=self.project_id,
                storyboard=storyboard,
                shot=first_shot,
                asset_type="shot_last_frame",
                uri="tail.png",
                prompt="tail",
                status="completed",
                meta_json=json_dumps({"shot_no": 1}),
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=2,
                narration_text="镜头继续推进。",
                visual_prompt="沿着上一镜头的雨夜街道继续前行。",
                character_refs_json="[]",
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
                duration_seconds=5,
                status="draft",
            )
            session.add_all([first_frame, tail, shot])
            session.commit()

            failures = video_quality_gate_failures(session, settings=load_settings(), project=storyboard.project, storyboard=storyboard)

        self.assertEqual(failures, [])

    def test_previous_last_frame_first_frame_reuses_tail_frame_without_image_generation(self) -> None:
        from app.visual_asset_service import VisualAssetService

        with self.SessionLocal() as session, TemporaryDirectory() as tmpdir:
            storyboard = session.get(Storyboard, self.storyboard_id)
            first_shot = storyboard.shots[0]
            tail_path = Path(tmpdir) / "shot-001-last-frame.png"
            tail_path.write_bytes(b"tail")
            tail = MediaAsset(
                project_id=self.project_id,
                storyboard=storyboard,
                shot=first_shot,
                asset_type="shot_last_frame",
                uri=str(tail_path),
                prompt="tail",
                status="completed",
                meta_json=json_dumps({"shot_no": 1}),
            )
            shot = StoryboardShot(
                storyboard=storyboard,
                shot_no=2,
                narration_text="镜头继续推进。",
                visual_prompt="沿着上一镜头的雨夜街道继续前行。",
                character_refs_json="[]",
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
                duration_seconds=5,
                status="draft",
            )
            session.add_all([tail, shot])
            session.commit()

            with patch("app.visual_asset_service.build_image_capability") as capability_factory:
                asset = VisualAssetService(load_settings()).generate_shot_first_frame(
                    db=session,
                    project=storyboard.project,
                    storyboard=storyboard,
                    shot=shot,
                )

            capability_factory.assert_not_called()
            self.assertEqual(asset.asset_type, "shot_first_frame")
            self.assertEqual(asset.uri, str(tail_path))
            self.assertEqual(asset.status, "completed")
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["source"], "previous_last_frame")
            self.assertEqual(meta["source_last_frame_asset_id"], tail.id)

    def test_render_post_process_writes_shot_last_frame_asset(self) -> None:
        from app.video_render_service import VideoRenderService

        with self.SessionLocal() as session, TemporaryDirectory() as tmpdir:
            storyboard = session.get(Storyboard, self.storyboard_id)
            shot = storyboard.shots[0]
            task = VideoTask(project_id=self.project_id, storyboard=storyboard, task_status="running", progress_json=json_dumps({"shots": []}))
            session.add(task)
            session.commit()
            output_dir = Path(tmpdir)
            segment_path = output_dir / "segment-001.mp4"
            segment_path.write_bytes(b"video")
            video_asset = MediaAsset(
                project_id=self.project_id,
                storyboard=storyboard,
                shot=shot,
                asset_type="video",
                uri=str(segment_path),
                prompt="video",
                status="completed",
                meta_json=json_dumps({"shot_no": shot.shot_no}),
            )
            session.add(video_asset)
            session.commit()
            last_frame_path = output_dir / "shot-001-last-frame.png"
            service = VideoRenderService(load_settings())

            with patch.object(service, "_run_ffmpeg", side_effect=lambda args: last_frame_path.write_bytes(b"frame")):
                service._post_process_shot(db=session, task=task, shot=shot, output_dir=output_dir, segment_path=segment_path)
                session.commit()

            asset = session.scalar(
                select(MediaAsset).where(
                    MediaAsset.storyboard_id == storyboard.id,
                    MediaAsset.shot_id == shot.id,
                    MediaAsset.asset_type == "shot_last_frame",
                )
            )
            self.assertIsNotNone(asset)
            self.assertEqual(asset.status, "completed")
            self.assertEqual(asset.uri, str(last_frame_path))
            meta = json_loads_object(asset.meta_json)
            self.assertEqual(meta["source_video_asset_id"], video_asset.id)
            self.assertEqual(meta["shot_id"], shot.id)
            self.assertEqual(meta["shot_no"], shot.shot_no)


if __name__ == "__main__":
    unittest.main()
