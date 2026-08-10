"""Small, secret-safe HTTP transport for the MiniMax API.

The client intentionally knows only the provider transport contract. Domain
services use the typed capability adapters instead of constructing payloads.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .capabilities import AdapterError, AdapterErrorCategory, sanitize_provider_payload


@dataclass(frozen=True)
class MiniMaxTaskResult:
    task_id: str
    status: str
    response: dict[str, Any]


class MiniMaxClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.minimax.io",
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 10,
        poll_timeout_seconds: int = 900,
        opener: urllib.request.OpenerDirector | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = (base_url or "https://api.minimax.io").rstrip("/")
        self.timeout_seconds = max(1, int(timeout_seconds or 180))
        self.poll_interval_seconds = max(1, int(poll_interval_seconds or 10))
        self.poll_timeout_seconds = max(1, int(poll_timeout_seconds or 900))
        self._opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._sleep = sleep

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload=payload)

    def get_json(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def download(self, url: str) -> tuple[bytes, str]:
        if not url:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="MiniMax 没有返回可下载的文件地址。",
            )
        request = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise AdapterError(
                AdapterErrorCategory.NETWORK_TIMEOUT if isinstance(exc, TimeoutError) else AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
                safe_message="MiniMax 文件下载失败。",
                details={"error_type": type(exc).__name__},
            ) from exc
        if not data:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 文件下载结果为空。")
        return data, content_type

    def poll_task(self, task_id: str, *, cancel_check: Callable[[], bool] | None = None) -> MiniMaxTaskResult:
        deadline = time.monotonic() + self.poll_timeout_seconds
        last: dict[str, Any] = {}
        while time.monotonic() <= deadline:
            if cancel_check and cancel_check():
                raise AdapterError(
                    AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                    safe_message="MiniMax 任务已被取消。",
                    provider_code="cancelled",
                    retryable=False,
                )
            body = self.get_json(f"/v2/query/video_generation?task_id={task_id}")
            last = body
            status = self._task_status(body)
            if status in {"Success", "Succeeded", "Failed", "Fail", "Canceled", "Cancelled", "Error"}:
                if status.lower() not in {"success", "succeeded"}:
                    raise AdapterError(
                        AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                        safe_message=f"MiniMax 视频任务失败：{status}。",
                        provider_code=status,
                        retryable=False,
                        details={"task_id": task_id, "response": sanitize_provider_payload(body)},
                    )
                return MiniMaxTaskResult(task_id=task_id, status=status, response=body)
            self._sleep(self.poll_interval_seconds)
        raise AdapterError(
            AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
            safe_message="MiniMax 视频任务轮询超时。",
            provider_code="poll_timeout",
            details={"task_id": task_id, "last_response": sanitize_provider_payload(last)},
        )

    def _request(self, method: str, path: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise AdapterError(AdapterErrorCategory.CONFIG_OR_AUTH, safe_message="MiniMax 配置缺失：MINIMAX_API_KEY。")
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            category = AdapterErrorCategory.NETWORK_TIMEOUT if isinstance(exc, TimeoutError) else AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE
            raise AdapterError(category, safe_message="MiniMax 接口网络请求失败。", details={"error_type": type(exc).__name__}) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 接口没有返回合法 JSON。") from exc
        if not isinstance(data, dict):
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 接口返回格式错误。")
        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict) and str(base_resp.get("status_code", "0")) not in {"0", "200", "20000000"}:
            code = str(base_resp.get("status_code"))
            raise AdapterError(
                AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                safe_message=f"MiniMax 接口返回错误：{base_resp.get('status_msg') or code}。",
                provider_code=code,
                retryable=False,
                details={"base_resp": sanitize_provider_payload(base_resp)},
            )
        return data

    def _http_error(self, exc: urllib.error.HTTPError) -> AdapterError:
        try:
            preview = exc.read().decode("utf-8", "replace")[:1000]
        except Exception:
            preview = ""
        if exc.code in {401, 403}:
            category = AdapterErrorCategory.CONFIG_OR_AUTH
        elif exc.code == 429:
            category = AdapterErrorCategory.RATE_LIMIT_OR_QUOTA
        elif 400 <= exc.code < 500:
            category = AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED
        else:
            category = AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE
        return AdapterError(category, safe_message=f"MiniMax 接口调用失败（HTTP {exc.code}）。", provider_code=str(exc.code), details={"status_code": exc.code, "response_preview": preview})

    @staticmethod
    def _task_status(body: dict[str, Any]) -> str:
        return str(body.get("status") or body.get("data", {}).get("status") or "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
