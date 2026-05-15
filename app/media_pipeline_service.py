from __future__ import annotations

from .json_utils import json_dumps
from .models import Storyboard


class MediaPipelineService:
    def plan_video_task(self, *, storyboard: Storyboard) -> dict[str, object]:
        shot_count = len(storyboard.shots)
        total_seconds = sum(float(shot.duration_seconds or 0) for shot in storyboard.shots)
        return {
            "stage": "queued",
            "message": "视频导出任务已创建，等待媒体管线处理。",
            "shot_count": shot_count,
            "estimated_duration_seconds": round(total_seconds, 1),
            "steps": [
                {"key": "image", "label": "镜头图生成", "status": "pending"},
                {"key": "voice", "label": "旁白生成", "status": "pending"},
                {"key": "subtitle", "label": "字幕生成", "status": "pending"},
                {"key": "compose", "label": "FFmpeg 合成", "status": "pending"},
            ],
        }

    def task_progress_json(self, *, storyboard: Storyboard) -> str:
        return json_dumps(self.plan_video_task(storyboard=storyboard))
