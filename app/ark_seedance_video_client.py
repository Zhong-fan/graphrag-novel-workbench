from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArkSeedanceVideoResult:
    status: str
    video_url: str
    last_frame_url: str
    raw: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)


class ArkSeedanceVideoClient:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def submit_text_to_video(
        self,
        *,
        prompt: str,
        duration_seconds: int,
        ratio: str,
        resolution: str,
        return_last_frame: bool,
    ) -> tuple[str, dict[str, Any]]:
        return self._submit(
            prompt=prompt,
            image_url="",
            duration_seconds=duration_seconds,
            ratio=ratio,
            resolution=resolution,
            return_last_frame=return_last_frame,
        )

    def submit_first_frame_to_video(
        self,
        *,
        prompt: str,
        image_url: str,
        duration_seconds: int,
        ratio: str,
        resolution: str,
        return_last_frame: bool,
    ) -> tuple[str, dict[str, Any]]:
        return self._submit(
            prompt=prompt,
            image_url=image_url,
            duration_seconds=duration_seconds,
            ratio=ratio,
            resolution=resolution,
            return_last_frame=return_last_frame,
        )

    def get_result(self, *, task_id: str) -> ArkSeedanceVideoResult:
        response = self._request(method="GET", path=f"/contents/generations/tasks/{task_id}")
        content = response.get("content") if isinstance(response.get("content"), dict) else {}
        status = response.get("status")
        if not isinstance(status, str) or not status:
            raise RuntimeError(f"Ark Seedance 查询任务没有返回 status：{self._error_summary(response)}")
        video_url = content.get("video_url")
        last_frame_url = content.get("last_frame_url")
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        return ArkSeedanceVideoResult(
            status=status,
            video_url=video_url if isinstance(video_url, str) else "",
            last_frame_url=last_frame_url if isinstance(last_frame_url, str) else "",
            raw=response,
            usage=usage,
        )

    def _submit(
        self,
        *,
        prompt: str,
        image_url: str,
        duration_seconds: int,
        ratio: str,
        resolution: str,
        return_last_frame: bool,
    ) -> tuple[str, dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_url:
            content.append({"type": "image_url", "role": "first_frame", "image_url": {"url": image_url}})
        payload: dict[str, Any] = {
            "model": self.model,
            "content": content,
            "duration": duration_seconds,
            "ratio": ratio,
            "return_last_frame": return_last_frame,
        }
        if resolution:
            payload["resolution"] = resolution
        response = self._request(method="POST", path="/contents/generations/tasks", payload=payload)
        task_id = response.get("id") or response.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"Ark Seedance 提交任务没有返回 id：{self._error_summary(response)}")
        return task_id, response

    def _request(self, *, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ark Seedance 接口 HTTP {exc.code}：{details}") from exc
        except Exception as exc:
            raise RuntimeError(f"Ark Seedance 接口调用失败：{exc}") from exc
        try:
            data = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ark Seedance 接口没有返回合法 JSON。") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Ark Seedance 接口返回不是 JSON 对象。")
        if "error" in data:
            raise RuntimeError(f"Ark Seedance 接口返回失败：{self._error_summary(data)}")
        return data

    @staticmethod
    def _error_summary(response: dict[str, Any]) -> str:
        error = response.get("error")
        if isinstance(error, dict):
            return f"code={error.get('code')}, message={error.get('message')}"
        return json.dumps(response, ensure_ascii=False)[:1000]
