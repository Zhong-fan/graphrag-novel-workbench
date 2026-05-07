from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .contracts import NovelCardOut, NovelChapterOut, NovelCommentOut, NovelDetailOut
from .models import GenerationRun, Novel, NovelChapter, NovelComment


def _novel_excerpt(novel: Novel) -> str:
    chapter = sorted(novel.chapters, key=lambda item: item.chapter_no)[0] if novel.chapters else None
    if chapter is not None and chapter.content.strip():
        return chapter.content.strip()[:160]
    if chapter is not None and chapter.summary.strip():
        return chapter.summary.strip()[:160]
    return novel.summary.strip()[:160]


def _novel_card_out(novel: Novel, current_user_id: int | None = None) -> NovelCardOut:
    favorite_user_ids = {item.user_id for item in novel.favorites}
    like_user_ids = {item.user_id for item in novel.likes}
    return NovelCardOut(
        id=novel.id,
        project_id=novel.project_id,
        source_generation_id=novel.source_generation_id,
        title=novel.title,
        author=novel.author_name,
        summary=novel.summary,
        genre=novel.genre,
        tagline=novel.tagline,
        cover_url=novel.cover_url,
        status=novel.status,
        visibility=novel.visibility,
        likes_count=len(novel.likes),
        favorites_count=len(novel.favorites),
        comments_count=len(novel.comments),
        chapters_count=len(novel.chapters),
        latest_excerpt=_novel_excerpt(novel),
        is_liked=current_user_id in like_user_ids if current_user_id is not None else False,
        is_favorited=current_user_id in favorite_user_ids if current_user_id is not None else False,
        created_at=novel.created_at,
        updated_at=novel.updated_at,
    )


def _novel_detail_out(novel: Novel, current_user_id: int | None = None) -> NovelDetailOut:
    return NovelDetailOut(
        **_novel_card_out(novel, current_user_id=current_user_id).model_dump(),
        chapters=[
            NovelChapterOut.model_validate(chapter)
            for chapter in sorted(novel.chapters, key=lambda item: item.chapter_no)
        ],
    )


def _novel_comment_out(comment: NovelComment) -> NovelCommentOut:
    return NovelCommentOut(
        id=comment.id,
        user_id=comment.user_id,
        username=comment.user.display_name,
        content=comment.content,
        created_at=comment.created_at,
    )


def _novel_viewable_or_404(db: Session, novel_id: int, current_user_id: int | None = None) -> Novel:
    novel = db.scalar(
        select(Novel)
        .options(
            selectinload(Novel.owner),
            selectinload(Novel.chapters),
            selectinload(Novel.likes),
            selectinload(Novel.favorites),
            selectinload(Novel.comments),
        )
        .where(Novel.id == novel_id, Novel.deleted_at.is_(None))
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="作品不存在。")
    if novel.visibility != "public" and novel.owner_id != current_user_id:
        raise HTTPException(status_code=404, detail="作品不存在。")
    return novel


def _novel_owned_or_404(db: Session, user_id: int, novel_id: int) -> Novel:
    novel = db.scalar(
        select(Novel)
        .options(
            selectinload(Novel.owner),
            selectinload(Novel.chapters),
            selectinload(Novel.likes),
            selectinload(Novel.favorites),
            selectinload(Novel.comments),
        )
        .where(Novel.id == novel_id, Novel.owner_id == user_id, Novel.deleted_at.is_(None))
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="作品不存在或无权限。")
    return novel


def _generation_or_404(db: Session, project_id: int, generation_id: int) -> GenerationRun:
    generation = db.scalar(
        select(GenerationRun).where(GenerationRun.project_id == project_id, GenerationRun.id == generation_id)
    )
    if generation is None:
        raise HTTPException(status_code=404, detail="生成结果不存在。")
    return generation
