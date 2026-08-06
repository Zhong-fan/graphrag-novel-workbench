from __future__ import annotations

import unittest

from app.prompt_validation import validate_storyboard_payload


def _valid_payload() -> dict:
    return {
        "title": "短片A",
        "summary": "概述",
        "shots": [
            {
                "shot_no": 1,
                "narration_text": "雨光落下。",
                "visual_prompt": "日系动画电影，雨夜城市街口，通透蓝绿色光影，一束光穿过雨幕。",
                "character_refs": [{"character_card_id": 1, "name": "阿离", "role": "女主"}],
                "scene_refs": [{"name": "雨夜街口", "role": "开场场景"}],
                "continuity": {
                    "shot_type": "new",
                    "depends_on_shot_no": None,
                    "first_frame_source": "generated",
                    "requires_i2v": True,
                    "end_frame_usage": "none",
                    "camera_motion": "无",
                    "character_state_delta": "",
                    "continuity_constraints": [],
                },
                "audio_script": {"dialogues": [], "narration": "", "music_cue": ""},
                "duration_seconds": 5,
            }
        ],
    }


class PromptValidationTests(unittest.TestCase):
    def test_valid_payload_passes(self) -> None:
        result = validate_storyboard_payload(_valid_payload())
        self.assertTrue(result.ok, result.error_text)
        self.assertEqual(result.errors, [])

    def test_lenient_fixture_passes(self) -> None:
        payload = {
            "title": "雨夜追光 15 秒",
            "summary": "图片先行短片。",
            "shots": [
                {
                    "shot_no": 1,
                    "visual_prompt": "二维动画，雨夜街口，光束穿过雨幕。",
                    "character_refs": [],
                    "scene_refs": [{"name": "雨夜街口", "role": "开场"}],
                    "continuity": {"shot_type": "new", "first_frame_source": "generated", "requires_i2v": True},
                    "audio_script": {},
                    "duration_seconds": 5,
                }
            ],
        }
        result = validate_storyboard_payload(payload)
        self.assertTrue(result.ok, result.error_text)

    def test_non_dict_payload_fails(self) -> None:
        result = validate_storyboard_payload([{"shot_no": 1}])
        self.assertFalse(result.ok)
        self.assertIn("必须是 JSON 对象", result.error_text)

    def test_missing_title_and_summary_fails(self) -> None:
        payload = _valid_payload()
        payload["title"] = ""
        payload["summary"] = "   "
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertIn("title", result.error_text)
        self.assertIn("summary", result.error_text)

    def test_empty_shots_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"] = []
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertIn("shots", result.error_text)

    def test_non_positive_shot_no_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"][0]["shot_no"] = 0
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertIn("shot_no", result.error_text)

    def test_blank_visual_prompt_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"][0]["visual_prompt"] = "  "
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertIn("visual_prompt", result.error_text)

    def test_continuity_not_dict_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"][0]["continuity"] = "新镜头"
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("continuity" in error for error in result.errors))

    def test_requires_i2v_missing_fails(self) -> None:
        payload = _valid_payload()
        del payload["shots"][0]["continuity"]["requires_i2v"]
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("requires_i2v" in error for error in result.errors))

    def test_character_refs_not_list_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"][0]["character_refs"] = {"name": "阿离"}
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("character_refs" in error for error in result.errors))

    def test_audio_script_not_dict_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"][0]["audio_script"] = "对白脚本"
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("audio_script" in error for error in result.errors))

    def test_shot_not_object_fails(self) -> None:
        payload = _valid_payload()
        payload["shots"].append("第二镜头")
        result = validate_storyboard_payload(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("shots[1]" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()