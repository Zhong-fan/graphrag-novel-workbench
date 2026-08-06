from __future__ import annotations

import json
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.generation_evidence_service import GenerationEvidence, record_generation_evidence
from app.models import GenerationAttempt


class GenerationEvidenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(bind=engine, future=True)

    def test_record_round_trip_persists_typed_fields(self) -> None:
        with self.SessionLocal() as session:
            record_generation_evidence(
                session,
                evidence=GenerationEvidence(
                    stage="image_first_frame",
                    status="succeeded",
                    provider="jimeng",
                    model="req",
                    project_id=7,
                    shot_id=3,
                    adopted_asset_id=9,
                    prompt_contract_id="storyboard_shots",
                    prompt_version="1.2",
                    rendered_prompt="一只红色的苹果",
                    raw_output='{"shots": []}',
                    parsed_output={"shots": [{"shot_no": 1}]},
                    validation_results={"initial_ok": True},
                    parameters={"width": 1024, "height": 1024},
                    usage={"total_tokens": 42},
                    input_asset_versions={"locked_references": [{"asset_id": 1}]},
                    cost_estimate_usd=0.05,
                    quality_outcome="accepted",
                    provider_ref="task-1",
                ),
            )
            session.commit()
            row = session.scalar(select(GenerationAttempt))
            self.assertIsNotNone(row)
            self.assertEqual(row.stage, "image_first_frame")
            self.assertEqual(row.status, "succeeded")
            self.assertEqual(row.provider, "jimeng")
            self.assertEqual(row.model, "req")
            self.assertEqual(row.project_id, 7)
            self.assertEqual(row.shot_id, 3)
            self.assertEqual(row.adopted_asset_id, 9)
            self.assertEqual(row.prompt_contract_id, "storyboard_shots")
            self.assertEqual(row.prompt_version, "1.2")
            self.assertEqual(row.rendered_prompt, "一只红色的苹果")
            self.assertEqual(json.loads(row.parsed_output)["shots"][0]["shot_no"], 1)
            self.assertTrue(json.loads(row.validation_results)["initial_ok"])
            self.assertEqual(json.loads(row.parameters)["width"], 1024)
            self.assertEqual(json.loads(row.usage)["total_tokens"], 42)
            self.assertEqual(row.cost_estimate_usd, 0.05)
            self.assertEqual(row.quality_outcome, "accepted")
            self.assertEqual(row.provider_ref, "task-1")

    def test_record_redacts_binary_and_truncates_long_text(self) -> None:
        with self.SessionLocal() as session:
            record_generation_evidence(
                session,
                evidence=GenerationEvidence(
                    stage="image_first_frame",
                    status="succeeded",
                    provider="openai_compatible",
                    model="gpt-image-2",
                    parsed_output={"binary_data_base64": ["a" * 5000], "ok": True},
                    raw_output="x" * 300_000,
                    error_message="e" * 300_000,
                ),
            )
            session.commit()
            row = session.scalar(select(GenerationAttempt))
            parsed = json.loads(row.parsed_output)
            self.assertEqual(parsed["binary_data_base64"], {"omitted": True, "items": 1})
            self.assertTrue(parsed["ok"])
            self.assertLessEqual(len(row.raw_output), 200_000)
            self.assertLessEqual(len(row.error_message), 200_000)

    def test_record_failed_attempt_keeps_error_category(self) -> None:
        with self.SessionLocal() as session:
            record_generation_evidence(
                session,
                evidence=GenerationEvidence(
                    stage="cost_gate",
                    status="blocked",
                    provider="ark_seedance",
                    model="doubao-seedance-2-0-mini",
                    project_id=1,
                    cost_estimate_usd=12.34,
                    error_category="budget_confirmation_required",
                    error_message="估算成本超过确认阈值。",
                ),
            )
            session.commit()
            row = session.scalar(select(GenerationAttempt))
            self.assertEqual(row.status, "blocked")
            self.assertEqual(row.error_category, "budget_confirmation_required")
            self.assertEqual(row.cost_estimate_usd, 12.34)


if __name__ == "__main__":
    unittest.main()
