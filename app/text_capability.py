from __future__ import annotations

from typing import Any

from .capabilities import AdapterError, AdapterErrorCategory, CapabilityRole


def text_model_for_role(settings: Any, role: CapabilityRole | str) -> str:
    """Resolve the configured deployment model for a text capability role.

    Central role-to-model mapping: creative text uses the writer model and
    utility text uses the utility model, both required deployment settings
    (``CHENFLOW_WRITER_MODEL`` / ``CHENFLOW_UTILITY_MODEL``). No GPT or
    DeepSeek model name is hardcoded here: providers and models are
    replaceable deployment defaults, and missing settings fail at startup
    before any role is used.
    """
    normalized = CapabilityRole(role)
    if normalized == CapabilityRole.CREATIVE_TEXT:
        return getattr(settings, "writer_model", "") or ""
    if normalized == CapabilityRole.UTILITY_TEXT:
        return getattr(settings, "utility_model", "") or ""
    raise AdapterError(
        AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
        safe_message=f"文本能力角色 {normalized.value} 不支持模型解析。",
    )
