import unittest

from pydantic import ValidationError

from app.contracts import StoryboardImportRequest


class StoryboardImportContractTests(unittest.TestCase):
    def test_accepts_documented_json_contract(self) -> None:
        payload = StoryboardImportRequest.model_validate(
            {
                "title": "第一集分镜",
                "source_chapter_ids": [1],
                "shots": [{"shot_no": 1, "visual_prompt": "雨夜街口，主角回头。", "duration_seconds": 4}],
            }
        )
        self.assertEqual(payload.shots[0].visual_prompt, "雨夜街口，主角回头。")
        self.assertEqual(payload.shots[0].duration_seconds, 4)

    def test_rejects_missing_visual_prompt(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            StoryboardImportRequest.model_validate({"title": "无效", "shots": [{"duration_seconds": 4}]})
        self.assertIn("visual_prompt", str(ctx.exception))

    def test_rejects_invalid_duration(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            StoryboardImportRequest.model_validate({"title": "无效", "shots": [{"visual_prompt": "画面", "duration_seconds": 0}]})
        self.assertIn("duration_seconds", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
