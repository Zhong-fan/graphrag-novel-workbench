"""Video preflight gate: blocking checks evaluated before spending tokens.

Kept as its own module because it composes domain services (visual assets,
character identity) that render services also use; a separate module avoids
circular imports between quality and render layers.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .character_identity_service import CharacterIdentityService
from .config import Settings
from .json_utils import json_loads_list, json_loads_object
from .models import MediaAsset, Project, Storyboard, StoryboardShot
from .visual_asset_service import VisualAssetService


def continuity_dependency_shot_no(continuity: dict, shot: StoryboardShot) -> int:
    value = continuity.get("depends_on_shot_no")
    try:
        dependency = int(value)
    except (TypeError, ValueError):
        dependency = shot.shot_no - 1
    return max(dependency, 1)


def video_quality_gate_failures(db: Session, *, settings: Settings, project: Project, storyboard: Storyboard) -> list[str]:
    """提交视频生成前的阻断性门禁：锁定三视图、延续尾帧、规范身份绑定、首帧就绪。

    每个失败都是可操作的中文原因；延续镜头必须带 identity_bindings，尾帧只能作
    连续性状态，不能替代规范身份。
    """
    failures: list[str] = []
    visual_service = VisualAssetService(settings)
    for shot in sorted(storyboard.shots, key=lambda item: item.shot_no):
        refs = visual_service.locked_turnaround_references(db=db, project=project, shot=shot)
        character_refs = json_loads_list(shot.character_refs_json)
        if character_refs and not refs:
            failures.append(f"镜头 {shot.shot_no} 有角色引用，但没有可用的锁定三视图。")
        meta = json_loads_object(shot.meta_json)
        continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
        source_mode = str(meta.get("source_mode") or continuity.get("source_mode") or "").strip()
        image_first_shot = source_mode in {"image_first_reference", "existing_images"}
        requires_i2v = continuity.get("requires_i2v") is not False
        first_frame_source = str(continuity.get("first_frame_source") or "generated")
        if requires_i2v and first_frame_source == "previous_last_frame":
            dependency_shot_no = continuity_dependency_shot_no(continuity, shot)
            dependency_shot = next((item for item in storyboard.shots if item.shot_no == dependency_shot_no), None)
            last_frame = None
            if dependency_shot is not None:
                last_frame = db.scalar(
                    select(MediaAsset).where(
                        MediaAsset.project_id == project.id,
                        MediaAsset.storyboard_id == storyboard.id,
                        MediaAsset.shot_id == dependency_shot.id,
                        MediaAsset.asset_type == "shot_last_frame",
                        MediaAsset.status == "completed",
                        MediaAsset.deleted_at.is_(None),
                    )
                )
            if last_frame is None:
                failures.append(f"镜头 {shot.shot_no} 依赖镜头 {dependency_shot_no} 缺少已完成尾帧。")
            if character_refs:
                identity_service = CharacterIdentityService(settings)
                bound_ids = {
                    item.get("character_card_id")
                    for item in identity_service.shot_identity_bindings(shot=shot)
                    if isinstance(item, dict) and item.get("character_card_id") is not None
                }
                character_ids = []
                for ref in character_refs:
                    if isinstance(ref, dict):
                        value = ref.get("character_card_id") or ref.get("id")
                    else:
                        value = ref
                    try:
                        character_ids.append(int(value))
                    except (TypeError, ValueError):
                        continue
                missing = [character_id for character_id in character_ids if character_id not in bound_ids]
                if missing:
                    failures.append(
                        f"镜头 {shot.shot_no} 为延续镜头，引用的角色缺少规范身份绑定（identity_bindings）；尾帧不能替代规范身份。"
                    )
        elif requires_i2v and first_frame_source == "generated":
            first_frame = db.scalar(
                select(MediaAsset).where(
                    MediaAsset.project_id == project.id,
                    MediaAsset.storyboard_id == storyboard.id,
                    MediaAsset.shot_id == shot.id,
                    MediaAsset.asset_type == "shot_first_frame",
                    MediaAsset.status == "completed",
                    MediaAsset.deleted_at.is_(None),
                )
            )
            if first_frame is None:
                if image_first_shot:
                    failures.append(f"镜头 {shot.shot_no} 图片先行镜头缺少已完成首帧。")
                else:
                    failures.append(f"镜头 {shot.shot_no} 需要首帧，但还没有完成的首帧素材。")
    return failures
