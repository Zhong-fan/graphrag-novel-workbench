from __future__ import annotations

from typing import Any, Callable

from .config import Settings
from .json_utils import parse_json_object
from .generation_evidence_service import GenerationEvidence
from .llm import OpenAICompatibleTextLLM
from .capabilities import CapabilityRole
from .text_capability import text_model_for_role
from .models import NovelChapter, Project
from .prompt_registry import (
    STORYBOARD_IMAGE_FIRST_CONTRACT,
    STORYBOARD_SHOTS_CONTRACT,
    PromptContract,
    build_repair_prompt,
)


class StoryboardService:
    def __init__(
        self,
        settings: Settings,
        *,
        evidence_sink: Callable[[GenerationEvidence], None] | None = None,
    ) -> None:
        if settings.llm_mode != "openai" or not settings.openai_api_key:
            raise RuntimeError("当前项目只支持真实模型模式。")
        self.settings = settings
        self.evidence_sink = evidence_sink
        self.llm = OpenAICompatibleTextLLM(
            settings.openai_api_key,
            settings.openai_base_url,
            use_system_proxy=settings.openai_use_system_proxy,
            use_responses=settings.llm_use_responses,
            stream_responses=settings.llm_stream_responses,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            retry_max_sleep_seconds=settings.llm_retry_max_sleep_seconds,
        )

    def generate_storyboard(
        self,
        *,
        project: Project,
        chapters: list[NovelChapter],
        title: str,
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._generate_with_contract(
            STORYBOARD_SHOTS_CONTRACT,
            build_kwargs={
                "project": project,
                "chapters": chapters,
                "title": title,
                "context_pack_inputs": context_pack_inputs,
            },
        )

    def generate_image_first_storyboard(
        self,
        *,
        project: Project,
        title: str,
        reference_video_brief: str,
        reference_image_notes: list[str],
        context_pack_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._generate_with_contract(
            STORYBOARD_IMAGE_FIRST_CONTRACT,
            build_kwargs={
                "project": project,
                "title": title,
                "reference_video_brief": reference_video_brief,
                "reference_image_notes": reference_image_notes,
                "context_pack_inputs": context_pack_inputs,
            },
        )

    def _generate_with_contract(
        self,
        contract: PromptContract,
        *,
        build_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        # 契约边界：每个失败阶段只做一次定向修复，之后失败抛错并落失败证据。
        project = build_kwargs.get("project")
        project_id = getattr(project, "id", None)
        system_prompt, prompt = contract.builder(**build_kwargs)
        payload, raw_text = self._request_payload(contract, system_prompt, prompt, project_id=project_id)
        result = contract.validator(payload)
        if result.ok:
            self._record_evidence(
                contract=contract,
                project_id=project_id,
                status="succeeded",
                rendered_prompt=prompt,
                raw_output=raw_text,
                parsed_output=payload,
                validation_results={"initial_ok": True},
                quality_outcome="adopted",
            )
            return payload
        repair_system, repair_prompt = build_repair_prompt(contract=contract, payload=payload, result=result)
        repaired, repaired_raw = self._request_payload(contract, repair_system, repair_prompt, project_id=project_id)
        repaired_result = contract.validator(repaired)
        if repaired_result.ok:
            self._record_evidence(
                contract=contract,
                project_id=project_id,
                status="succeeded",
                rendered_prompt=repair_prompt,
                raw_output=repaired_raw,
                parsed_output=repaired,
                validation_results={"initial_ok": False, "repair_attempted": True, "final_ok": True},
                quality_outcome="adopted",
            )
            return repaired
        self._record_evidence(
            contract=contract,
            project_id=project_id,
            status="failed",
            rendered_prompt=repair_prompt,
            raw_output=repaired_raw,
            parsed_output=repaired,
            validation_results={
                "initial_ok": False,
                "repair_attempted": True,
                "final_ok": False,
                "error_text": repaired_result.error_text,
            },
            error_category="validation_failed",
            error_message=f"{contract.prompt_id} 校验失败：{repaired_result.error_text}",
        )
        raise RuntimeError(f"{contract.prompt_id} 校验失败：{repaired_result.error_text}")

    def _record_evidence(
        self,
        *,
        contract: PromptContract,
        project_id: int | None,
        status: str,
        rendered_prompt: str,
        raw_output: str,
        parsed_output: dict[str, Any],
        validation_results: dict[str, Any],
        quality_outcome: str = "",
        error_category: str = "",
        error_message: str = "",
    ) -> None:
        if self.evidence_sink is None:
            return
        self.evidence_sink(
            GenerationEvidence(
                stage=contract.prompt_id,
                status=status,
                provider="openai",
                model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
                project_id=project_id,
                prompt_contract_id=contract.prompt_id,
                prompt_version=contract.version,
                rendered_prompt=rendered_prompt,
                raw_output=raw_output,
                parsed_output=parsed_output,
                validation_results=validation_results,
                quality_outcome=quality_outcome,
                error_category=error_category,
                error_message=error_message,
            )
        )

    def _request_payload(
        self,
        contract: PromptContract,
        system_prompt: str,
        prompt: str,
        *,
        project_id: int | None,
    ) -> tuple[dict[str, Any], str]:
        response = self.llm.generate(
            model=text_model_for_role(self.settings, CapabilityRole.UTILITY_TEXT),
            system_prompt=system_prompt,
            user_prompt=prompt,
            json_mode=True,
        )
        try:
            payload = parse_json_object(response.text)
        except RuntimeError:
            self._record_evidence(
                contract=contract,
                project_id=project_id,
                status="failed",
                rendered_prompt=prompt,
                raw_output=response.text,
                parsed_output={},
                validation_results={"initial_ok": False, "parse_ok": False},
                error_category="invalid_json_response",
                error_message=f"{contract.prompt_id} 模型没有返回可解析的 JSON。",
            )
            raise
        if not isinstance(payload, dict):
            self._record_evidence(
                contract=contract,
                project_id=project_id,
                status="failed",
                rendered_prompt=prompt,
                raw_output=response.text,
                parsed_output={},
                validation_results={"initial_ok": False, "parse_ok": False},
                error_category="invalid_json_response",
                error_message=f"{contract.prompt_id} 模型没有返回 JSON 对象。",
            )
            raise RuntimeError(f"{contract.prompt_id} 模型没有返回 JSON 对象。")
        return payload, response.text