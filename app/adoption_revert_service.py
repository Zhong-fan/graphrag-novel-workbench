from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .character_identity_service import CharacterIdentityService
from .config import Settings
from .json_utils import json_dumps, json_loads_list, json_loads_object
from .models import (
    CharacterCard,
    CharacterIdentityVersion,
    CharacterReferenceProfile,
    MediaAsset,
    MediaAssetVersion,
    Project,
    Storyboard,
    StoryboardShot,
    TaskEvent,
)


class AdoptionRevertService:
    """Version snapshots and reversibility for automatically adopted changes.

    Two automatic adoptions must stay reversible:

    1. Shot first-frame regeneration overwrites the same asset in place.
       ``snapshot_before_overwrite`` preserves the previous file and metadata
       before the overwrite; ``restore_asset_version`` copies a snapshot back
       and snapshots the current state first, so every step stays reversible.
    2. Turnaround lock creates a new canonical identity version.
       ``revert_identity_adoption`` restores a previous confirmed version as
       the canonical identity and re-syncs the reference profile and shot
       bindings without creating a new version number.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def snapshot_before_overwrite(
        self,
        *,
        db: Session,
        asset: MediaAsset,
        reason: str,
    ) -> MediaAssetVersion | None:
        """Preserve the current file and metadata before an adoption overwrite.

        Returns ``None`` when there is nothing to preserve (no completed file),
        so callers can snapshot unconditionally before writing.
        """
        if asset.status != "completed" or not asset.uri:
            return None
        source = Path(asset.uri)
        if not source.is_file():
            return None
        latest = db.scalar(
            select(MediaAssetVersion)
            .where(MediaAssetVersion.media_asset_id == asset.id)
            .order_by(MediaAssetVersion.version_no.desc())
            .limit(1)
        )
        version_no = 1 if latest is None else latest.version_no + 1
        snapshot_path = self._version_path(asset, version_no)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(snapshot_path))
        version = MediaAssetVersion(
            media_asset_id=asset.id,
            version_no=version_no,
            uri=str(snapshot_path),
            prompt=asset.prompt,
            meta_json=json_dumps(self._compact_meta(asset)),
            reason=(reason or "").strip(),
        )
        db.add(version)
        db.flush()
        return version

    def list_versions(self, *, db: Session, asset: MediaAsset) -> list[MediaAssetVersion]:
        return db.scalars(
            select(MediaAssetVersion)
            .where(MediaAssetVersion.media_asset_id == asset.id)
            .order_by(MediaAssetVersion.version_no.asc())
        ).all()

    def restore_asset_version(
        self,
        *,
        db: Session,
        asset: MediaAsset,
        version_no: int,
    ) -> MediaAssetVersion:
        """Restore a snapshot onto the canonical asset, keeping the restore reversible."""
        version = db.scalar(
            select(MediaAssetVersion).where(
                MediaAssetVersion.media_asset_id == asset.id,
                MediaAssetVersion.version_no == int(version_no),
            )
        )
        if version is None:
            raise LookupError(f"素材 {asset.id} 没有版本 {version_no}。")
        if not Path(version.uri).is_file():
            raise RuntimeError(f"版本 {version_no} 的快照文件缺失，无法恢复。")
        if not asset.uri:
            raise RuntimeError("素材没有可恢复的文件路径。")
        # Snapshot the current state first so the restore itself is reversible.
        self.snapshot_before_overwrite(db=db, asset=asset, reason="restore_snapshot")
        destination = Path(asset.uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(version.uri), str(destination))
        asset.uri = str(destination)
        asset.prompt = version.prompt
        meta = json_loads_object(version.meta_json)
        meta["restored_from_version"] = version.version_no
        asset.meta_json = json_dumps(meta)
        db.flush()
        return version

    def revert_identity_adoption(
        self,
        *,
        db: Session,
        project: Project,
        character: CharacterCard,
        target_version_id: int,
    ) -> CharacterIdentityVersion:
        """Restore a previous identity version as the canonical identity.

        Re-confirms the target version (no new version number), points the
        character reference profile back at its turnaround, re-locks the
        target turnaround, and rebinds every project shot that references the
        character to the target version.
        """
        target = db.get(CharacterIdentityVersion, int(target_version_id))
        if (
            target is None
            or target.character_card_id != character.id
            or target.project_id != project.id
        ):
            raise RuntimeError("目标身份版本不存在或不属于该角色。")
        identity = CharacterIdentityService(self.settings)
        current = identity.current_identity_version(db=db, character_id=character.id)
        if current is not None and current.id == target.id:
            return target
        identity.set_confirmed_version(db=db, character_id=character.id, version=target)

        profile = db.scalar(
            select(CharacterReferenceProfile).where(
                CharacterReferenceProfile.project_id == project.id,
                CharacterReferenceProfile.character_card_id == character.id,
            )
        )
        if profile is not None:
            profile.locked_turnaround_asset_id = target.turnaround_asset_id
            profile.status = "turnaround_locked"
            profile.reference_character_name = profile.reference_character_name or character.name

        for item in db.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == project.id,
                MediaAsset.asset_type == "character_turnaround",
                MediaAsset.deleted_at.is_(None),
            )
        ).all():
            meta = json_loads_object(item.meta_json)
            is_target = item.id == target.turnaround_asset_id
            meta["locked"] = is_target
            meta["candidate_status"] = "locked" if is_target else "candidate"
            meta["turnaround_status"] = "turnaround_locked" if is_target else "candidate_ready"
            item.meta_json = json_dumps(meta)

        shots = db.scalars(
            select(StoryboardShot)
            .join(Storyboard, StoryboardShot.storyboard_id == Storyboard.id)
            .where(Storyboard.project_id == project.id)
        ).all()
        for shot in shots:
            if self._shot_references_character(shot, character.id):
                identity.bind_shot_identity(
                    db=db,
                    shot=shot,
                    character_id=character.id,
                    identity_version_id=target.id,
                )

        db.add(
            TaskEvent(
                project_id=project.id,
                event_type="identity_adoption_reverted",
                message=f"角色 {character.name} 身份已回退到版本 {target.version_no}。",
                payload_json=json_dumps(
                    {
                        "character_card_id": character.id,
                        "target_version_id": target.id,
                        "version_no": target.version_no,
                        "turnaround_asset_id": target.turnaround_asset_id,
                    }
                ),
            )
        )
        db.flush()
        return target

    def _version_path(self, asset: MediaAsset, version_no: int) -> Path:
        if asset.uri:
            parent = Path(asset.uri).parent
            name = Path(asset.uri).name
        else:
            parent = self.settings.output_dir
            name = f"asset-{asset.id:06d}.bin"
        return parent / "versions" / f"v{version_no:03d}-{name}"

    @staticmethod
    def _compact_meta(asset: MediaAsset) -> dict[str, Any]:
        meta = json_loads_object(asset.meta_json)
        for key in ("submit_response", "result_response", "submit_summary", "result_summary", "provider_debug_uri"):
            meta.pop(key, None)
        return meta

    @staticmethod
    def _shot_references_character(shot: StoryboardShot, character_id: int) -> bool:
        for item in json_loads_list(shot.character_refs_json):
            if isinstance(item, dict):
                value = item.get("character_card_id") or item.get("id")
            else:
                value = item
            try:
                if int(value) == character_id:
                    return True
            except (TypeError, ValueError):
                continue
        for item in json_loads_list(shot.meta_json and (json_loads_object(shot.meta_json).get("identity_bindings") or [])):
            if isinstance(item, dict):
                try:
                    if int(item.get("character_card_id") or 0) == character_id:
                        return True
                except (TypeError, ValueError):
                    continue
        return False
