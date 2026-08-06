from __future__ import annotations

import base64
import hashlib
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .capabilities import ImageGenerationRequest, ImageGenerationResult
from .adoption_revert_service import AdoptionRevertService
from .character_identity_service import CharacterIdentityService
from .config import Settings
from .generation_evidence_service import GenerationEvidence, record_generation_evidence
from .image_capability import ImageCapability, build_image_capability
from .json_utils import json_dumps, json_loads_list, json_loads_object
from .media_asset_recycle import media_asset_file_path
from .models import CharacterCard, CharacterReferenceProfile, MediaAsset, Project, ReferenceImageAsset, Storyboard, StoryboardShot, TaskEvent
from .video_render_service import VideoRenderService
from .visual_style_prompt import build_character_visual_prompt, build_visual_generation_prompt, project_visual_style_summary


class CharacterReferenceProfileService:
    def ensure_profiles(self, db: Session, project: Project) -> list[CharacterReferenceProfile]:
        cards = [
            item
            for item in db.scalars(
                select(CharacterCard)
                .where(CharacterCard.project_id == project.id, CharacterCard.deleted_at.is_(None))
                .order_by(CharacterCard.id.asc())
            ).all()
        ]
        existing = {
            item.character_card_id: item
            for item in db.scalars(
                select(CharacterReferenceProfile).where(CharacterReferenceProfile.project_id == project.id)
            ).all()
        }
        profiles: list[CharacterReferenceProfile] = []
        for card in cards:
            profile = existing.get(card.id)
            if profile is None:
                profile = CharacterReferenceProfile(project_id=project.id, character_card_id=card.id)
                db.add(profile)
            self._sync_profile_from_existing_assets(db, profile=profile, character=card, project=project)
            profiles.append(profile)
        return profiles

    def apply_turnaround_lock(self, db: Session, project: Project, asset: MediaAsset, locked: bool) -> CharacterReferenceProfile | None:
        if asset.asset_type != "character_turnaround":
            return None
        meta = json_loads_object(asset.meta_json)
        character_id = self._safe_int(meta.get("character_card_id"))
        if character_id is None:
            return None
        character = db.scalar(
            select(CharacterCard).where(
                CharacterCard.id == character_id,
                CharacterCard.project_id == project.id,
                CharacterCard.deleted_at.is_(None),
            )
        )
        if character is None:
            return None
        profile = self._profile_for_character(db, project=project, character=character)
        if meta.get("character_name"):
            profile.reference_character_name = str(meta.get("character_name") or "").strip()
        elif not profile.reference_character_name:
            profile.reference_character_name = character.name
        if locked:
            profile.locked_turnaround_asset_id = asset.id
            profile.status = "turnaround_locked"
        else:
            profile.locked_turnaround_asset_id = None if profile.locked_turnaround_asset_id == asset.id else profile.locked_turnaround_asset_id
            if profile.locked_turnaround_asset_id is None:
                profile.status = "unmapped"
            self._sync_profile_from_existing_assets(db, profile=profile, character=character, project=project, ignored_locked_asset_id=asset.id)
        return profile

    def locked_turnaround_for_shot(self, db: Session, project: Project, shot: StoryboardShot, character_ids: list[int]) -> list[dict[str, Any]]:
        if not character_ids:
            return []
        profiles = {
            profile.character_card_id: profile
            for profile in self.ensure_profiles(db, project)
            if profile.character_card_id in character_ids
        }
        result: list[dict[str, Any]] = []
        for character_id in character_ids:
            profile = profiles.get(character_id)
            if profile is None or profile.status != "turnaround_locked" or profile.locked_turnaround_asset_id is None:
                continue
            asset = db.get(MediaAsset, profile.locked_turnaround_asset_id)
            if asset is None or asset.project_id != project.id or asset.asset_type != "character_turnaround" or asset.status != "completed":
                continue
            result.append(
                {
                    "asset_id": asset.id,
                    "character_card_id": character_id,
                    "character_name": profile.reference_character_name,
                    "uri": asset.uri,
                    "status": asset.status,
                }
            )
        return result

    def _profile_for_character(self, db: Session, *, project: Project, character: CharacterCard) -> CharacterReferenceProfile:
        profile = db.scalar(
            select(CharacterReferenceProfile).where(
                CharacterReferenceProfile.project_id == project.id,
                CharacterReferenceProfile.character_card_id == character.id,
            )
        )
        if profile is None:
            profile = CharacterReferenceProfile(project_id=project.id, character_card_id=character.id)
            db.add(profile)
            db.flush()
        return profile

    def _sync_profile_from_existing_assets(
        self,
        db: Session,
        *,
        profile: CharacterReferenceProfile,
        character: CharacterCard,
        project: Project,
        ignored_locked_asset_id: int | None = None,
    ) -> None:
        approved_assets = db.scalars(
            select(ReferenceImageAsset).where(
                ReferenceImageAsset.project_id == project.id,
                ReferenceImageAsset.status == "approved",
                ReferenceImageAsset.mapped_character_name == character.name,
            )
        ).all()
        turnarounds = db.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == project.id,
                MediaAsset.asset_type == "character_turnaround",
                MediaAsset.status == "completed",
                MediaAsset.deleted_at.is_(None),
            )
        ).all()
        character_turnarounds: list[MediaAsset] = []
        locked_asset: MediaAsset | None = None
        for asset in turnarounds:
            meta = json_loads_object(asset.meta_json)
            if self._safe_int(meta.get("character_card_id")) != character.id:
                continue
            character_turnarounds.append(asset)
            if asset.id != ignored_locked_asset_id and meta.get("locked") is True:
                locked_asset = asset
        profile.visual_reference_asset_ids = [asset.id for asset in approved_assets]
        profile.reference_character_name = profile.reference_character_name or character.name
        if locked_asset is not None:
            meta = json_loads_object(locked_asset.meta_json)
            profile.locked_turnaround_asset_id = locked_asset.id
            profile.reference_character_name = str(meta.get("character_name") or profile.reference_character_name or character.name).strip()
            profile.status = "turnaround_locked"
            return
        if character_turnarounds:
            profile.status = "turnaround_candidate_ready"
            profile.locked_turnaround_asset_id = None
            return
        if approved_assets:
            profile.status = "reference_assets_ready"
            profile.locked_turnaround_asset_id = None
            return
        profile.status = "mapped" if profile.reference_character_name and profile.reference_character_name != character.name else "unmapped"
        profile.locked_turnaround_asset_id = None

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class VisualAssetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.character_reference_profiles = CharacterReferenceProfileService()
        self._adoption_revert = AdoptionRevertService(settings)
        self._capability: ImageCapability | None = None

    def _record_attempt(
        self,
        db: Session,
        *,
        stage: str,
        status: str,
        result: ImageGenerationResult | None = None,
        project: Project | None = None,
        storyboard: Storyboard | None = None,
        shot: StoryboardShot | None = None,
        character: CharacterCard | None = None,
        prompt: str = "",
        input_asset_versions: dict[str, Any] | None = None,
        adopted_asset_id: int | None = None,
        quality_outcome: str = "",
        error: Exception | None = None,
    ) -> None:
        # 证据记录是尽力而为的遥测：记录失败绝不能掩盖生成错误或破坏事务，
        # 因此这里吞掉记录过程中的异常，主路径（成功/失败）照常进行。
        try:
            try:
                declaration = self._image_capability().declaration()
                provider = result.provider if result is not None else declaration.provider
                model = result.model if result is not None else declaration.model
            except Exception:
                provider, model = "", ""
            record_generation_evidence(
                db,
                evidence=GenerationEvidence(
                    stage=stage,
                    status=status,
                    provider=provider,
                    model=model,
                    project_id=project.id if project is not None else None,
                    storyboard_id=storyboard.id if storyboard is not None else None,
                    shot_id=shot.id if shot is not None else None,
                    adopted_asset_id=adopted_asset_id,
                    rendered_prompt=prompt,
                    parsed_output=(
                        {
                            "submit_summary": result.submit_summary,
                            "result_summary": result.result_summary,
                        }
                        if result is not None
                        else None
                    ),
                    parameters=result.parameters if result is not None else None,
                    input_asset_versions=input_asset_versions,
                    provider_ref=result.provider_ref if result is not None else "",
                    quality_outcome=quality_outcome,
                    error_category=type(error).__name__ if error is not None else "",
                    error_message=str(error) if error is not None else "",
                ),
            )
        except Exception:
            pass

    def _image_capability(self) -> ImageCapability:
        if self._capability is None:
            self._capability = build_image_capability(self.settings)
        return self._capability

    def generate_shot_first_frame(
        self,
        *,
        db: Session,
        project: Project,
        storyboard: Storyboard,
        shot: StoryboardShot,
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> MediaAsset:
        existing_assets = db.query(MediaAsset).filter(
            MediaAsset.project_id == project.id,
            MediaAsset.storyboard_id == storyboard.id,
            MediaAsset.shot_id == shot.id,
            MediaAsset.asset_type == "shot_first_frame",
            MediaAsset.deleted_at.is_(None),
        ).all()
        for asset in existing_assets:
            meta = json_loads_object(asset.meta_json)
            if asset.status == "completed" and meta.get("locked") is True:
                return asset

        previous_last_frame = self._previous_last_frame_asset(db=db, project=project, storyboard=storyboard, shot=shot)
        if previous_last_frame is not None:
            asset = next((item for item in existing_assets if item.asset_type == "shot_first_frame"), None)
            if asset is None:
                asset = MediaAsset(
                    project_id=project.id,
                    storyboard=storyboard,
                    shot=shot,
                    asset_type="shot_first_frame",
                    uri=previous_last_frame.uri,
                    prompt=previous_last_frame.prompt,
                    status="completed",
                    meta_json=json_dumps({}),
                )
                db.add(asset)
            asset.uri = previous_last_frame.uri
            asset.prompt = previous_last_frame.prompt
            asset.status = "completed"
            existing_meta = self._compact_asset_meta(json_loads_object(asset.meta_json))
            asset.meta_json = json_dumps(
                {
                    **existing_meta,
                    "shot_id": shot.id,
                    "shot_no": shot.shot_no,
                    "locked": False,
                    "source": "previous_last_frame",
                    "source_last_frame_asset_id": previous_last_frame.id,
                    "depends_on_shot_id": previous_last_frame.shot_id,
                    "depends_on_shot_no": json_loads_object(previous_last_frame.meta_json).get("shot_no"),
                    "mime_type": previous_last_frame.meta_json and (json_loads_object(previous_last_frame.meta_json).get("mime_type") or "image/png"),
                    "context_pack_id": context_pack_inputs.get("context_pack_id") if isinstance(context_pack_inputs, dict) else None,
                    "context_pack_version": context_pack_inputs.get("context_pack_version") if isinstance(context_pack_inputs, dict) else None,
                    "context_pack_reference_mode": context_pack_inputs.get("reference_mode") if isinstance(context_pack_inputs, dict) else None,
                }
            )
            db.add(
                TaskEvent(
                    project_id=project.id,
                    storyboard=storyboard,
                    event_type="visual_asset_shot_first_frame_completed",
                    message=f"镜头 {shot.shot_no} 首帧已继承上一镜头尾帧。",
                    payload_json=json_dumps(
                        {
                            "asset_type": "shot_first_frame",
                            "shot_id": shot.id,
                            "shot_no": shot.shot_no,
                            "source": "previous_last_frame",
                            "source_last_frame_asset_id": previous_last_frame.id,
                            "uri": previous_last_frame.uri,
                        }
                    ),
                )
            )
            db.commit()
            db.refresh(asset)
            return asset

        locked_references = self.locked_turnaround_references(db=db, project=project, shot=shot)
        prompt = build_visual_generation_prompt(project=project, shot=shot, include_narration=False, max_length=1800)
        if locked_references:
            prompt = "\n".join(
                [
                    prompt,
                    "",
                    "锁定角色视觉母版（必须强继承，不能只作为风格提示）：",
                    *[
                        f"- {item['character_name']}：使用素材 #{item['asset_id']}，保持脸型、发型、服装轮廓、配色和标志物一致。"
                        for item in locked_references
                    ],
                ]
            )
        try:
            result = self._image_capability().generate(
                ImageGenerationRequest(
                    prompt=prompt,
                    reference_images=tuple(str(item["uri"]) for item in locked_references),
                )
            )
        except Exception as exc:
            self._record_attempt(
                db,
                stage="image_first_frame",
                status="failed",
                project=project,
                storyboard=storyboard,
                shot=shot,
                prompt=prompt,
                input_asset_versions={"locked_references": locked_references},
                error=exc,
            )
            raise

        asset = next((item for item in existing_assets if item.asset_type == "shot_first_frame"), None)
        if asset is None:
            asset = MediaAsset(
                project_id=project.id,
                storyboard=storyboard,
                shot=shot,
                asset_type="shot_first_frame",
                uri="",
                prompt=prompt,
                status="processing",
                meta_json=json_dumps({}),
            )
            db.add(asset)
            db.flush()

        # Auto-adoption reversibility: snapshot the previous file and metadata
        # before overwriting a completed first frame. A snapshot failure aborts
        # the write instead of silently losing the previous version.
        self._adoption_revert.snapshot_before_overwrite(
            db=db, asset=asset, reason="shot_first_frame_regeneration"
        )

        image_path = media_asset_file_path(asset, settings=self.settings, file_name=f"shot-{shot.shot_no:03d}-first-frame-v001.png")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_image_payload(payload={"kind": result.kind, "value": result.value}, path=image_path)
        provider_debug_path = self._provider_debug_path(image_path)
        self._write_provider_debug_sidecar(
            path=provider_debug_path,
            payload={
                "provider": result.provider,
                "asset_type": "shot_first_frame",
                "shot_id": shot.id,
                "shot_no": shot.shot_no,
                "task_id": result.provider_ref,
                "submit_summary": result.submit_summary,
                "result_summary": result.result_summary,
            },
        )

        asset.uri = str(image_path)
        asset.prompt = prompt
        asset.status = "completed"
        self._record_attempt(
            db,
            stage="image_first_frame",
            status="succeeded",
            result=result,
            project=project,
            storyboard=storyboard,
            shot=shot,
            prompt=prompt,
            input_asset_versions={"locked_references": locked_references},
            adopted_asset_id=asset.id,
            quality_outcome="accepted",
        )
        existing_meta = self._compact_asset_meta(json_loads_object(asset.meta_json))
        asset.meta_json = json_dumps(
            {
                **existing_meta,
                "shot_id": shot.id,
                "shot_no": shot.shot_no,
                "locked": False,
                "provider": result.provider,
                "model": result.model,
                "req_key": (result.parameters or {}).get("req_key") or "",
                "jimeng_task_id": result.provider_ref,
                "provider_debug_uri": str(provider_debug_path),
                "submit_summary": result.submit_summary,
                "result_summary": result.result_summary,
                "image_source": result.kind,
                "width": (result.parameters or {}).get("width") or 1024,
                "height": (result.parameters or {}).get("height") or 1024,
                "mime_type": "image/png",
                "visual_style": project_visual_style_summary(project),
                "locked_turnaround_references": locked_references,
                "locked_turnaround_asset_ids": [item["asset_id"] for item in locked_references],
                "context_pack_id": context_pack_inputs.get("context_pack_id") if isinstance(context_pack_inputs, dict) else None,
                "context_pack_version": context_pack_inputs.get("context_pack_version") if isinstance(context_pack_inputs, dict) else None,
                "context_pack_reference_mode": context_pack_inputs.get("reference_mode") if isinstance(context_pack_inputs, dict) else None,
            }
        )
        db.add(
            TaskEvent(
                project_id=project.id,
                storyboard=storyboard,
                event_type="visual_asset_shot_first_frame_completed",
                message=f"镜头 {shot.shot_no} 首帧生成完成。",
                payload_json=json_dumps({"asset_type": "shot_first_frame", "shot_id": shot.id, "shot_no": shot.shot_no, "uri": str(image_path)}),
            )
        )
        db.commit()
        db.refresh(asset)
        return asset

    def _previous_last_frame_asset(
        self,
        *,
        db: Session,
        project: Project,
        storyboard: Storyboard,
        shot: StoryboardShot,
    ) -> MediaAsset | None:
        meta = json_loads_object(shot.meta_json)
        continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
        if str(continuity.get("first_frame_source") or "").strip() != "previous_last_frame":
            return None
        try:
            dependency_shot_no = int(continuity.get("depends_on_shot_no"))
        except (TypeError, ValueError):
            dependency_shot_no = shot.shot_no - 1
        dependency_shot = db.scalar(
            select(StoryboardShot).where(
                StoryboardShot.storyboard_id == storyboard.id,
                StoryboardShot.shot_no == max(dependency_shot_no, 1),
            )
        )
        if dependency_shot is None:
            raise RuntimeError(f"镜头 {shot.shot_no} 依赖镜头 {max(dependency_shot_no, 1)} 不存在，无法继承尾帧。")
        asset = db.scalar(
            select(MediaAsset).where(
                MediaAsset.project_id == project.id,
                MediaAsset.storyboard_id == storyboard.id,
                MediaAsset.shot_id == dependency_shot.id,
                MediaAsset.asset_type == "shot_last_frame",
                MediaAsset.status == "completed",
            )
        )
        if asset is None:
            raise RuntimeError(f"镜头 {shot.shot_no} 依赖镜头 {dependency_shot.shot_no} 缺少已完成尾帧。")
        return asset

    def locked_turnaround_references(
        self,
        *,
        db: Session,
        project: Project,
        shot: StoryboardShot,
    ) -> list[dict[str, Any]]:
        character_ids = self._shot_character_ids(shot)
        if not character_ids:
            names = self._shot_character_names(shot)
            if names:
                cards = db.scalars(
                    select(CharacterCard).where(
                        CharacterCard.project_id == project.id,
                        CharacterCard.deleted_at.is_(None),
                        CharacterCard.name.in_(names),
                    )
                ).all()
                character_ids = [card.id for card in cards]
        if not character_ids:
            return []
        return self.character_reference_profiles.locked_turnaround_for_shot(
            db=db,
            project=project,
            shot=shot,
            character_ids=character_ids,
        )

    def apply_turnaround_lock(
        self,
        *,
        db: Session,
        project: Project,
        asset: MediaAsset,
        locked: bool,
    ) -> None:
        if asset.asset_type != "character_turnaround":
            return
        meta = json_loads_object(asset.meta_json)
        character_id = self._safe_int(meta.get("character_card_id"))
        if character_id is None:
            meta["locked"] = bool(locked)
            meta["candidate_status"] = "locked" if locked else "candidate"
            meta["turnaround_status"] = "turnaround_locked" if locked else "candidate_ready"
            asset.meta_json = json_dumps(meta)
            return

        if locked:
            sibling_assets = db.query(MediaAsset).filter(
                MediaAsset.project_id == project.id,
                MediaAsset.asset_type == "character_turnaround",
                MediaAsset.deleted_at.is_(None),
            ).all()
            for sibling in sibling_assets:
                if sibling.id == asset.id:
                    continue
                sibling_meta = json_loads_object(sibling.meta_json)
                if self._safe_int(sibling_meta.get("character_card_id")) != character_id:
                    continue
                sibling_meta["locked"] = False
                sibling_meta["candidate_status"] = "candidate"
                sibling_meta["turnaround_status"] = "candidate_ready"
                sibling.meta_json = json_dumps(sibling_meta)

        meta["locked"] = bool(locked)
        meta["candidate_status"] = "locked" if locked else "candidate"
        meta["turnaround_status"] = "turnaround_locked" if locked else "candidate_ready"
        asset.meta_json = json_dumps(meta)
        self.character_reference_profiles.apply_turnaround_lock(db, project, asset, locked)
        if locked and asset.status == "completed":
            character = db.scalar(
                select(CharacterCard).where(
                    CharacterCard.id == character_id,
                    CharacterCard.project_id == project.id,
                    CharacterCard.deleted_at.is_(None),
                )
            )
            if character is not None:
                CharacterIdentityService(self.settings).approve_turnaround(
                    db=db, project=project, character=character, asset=asset
                )

    def _shot_character_ids(self, shot: StoryboardShot) -> list[int]:
        ids: list[int] = []
        for item in json_loads_list(shot.character_refs_json):
            if isinstance(item, dict):
                value = item.get("character_card_id") or item.get("id")
            else:
                value = item
            character_id = self._safe_int(value)
            if character_id is not None and character_id not in ids:
                ids.append(character_id)
        return ids

    def _shot_character_names(self, shot: StoryboardShot) -> list[str]:
        names: list[str] = []
        for item in json_loads_list(shot.character_refs_json):
            if isinstance(item, dict):
                value = item.get("name") or item.get("character_name") or item.get("value")
            else:
                value = item
            name = str(value or "").strip()
            if name and name not in names and self._safe_int(name) is None:
                names.append(name)
        return names

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _next_turnaround_version(self, db: Session, project: Project, character_id: int) -> int:
        versions: list[int] = []
        assets = db.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == project.id,
                MediaAsset.asset_type == "character_turnaround",
            )
        ).all()
        for asset in assets:
            meta = json_loads_object(asset.meta_json)
            if self._safe_int(meta.get("character_card_id")) != character_id:
                continue
            version = self._safe_int(meta.get("candidate_version") or meta.get("version"))
            if version is not None and version > 0:
                versions.append(version)
        return (max(versions) if versions else 0) + 1

    def generate_character_turnaround(
        self,
        *,
        db: Session,
        project: Project,
        character: CharacterCard,
        chapter_no: int | None = None,
        prompt_note: str = "",
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> MediaAsset:
        next_version = self._next_turnaround_version(db, project, character.id)
        prompt = self._build_turnaround_prompt(project=project, character=character, prompt_note=prompt_note)
        reference_assets = self._approved_character_reference_assets(db, project=project, character=character)
        reference_images = [asset.remote_url for asset in reference_assets if asset.remote_url]
        try:
            result = self._image_capability().generate(
                ImageGenerationRequest(
                    prompt=prompt,
                    reference_images=tuple(reference_images),
                )
            )
        except Exception as exc:
            self._record_attempt(
                db,
                stage="image_turnaround",
                status="failed",
                project=project,
                character=character,
                prompt=prompt,
                input_asset_versions={"reference_asset_ids": [asset.id for asset in reference_assets]},
                error=exc,
            )
            raise

        asset = MediaAsset(
            project_id=project.id,
            storyboard_id=None,
            shot_id=None,
            asset_type="character_turnaround",
            uri="",
            prompt=prompt,
            status="processing",
            meta_json=json_dumps({}),
        )
        db.add(asset)
        db.flush()

        image_path = media_asset_file_path(asset, settings=self.settings, file_name=f"turnaround-v{next_version:03d}.png")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_image_payload(payload={"kind": result.kind, "value": result.value}, path=image_path)
        provider_debug_path = self._provider_debug_path(image_path)
        self._write_provider_debug_sidecar(
            path=provider_debug_path,
            payload={
                "provider": result.provider,
                "asset_type": "character_turnaround",
                "character_card_id": character.id,
                "character_name": character.name,
                "task_id": result.provider_ref,
                "submit_summary": result.submit_summary,
                "result_summary": result.result_summary,
            },
        )
        asset.uri = str(image_path)
        asset.status = "completed"
        self._record_attempt(
            db,
            stage="image_turnaround",
            status="succeeded",
            result=result,
            project=project,
            character=character,
            prompt=prompt,
            input_asset_versions={"reference_asset_ids": [asset.id for asset in reference_assets]},
            adopted_asset_id=asset.id,
            quality_outcome="candidate_created",
        )
        asset.meta_json = json_dumps(
            {
                "character_card_id": character.id,
                "character_name": character.name,
                "version": next_version,
                "candidate_version": next_version,
                "candidate_status": "candidate",
                "locked": False,
                "views": ["front", "side", "back"],
                "visual_reference_asset_ids": [asset.id for asset in reference_assets],
                "visual_reference_image_count": len(reference_images),
                "provider": result.provider,
                "model": result.model,
                "req_key": (result.parameters or {}).get("req_key") or "",
                "jimeng_task_id": result.provider_ref,
                "provider_debug_uri": str(provider_debug_path),
                "submit_summary": result.submit_summary,
                "result_summary": result.result_summary,
                "image_source": result.kind,
                "width": (result.parameters or {}).get("width") or 1024,
                "height": (result.parameters or {}).get("height") or 1024,
                "mime_type": "image/png",
                "visual_style": project_visual_style_summary(project),
                "context_pack_id": context_pack_inputs.get("context_pack_id") if isinstance(context_pack_inputs, dict) else None,
                "context_pack_version": context_pack_inputs.get("context_pack_version") if isinstance(context_pack_inputs, dict) else None,
                "context_pack_reference_mode": context_pack_inputs.get("reference_mode") if isinstance(context_pack_inputs, dict) else None,
            }
        )
        db.add(
            TaskEvent(
                project_id=project.id,
                event_type="visual_asset_character_turnaround_completed",
                message=f"{character.name} 三视图生成完成。",
                payload_json=json_dumps({"asset_type": asset.asset_type, "uri": str(image_path), "character_card_id": character.id}),
            )
        )
        db.commit()
        db.refresh(asset)
        return asset

    def _approved_character_reference_assets(
        self,
        db: Session,
        *,
        project: Project,
        character: CharacterCard,
    ) -> list[ReferenceImageAsset]:
        return db.scalars(
            select(ReferenceImageAsset).where(
                ReferenceImageAsset.project_id == project.id,
                ReferenceImageAsset.status == "approved",
                ReferenceImageAsset.asset_kind == "character_reference",
                ReferenceImageAsset.mapped_character_name == character.name,
            )
        ).all()


    def _download_file(self, *, url: str, path: Path) -> None:
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                content = response.read()
        except Exception as exc:
            raise RuntimeError(f"下载即梦图片失败：{exc}") from exc
        if not content:
            raise RuntimeError("下载即梦图片失败：返回空文件。")
        path.write_bytes(content)

    def _save_image_payload(self, *, payload: dict[str, str], path: Path) -> None:
        if payload["kind"] == "url":
            self._download_file(url=payload["value"], path=path)
            return
        if payload["kind"] == "base64":
            path.write_bytes(base64.b64decode(payload["value"]))
            return
        raise RuntimeError(f"不支持的图片返回类型：{payload['kind']}")

    def _provider_debug_path(self, asset_path: Path) -> Path:
        return asset_path.with_name(f"{asset_path.name}.provider.json")

    def _write_provider_debug_sidecar(self, *, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json_dumps(payload), encoding="utf-8")

    def _compact_asset_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        drop_keys = {"submit_response", "result_response", "submit_summary", "result_summary", "provider_debug_uri"}
        return {key: value for key, value in meta.items() if key not in drop_keys}


    def _visual_output_dir(self, *, project: Project, chapter_no: int | None, character: CharacterCard) -> Path:
        path_helper = VideoRenderService(self.settings)
        project_dir = f"{project.id:04d}-{path_helper._path_slug(project.title)}"
        chapter_dir = f"chapter-{chapter_no:03d}" if chapter_no is not None else "characters"
        character_dir = f"{character.id:04d}-{path_helper._path_slug(character.name)}"
        return self.settings.output_dir / "projects" / project_dir / "chapters" / chapter_dir / "visual_assets" / "characters" / character_dir

    def _shot_visual_output_dir(self, *, project: Project, storyboard: Storyboard, shot: StoryboardShot) -> Path:
        path_helper = VideoRenderService(self.settings)
        project_dir = f"{project.id:04d}-{path_helper._path_slug(project.title)}"
        storyboard_dir = f"{storyboard.id:04d}-{path_helper._path_slug(storyboard.title)}"
        return self.settings.output_dir / "projects" / project_dir / "storyboards" / storyboard_dir / "shots" / f"shot-{shot.shot_no:03d}" / "first_frame"

    def _build_turnaround_prompt(self, *, project: Project, character: CharacterCard, prompt_note: str) -> str:
        differentiation = self._character_differentiation_anchor(character)
        details = [
            f"角色名：{character.name}",
            f"年龄：{character.age}",
            f"性别：{character.gender}",
            f"角色定位：{character.story_role}",
            f"性格：{character.personality}",
            f"背景：{character.background}",
            f"角色差异锚点：{differentiation}",
            "请把角色定位、性格和背景转化为可见外观，而不是只画普通美型人物。",
        ]
        return build_character_visual_prompt(project=project, character_details=details, prompt_note=prompt_note)

    def _character_differentiation_anchor(self, character: CharacterCard) -> str:
        seed = f"{character.id}:{character.name}:{character.story_role}:{character.personality}:{character.background}"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        palettes = [
            "天青、白、少量暖橙点缀",
            "靛蓝、灰白、银色细节",
            "墨绿、米白、深棕皮革细节",
            "酒红、黑、冷灰金属细节",
            "浅紫、雾粉、珍珠白细节",
            "暖黄、藏青、浅棕布料细节",
        ]
        silhouettes = [
            "修长利落，窄肩长外套",
            "轻盈少年感，短外套和清晰腰线",
            "沉稳成熟，长衣摆和层叠内搭",
            "行动派轮廓，短靴、束口袖和功能性配件",
            "温柔文艺轮廓，柔软针织或衬衫层次",
            "冷静疏离轮廓，直线剪裁和低饱和配色",
        ]
        motifs = [
            "透明伞、雨滴或晴雨交界的细节",
            "旧书、笔记本或书签",
            "星空、列车票或远行符号",
            "耳机、相机或小型机械物件",
            "发夹、丝带或细小首饰",
            "校服改造、徽章或围巾",
        ]
        return "；".join(
            [
                f"专属配色：{palettes[digest[0] % len(palettes)]}",
                f"轮廓语言：{silhouettes[digest[1] % len(silhouettes)]}",
                f"标志物：{motifs[digest[2] % len(motifs)]}",
            ]
        )
