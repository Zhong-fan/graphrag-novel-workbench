from __future__ import annotations

import unittest

from app.prompt_registry import PROMPT_REGISTRY, get_prompt_contract
from app.prompt_regression_corpus import PROMPT_REGRESSION_CORPUS


class PromptRegressionCorpusTests(unittest.TestCase):
    """语料防护：注册表版本、构建器、校验器与提示词关键内容不得回归强制场景。"""

    def test_all_corpus_contracts_still_registered_with_same_version(self) -> None:
        for case in PROMPT_REGRESSION_CORPUS:
            contract = get_prompt_contract(case.prompt_id)
            self.assertEqual(contract.version, case.version, case.prompt_id)

    def test_mandatory_cases_build_and_validate(self) -> None:
        for case in PROMPT_REGRESSION_CORPUS:
            contract = get_prompt_contract(case.prompt_id)
            with self.subTest(prompt_id=case.prompt_id):
                system_prompt, prompt = contract.builder(**case.build_kwargs)
                self.assertTrue(system_prompt.strip())
                self.assertTrue(prompt.strip())
                for marker in case.mandatory_prompt_markers:
                    self.assertIn(marker, system_prompt + prompt, marker)
                result = contract.validator(case.golden_payload)
                self.assertTrue(result.ok, result.error_text)

    def test_registry_has_no_unknown_contracts_beyond_corpus(self) -> None:
        # 新契约必须先在语料里注册强制场景，防止悄悄新增无法防护的提示词。
        for prompt_id in PROMPT_REGISTRY:
            self.assertIn(prompt_id, {case.prompt_id for case in PROMPT_REGRESSION_CORPUS}, prompt_id)


if __name__ == "__main__":
    unittest.main()
