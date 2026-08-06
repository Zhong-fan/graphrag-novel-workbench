from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.llm import LLMResponse
from app.storyboard_service import StoryboardService


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        llm_mode="openai",
        openai_api_key="sk-fake",
        openai_base_url="http://fake",
        openai_use_system_proxy=False,
        llm_use_responses=False,
        llm_stream_responses=False,
        llm_request_timeout_seconds=30,
        llm_max_attempts=1,
        llm_retry_max_sleep_seconds=1,
        utility_model="fake-model",
    )


def _project() -> SimpleNamespace:
    card = SimpleNamespace(id=1, name="阿离", story_role="女主", deleted_at=None)
    return SimpleNamespace(
        title="测试项目",
        genre="古风",
        visual_style_locked=True,
        visual_style_medium="日系动画",
        visual_style_artists=["新海诚"],
        visual_style_positive=[],
        visual_style_negative=[],
        visual_style_notes="",
        reference_work="",
        world_brief="架空世界",
        character_cards=[card],
    )


def _chapter() -> SimpleNamespace:
    return SimpleNamespace(chapter_no=1, title="第一章", summary="摘要", content="正文" * 10)


def _valid_payload() -> dict:
    return {
        "title": "短片A",
        "summary": "概述",
        "shots": [
            {
                "shot_no": 1,
                "visual_prompt": "日系动画电影，雨夜街口，蓝绿色光束。",
                "character_refs": [{"character_card_id": 1, "name": "阿离"}],
                "scene_refs": [{"name": "街口", "role": "开场"}],
                "continuity": {"shot_type": "new", "requires_i2v": True},
                "audio_script": {},
            }
        ],
    }


def _invalid_payload() -> dict:
    payload = _valid_payload()
    payload["shots"][0]["visual_prompt"] = "  "
    return payload


class StoryboardServiceValidationTests(unittest.TestCase):
    def _service(self) -> StoryboardService:
        return StoryboardService(_settings())

    def test_accepts_valid_first_response(self) -> None:
        service = self._service()
        with patch.object(service.llm, "generate", return_value=LLMResponse(text=json.dumps(_valid_payload()), model="fake")) as mocked:
            result = service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(result["title"], "短片A")
        mocked.assert_called_once()

    def test_repairs_invalid_payload_with_single_targeted_attempt(self) -> None:
        service = self._service()
        responses = [
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
            LLMResponse(text=json.dumps(_valid_payload()), model="fake"),
        ]
        with patch.object(service.llm, "generate", side_effect=responses) as mocked:
            result = service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(result["shots"][0]["visual_prompt"], _valid_payload()["shots"][0]["visual_prompt"])
        self.assertEqual(mocked.call_count, 2)
        repair_prompt = mocked.call_args_list[1].kwargs["user_prompt"]
        self.assertIn("修复", repair_prompt)

    def test_raises_after_single_repair_failure(self) -> None:
        service = self._service()
        responses = [
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
        ]
        with patch.object(service.llm, "generate", side_effect=responses) as mocked:
            with self.assertRaises(RuntimeError) as ctx:
                service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertIn("校验失败", str(ctx.exception))
        self.assertEqual(mocked.call_count, 2)

    def test_image_first_uses_registered_contract_prompt(self) -> None:
        service = self._service()
        with patch.object(service.llm, "generate", return_value=LLMResponse(text=json.dumps(_valid_payload()), model="fake")) as mocked:
            service.generate_image_first_storyboard(
                project=_project(),
                title="短片A",
                reference_video_brief="雨夜追光",
                reference_image_notes=["参考图说明"],
            )
        system_prompt = mocked.call_args.kwargs["system_prompt"]
        self.assertIn("图片先行的视频分镜导演", system_prompt)


if __name__ == "__main__":
    unittest.main()