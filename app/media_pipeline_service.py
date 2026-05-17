from __future__ import annotations

from .json_utils import json_dumps
from .models import Storyboard


class MediaPipelineService:
    def plan_video_task(self, *, storyboard: Storyboard) -> dict[str, object]:
        shots = sorted(storyboard.shots, key=lambda item: item.shot_no)
        total_seconds = sum(float(shot.duration_seconds or 0) for shot in shots)
        return {
            "stage": "queued",
            "message": "视频导出任务已创建，等待媒体管线处理。",
            "shot_count": len(shots),
            "estimated_duration_seconds": round(total_seconds, 1),
            "completed_shot_count": 0,
            "current_shot_no": None,
            "current_step": "",
            "last_updated_at": "",
            "failure_stage": "",
            "segment_count": 0,
            "audio_composed_count": 0,
            "subtitle_count": 0,
            "steps": [
                {"key": "image", "label": "镜头画面生成", "status": "pending"},
                {"key": "voice", "label": "对白/旁白准备", "status": "pending"},
                {"key": "subtitle", "label": "字幕生成", "status": "pending"},
                {"key": "compose", "label": "FFmpeg 合成", "status": "pending"},
            ],
            "shots": [
                {
                    "shot_id": shot.id,
                    "shot_no": shot.shot_no,
                    "duration_seconds": float(shot.duration_seconds or 0),
                    "image_status": "pending",
                    "dialogue_status": "pending",
                    "subtitle_status": "pending",
                    "segment_status": "pending",
                    "composed_status": "pending",
                    "segment_uri": "",
                    "dialogue_uri": "",
                    "subtitle_uri": "",
                    "composed_uri": "",
                    "warnings": [],
                }
                for shot in shots
            ],
        }

    def task_progress_json(self, *, storyboard: Storyboard) -> str:
        return json_dumps(self.plan_video_task(storyboard=storyboard))
