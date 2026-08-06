from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import MediaAsset, MediaPublication


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MediaPublicationService:
    """本地媒体到 provider 可读临时 URL 的唯一发布边界。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def publish(
        self,
        *,
        db: Session,
        asset: MediaAsset,
        purpose: str,
        ttl_seconds: int | None = None,
    ) -> MediaPublication:
        source_path = Path(asset.uri or "")
        if not source_path.is_file():
            publication = self._record_failed(db=db, asset=asset, purpose=purpose, error="源文件不存在或不可读。")
            raise RuntimeError(f"媒体发布失败：{publication.error_message}")
        ttl = max(1, ttl_seconds or self.settings.media_publication_ttl_seconds)
        token = secrets.token_urlsafe(24)
        self._expire_active(db=db, asset=asset, purpose=purpose)
        publication = MediaPublication(
            media_asset_id=asset.id,
            source_uri=str(source_path),
            checksum=file_sha256(source_path),
            provider_purpose=purpose,
            token_hash=sha256_hex(token),
            access_url=self._access_url(token),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            status="active",
            error_message="",
        )
        db.add(publication)
        db.flush()
        return publication

    def get_or_create_active(
        self,
        *,
        db: Session,
        asset: MediaAsset,
        purpose: str,
        ttl_seconds: int | None = None,
    ) -> MediaPublication:
        active = db.scalar(
            select(MediaPublication)
            .where(
                MediaPublication.media_asset_id == asset.id,
                MediaPublication.provider_purpose == purpose,
                MediaPublication.status == "active",
                MediaPublication.expires_at > datetime.utcnow(),
            )
            .order_by(MediaPublication.created_at.desc())
            .limit(1)
        )
        if active is not None:
            return active
        return self.publish(db=db, asset=asset, purpose=purpose, ttl_seconds=ttl_seconds)

    def verify(self, *, publication: MediaPublication) -> str:
        """提交昂贵生成请求前的最后校验：有效、未过期、源文件可读。失败抛出可操作原因。"""
        if publication.status != "active":
            self._mark_expired(publication)
            raise RuntimeError("媒体发布引用已失效。")
        if publication.expires_at is None or publication.expires_at <= datetime.utcnow():
            self._mark_expired(publication)
            raise RuntimeError("媒体发布引用已过期。")
        if not Path(publication.source_uri or "").is_file():
            self._mark_expired(publication)
            raise RuntimeError("媒体发布引用对应的源文件已不可访问。")
        return publication.access_url

    def _expire_active(self, *, db: Session, asset: MediaAsset, purpose: str) -> None:
        active_rows = db.scalars(
            select(MediaPublication).where(
                MediaPublication.media_asset_id == asset.id,
                MediaPublication.provider_purpose == purpose,
                MediaPublication.status == "active",
            )
        ).all()
        for row in active_rows:
            row.status = "expired"

    def _mark_expired(self, publication: MediaPublication) -> None:
        publication.status = "expired"

    def _record_failed(
        self,
        *,
        db: Session,
        asset: MediaAsset,
        purpose: str,
        error: str,
    ) -> MediaPublication:
        publication = MediaPublication(
            media_asset_id=asset.id,
            source_uri=asset.uri or "",
            checksum="",
            provider_purpose=purpose,
            token_hash="",
            access_url="",
            expires_at=None,
            status="failed",
            error_message=error,
        )
        db.add(publication)
        db.flush()
        return publication

    def _access_url(self, token: str) -> str:
        base = (self.settings.media_public_base_url or "").rstrip("/")
        return f"{base}/api/media/publications/{token}"