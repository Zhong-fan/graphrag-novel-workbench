from __future__ import annotations

from typing import Any

from .json_utils import ensure_list, json_loads_object
from .models import Storyboard, VideoTask


def build_review_findings(shot_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for item in shot_results:
        shot_no = item.get("shot_no")
        shot_label = f"镜头 {shot_no}" if shot_no is not None else "当前镜头"
        if item.get("continuity_failed"):
            findings.append(
                {
                    "finding_id": f"shot-{shot_no}-continuity" if shot_no is not None else "shot-continuity",
                    "severity": "blocking",
                    "category": "continuity",
                    "title": f"{shot_label} 连续性失败",
                    "detail": "角色或首尾帧连续性不稳定。",
                    "recommended_rework_level": "shot",
                }
            )
        if item.get("pacing_failed"):
            findings.append(
                {
                    "finding_id": f"shot-{shot_no}-pacing" if shot_no is not None else "shot-pacing",
                    "severity": "advisory",
                    "category": "pacing",
                    "title": f"{shot_label} 节奏偏弱",
                    "detail": "镜头节奏或叙事结构需要回到分镜层调整。",
                    "recommended_rework_level": "storyboard",
                }
            )
        if item.get("local_defect"):
            findings.append(
                {
                    "finding_id": f"shot-{shot_no}-local-defect" if shot_no is not None else "shot-local-defect",
                    "severity": "advisory",
                    "category": "local_defect",
                    "title": f"{shot_label} 存在局部画面缺陷",
                    "detail": "局部构图或细节异常，优先尝试局部修正。",
                    "recommended_rework_level": "local_fix",
                }
            )
    return findings


class VideoQualityService:
    def build_quality_plan(self, storyboard: Storyboard) -> dict[str, Any]:
        shots = sorted(storyboard.shots, key=lambda item: item.shot_no)
        first_meta = json_loads_object(shots[0].meta_json) if shots else {}
        source_trace = first_meta.get("source_trace") if isinstance(first_meta.get("source_trace"), dict) else {}
        source_mode = str(first_meta.get("source_mode") or source_trace.get("source_mode") or "novel_chapters")
        planned_shots = []
        for shot in shots:
            meta = json_loads_object(shot.meta_json)
            continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
            audio_script = meta.get("audio_script") if isinstance(meta.get("audio_script"), dict) else {}
            planned_shots.append(
                {
                    "shot_no": shot.shot_no,
                    "purpose": shot.narration_text.strip() or shot.visual_prompt.strip(),
                    "visual_continuity": ensure_list(continuity.get("continuity_constraints")),
                    "subtitle_text": str(audio_script.get("subtitle_text") or "").strip(),
                    "duration_seconds": shot.duration_seconds,
                }
            )
        return {
            "source_mode": source_mode,
            "source_trace": source_trace,
            "shot_count": len(planned_shots),
            "structure": {
                "opening": "Shot 1 establishes the scene." if planned_shots else "",
                "development": "Middle shots advance the change." if len(planned_shots) >= 2 else "",
                "ending": f"Shot {planned_shots[-1]['shot_no']} resolves the emotion or action." if planned_shots else "",
            },
            "shots": planned_shots,
            "quality_dimensions": ["short_film_structure", "visual_stability", "content_consistency"],
        }

    def build_result(
        self,
        *,
        task: VideoTask,
        status: str,
        message: str,
        quality_accepted: bool = False,
    ) -> dict[str, Any]:
        """渲染完成与质量验收分离：render_status 记录渲染结果，status/quality_accepted 记录验收状态。"""
        progress = json_loads_object(task.progress_json)
        plan = progress.get("video_quality_plan") if isinstance(progress.get("video_quality_plan"), dict) else {}
        shot_results = ensure_list(progress.get("shot_results"))
        render_completed = status == "completed" and bool(task.output_uri)
        if quality_accepted:
            result_status = "passed"
        elif render_completed:
            result_status = "requires_review"
        else:
            result_status = "failed"
        return {
            "status": result_status,
            "render_status": "completed" if render_completed else "failed",
            "quality_accepted": bool(quality_accepted),
            "message": message,
            "checked_against_plan": bool(plan),
            "short_film_structure": "passed" if quality_accepted else "requires_review",
            "visual_stability": "requires_review",
            "content_consistency": "requires_review",
            "review_findings": build_review_findings([item for item in shot_results if isinstance(item, dict)]),
        }

