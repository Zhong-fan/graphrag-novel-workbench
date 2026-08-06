from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import get_db
from .media_publication_service import sha256_hex
from .models import MediaPublication


def register_media_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/media/publications/{token}")
    def serve_media_publication(token: str, db: Session = Depends(get_db)) -> FileResponse:
        """契约：访问只靠不可猜测的随机 token + 过期时间，不要求登录态；token 只存哈希。"""
        publication = db.scalar(select(MediaPublication).where(MediaPublication.token_hash == sha256_hex(token)))
        publication = db.scalar(select(MediaPublication).where(MediaPublication.token_hash == sha256_hex(token)))
        if publication is None:
            raise HTTPException(status_code=404, detail="发布引用不存在。")
        if publication.status != "active":
            raise HTTPException(status_code=410, detail="发布引用已失效。")
        if publication.expires_at is None or publication.expires_at <= datetime.utcnow():
            raise HTTPException(status_code=410, detail="发布引用已过期。")
        source_path = Path(publication.source_uri or "")
        if not source_path.is_file():
            raise HTTPException(status_code=410, detail="发布引用对应的源文件已不可访问。")
        return FileResponse(source_path)