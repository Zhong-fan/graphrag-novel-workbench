from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class JimengVideoResult:
    status: str
    video_url: str
    raw: dict[str, Any]


class JimengVideoClient:
    api_version = "2022-08-31"
    submit_action = "CVSync2AsyncSubmitTask"
    result_action = "CVSync2AsyncGetResult"

    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        endpoint: str,
        region: str,
        service: str,
        req_key: str,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self.service = service
        self.req_key = req_key

    def submit_text_to_video(
        self,
        *,
        prompt: str,
        frames: int,
        aspect_ratio: str,
        seed: int = -1,
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "req_key": self.req_key,
            "prompt": prompt,
            "seed": seed,
            "frames": frames,
            "aspect_ratio": aspect_ratio,
        }
        response = self._request(action=self.submit_action, payload=payload)
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"即梦提交任务没有返回 task_id：{self._error_summary(response)}")
        return task_id, response

    def get_result(self, *, task_id: str) -> JimengVideoResult:
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
            raise RuntimeError(f"即梦查询任务没有返回 status：{self._error_summary(response)}")
        video_url = data.get("video_url")
        return JimengVideoResult(
            status=status,
            video_url=video_url if isinstance(video_url, str) else "",
            raw=response,
        )

    def _request(self, *, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        parsed = urllib.parse.urlparse(self.endpoint)
        host = parsed.netloc
        path = parsed.path or "/"
        query = urllib.parse.urlencode({"Action": action, "Version": self.api_version})
        url = f"{self.endpoint}?{query}"
        headers = self._signed_headers(host=host, path=path, query=query, body=body)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"即梦接口 HTTP {exc.code}：{details}") from exc
        except Exception as exc:
            raise RuntimeError(f"即梦接口调用失败：{exc}") from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("即梦接口没有返回合法 JSON。") from exc
        if not isinstance(data, dict):
            raise RuntimeError("即梦接口返回不是 JSON 对象。")
        if data.get("code") != 10000:
            raise RuntimeError(f"即梦接口返回失败：{self._error_summary(data)}")
        return data

    def _signed_headers(self, *, host: str, path: str, query: str, body: bytes) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(body).hexdigest()
        content_type = "application/json"
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{host}\n"
            f"x-content-sha256:{payload_hash}\n"
            f"x-date:{x_date}\n"
        )
        canonical_request = "\n".join(
            [
                "POST",
                path,
                query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = f"{short_date}/{self.region}/{self.service}/request"
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                x_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signing_key = self._signing_key(short_date)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": host,
            "X-Content-Sha256": payload_hash,
            "X-Date": x_date,
        }

    def _signing_key(self, short_date: str) -> bytes:
        date_key = self._hmac(self.secret_key.encode("utf-8"), short_date)
        region_key = self._hmac(date_key, self.region)
        service_key = self._hmac(region_key, self.service)
        return self._hmac(service_key, "request")

    @staticmethod
    def _hmac(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _error_summary(response: dict[str, Any]) -> str:
        message = response.get("message")
        request_id = response.get("request_id")
        code = response.get("code")
        return f"code={code}, message={message}, request_id={request_id}"
