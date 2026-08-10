"""Typed MiniMax video capability with preflight before paid submission."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .capabilities import (
    AdapterError,
    AdapterErrorCategory,
    CapabilityDeclaration,
    CapabilityRole,
    VideoGenerationRequest,
    VideoGenerationResult,
    sanitize_provider_payload,
)
from .minimax_client import MiniMaxClient


class VideoCapability(ABC):
    role = CapabilityRole.VIDEO

    @abstractmethod
    def declaration(self) -> CapabilityDeclaration: ...

    @abstractmethod
    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult: ...


class MiniMaxVideoAdapter(VideoCapability):
    def __init__(self, *, api_key: str, base_url: str = "https://api.minimax.io", model: str = "MiniMax-H3", timeout_seconds: int = 180, poll_interval_seconds: int = 10, poll_timeout_seconds: int = 900, client: MiniMaxClient | None = None) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else "https://api.minimax.io"
        self._model = model or "MiniMax-H3"
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._client = client

    @classmethod
    def from_settings(cls, settings: Any) -> "MiniMaxVideoAdapter":
        return cls(
            api_key=getattr(settings, "minimax_api_key", "") or "",
            base_url=getattr(settings, "minimax_base_url", "https://api.minimax.io") or "https://api.minimax.io",
            model=getattr(settings, "minimax_video_model", "MiniMax-H3") or "MiniMax-H3",
            timeout_seconds=getattr(settings, "minimax_timeout_seconds", 180) or 180,
            poll_interval_seconds=getattr(settings, "minimax_poll_interval_seconds", 10) or 10,
            poll_timeout_seconds=getattr(settings, "minimax_poll_timeout_seconds", 900) or 900,
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=self.role,
            provider="minimax",
            model=self._model,
            supports_reference_images=True,
            supported_input_roles=("first_frame", "last_frame", "reference_image"),
            flags={"modes": "text_to_video,image_to_video,first_last_frame,reference", "duration_min": 4, "duration_max": 15, "resolutions": "768P,2K"},
        )

    def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        self._validate(request)
        client = self._client or MiniMaxClient(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
            poll_interval_seconds=self._poll_interval_seconds,
            poll_timeout_seconds=self._poll_timeout_seconds,
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
        if request.first_frame_url:
            content.append({"type": "image_url", "image_url": {"url": request.first_frame_url}, "role": "first_frame"})
        if request.last_frame_url:
            content.append({"type": "image_url", "image_url": {"url": request.last_frame_url}, "role": "last_frame"})
        for url in request.reference_image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}, "role": "reference_image"})
        payload: dict[str, Any] = {"model": self._model, "content": content, "duration": request.duration_seconds, "resolution": request.resolution}
        if request.mode == "text_to_video":
            payload["ratio"] = request.ratio
        submitted = client.post_json("/v2/video_generation", payload)
        task_id = str(submitted.get("task_id") or "")
        if not task_id:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 视频接口没有返回 task_id。", details={"response": sanitize_provider_payload(submitted)})
        completed = client.poll_task(task_id)
        response = completed.response
        content_result = response.get("content") if isinstance(response.get("content"), dict) else {}
        video_url = str(content_result.get("url") or response.get("video_url") or "")
        file_id = str(content_result.get("file_id") or response.get("file_id") or "")
        return VideoGenerationResult(provider="minimax", model=self._model, task_id=task_id, status=completed.status, video_url=video_url, file_id=file_id, usage=dict(response.get("usage") or {}), parameters={"mode": request.mode, "duration": request.duration_seconds, "resolution": request.resolution, "ratio": request.ratio}, result_summary=sanitize_provider_payload({"task_id": task_id, "status": completed.status, "has_video_url": bool(video_url), "has_file_id": bool(file_id)}))

    def _validate(self, request: VideoGenerationRequest) -> None:
        if not request.prompt.strip() or len(request.prompt) > 7000:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax 视频 prompt 必须为 1-7000 个字符。", provider_code="prompt_length", retryable=False)
        if request.duration_seconds < 4 or request.duration_seconds > 15:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax H3 视频时长必须为 4-15 秒。", provider_code="duration", retryable=False)
        if request.resolution not in {"768P", "2K"}:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax H3 只支持 768P 或 2K。", provider_code="resolution", retryable=False)
        if request.mode not in {"text_to_video", "image_to_video", "first_last_frame", "reference"}:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message=f"MiniMax 不支持视频模式：{request.mode}。", provider_code="mode", retryable=False)
        if request.mode == "image_to_video" and not request.first_frame_url:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="image_to_video 必须提供 first_frame_url。", provider_code="first_frame", retryable=False)
        if request.mode == "first_last_frame" and not (request.first_frame_url or request.last_frame_url):
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="first_last_frame 至少需要一张边界帧。", provider_code="boundary_frames", retryable=False)
        if len(request.reference_image_urls) > 9:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax 参考图片最多 9 张。", provider_code="reference_limit", retryable=False)


def build_video_capability(settings: Any, *, provider_hint: str = "") -> VideoCapability:
    provider = (provider_hint or getattr(settings, "video_provider", "") or "minimax").strip().lower()
    if provider == "minimax":
        return MiniMaxVideoAdapter.from_settings(settings)
    raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message=f"视频能力暂未接入 provider：{provider}。", provider_code="provider", retryable=False)
