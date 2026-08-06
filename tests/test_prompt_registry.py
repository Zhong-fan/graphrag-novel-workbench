from __future__ import annotations

import unittest

from app.prompt_registry import (
    PROMPT_REGISTRY,
    STORYBOARD_IMAGE_FIRST_CONTRACT,
    STORYBOARD_SHOTS_CONTRACT,
    PromptContract,
    get_prompt_contract,
    register_prompt,
)
from app.prompt_validation import validate_storyboard_payload


class PromptRegistryTests(unittest.TestCase):
    def test_known_contracts_registered(self) -> None:
        self.assertIn("storyboard.shots.v1", PROMPT_REGISTRY)
        self.assertIn("storyboard.image_first.v1", PROMPT_REGISTRY)
        self.assertIs(get_prompt_contract("storyboard.shots.v1"), STORYBOARD_SHOTS_CONTRACT)
        self.assertIs(get_prompt_contract("storyboard.image_first.v1"), STORYBOARD_IMAGE_FIRST_CONTRACT)

    def test_contract_fields_complete(self) -> None:
        for contract in (STORYBOARD_SHOTS_CONTRACT, STORYBOARD_IMAGE_FIRST_CONTRACT):
            self.assertEqual(contract.version, "v1")
            self.assertEqual(contract.model_contract, "strict-json-object")
            self.assertTrue(contract.role)
            self.assertTrue(contract.repair_instruction.strip())
            self.assertTrue(callable(contract.builder))
            self.assertIs(contract.validator, validate_storyboard_payload)

    def test_get_unknown_contract_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            get_prompt_contract("no.such.prompt.v9")

    def test_duplicate_registration_raises(self) -> None:
        duplicate = PromptContract(
            prompt_id="storyboard.shots.v1",
            version="v2",
            role="storyboard_director",
            model_contract="strict-json-object",
            builder=STORYBOARD_SHOTS_CONTRACT.builder,
            validator=STORYBOARD_SHOTS_CONTRACT.validator,
            repair_instruction="x",
        )
        with self.assertRaises(RuntimeError):
            register_prompt(duplicate)


if __name__ == "__main__":
    unittest.main()