from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api_routes_media import register_media_routes
from app.db import Base, get_db
from app.media_publication_service import MediaPublicationService
from app.models import MediaAsset, MediaPublication, Project, Storyboard, User


class MediaPublicationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.tmpdir.name) / "first-frame.png"
        self.file_bytes = b"fake-png-bytes" * 50
        self.file_path.write_bytes(self.file_bytes)
        self.settings = SimpleNamespace(
            media_public_base_url="https://media.example.com",
            media_publication_ttl_seconds=1800,
        )
        with self.SessionLocal() as session:
            user = User(email="pubapi@example.com", display_name="发布API用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
            project = Project(owner=user, title="发布项目", genre="青春")
            storyboard = Storyboard(project=project, title="短片", source_chapter_ids_json="[]")
            asset = MediaAsset(
                project=project,
                storyboard=storyboard,
                asset_type="shot_first_frame",
                uri=str(self.file_path),
                status="completed",
            )
            session.add_all([user, project, storyboard, asset])
            session.commit()
            publication = MediaPublicationService(self.settings).publish(
                db=session, asset=asset, purpose="seedance_first_frame"
            )
            session.commit()
            self.publication_access_url = publication.access_url
            self.publication_id = publication.id

        app = FastAPI()
        router = APIRouter()
        register_media_routes(router, settings=self.settings)
        app.include_router(router)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _publication_path(self) -> str:
        return urlparse(self.publication_access_url).path

    def test_serve_active_publication(self) -> None:
        response = self.client.get(self._publication_path())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.file_bytes)

    def test_serve_unknown_token_returns_404(self) -> None:
        response = self.client.get("/api/media/publications/unknown-token")
        self.assertEqual(response.status_code, 404)

    def test_serve_expired_publication_returns_410(self) -> None:
        with self.SessionLocal() as session:
            publication = session.get(MediaPublication, self.publication_id)
            publication.expires_at = datetime.utcnow() - timedelta(seconds=1)
            session.commit()
        response = self.client.get(self._publication_path())
        self.assertEqual(response.status_code, 410)

    def test_serve_inactive_publication_returns_410(self) -> None:
        with self.SessionLocal() as session:
            publication = session.get(MediaPublication, self.publication_id)
            publication.status = "failed"
            session.commit()
        response = self.client.get(self._publication_path())
        self.assertEqual(response.status_code, 410)

    def test_serve_missing_source_returns_410(self) -> None:
        self.file_path.unlink()
        response = self.client.get(self._publication_path())
        self.assertEqual(response.status_code, 410)


if __name__ == "__main__":
    unittest.main()