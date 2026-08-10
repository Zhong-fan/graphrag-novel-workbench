"""MiniMax OpenAI-compatible text capability adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import AdapterError, AdapterErrorCategory, CapabilityDeclaration, CapabilityRole, sanitize_provider_payload
from .minimax_client import MiniMaxClient


@dataclass(frozen=True)
class MiniMaxTextResult:
    provider: str
    model: str
    text: str
    reasoning: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = None  # type: ignore[assignment]
    sensitive: bool = False
    response_summary: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.usage is None:
            object.__setattr__(self, "usage", {})
        if self.response_summary is None:
            object.__setattr__(self, "response_summary", {})


class MiniMaxTextAdapter:
    def __init__(self, *, api_key: str, base_url: str = "https://api.minimax.io", model: str = "MiniMax-M3", timeout_seconds: int = 180, client: MiniMaxClient | None = None) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else "https://api.minimax.io"
        self._model = model or "MiniMax-M3"
        self._timeout_seconds = timeout_seconds
        self._client = client

    @classmethod
    def from_settings(cls, settings: Any, *, role: CapabilityRole = CapabilityRole.CREATIVE_TEXT) -> "MiniMaxTextAdapter":
        model = getattr(settings, "minimax_text_model", "MiniMax-M3") or "MiniMax-M3"
        return cls(api_key=getattr(settings, "minimax_api_key", "") or "", base_url=getattr(settings, "minimax_base_url", "https://api.minimax.io") or "https://api.minimax.io", model=model, timeout_seconds=getattr(settings, "minimax_timeout_seconds", 180) or 180)

    def declaration(self, role: CapabilityRole = CapabilityRole.CREATIVE_TEXT) -> CapabilityDeclaration:
        return CapabilityDeclaration(role=role, provider="minimax", model=self._model, flags={"protocol": "openai_chat_completions"})

    def generate(self, *, system_prompt: str, user_prompt: str, json_mode: bool = False) -> MiniMaxTextResult:
        client = self._client or MiniMaxClient(api_key=self._api_key, base_url=f"{self._base_url}/v1", timeout_seconds=self._timeout_seconds)
        payload: dict[str, Any] = {"model": self._model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = client.post_json("/chat/completions", payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 文本接口没有返回 choices。", details={"response": sanitize_provider_payload(response)})
        message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax 文本接口没有返回文本内容。", details={"response": sanitize_provider_payload(response)})
        return MiniMaxTextResult(provider="minimax", model=str(response.get("model") or self._model), text=content, reasoning=str(message.get("reasoning_content") or ""), finish_reason=str(choices[0].get("finish_reason") or ""), usage=dict(response.get("usage") or {}), sensitive=bool(response.get("base_resp", {}).get("status_code") == 1008), response_summary=sanitize_provider_payload({"model": response.get("model"), "finish_reason": choices[0].get("finish_reason")}))
