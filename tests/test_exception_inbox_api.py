from __future__ import annotations

import unittest

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_routes_inbox import register_inbox_routes
from app.auth import get_current_user
from app.config import load_settings
from app.db import Base, get_db
from app.exception_inbox_service import create_inbox_item
from app.models import Project, User


class ExceptionInboxApiTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="inbox-api@example.com", display_name="收件箱用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="收件箱项目", genre="青春")
            session.add_all([user, project])
            session.commit()
            self.user_id = user.id
            self.project_id = project.id
            self.other_project_id = None

        settings = load_settings()
        app = FastAPI()
        router = APIRouter()
        register_inbox_routes(router, settings=settings)
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

    def _seed_item(self, project_id: int | None = None) -> int:
        with self.SessionLocal() as session:
            project = session.get(Project, project_id or self.project_id)
            item = create_inbox_item(
                db=session,
                project=project,
                item_type="budget_approval",
                title="视频生成成本需要确认",
                reason="估算成本超阈值。",
                recommended_action="确认预算后继续。",
                evidence={"generation_attempt_id": 1},
            )
            session.commit()
            return item.id

    def test_list_returns_open_items(self) -> None:
        item_id = self._seed_item()
        response = self.client.get(f"/api/projects/{self.project_id}/exception-inbox")
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], item_id)
        self.assertEqual(items[0]["item_type"], "budget_approval")
        self.assertEqual(items[0]["status"], "open")
        self.assertEqual(items[0]["recommended_action"], "确认预算后继续。")

    def test_resolve_marks_item_resolved(self) -> None:
        item_id = self._seed_item()
        response = self.client.post(
            f"/api/projects/{self.project_id}/exception-inbox/{item_id}/resolve",
            json={"resolution": "accepted"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "resolved")
        self.assertEqual(response.json()["resolution"], "accepted")
        empty = self.client.get(f"/api/projects/{self.project_id}/exception-inbox")
        self.assertEqual(empty.json()["items"], [])
        history = self.client.get(f"/api/projects/{self.project_id}/exception-inbox?status=all")
        self.assertEqual(len(history.json()["items"]), 1)
        self.assertEqual(history.json()["items"][0]["status"], "resolved")

    def test_resolve_rejects_invalid_resolution(self) -> None:
        item_id = self._seed_item()
        response = self.client.post(
            f"/api/projects/{self.project_id}/exception-inbox/{item_id}/resolve",
            json={"resolution": "maybe"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_unknown_project_returns_404(self) -> None:
        response = self.client.get("/api/projects/99999/exception-inbox")
        self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
