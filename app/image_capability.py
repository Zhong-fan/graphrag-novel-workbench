"""Reference-aware image capability: port, adapters, and factory.

Business services depend on :class:`ImageCapability`, never on a provider
client directly. Provider-specific payloads and polling stay inside the
adapters. The factory selects an adapter from centralized settings; the
Doubao/Jimeng adapter remains the default deployment choice.
"""

from __future__ import annotations


import http.client
import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from .capabilities import (
    AdapterError,
    AdapterErrorCategory,
    CapabilityDeclaration,
    CapabilityRole,
    ImageGenerationRequest,
    ImageGenerationResult,
    sanitize_provider_payload,
)
from .jimeng_image_client import JimengImageClient

DEFAULT_POLL_INTERVAL_SECONDS = 10
DEFAULT_POLL_TIMEOUT_SECONDS = 900
DEFAULT_REQUEST_TIMEOUT_SECONDS = 180


class ImageCapability(ABC):
    """Port used by asset and render workflows for image generation."""

    role = CapabilityRole.IMAGE

    @abstractmethod
    def declaration(self) -> CapabilityDeclaration:
        """Declare provider, model, and supported input roles."""

    @abstractmethod
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate one image and return sanitized trace evidence."""


def _map_http_error(exc: urllib.error.HTTPError) -> AdapterError:
    status = exc.code
    body = ""
    try:
        body = exc.read().decode("utf-8", "replace")[:2000]
    except Exception:
        pass
    if "content_policy" in body.lower() or "safety" in body.lower():
        category = AdapterErrorCategory.CONTENT_POLICY_REJECTION
    elif status == 429:
        category = AdapterErrorCategory.RATE_LIMIT_OR_QUOTA
    elif status in (401, 403):
        category = AdapterErrorCategory.CONFIG_OR_AUTH
    elif 400 <= status < 500:
        category = AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED
    else:
        category = AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE
    return AdapterError(
        category,
        safe_message=f"图像生成接口调用失败（HTTP {status}）。",
        provider_code=str(status),
        details={"status_code": status, "response_preview": body[:500]},
    )


def _map_network_error(exc: Exception) -> AdapterError:
    if isinstance(exc, TimeoutError):
        return AdapterError(
            AdapterErrorCategory.NETWORK_TIMEOUT,
            safe_message="图像生成接口请求超时。",
            details={"error_type": type(exc).__name__},
        )
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return AdapterError(
                AdapterErrorCategory.NETWORK_TIMEOUT,
                safe_message="图像生成接口请求超时。",
                details={"error_type": type(reason).__name__},
            )
        return AdapterError(
            AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
            safe_message="图像生成接口网络请求失败。",
            details={"error_type": type(reason).__name__ if reason is not None else "unknown"},
        )
    return AdapterError(
        AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
        safe_message="图像生成接口调用失败。",
        details={"error_type": type(exc).__name__},
    )


class JimengImageAdapter(ImageCapability):
    """Doubao/Jimeng text-to-image adapter (async submit + poll)."""

    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        endpoint: str,
        region: str,
        service: str,
        req_key: str,
        width: int = 1024,
        height: int = 1024,
        poll_timeout_seconds: int = DEFAULT_POLL_TIMEOUT_SECONDS,
        poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._access_key = access_key or ""
        self._secret_key = secret_key or ""
        self._endpoint = endpoint or ""
        self._region = region or ""
        self._service = service or ""
        self._req_key = req_key or ""
        self._width = int(width or 1024)
        self._height = int(height or 1024)
        self._poll_timeout_seconds = int(poll_timeout_seconds or DEFAULT_POLL_TIMEOUT_SECONDS)
        self._poll_interval_seconds = int(poll_interval_seconds or DEFAULT_POLL_INTERVAL_SECONDS)

    @classmethod
    def from_settings(cls, settings: Any) -> "JimengImageAdapter":
        return cls(
            access_key=getattr(settings, "jimeng_access_key", "") or "",
            secret_key=getattr(settings, "jimeng_secret_key", "") or "",
            endpoint=getattr(settings, "jimeng_endpoint", "") or "",
            region=getattr(settings, "jimeng_region", "") or "",
            service=getattr(settings, "jimeng_service", "") or "",
            req_key=getattr(settings, "jimeng_image_req_key", "") or "",
            width=int(getattr(settings, "jimeng_image_width", 1024) or 1024),
            height=int(getattr(settings, "jimeng_image_height", 1024) or 1024),
            poll_timeout_seconds=int(getattr(settings, "jimeng_poll_timeout_seconds", DEFAULT_POLL_TIMEOUT_SECONDS) or DEFAULT_POLL_TIMEOUT_SECONDS),
            poll_interval_seconds=int(getattr(settings, "jimeng_poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS) or DEFAULT_POLL_INTERVAL_SECONDS),
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=CapabilityRole.IMAGE,
            provider="jimeng",
            model=self._req_key,
            supports_reference_images=True,
            supported_input_roles=("image",),
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_config()
        client = JimengImageClient(
            access_key=self._access_key,
            secret_key=self._secret_key,
            endpoint=self._endpoint,
            region=self._region,
            service=self._service,
            req_key=self._req_key,
        )
        try:
            task_id, submit_response = client.submit_text_to_image(
                prompt=request.prompt,
                width=request.width or self._width,
                height=request.height or self._height,
                reference_images=list(request.reference_images),
            )
            if task_id:
                image_payload, result_response = self._wait_for_image_result(client=client, task_id=task_id)
            else:
                data = submit_response.get("data") if isinstance(submit_response.get("data"), dict) else {}
                urls = client._extract_image_urls(data)
                images = client._extract_image_base64(data)
                if urls:
                    image_payload = {"kind": "url", "value": urls[0]}
                elif images:
                    image_payload = {"kind": "base64", "value": images[0]}
                else:
                    raise AdapterError(
                        AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                        safe_message="即梦图片接口没有返回 task_id 或图片 URL。",
                    )
                result_response = submit_response
        except AdapterError:
            raise
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise _map_network_error(exc) from exc
        except RuntimeError as exc:
            # JimengImageClient signals provider/response problems with RuntimeError;
            # unexpected exceptions propagate so programming bugs stay visible.
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message=f"即梦图片接口调用失败：{exc}",
                details={"error_type": type(exc).__name__},
            ) from exc
        return ImageGenerationResult(
            provider="jimeng",
            model=self._req_key,
            kind=image_payload["kind"],
            value=image_payload["value"],
            provider_ref=task_id or None,
            submit_summary=sanitize_provider_payload(self._summarize_image_response(submit_response)),
            result_summary=sanitize_provider_payload(self._summarize_image_response(result_response)),
            parameters={"req_key": self._req_key, "width": request.width or self._width, "height": request.height or self._height},
        )

    def _require_config(self) -> None:
        missing: list[str] = []
        if not self._access_key:
            missing.append("JIMENG_ACCESS_KEY")
        if not self._secret_key:
            missing.append("JIMENG_SECRET_KEY")
        if not self._req_key:
            missing.append("JIMENG_IMAGE_REQ_KEY")
        if missing:
            raise AdapterError(
                AdapterErrorCategory.CONFIG_OR_AUTH,
                safe_message="即梦图片生成配置缺失：" + "、".join(missing),
            )

    def _wait_for_image_result(self, *, client: JimengImageClient, task_id: str) -> tuple[dict[str, str], dict[str, Any]]:
        deadline = time.monotonic() + self._poll_timeout_seconds
        last_response: dict[str, Any] = {}
        while time.monotonic() < deadline:
            result = client.get_image_result(task_id=task_id)
            last_response = result.raw
            if result.status == "done":
                if result.image_urls:
                    return {"kind": "url", "value": result.image_urls[0]}, result.raw
                if result.image_base64:
                    return {"kind": "base64", "value": result.image_base64[0]}, result.raw
                raise AdapterError(
                    AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                    safe_message=f"即梦图片任务已完成但没有返回图片 URL 或 base64：{task_id}",
                )
            if result.status in {"not_found", "expired"}:
                raise AdapterError(
                    AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                    safe_message=f"即梦图片任务状态异常：{result.status}，task_id={task_id}",
                )
            if result.status not in {"in_queue", "generating"}:
                raise AdapterError(
                    AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                    safe_message=f"即梦图片任务返回未知状态：{result.status}，task_id={task_id}",
                )
            time.sleep(self._poll_interval_seconds)
        raise AdapterError(
            AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
            safe_message=f"即梦图片任务等待超时：task_id={task_id}",
        )

    @staticmethod
    def _summarize_image_response(response: dict[str, Any]) -> dict[str, Any]:
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        return {
            "code": response.get("code"),
            "message": response.get("message") or response.get("msg") or "",
            "status": data.get("status") or "",
            "task_id": data.get("task_id") or "",
            "image_url_count": len(JimengImageClient._extract_image_urls(data)),
            "has_image_base64": bool(JimengImageClient._extract_image_base64(data)),
        }


class OpenAICompatibleImageAdapter(ImageCapability):
    """OpenAI-compatible /images/generations adapter (synchronous)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        size: str = "1024x1024",
        timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._model = model or ""
        self._size = size or "1024x1024"
        self._timeout_seconds = int(timeout_seconds or DEFAULT_REQUEST_TIMEOUT_SECONDS)

    @classmethod
    def from_settings(cls, settings: Any) -> "OpenAICompatibleImageAdapter":
        return cls(
            api_key=getattr(settings, "image_api_key", "") or "",
            base_url=getattr(settings, "image_base_url", "") or "",
            model=getattr(settings, "image_model", "") or "",
            size=getattr(settings, "image_size", "1024x1024") or "1024x1024",
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=CapabilityRole.IMAGE,
            provider="openai_compatible",
            model=self._model,
            supports_reference_images=False,
            supported_input_roles=(),
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_config()
        payload = {
            "model": self._model,
            "prompt": request.prompt,
            "size": self._size,
            "n": max(1, request.count),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self._base_url}/images/generations"
        http_request = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise _map_network_error(exc) from exc
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="图像生成接口没有返回合法 JSON。",
            ) from exc
        entries = data.get("data") if isinstance(data.get("data"), list) else []
        if not entries or not isinstance(entries[0], dict):
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="图像生成接口没有返回 data。",
            )
        first = entries[0]
        if isinstance(first.get("b64_json"), str) and first["b64_json"]:
            kind, value = "base64", first["b64_json"]
        elif isinstance(first.get("url"), str) and first["url"]:
            kind, value = "url", first["url"]
        else:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="图像生成接口没有返回 b64_json 或 url。",
            )
        return ImageGenerationResult(
            provider="openai_compatible",
            model=self._model,
            kind=kind,
            value=value,
            result_summary=sanitize_provider_payload(
                {"model": data.get("model") or first.get("model") or self._model, "images": len(entries)}
            ),
            parameters={"size": self._size, "width": request.width, "height": request.height},
        )

    def _require_config(self) -> None:
        missing: list[str] = []
        if not self._api_key:
            missing.append("CHENFLOW_IMAGE_API_KEY")
        if not self._base_url:
            missing.append("CHENFLOW_IMAGE_BASE_URL")
        if not self._model:
            missing.append("CHENFLOW_IMAGE_MODEL")
        if missing:
            raise AdapterError(
                AdapterErrorCategory.CONFIG_OR_AUTH,
                safe_message="OpenAI 兼容图像生成配置缺失：" + "、".join(missing),
            )


class ArkSeedreamImageAdapter(ImageCapability):
    """Doubao Seedream image adapter via Ark /images/generations (synchronous).

    Reference images use Ark's content-array URL-role contract, mirroring the
    Seedance client convention; declared in ``flags`` so the wire contract is
    verifiable before it becomes the deployment default.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        size: str = "1024x1024",
        timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._model = model or ""
        self._size = size or "1024x1024"
        self._timeout_seconds = int(timeout_seconds or DEFAULT_REQUEST_TIMEOUT_SECONDS)

    @classmethod
    def from_settings(cls, settings: Any) -> "ArkSeedreamImageAdapter":
        return cls(
            api_key=getattr(settings, "ark_api_key", "") or "",
            base_url=getattr(settings, "ark_base_url", "") or "",
            model=getattr(settings, "ark_image_model", "") or "",
            size=getattr(settings, "ark_image_size", "1024x1024") or "1024x1024",
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=CapabilityRole.IMAGE,
            provider="ark_seedream",
            model=self._model,
            supports_reference_images=True,
            supported_input_roles=("reference_image",),
            flags={"reference_contract": "content-array-url-role"},
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_config()
        payload = self._build_payload(request)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = f"{self._base_url}/images/generations"
        http_request = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise _map_network_error(exc) from exc
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="Ark Seedream 图像接口没有返回合法 JSON。",
            ) from exc
        entries = data.get("data") if isinstance(data.get("data"), list) else []
        if not entries or not isinstance(entries[0], dict):
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="Ark Seedream 图像接口没有返回 data。",
            )
        first = entries[0]
        if isinstance(first.get("url"), str) and first["url"]:
            kind, value = "url", first["url"]
        elif isinstance(first.get("b64_json"), str) and first["b64_json"]:
            kind, value = "base64", first["b64_json"]
        else:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="Ark Seedream 图像接口没有返回 url 或 b64_json。",
            )
        return ImageGenerationResult(
            provider="ark_seedream",
            model=self._model,
            kind=kind,
            value=value,
            result_summary=sanitize_provider_payload({"images": len(entries), "response_format": "url"}),
            parameters={
                "size": self._size,
                # Ark honors the configured size string; request.width/height are
                # recorded for trace parity and are not applied to the payload.
                "width": request.width,
                "height": request.height,
                "reference_image_count": len(request.reference_images),
            },
        )

    def _build_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": request.prompt,
            "size": self._size,
            "response_format": "url",
            "n": max(1, request.count),
        }
        if request.reference_images:
            # Ark Seedream reads references from a content array; the top-level
            # prompt must move inside it and image URLs use role "reference".
            content: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
            for image_url in request.reference_images:
                content.append({"type": "image_url", "role": "reference", "image_url": {"url": image_url}})
            payload.pop("prompt")
            payload["content"] = content
        return payload

    def _require_config(self) -> None:
        missing: list[str] = []
        if not self._api_key:
            missing.append("ARK_API_KEY")
        if not self._base_url:
            missing.append("ARK_BASE_URL")
        if not self._model:
            missing.append("ARK_IMAGE_MODEL")
        if missing:
            raise AdapterError(
                AdapterErrorCategory.CONFIG_OR_AUTH,
                safe_message="Ark Seedream 图像生成配置缺失：" + "、".join(missing),
            )


def build_image_capability(settings: Any) -> ImageCapability:
    """Select the configured image adapter without leaking provider logic."""

    image_model = (getattr(settings, "image_model", "") or "").strip()
    image_base_url = (getattr(settings, "image_base_url", "") or "").strip()
    has_jimeng_config = bool(
        (getattr(settings, "jimeng_access_key", "") or "")
        and (getattr(settings, "jimeng_image_req_key", "") or "")
    )
    image_provider = (getattr(settings, "image_provider", "") or "").strip().lower()
    if image_provider == "ark_seedream":
        return ArkSeedreamImageAdapter.from_settings(settings)
    if image_model.startswith("jimeng_") or (not image_base_url and has_jimeng_config):
        return JimengImageAdapter.from_settings(settings)
    if image_base_url and image_model:
        return OpenAICompatibleImageAdapter.from_settings(settings)
    raise AdapterError(
        AdapterErrorCategory.CONFIG_OR_AUTH,
        safe_message="图像生成配置缺失：请配置 JIMENG_*、CHENFLOW_IMAGE_* 或 CHENFLOW_IMAGE_PROVIDER=ark_seedream。",
    )
