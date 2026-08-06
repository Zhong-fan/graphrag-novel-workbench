from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.media_publication_service import MediaPublicationService, file_sha256, sha256_hex
from app.models import MediaAsset, MediaPublication, Project, Storyboard, User


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        media_public_base_url="https://media.example.com",
        media_publication_ttl_seconds=1800,
    )


class MediaPublicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite://", future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.tmpdir.name) / "first-frame.png"
        self.file_path.write_bytes(b"fake-png-bytes" * 100)
        with self.SessionLocal() as session:
            user = User(email="pub@example.com", display_name="发布用户", password_hash=b"0" * 32, password_salt=b"1" * 16)
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
            self.asset_id = asset.id

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _asset(self, session) -> MediaAsset:
        return session.get(MediaAsset, self.asset_id)

    def test_publish_creates_active_publication(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            publication = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            self.assertEqual(publication.status, "active")
            self.assertEqual(publication.checksum, file_sha256(self.file_path))
            self.assertTrue(publication.access_url.startswith("https://media.example.com/api/media/publications/"))
            token = publication.access_url.rsplit("/", 1)[-1]
            self.assertEqual(publication.token_hash, sha256_hex(token))
            self.assertIsNotNone(publication.expires_at)
            self.assertGreater(publication.expires_at, datetime.utcnow())

    def test_get_or_create_active_reuses_publication(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            first = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            second = service.get_or_create_active(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            self.assertEqual(first.id, second.id)

    def test_publish_expires_previous_active(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            first = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            second = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            session.refresh(first)
            self.assertEqual(first.status, "expired")
            self.assertEqual(second.status, "active")

    def test_verify_returns_access_url(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            publication = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            self.assertEqual(service.verify(publication=publication), publication.access_url)

    def test_verify_raises_when_expired(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            publication = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            publication.expires_at = datetime.utcnow() - timedelta(seconds=1)
            with self.assertRaises(RuntimeError) as ctx:
                service.verify(publication=publication)
            self.assertIn("过期", str(ctx.exception))
            self.assertEqual(publication.status, "expired")

    def test_verify_raises_when_source_missing(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            publication = service.publish(db=session, asset=self._asset(session), purpose="seedance_first_frame")
            self.file_path.unlink()
            with self.assertRaises(RuntimeError) as ctx:
                service.verify(publication=publication)
            self.assertIn("源文件", str(ctx.exception))

    def test_publish_missing_file_records_failed_without_secrets(self) -> None:
        service = MediaPublicationService(_settings())
        with self.SessionLocal() as session:
            asset = self._asset(session)
            asset.uri = str(Path(self.tmpdir.name) / "missing.png")
            with self.assertRaises(RuntimeError) as ctx:
                service.publish(db=session, asset=asset, purpose="seedance_first_frame")
            self.assertIn("源文件", str(ctx.exception))
            failed = session.query(MediaPublication).filter_by(status="failed").one()
            self.assertEqual(failed.provider_purpose, "seedance_first_frame")
            self.assertNotIn("Bearer", failed.error_message)
            self.assertEqual(failed.access_url, "")

    def test_file_sha256_is_stable(self) -> None:
        expected = hashlib.sha256(b"fake-png-bytes" * 100).hexdigest()
        self.assertEqual(file_sha256(self.file_path), expected)

    def test_video_render_provider_asset_url_publishes_and_reuses(self) -> None:
        from app.video_render_service import VideoRenderService

        service = VideoRenderService(_settings())
        with self.SessionLocal() as session:
            url, publication_id = service._provider_asset_url(
                db=session, asset=self._asset(session), purpose="seedance_first_frame"
            )
            self.assertTrue(url.startswith("https://media.example.com/api/media/publications/"))
            self.assertIsNotNone(publication_id)
            url2, publication_id2 = service._provider_asset_url(
                db=session, asset=self._asset(session), purpose="seedance_first_frame"
            )
            self.assertEqual(publication_id, publication_id2)
            self.assertEqual(url, url2)


if __name__ == "__main__":
    unittest.main()