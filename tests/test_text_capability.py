from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.capabilities import AdapterError, CapabilityRole
from app.llm import OpenAICompatibleTextLLM, OpenAIResponsesLLM
from app.text_capability import text_model_for_role


class _Settings:
    writer_model = "deepseek-creative"
    utility_model = "deepseek-utility"


class TextCapabilityTests(unittest.TestCase):
    def test_creative_role_resolves_writer_model(self) -> None:
        self.assertEqual(
            text_model_for_role(_Settings(), CapabilityRole.CREATIVE_TEXT),
            "deepseek-creative",
        )

    def test_utility_role_resolves_utility_model(self) -> None:
        self.assertEqual(
            text_model_for_role(_Settings(), CapabilityRole.UTILITY_TEXT),
            "deepseek-utility",
        )

    def test_role_accepts_string_forms(self) -> None:
        self.assertEqual(text_model_for_role(_Settings(), "creative_text"), "deepseek-creative")
        self.assertEqual(text_model_for_role(_Settings(), CapabilityRole.UTILITY_TEXT.value), "deepseek-utility")

    def test_unknown_role_raises_actionable_error(self) -> None:
        with self.assertRaises(AdapterError) as ctx:
            text_model_for_role(_Settings(), CapabilityRole.IMAGE)
        self.assertIn("image", str(ctx.exception))

    def test_missing_model_resolves_empty_without_crash(self) -> None:
        self.assertEqual(text_model_for_role(SimpleNamespace(writer_model="", utility_model=""), CapabilityRole.UTILITY_TEXT), "")


class TextTransportAliasTests(unittest.TestCase):
    def test_legacy_alias_points_to_protocol_transport(self) -> None:
        self.assertIs(OpenAIResponsesLLM, OpenAICompatibleTextLLM)

    def test_transport_accepts_legacy_constructor_args(self) -> None:
        transport = OpenAIResponsesLLM(api_key="k", base_url="https://example.test/v1")
        self.assertIsInstance(transport, OpenAICompatibleTextLLM)
        self.assertEqual(transport.base_url, "https://example.test/v1")


if __name__ == "__main__":
    unittest.main()
