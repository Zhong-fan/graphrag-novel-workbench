from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .api_support import (
    _canonicalize_generation,
    _generation_or_404,
    _novel_card_out,
    _novel_comment_out,
    _novel_detail_out,
    _novel_owned_or_404,
    _novel_viewable_or_404,
    _project_chapter_or_404,
    _project_or_404,
)
from .auth import get_current_user, get_optional_user
from .config import Settings
from .contracts import (
    AppendNovelChapterRequest,
    DeleteNovelRequest,
    FavoriteToggleResponse,
    LikeToggleResponse,
    NovelCardOut,
    NovelCommentCreateRequest,
    NovelCommentOut,
    NovelDetailOut,
    PublishNovelRequest,
    UpdateNovelChapterRequest,
    UpdateNovelRequest,
)
from .db import get_db
from .models import Novel, NovelChapter, NovelComment, NovelFavorite, NovelLike, User


def register_novel_routes(router: APIRouter, *, settings: Settings) -> None:
    @router.get("/api/novels", response_model=list[NovelCardOut])
    def list_novels(
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> list[NovelCardOut]:
        novels = db.scalars(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.visibility == "public", Novel.deleted_at.is_(None))
            .order_by(Novel.updated_at.desc())
        ).unique().all()
        current_user_id = current_user.id if current_user is not None else None
        return [_novel_card_out(item, current_user_id=current_user_id) for item in novels]

    @router.get("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def novel_detail(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> NovelDetailOut:
        current_user_id = current_user.id if current_user is not None else None
        novel = _novel_viewable_or_404(db, novel_id, current_user_id=current_user_id)
        return _novel_detail_out(novel, current_user_id=current_user_id)

    @router.get("/api/me/favorites", response_model=list[NovelCardOut])
    def my_favorites(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[NovelCardOut]:
        favorites = db.scalars(
            select(NovelFavorite)
            .options(
                selectinload(NovelFavorite.novel).selectinload(Novel.owner),
                selectinload(NovelFavorite.novel).selectinload(Novel.chapters),
                selectinload(NovelFavorite.novel).selectinload(Novel.likes),
                selectinload(NovelFavorite.novel).selectinload(Novel.favorites),
                selectinload(NovelFavorite.novel).selectinload(Novel.comments),
            )
            .where(NovelFavorite.user_id == current_user.id)
            .order_by(NovelFavorite.created_at.desc())
        ).all()
        novels = [item.novel for item in favorites if item.novel.visibility == "public" and item.novel.deleted_at is None]
        return [_novel_card_out(item, current_user_id=current_user.id) for item in novels]

    @router.get("/api/me/novels", response_model=list[NovelCardOut])
    def my_novels(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[NovelCardOut]:
        novels = db.scalars(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.owner_id == current_user.id, Novel.deleted_at.is_(None))
            .order_by(Novel.updated_at.desc())
        ).unique().all()
        return [_novel_card_out(item, current_user_id=current_user.id) for item in novels]

    @router.post("/api/novels/{novel_id}/favorite", response_model=FavoriteToggleResponse)
    def create_favorite(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> FavoriteToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        exists = db.scalar(
            select(NovelFavorite).where(NovelFavorite.novel_id == novel_id, NovelFavorite.user_id == current_user.id)
        )
        if exists is None:
            db.add(NovelFavorite(novel=novel, user=current_user))
            db.commit()
            db.refresh(novel)
        return FavoriteToggleResponse(
            favorited=True,
            novel_id=novel.id,
            favorites_count=len(novel.favorites),
        )

    @router.delete("/api/novels/{novel_id}/favorite", response_model=FavoriteToggleResponse)
    def delete_favorite(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> FavoriteToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        favorite = db.scalar(
            select(NovelFavorite).where(NovelFavorite.novel_id == novel_id, NovelFavorite.user_id == current_user.id)
        )
        if favorite is not None:
            db.delete(favorite)
            db.commit()
            db.refresh(novel)
        return FavoriteToggleResponse(
            favorited=False,
            novel_id=novel.id,
            favorites_count=len(novel.favorites),
        )

    @router.post("/api/novels/{novel_id}/like", response_model=LikeToggleResponse)
    def create_like(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> LikeToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        exists = db.scalar(select(NovelLike).where(NovelLike.novel_id == novel_id, NovelLike.user_id == current_user.id))
        if exists is None:
            db.add(NovelLike(novel=novel, user=current_user))
            db.commit()
            db.refresh(novel)
        return LikeToggleResponse(
            liked=True,
            novel_id=novel.id,
            likes_count=len(novel.likes),
        )

    @router.delete("/api/novels/{novel_id}/like", response_model=LikeToggleResponse)
    def delete_like(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> LikeToggleResponse:
        novel = db.get(Novel, novel_id)
        if novel is None or novel.visibility != "public":
            raise HTTPException(status_code=404, detail="作品不存在。")
        like = db.scalar(select(NovelLike).where(NovelLike.novel_id == novel_id, NovelLike.user_id == current_user.id))
        if like is not None:
            db.delete(like)
            db.commit()
            db.refresh(novel)
        return LikeToggleResponse(
            liked=False,
            novel_id=novel.id,
            likes_count=len(novel.likes),
        )

    @router.get("/api/novels/{novel_id}/comments", response_model=list[NovelCommentOut])
    def list_novel_comments(
        novel_id: int,
        db: Session = Depends(get_db),
        current_user: User | None = Depends(get_optional_user),
    ) -> list[NovelCommentOut]:
        current_user_id = current_user.id if current_user is not None else None
        _novel_viewable_or_404(db, novel_id, current_user_id=current_user_id)
        comments = db.scalars(
            select(NovelComment)
            .options(selectinload(NovelComment.user))
            .where(NovelComment.novel_id == novel_id)
            .order_by(NovelComment.created_at.desc())
        ).all()
        return [_novel_comment_out(item) for item in comments]

    @router.post("/api/novels/{novel_id}/comments", response_model=NovelCommentOut)
    def create_novel_comment(
        novel_id: int,
        payload: NovelCommentCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelCommentOut:
        novel = _novel_viewable_or_404(db, novel_id, current_user_id=current_user.id)
        comment = NovelComment(novel=novel, user=current_user, content=payload.content.strip())
        db.add(comment)
        db.commit()
        db.refresh(comment)
        db.refresh(novel)
        return _novel_comment_out(comment)

    @router.post("/api/novels/from-generation", response_model=NovelDetailOut)
    def publish_novel_from_generation(
        payload: PublishNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        project = _project_or_404(db, current_user.id, payload.project_id)
        project_chapter = _project_chapter_or_404(db, project.id, payload.project_chapter_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)
        if generation.project_chapter_id != project_chapter.id:
            raise HTTPException(status_code=409, detail="Generation does not belong to the selected project chapter.")

        novel = Novel(
            owner=current_user,
            project=project,
            source_generation=generation,
            author_name=payload.author_name.strip(),
            title=payload.title.strip(),
            summary=payload.summary.strip() or generation.summary,
            genre=project.genre,
            tagline=payload.tagline.strip(),
            status="published",
            visibility=payload.visibility,
        )
        db.add(novel)
        db.flush()

        chapter_title = payload.chapter_title.strip() or generation.title.strip() or "第一章"
        chapter_summary = payload.chapter_summary.strip() or generation.summary
        chapter_content = payload.chapter_content.strip() or generation.content
        db.add(
            NovelChapter(
                novel=novel,
                title=chapter_title,
                summary=chapter_summary,
                content=chapter_content,
                chapter_no=payload.chapter_no,
            )
        )
        _canonicalize_generation(
            db,
            settings,
            project,
            project_chapter,
            generation,
            adopted_title=chapter_title,
            adopted_summary=chapter_summary,
            adopted_content=chapter_content,
        )
        db.commit()

        created = db.scalar(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.id == novel.id)
        )
        if created is None:
            raise HTTPException(status_code=500, detail="作品发布失败。")
        return _novel_detail_out(created, current_user_id=current_user.id)

    @router.put("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def update_novel(
        novel_id: int,
        payload: UpdateNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        novel.title = payload.title.strip()
        novel.author_name = payload.author_name.strip()
        novel.summary = payload.summary.strip()
        novel.tagline = payload.tagline.strip()
        novel.visibility = payload.visibility
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

    @router.delete("/api/novels/{novel_id}", response_model=NovelDetailOut)
    def delete_novel(
        novel_id: int,
        payload: DeleteNovelRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = db.scalar(
            select(Novel)
            .options(
                selectinload(Novel.owner),
                selectinload(Novel.chapters),
                selectinload(Novel.likes),
                selectinload(Novel.favorites),
                selectinload(Novel.comments),
            )
            .where(Novel.id == novel_id, Novel.owner_id == current_user.id)
        )
        if novel is None:
            raise HTTPException(status_code=404, detail="作品不存在。")
        if payload.hard_delete:
            result = _novel_detail_out(novel, current_user_id=current_user.id)
            db.delete(novel)
            db.commit()
            return result
        novel.deleted_at = datetime.utcnow()
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

    @router.post("/api/novels/{novel_id}/chapters/from-generation", response_model=NovelDetailOut)
    def append_novel_chapter_from_generation(
        novel_id: int,
        payload: AppendNovelChapterRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        project = _project_or_404(db, current_user.id, payload.project_id)
        if novel.project_id is not None and novel.project_id != project.id:
            raise HTTPException(status_code=409, detail="Novel does not belong to the selected project.")
        project_chapter = _project_chapter_or_404(db, project.id, payload.project_chapter_id)
        generation = _generation_or_404(db, project.id, payload.generation_id)
        if generation.project_chapter_id != project_chapter.id:
            raise HTTPException(status_code=409, detail="Generation does not belong to the selected project chapter.")
        next_chapter_no = payload.chapter_no or max((item.chapter_no for item in novel.chapters), default=0) + 1
        if any(item.chapter_no == next_chapter_no for item in novel.chapters):
            raise HTTPException(status_code=409, detail=f"第 {next_chapter_no} 章已经存在。")

        chapter_title = payload.title.strip() or generation.title.strip() or f"第{next_chapter_no}章"
        chapter_summary = payload.summary.strip() or generation.summary
        chapter_content = payload.content.strip() or generation.content
        db.add(
            NovelChapter(
                novel=novel,
                title=chapter_title,
                summary=chapter_summary,
                content=chapter_content,
                chapter_no=next_chapter_no,
            )
        )
        _canonicalize_generation(
            db,
            settings,
            project,
            project_chapter,
            generation,
            adopted_title=chapter_title,
            adopted_summary=chapter_summary,
            adopted_content=chapter_content,
        )
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)

    @router.put("/api/novels/{novel_id}/chapters/{chapter_id}", response_model=NovelDetailOut)
    def update_novel_chapter(
        novel_id: int,
        chapter_id: int,
        payload: UpdateNovelChapterRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> NovelDetailOut:
        novel = _novel_owned_or_404(db, current_user.id, novel_id)
        chapter = next((item for item in novel.chapters if item.id == chapter_id), None)
        if chapter is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        if any(item.id != chapter_id and item.chapter_no == payload.chapter_no for item in novel.chapters):
            raise HTTPException(status_code=409, detail=f"第 {payload.chapter_no} 章已经存在。")

        chapter.title = payload.title.strip()
        chapter.summary = payload.summary.strip()
        chapter.content = payload.content.strip()
        chapter.chapter_no = payload.chapter_no
        db.commit()
        db.refresh(novel)
        return _novel_detail_out(novel, current_user_id=current_user.id)
