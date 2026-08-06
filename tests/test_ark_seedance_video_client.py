from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.ark_seedance_video_client import ArkSeedanceVideoClient


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ArkSeedanceVideoClientTests(unittest.TestCase):
    def test_submit_first_frame_uses_ark_content_generation_contract(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse({"id": "cgt-test-001"})

        client = ArkSeedanceVideoClient(api_key="ark-key", base_url="https://ark.example/api/v3", model="doubao-seedance-2-0-mini")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            task_id, raw = client.submit_first_frame_to_video(
                prompt="雨夜街道，镜头缓慢前推。",
                image_url="https://assets.example/shot-001.png",
                duration_seconds=5,
                ratio="16:9",
                resolution="1080p",
                return_last_frame=True,
            )

        self.assertEqual(task_id, "cgt-test-001")
        self.assertEqual(raw["id"], "cgt-test-001")
        self.assertEqual(captured["url"], "https://ark.example/api/v3/contents/generations/tasks")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer ark-key")
        self.assertEqual(captured["payload"]["model"], "doubao-seedance-2-0-mini")
        self.assertEqual(captured["payload"]["duration"], 5)
        self.assertEqual(captured["payload"]["ratio"], "16:9")
        self.assertEqual(captured["payload"]["resolution"], "1080p")
        self.assertTrue(captured["payload"]["return_last_frame"])
        self.assertEqual(
            captured["payload"]["content"],
            [
                {"type": "text", "text": "雨夜街道，镜头缓慢前推。"},
                {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://assets.example/shot-001.png"}},
            ],
        )

    def test_get_result_reads_video_and_last_frame_urls(self) -> None:
        def fake_urlopen(request, timeout):
            self.assertEqual(request.full_url, "https://ark.example/api/v3/contents/generations/tasks/cgt-test-001")
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(timeout, 60)
            return _FakeResponse(
                {
                    "id": "cgt-test-001",
                    "model": "doubao-seedance-2-0-mini",
                    "status": "succeeded",
                    "content": {
                        "video_url": "https://assets.example/video.mp4",
                        "last_frame_url": "https://assets.example/last-frame.png",
                    },
                    "usage": {"video_tokens": 123},
                }
            )

        client = ArkSeedanceVideoClient(api_key="ark-key", base_url="https://ark.example/api/v3", model="doubao-seedance-2-0-mini")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.get_result(task_id="cgt-test-001")

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.video_url, "https://assets.example/video.mp4")
        self.assertEqual(result.last_frame_url, "https://assets.example/last-frame.png")
        self.assertEqual(result.usage, {"video_tokens": 123})


if __name__ == "__main__":
    unittest.main()
