from __future__ import annotations

import unittest

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_routes_evidence import register_evidence_routes
from app.auth import get_current_user
from app.config import load_settings
from app.db import Base, get_db
from app.generation_evidence_service import GenerationEvidence, record_generation_evidence
from app.models import Project, User


class GenerationEvidenceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        with self.SessionLocal() as session:
            user = User(email="evidence-api@example.com", display_name="证据用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="证据项目", genre="青春")
            session.add_all([user, project])
            session.commit()
            self.user_id = user.id
            self.project_id = project.id

        settings = load_settings()
        app = FastAPI()
        router = APIRouter()
        register_evidence_routes(router, settings=settings)
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

    def _seed(self) -> None:
        with self.SessionLocal() as session:
            record_generation_evidence(
                session,
                evidence=GenerationEvidence(
                    stage="image_first_frame",
                    status="succeeded",
                    provider="jimeng",
                    model="req",
                    project_id=self.project_id,
                    quality_outcome="accepted",
                    parameters={"width": 1024, "height": 1024},
                ),
            )
            record_generation_evidence(
                session,
                evidence=GenerationEvidence(
                    stage="cost_gate",
                    status="blocked",
                    provider="ark_seedance",
                    model="doubao-seedance-2-0-mini",
                    project_id=self.project_id,
                    error_category="budget_confirmation_required",
                ),
            )
            session.commit()

    def test_list_returns_attempts_newest_first(self) -> None:
        self._seed()
        response = self.client.get(f"/api/projects/{self.project_id}/generation-attempts")
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["stage"], "cost_gate")
        self.assertEqual(items[0]["status"], "blocked")
        self.assertEqual(items[0]["error_category"], "budget_confirmation_required")
        self.assertEqual(items[1]["stage"], "image_first_frame")
        self.assertEqual(items[1]["quality_outcome"], "accepted")
        self.assertEqual(items[1]["parameters"]["width"], 1024)

    def test_filters_by_stage_and_status(self) -> None:
        self._seed()
        response = self.client.get(f"/api/projects/{self.project_id}/generation-attempts?stage=cost_gate")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stage"], "cost_gate")
        response = self.client.get(f"/api/projects/{self.project_id}/generation-attempts?status=succeeded")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stage"], "image_first_frame")

    def test_unknown_project_returns_404(self) -> None:
        response = self.client.get("/api/projects/99999/generation-attempts")
        self.assertEqual(response.status_code, 404, response.text)


if __name__ == "__main__":
    unittest.main()
