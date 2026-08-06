from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.generation_evidence_service import GenerationEvidence
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
        id=5,
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


class StoryboardEvidenceSinkTests(unittest.TestCase):
    def _service(self) -> tuple[StoryboardService, list[GenerationEvidence]]:
        records: list[GenerationEvidence] = []
        service = StoryboardService(_settings(), evidence_sink=records.append)
        return service, records

    def test_success_records_evidence_with_contract_and_payload(self) -> None:
        service, records = self._service()
        with patch.object(service.llm, "generate", return_value=LLMResponse(text=json.dumps(_valid_payload()), model="fake")):
            service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.stage, "storyboard.shots.v1")
        self.assertEqual(record.status, "succeeded")
        self.assertEqual(record.provider, "openai")
        self.assertEqual(record.model, "fake-model")
        self.assertEqual(record.project_id, 5)
        self.assertEqual(record.prompt_contract_id, "storyboard.shots.v1")
        self.assertEqual(record.prompt_version, "v1")
        self.assertIn("短片A", record.rendered_prompt)
        self.assertIn("shots", record.raw_output)
        self.assertEqual(record.parsed_output["title"], "短片A")
        self.assertTrue(record.validation_results["initial_ok"])
        self.assertEqual(record.quality_outcome, "adopted")

    def test_repair_success_records_single_targeted_attempt(self) -> None:
        service, records = self._service()
        responses = [
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
            LLMResponse(text=json.dumps(_valid_payload()), model="fake"),
        ]
        with patch.object(service.llm, "generate", side_effect=responses):
            service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.status, "succeeded")
        self.assertFalse(record.validation_results["initial_ok"])
        self.assertTrue(record.validation_results["repair_attempted"])
        self.assertTrue(record.validation_results["final_ok"])
        self.assertEqual(record.quality_outcome, "adopted")

    def test_double_failure_records_failed_evidence_then_raises(self) -> None:
        service, records = self._service()
        responses = [
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
            LLMResponse(text=json.dumps(_invalid_payload()), model="fake"),
        ]
        with patch.object(service.llm, "generate", side_effect=responses):
            with self.assertRaises(RuntimeError):
                service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.error_category, "validation_failed")
        self.assertIn("校验失败", record.error_message)
        self.assertFalse(record.validation_results["final_ok"])


    def test_non_json_response_records_failed_evidence(self) -> None:
        service, records = self._service()
        with patch.object(service.llm, "generate", return_value=LLMResponse(text="不是 JSON", model="fake")):
            with self.assertRaises(RuntimeError):
                service.generate_storyboard(project=_project(), chapters=[_chapter()], title="短片A")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.error_category, "invalid_json_response")
        self.assertEqual(record.project_id, 5)
        self.assertFalse(record.validation_results["parse_ok"])


if __name__ == "__main__":
    unittest.main()
