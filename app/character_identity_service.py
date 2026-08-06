from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .json_utils import json_dumps, json_loads_list, json_loads_object
from .models import (
    CharacterAppearanceVersion,
    CharacterCard,
    CharacterIdentityVersion,
    MediaAsset,
    Project,
    StoryboardShot,
)


class CharacterIdentityService:
    """规范身份版本化：确认三视图 → 不可变身份版本；外观状态独立版本化；镜头绑定规范身份。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def approve_turnaround(
        self,
        *,
        db: Session,
        project: Project,
        character: CharacterCard,
        asset: MediaAsset,
        user_id: int | None = None,
    ) -> CharacterIdentityVersion:
        if asset.asset_type != "character_turnaround" or asset.status != "completed":
            raise RuntimeError("只有已完成的角色三视图才能成为规范身份版本。")
        if asset.project_id != project.id:
            raise RuntimeError("三视图不属于当前项目。")
        meta = json_loads_object(asset.meta_json)
        if self._safe_int(meta.get("character_card_id")) != character.id:
            raise RuntimeError("三视图与角色不匹配。")
        latest = db.scalar(
            select(CharacterIdentityVersion)
            .where(CharacterIdentityVersion.character_card_id == character.id)
            .order_by(CharacterIdentityVersion.version_no.desc())
            .limit(1)
        )
        if latest is not None and latest.turnaround_asset_id == asset.id:
            return latest
        version_no = 1 if latest is None else latest.version_no + 1
        self._supersede(db=db, character_id=character.id)
        version = CharacterIdentityVersion(
            character_card_id=character.id,
            project_id=project.id,
            version_no=version_no,
            turnaround_asset_id=asset.id,
            checksum=self._asset_checksum(asset),
            status="confirmed",
            reason="creator_approval",
            created_by_user_id=user_id,
        )
        db.add(version)
        db.flush()
        return version

    def current_identity_version(self, *, db: Session, character_id: int) -> CharacterIdentityVersion | None:
        return db.scalar(
            select(CharacterIdentityVersion)
            .where(
                CharacterIdentityVersion.character_card_id == character_id,
                CharacterIdentityVersion.status == "confirmed",
            )
            .order_by(CharacterIdentityVersion.version_no.desc())
            .limit(1)
        )

    def bind_shot_identity(
        self,
        *,
        db: Session,
        shot: StoryboardShot,
        character_id: int,
        identity_version_id: int,
    ) -> None:
        meta = json_loads_object(shot.meta_json)
        bindings = meta.get("identity_bindings")
        if not isinstance(bindings, list):
            bindings = []
            meta["identity_bindings"] = bindings
        for index, item in enumerate(bindings):
            if isinstance(item, dict) and self._safe_int(item.get("character_card_id")) == character_id:
                bindings[index] = {
                    "character_card_id": character_id,
                    "identity_version_id": identity_version_id,
                }
                shot.meta_json = json_dumps(meta)
                return
        bindings.append(
            {
                "character_card_id": character_id,
                "identity_version_id": identity_version_id,
            }
        )
        shot.meta_json = json_dumps(meta)

    def shot_identity_bindings(self, *, shot: StoryboardShot) -> list[dict[str, Any]]:
        meta = json_loads_object(shot.meta_json)
        bindings = meta.get("identity_bindings") if isinstance(meta.get("identity_bindings"), list) else []
        return [item for item in bindings if isinstance(item, dict)]

    def bind_all_shot_characters(
        self,
        *,
        db: Session,
        project: Project,
        shot: StoryboardShot,
    ) -> list[dict[str, Any]]:
        """为镜头引用且已有规范身份版本的角色写入身份绑定；返回绑定列表。"""
        bound: list[dict[str, Any]] = []
        for character_id in self._shot_character_ids(shot):
            version = self.current_identity_version(db=db, character_id=character_id)
            if version is None:
                continue
            self.bind_shot_identity(
                db=db,
                shot=shot,
                character_id=character_id,
                identity_version_id=version.id,
            )
            bound.append(
                {
                    "character_card_id": character_id,
                    "identity_version_id": version.id,
                    "version_no": version.version_no,
                }
            )
        return bound

    def create_appearance_version(
        self,
        *,
        db: Session,
        identity_version_id: int,
        costume_name: str = "",
        costume_details: str = "",
        hairstyle: str = "",
        props: str = "",
        user_id: int | None = None,
    ) -> CharacterAppearanceVersion:
        latest = db.scalar(
            select(CharacterAppearanceVersion)
            .where(CharacterAppearanceVersion.identity_version_id == identity_version_id)
            .order_by(CharacterAppearanceVersion.version_no.desc())
            .limit(1)
        )
        version_no = 1 if latest is None else latest.version_no + 1
        if latest is not None:
            latest.status = "superseded"
        version = CharacterAppearanceVersion(
            identity_version_id=identity_version_id,
            version_no=version_no,
            costume_name=costume_name,
            costume_details=costume_details,
            hairstyle=hairstyle,
            props=props,
            status="active",
            created_by_user_id=user_id,
        )
        db.add(version)
        db.flush()
        return version

    def current_appearance_version(
        self,
        *,
        db: Session,
        identity_version_id: int,
    ) -> CharacterAppearanceVersion | None:
        return db.scalar(
            select(CharacterAppearanceVersion)
            .where(
                CharacterAppearanceVersion.identity_version_id == identity_version_id,
                CharacterAppearanceVersion.status == "active",
            )
            .order_by(CharacterAppearanceVersion.version_no.desc())
            .limit(1)
        )

    def set_confirmed_version(
        self,
        *,
        db: Session,
        character_id: int,
        version: CharacterIdentityVersion,
    ) -> None:
        """Supersede all confirmed versions and confirm the target version.

        Revert path: restores a previous identity version as the canonical
        version without creating a new one, so the version chain keeps its
        original numbers and provenance.
        """
        if version.character_card_id != character_id:
            raise RuntimeError("目标身份版本不属于该角色。")
        self._supersede(db=db, character_id=character_id)
        version.status = "confirmed"
        db.flush()

    def _supersede(self, *, db: Session, character_id: int) -> None:
        rows = db.scalars(
            select(CharacterIdentityVersion).where(
                CharacterIdentityVersion.character_card_id == character_id,
                CharacterIdentityVersion.status == "confirmed",
            )
        ).all()
        for row in rows:
            row.status = "superseded"

    def _asset_checksum(self, asset: MediaAsset) -> str:
        source = Path(asset.uri or "")
        if source.is_file():
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        return hashlib.sha256(str(asset.uri or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _shot_character_ids(shot: StoryboardShot) -> list[int]:
        ids: list[int] = []
        for item in json_loads_list(shot.character_refs_json):
            if isinstance(item, dict):
                value = item.get("character_card_id") or item.get("id")
            else:
                value = item
            try:
                character_id = int(value)
            except (TypeError, ValueError):
                continue
            if character_id not in ids:
                ids.append(character_id)
        return ids

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None