from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .adoption_revert_service import AdoptionRevertService
from .auth import get_current_user
from .config import Settings
from .db import get_db
from .models import CharacterCard, MediaAsset, Project, User


class IdentityRevertRequest(BaseModel):
    target_version_id: int


def register_revert_routes(router: APIRouter, *, settings: Settings) -> None:
    service = AdoptionRevertService(settings)

    @router.get("/api/projects/{project_id}/assets/{asset_id}/versions")
    def list_asset_versions(
        project_id: int,
        asset_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        """List version snapshots for an auto-adopted asset (progressive disclosure)."""
        asset = _owned_asset(db, project_id=project_id, asset_id=asset_id, current_user=current_user)
        versions = service.list_versions(db=db, asset=asset)
        return {
            "items": [
                {
                    "version_no": item.version_no,
                    "uri": item.uri,
                    "prompt": item.prompt,
                    "reason": item.reason,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in versions
            ]
        }

    @router.post("/api/projects/{project_id}/assets/{asset_id}/versions/{version_no}/restore")
    def restore_asset_version(
        project_id: int,
        asset_id: int,
        version_no: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        """Restore a snapshot onto the canonical asset; the restore is itself versioned."""
        asset = _owned_asset(db, project_id=project_id, asset_id=asset_id, current_user=current_user)
        try:
            restored = service.restore_asset_version(db=db, asset=asset, version_no=version_no)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        db.commit()
        return {
            "asset_id": asset.id,
            "restored_version_no": restored.version_no,
            "uri": asset.uri,
        }

    @router.post("/api/projects/{project_id}/characters/{character_id}/identity/revert")
    def revert_identity_adoption(
        project_id: int,
        character_id: int,
        payload: IdentityRevertRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> dict:
        """Restore a previous identity version as the canonical character identity."""
        project = _owned_project(db, project_id=project_id, current_user=current_user)
        character = db.scalar(
            select(CharacterCard).where(
                CharacterCard.id == character_id,
                CharacterCard.project_id == project.id,
                CharacterCard.deleted_at.is_(None),
            )
        )
        if character is None:
            raise HTTPException(status_code=404, detail="角色不存在。")
        try:
            target = service.revert_identity_adoption(
                db=db,
                project=project,
                character=character,
                target_version_id=payload.target_version_id,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.commit()
        return {
            "character_card_id": character.id,
            "target_version_id": target.id,
            "version_no": target.version_no,
            "turnaround_asset_id": target.turnaround_asset_id,
        }


def _owned_project(db: Session, *, project_id: int, current_user: User) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    return project


def _owned_asset(db: Session, *, project_id: int, asset_id: int, current_user: User) -> MediaAsset:
    project = _owned_project(db, project_id=project_id, current_user=current_user)
    asset = db.get(MediaAsset, asset_id)
    if asset is None or asset.project_id != project.id:
        raise HTTPException(status_code=404, detail="素材不存在。")
    return asset
