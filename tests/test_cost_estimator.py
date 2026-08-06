from __future__ import annotations

import unittest

from app.cost_estimator import check_cost_gate, estimate_video_generation_cost


class CostEstimatorTests(unittest.TestCase):
    def test_estimate_scales_with_shots_resolution_and_duration(self) -> None:
        low = estimate_video_generation_cost(shot_count=1, duration_seconds=5, resolution="720p", model="m")
        high = estimate_video_generation_cost(shot_count=10, duration_seconds=10, resolution="4k", model="m")
        self.assertGreater(high.estimated_cost_usd, low.estimated_cost_usd * 10)
        self.assertEqual(low.currency, "USD")
        self.assertEqual(low.basis["shot_count"], 1)
        self.assertEqual(low.basis["resolution"], "720p")
        self.assertEqual(low.basis["model"], "m")

    def test_estimate_basis_records_inputs(self) -> None:
        estimate = estimate_video_generation_cost(
            shot_count=3, duration_seconds=5, resolution="1080p", model="doubao-seedance-2-0-mini"
        )
        self.assertEqual(estimate.basis["model"], "doubao-seedance-2-0-mini")
        self.assertEqual(estimate.basis["duration_seconds"], 5)
        expected = round(0.05 * 1.4 * 1.0, 4) * 3
        self.assertAlmostEqual(estimate.estimated_cost_usd, expected, places=4)

    def test_gate_disabled_at_zero_threshold(self) -> None:
        estimate = estimate_video_generation_cost(shot_count=100, duration_seconds=20, resolution="4k", model="m")
        result = check_cost_gate(estimate=estimate, confirmation_threshold_usd=0.0)
        self.assertTrue(result.approved)
        self.assertFalse(result.needs_confirmation)

    def test_gate_requires_confirmation_above_threshold(self) -> None:
        estimate = estimate_video_generation_cost(shot_count=10, duration_seconds=5, resolution="1080p", model="m")
        result = check_cost_gate(estimate=estimate, confirmation_threshold_usd=0.05)
        self.assertFalse(result.approved)
        self.assertTrue(result.needs_confirmation)
        self.assertIn("超过确认阈值", result.reason)

    def test_gate_approves_below_threshold(self) -> None:
        estimate = estimate_video_generation_cost(shot_count=1, duration_seconds=5, resolution="720p", model="m")
        result = check_cost_gate(estimate=estimate, confirmation_threshold_usd=0.5)
        self.assertTrue(result.approved)
        self.assertFalse(result.needs_confirmation)


if __name__ == "__main__":
    unittest.main()