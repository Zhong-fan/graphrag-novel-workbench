"""Typed generation capability contracts.

Business workflows depend on role-specific capability contracts instead of
provider-specific calls. Adapters implement one capability and translate
provider failures into typed :class:`AdapterError` categories. Providers and
model names are replaceable deployment defaults, never domain rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CapabilityRole(str, Enum):
    """Stable roles used by business workflows."""

    CREATIVE_TEXT = "creative_text"
    UTILITY_TEXT = "utility_text"
    IMAGE = "image"
    VIDEO = "video"
    VISION = "vision"
    VOICE_DESIGN = "voice_design"
    SPEECH_SYNTHESIS = "speech_synthesis"
    EMBEDDINGS = "embeddings"


class AdapterErrorCategory(str, Enum):
    """Typed failure categories shared by every capability adapter."""

    CONFIG_OR_AUTH = "config_or_auth"
    INVALID_REQUEST_OR_UNSUPPORTED = "invalid_request_or_unsupported"
    RATE_LIMIT_OR_QUOTA = "rate_limit_or_quota"
    RETRYABLE_PROVIDER_FAILURE = "retryable_provider_failure"
    NETWORK_TIMEOUT = "network_timeout"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    CONTENT_POLICY_REJECTION = "content_policy_rejection"
    LOCAL_MEDIA_FAILURE = "local_media_failure"


RETRYABLE_CATEGORIES = frozenset(
    {
        AdapterErrorCategory.RATE_LIMIT_OR_QUOTA,
        AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
        AdapterErrorCategory.NETWORK_TIMEOUT,
    }
)


class AdapterError(RuntimeError):
    """Provider failure translated into an actionable, sanitized category.

    Adapters translate errors but do not decide business retries; the
    coordinator applies bounded retry policy from ``retryable`` plus the
    category. ``details`` never contains secrets or full authentication
    headers.
    """

    def __init__(
        self,
        category: AdapterErrorCategory | str,
        *,
        safe_message: str,
        provider_code: str | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.category = AdapterErrorCategory(category)
        self.provider_code = provider_code
        self.retryable = self.category in RETRYABLE_CATEGORIES if retryable is None else bool(retryable)
        self.details = dict(details or {})
        super().__init__(safe_message)

    @property
    def safe_message(self) -> str:
        return str(self)


@dataclass(frozen=True)
class CapabilityDeclaration:
    """What an adapter declares it can do for its capability role."""

    role: CapabilityRole
    provider: str
    model: str
    supports_reference_images: bool = False
    supported_input_roles: tuple[str, ...] = ()
    flags: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageGenerationRequest:
    """Typed input for the reference-aware image capability."""

    prompt: str
    width: int = 1024
    height: int = 1024
    reference_images: tuple[str, ...] = ()
    count: int = 1


@dataclass(frozen=True)
class ImageGenerationResult:
    """Typed output plus sanitized trace evidence for one generation."""

    provider: str
    model: str
    kind: str  # "url" or "base64"
    value: str
    provider_ref: str | None = None
    submit_summary: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpeechSynthesisRequest:
    """Typed input for the speech-synthesis capability."""

    text: str
    voice_profile: str
    speed: float = 1.0
    emotion: str = ""
    output_format: str = "mp3"


@dataclass(frozen=True)
class SpeechSynthesisResult:
    """Typed output plus sanitized trace evidence for one synthesis."""

    provider: str
    model: str
    audio_base64: str
    mime_type: str = "audio/mpeg"
    parameters: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceDesignRequest:
    """Typed input for the voice-design capability."""

    character_name: str
    preset_speaker: str = ""
    description: str = ""
    reference_audio_base64: str = ""


@dataclass(frozen=True)
class VoiceDesignResult:
    """Typed output for one voice-design submission.

    A design starts in ``pending_approval`` and must be approved by the
    creator before speech synthesis may use ``voice_ref``.
    """

    provider: str
    model: str
    voice_ref: str
    status: str = "pending_approval"
    parameters: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)


def sanitize_provider_payload(value: Any) -> Any:
    """Trim large or binary provider payloads before they are persisted."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"binary_data_base64", "content_base64"}:
                if isinstance(item, list):
                    cleaned[key] = {"omitted": True, "items": len(item)}
                elif isinstance(item, str):
                    cleaned[key] = {"omitted": True, "chars": len(item)}
                else:
                    cleaned[key] = {"omitted": True}
                continue
            cleaned[key] = sanitize_provider_payload(item)
        return cleaned
    if isinstance(value, list):
        if len(value) > 20:
            preview = [sanitize_provider_payload(item) for item in value[:20]]
            preview.append(f"... ({len(value) - 20} more items)")
            return preview
        return [sanitize_provider_payload(item) for item in value]
    if isinstance(value, str) and len(value) > 1200:
        return value[:1200] + f"... [truncated {len(value) - 1200} chars]"
    return value