from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_routes_longform import register_longform_routes
from app.auth import get_current_user
from app.config import load_settings
from app.db import Base, get_db
from app.json_utils import json_dumps
from app.models import BatchGenerationChapterTask, BatchGenerationJob, ChapterOutline, DraftVersion, Project, SeriesPlan, User


class ChapterDependencyInvalidationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="dependency-api@example.com", display_name="依赖测试", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="依赖测试项目", genre="悬疑")
            plan = SeriesPlan(project=project, title="规划", target_chapter_count=2, theme="主题", main_conflict="冲突", ending_direction="结局", status="locked")
            outline_one = ChapterOutline(project=project, series_plan=plan, chapter_no=1, title="第一章", outline_json=json_dumps({"goal": "旧开场"}), status="outline_locked")
            outline_two = ChapterOutline(project=project, series_plan=plan, chapter_no=2, title="第二章", outline_json=json_dumps({"goal": "延续"}), status="draft_generated")
            job = BatchGenerationJob(project=project, series_plan=plan, start_chapter_no=2, end_chapter_no=2, job_status="completed", result_summary_json="{}")
            task = BatchGenerationChapterTask(job=job, chapter_outline=outline_two, chapter_no=2, status="completed", error_message="", output_validity="valid")
            session.add(task)
            session.commit()
            self.user_id = user.id
            self.project_id = project.id
            self.outline_id = outline_one.id
            self.job_id = job.id
            self.task_id = task.id

        app = FastAPI()
        router = APIRouter()
        settings = replace(load_settings(), output_dir=Path(self.temp_dir.name) / "output")
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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_outline_change_invalidates_generated_descendants(self) -> None:
        response = self.client.put(
            f"/api/projects/{self.project_id}/chapter-outlines/{self.outline_id}",
            json={"title": "第一章", "outline": {"goal": "新的开场"}, "status": "outline_draft"},
        )
        self.assertEqual(response.status_code, 200)
        with self.SessionLocal() as session:
            task = session.get(BatchGenerationChapterTask, self.task_id)
            self.assertEqual(task.status, "completed")
            self.assertEqual(task.output_validity, "stale_dependency")
            self.assertEqual(task.invalidated_by_chapter_no, 1)
            self.assertIn("概要已修改", task.invalidation_reason)

    def test_outline_change_is_rejected_while_generation_is_active(self) -> None:
        with self.SessionLocal() as session:
            session.get(BatchGenerationJob, self.job_id).job_status = "queued"
            session.commit()
        response = self.client.put(
            f"/api/projects/{self.project_id}/chapter-outlines/{self.outline_id}",
            json={"title": "第一章", "outline": {"goal": "不能并发修改"}, "status": "outline_draft"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("尚未结束", response.json()["detail"])

    def test_confirming_new_body_version_invalidates_only_descendants(self) -> None:
        with self.SessionLocal() as session:
            previous = DraftVersion(project_id=self.project_id, chapter_outline_id=self.outline_id, version_no=1, title="旧正文", summary="旧", content="旧内容", status="chapter_canonical", revision_reason="initial")
            current = DraftVersion(project_id=self.project_id, chapter_outline_id=self.outline_id, version_no=2, title="新正文", summary="新", content="新内容", status="draft_revised", revision_reason="rewrite")
            session.add_all([previous, current])
            session.commit()
            current_id = current.id

        response = self.client.post(
            f"/api/projects/{self.project_id}/draft-versions/{current_id}/canonicalize",
            json={"visibility": "private", "author_name": "依赖测试"},
        )
        self.assertEqual(response.status_code, 200)
        repeated = self.client.post(
            f"/api/projects/{self.project_id}/draft-versions/{current_id}/canonicalize",
            json={"visibility": "private", "author_name": "依赖测试"},
        )
        self.assertEqual(repeated.status_code, 409)
        with self.SessionLocal() as session:
            task = session.get(BatchGenerationChapterTask, self.task_id)
            self.assertEqual(task.output_validity, "stale_dependency")
            self.assertEqual(task.invalidated_by_chapter_no, 1)
            self.assertEqual(task.invalidated_by_draft_version_id, current_id)
            self.assertIn("正文版本 v2", task.invalidation_reason)


if __name__ == "__main__":
    unittest.main()
