from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .jimeng_video_client import JimengVideoClient


@dataclass(frozen=True)
class JimengImageResult:
    status: str
    image_urls: list[str]
    image_base64: list[str]
    raw: dict[str, Any]


class JimengImageClient(JimengVideoClient):
    def submit_text_to_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int = -1,
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "req_key": self.req_key,
            "prompt": prompt,
            "seed": seed,
            "width": width,
            "height": height,
        }
        response = self._request(action=self.submit_action, payload=payload)
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            urls = self._extract_image_urls(data)
            images = self._extract_image_base64(data)
            if urls or images:
                return "", response
            raise RuntimeError(f"即梦图片提交任务没有返回 task_id 或图片 URL：{self._error_summary(response)}")
        return task_id, response

    def get_image_result(self, *, task_id: str) -> JimengImageResult:
        response = self._request(
            action=self.result_action,
            payload={
                "req_key": self.req_key,
                "task_id": task_id,
            },
        )
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        status = data.get("status")
        if not isinstance(status, str) or not status:
            raise RuntimeError(f"即梦图片查询任务没有返回 status：{self._error_summary(response)}")
        return JimengImageResult(
            status=status,
            image_urls=self._extract_image_urls(data),
            image_base64=self._extract_image_base64(data),
            raw=response,
        )

    @classmethod
    def _extract_image_urls(cls, data: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for key in ("image_urls", "image_urls_map", "binary_data_base64", "result_urls", "urls"):
            value = data.get(key)
            if isinstance(value, list):
                urls.extend(str(item) for item in value if str(item).startswith(("http://", "https://")))
            elif isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, list):
                        urls.extend(str(url) for url in item if str(url).startswith(("http://", "https://")))
                    elif isinstance(item, str) and item.startswith(("http://", "https://")):
                        urls.append(item)
            elif isinstance(value, str) and value.startswith(("http://", "https://")):
                urls.append(value)

        image_url = data.get("image_url")
        if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
            urls.append(image_url)

        return list(dict.fromkeys(urls))

    @classmethod
    def _extract_image_base64(cls, data: dict[str, Any]) -> list[str]:
        images: list[str] = []
        value = data.get("binary_data_base64")
        if isinstance(value, list):
            images.extend(str(item) for item in value if isinstance(item, str) and item.strip())
        elif isinstance(value, str) and value.strip():
            images.append(value)
        return images
