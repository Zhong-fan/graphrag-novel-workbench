from __future__ import annotations

import base64
import binascii
import http.client
import json
import urllib.error
import urllib.request
import uuid
from abc import ABC, abstractmethod
from typing import Any

from .capabilities import (
    AdapterError,
    AdapterErrorCategory,
    CapabilityDeclaration,
    CapabilityRole,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    VoiceDesignRequest,
    VoiceDesignResult,
    sanitize_provider_payload,
)
from .minimax_client import MiniMaxClient

DEFAULT_REQUEST_TIMEOUT_SECONDS = 180
DOUBAO_DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DOUBAO_DEFAULT_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
_DOUBAO_SUCCESS_CODES = (None, 0, 20000000)


class SpeechSynthesisCapability(ABC):
    """Port used by the voice workflow for text-to-speech synthesis."""

    role = CapabilityRole.SPEECH_SYNTHESIS

    @abstractmethod
    def declaration(self) -> CapabilityDeclaration:
        """Declare provider, model, and capability flags."""

    @abstractmethod
    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        """Synthesize one audio clip and return sanitized trace evidence."""


class VoiceDesignCapability(ABC):
    """Port used by the voice workflow to design a character voice.

    A design only produces a candidate reference; approval is a separate
    workflow state owned by the voice-design service, never by synthesis.
    """

    role = CapabilityRole.VOICE_DESIGN

    @abstractmethod
    def declaration(self) -> CapabilityDeclaration:
        """Declare provider, model, and design capabilities."""

    @abstractmethod
    def design(self, request: VoiceDesignRequest) -> VoiceDesignResult:
        """Submit one voice design and return a pending approval reference."""


class MiniMaxVoiceDesignAdapter(VoiceDesignCapability):
    """MiniMax Voice Design; the returned voice remains pending approval."""

    def __init__(self, *, api_key: str, base_url: str = "https://api.minimax.io", timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else "https://api.minimax.io"
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, settings: Any) -> "MiniMaxVoiceDesignAdapter":
        return cls(api_key=getattr(settings, "minimax_api_key", "") or "", base_url=getattr(settings, "minimax_base_url", "https://api.minimax.io") or "https://api.minimax.io", timeout_seconds=getattr(settings, "minimax_timeout_seconds", 180) or 180)

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(role=self.role, provider="minimax", model="voice_design", flags={"approval_required": True, "voice_clone": False})

    def design(self, request: VoiceDesignRequest) -> VoiceDesignResult:
        prompt = request.description.strip()
        preview_text = (request.preview_text or request.character_name).strip()
        if not prompt or not preview_text:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax Voice Design 需要声音描述和试听文本。", retryable=False)
        if len(preview_text) > 500:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax Voice Design 试听文本最多 500 个字符。", provider_code="preview_text", retryable=False)
        client = MiniMaxClient(api_key=self._api_key, base_url=self._base_url, timeout_seconds=self._timeout_seconds)
        data = client.post_json("/v1/voice_design", {"prompt": prompt, "preview_text": preview_text})
        voice_ref = str(data.get("voice_id") or "")
        if not voice_ref:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax Voice Design 没有返回 voice_id。", details={"response": sanitize_provider_payload(data)})
        return VoiceDesignResult(provider="minimax", model="voice_design", voice_ref=voice_ref, status="pending_approval", parameters={"character_name": request.character_name}, result_summary=sanitize_provider_payload({"voice_id": voice_ref, "has_trial_audio": bool(data.get("trial_audio"))}))


class MiniMaxSpeechSynthesisAdapter(SpeechSynthesisCapability):
    def __init__(self, *, api_key: str, base_url: str = "https://api.minimax.io", model: str = "speech-2.8-hd", timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/") if base_url else "https://api.minimax.io"
        self._model = model or "speech-2.8-hd"
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, settings: Any) -> "MiniMaxSpeechSynthesisAdapter":
        return cls(api_key=getattr(settings, "minimax_api_key", "") or "", base_url=getattr(settings, "minimax_base_url", "https://api.minimax.io") or "https://api.minimax.io", model=getattr(settings, "minimax_voice_model", "speech-2.8-hd") or "speech-2.8-hd", timeout_seconds=getattr(settings, "minimax_timeout_seconds", 180) or 180)

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(role=self.role, provider="minimax", model=self._model, flags={"protocol": "t2a_v2", "long_text_async": True})

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        if not request.text.strip() or len(request.text) > 10000:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax T2A 文本必须为 1-10000 个字符。", provider_code="text_length", retryable=False)
        voice_id = request.voice_profile.strip()
        if not voice_id:
            raise AdapterError(AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED, safe_message="MiniMax T2A 需要 voice_profile。", provider_code="voice_id", retryable=False)
        payload = {"model": self._model, "text": request.text, "stream": False, "output_format": "hex", "voice_setting": {"voice_id": voice_id, "speed": request.speed, "vol": 1, "pitch": 0}, "audio_setting": {"format": request.output_format, "sample_rate": 32000, "channel": 1}}
        data = MiniMaxClient(api_key=self._api_key, base_url=self._base_url, timeout_seconds=self._timeout_seconds).post_json("/v1/t2a_v2", payload)
        audio_value = ((data.get("data") or {}).get("audio") if isinstance(data.get("data"), dict) else "")
        if not isinstance(audio_value, str) or not audio_value:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax T2A 没有返回音频。", details={"response": sanitize_provider_payload(data)})
        try:
            audio_bytes = binascii.unhexlify(audio_value)
        except (binascii.Error, ValueError) as exc:
            raise AdapterError(AdapterErrorCategory.INVALID_PROVIDER_RESPONSE, safe_message="MiniMax T2A 返回的音频不是合法 hex。", retryable=False) from exc
        return SpeechSynthesisResult(provider="minimax", model=self._model, audio_base64=base64.b64encode(audio_bytes).decode("ascii"), mime_type=f"audio/{request.output_format}", parameters={"voice_id": voice_id, "sample_rate": 32000}, result_summary=sanitize_provider_payload({"bytes": len(audio_bytes), "extra_info": data.get("extra_info")}))


def _map_http_error(exc: urllib.error.HTTPError) -> AdapterError:
    status = exc.code
    body = ""
    try:
        body = exc.read().decode("utf-8", "replace")[:2000]
    except Exception:
        pass
    lowered = body.lower()
    if "content_policy" in lowered or "safety" in lowered:
        category = AdapterErrorCategory.CONTENT_POLICY_REJECTION
    elif status == 429:
        category = AdapterErrorCategory.RATE_LIMIT_OR_QUOTA
    elif status in (401, 403):
        category = AdapterErrorCategory.CONFIG_OR_AUTH
    elif 400 <= status < 500:
        category = AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED
    else:
        category = AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE
    return AdapterError(
        category,
        safe_message=f"语音接口调用失败（HTTP {status}）。",
        provider_code=str(status),
        details={"status_code": status, "response_preview": body[:500]},
    )


def _map_network_error(exc: Exception) -> AdapterError:
    if isinstance(exc, TimeoutError):
        return AdapterError(
            AdapterErrorCategory.NETWORK_TIMEOUT,
            safe_message="语音接口请求超时。",
            details={"error_type": type(exc).__name__},
        )
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return AdapterError(
                AdapterErrorCategory.NETWORK_TIMEOUT,
                safe_message="语音接口请求超时。",
                details={"error_type": type(reason).__name__},
            )
        return AdapterError(
            AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
            safe_message="语音接口网络请求失败。",
            details={"error_type": type(reason).__name__ if reason is not None else "unknown"},
        )
    return AdapterError(
        AdapterErrorCategory.RETRYABLE_PROVIDER_FAILURE,
        safe_message="语音接口调用失败。",
        details={"error_type": type(exc).__name__},
    )


def _decode_base64_padded(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, validate=False)


class DoubaoSpeechSynthesisAdapter(SpeechSynthesisCapability):
    """Doubao TTS 2.0 unidirectional speech synthesis.

    ``X-Api-Resource-Id`` selects the TTS version (default ``seed-tts-2.0``)
    and an optional ``X-Api-Model`` overrides the voice model. The endpoint
    returns newline-delimited JSON chunks, each carrying base64 audio data
    that must be concatenated in order.
    """

    def __init__(
        self,
        *,
        app_id: str,
        access_key: str,
        resource_id: str,
        endpoint: str,
        speaker: str,
        model: str = "",
        sample_rate: int = 24000,
        timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._app_id = app_id or ""
        self._access_key = access_key or ""
        self._resource_id = (resource_id or "").strip() or DOUBAO_DEFAULT_RESOURCE_ID
        self._endpoint = (endpoint or "").strip() or DOUBAO_DEFAULT_ENDPOINT
        self._speaker = speaker or ""
        self._model = model or ""
        self._sample_rate = int(sample_rate or 24000)
        self._timeout_seconds = int(timeout_seconds or DEFAULT_REQUEST_TIMEOUT_SECONDS)

    @classmethod
    def from_settings(cls, settings: Any) -> "DoubaoSpeechSynthesisAdapter":
        return cls(
            app_id=getattr(settings, "volcengine_tts_app_id", "") or "",
            access_key=(getattr(settings, "volcengine_tts_access_key", "") or "")
            or (getattr(settings, "volcengine_tts_api_key", "") or ""),
            resource_id=(getattr(settings, "volcengine_tts_resource_id", "") or "") or DOUBAO_DEFAULT_RESOURCE_ID,
            endpoint=(getattr(settings, "volcengine_tts_endpoint", "") or "") or DOUBAO_DEFAULT_ENDPOINT,
            speaker=(getattr(settings, "volcengine_tts_speaker", "") or ""),
            model=(getattr(settings, "volcengine_tts_model", "") or ""),
            sample_rate=getattr(settings, "volcengine_tts_sample_rate", 24000) or 24000,
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=self.role,
            provider="volcengine_doubao",
            model=self._model or self._resource_id,
            flags={"tts_version": "2.0"},
        )

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        self._require_config()
        speaker = request.voice_profile.strip() or self._speaker
        payload = {
            "user": {"uid": "chenflow"},
            "req_params": {
                "text": request.text,
                "speaker": speaker,
                "audio_params": {
                    "format": request.output_format,
                    "sample_rate": self._sample_rate,
                    "enable_timestamp": False,
                },
                "additions": self._additions(speed=request.speed, emotion=request.emotion),
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Api-App-Id": self._app_id,
            "X-Api-Access-Key": self._access_key,
            "X-Api-Resource-Id": self._resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
        }
        if self._model:
            headers["X-Api-Model"] = self._model
        http_request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise _map_network_error(exc) from exc
        audio_bytes, chunks = self._extract_audio(content)
        return SpeechSynthesisResult(
            provider="volcengine_doubao",
            model=self.declaration().model,
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            mime_type="audio/mpeg",
            parameters={
                "speaker": speaker,
                "sample_rate": self._sample_rate,
                "resource_id": self._resource_id,
                "model": self._model,
            },
            result_summary=sanitize_provider_payload({"chunks": chunks, "bytes": len(audio_bytes)}),
        )

    def _extract_audio(self, content: bytes) -> tuple[bytes, int]:
        """Concatenate base64 audio chunks from newline-delimited JSON.

        Each line must carry an accepted ``code`` and a base64 ``data``
        string; the whole body is also accepted as a single JSON object so
        both streaming and non-streaming endpoints parse.
        """
        chunks: list[bytes] = []
        last_error = ""
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line.decode("utf-8"))
            except Exception as exc:
                last_error = str(exc)
                continue
            code = payload.get("code")
            if code not in _DOUBAO_SUCCESS_CODES:
                raise AdapterError(
                    AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                    safe_message=f"豆包语音接口返回错误码 {code}。",
                    provider_code=str(code),
                    details={"response_preview": sanitize_provider_payload(payload)},
                )
            data = payload.get("data")
            if isinstance(data, str) and data:
                chunks.append(_decode_base64_padded(data))
        if chunks:
            audio = b"".join(chunks)
            if audio:
                return audio, len(chunks)
        try:
            payload = json.loads(content.decode("utf-8"))
        except Exception as exc:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="豆包语音接口返回无法解析的响应。",
                details={"parse_error": last_error or str(exc)},
            ) from exc
        data = payload.get("data")
        if isinstance(data, str) and data:
            audio = _decode_base64_padded(data)
            if audio:
                return audio, 1
        raise AdapterError(
            AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
            safe_message="豆包语音接口没有返回音频 data。",
            details={"response_preview": sanitize_provider_payload(payload)},
        )

    def _additions(self, *, speed: float, emotion: str) -> dict[str, str]:
        additions: dict[str, str] = {}
        if speed and abs(speed - 1.0) > 0.001:
            additions["speed_ratio"] = f"{speed:.2f}"
        if emotion.strip():
            additions["emotion"] = emotion.strip()
        return additions

    def _require_config(self) -> None:
        missing: list[str] = []
        if not self._app_id:
            missing.append("VOLCENGINE_TTS_APP_ID")
        if not self._access_key:
            missing.append("VOLCENGINE_TTS_ACCESS_KEY 或 VOLCENGINE_TTS_API_KEY")
        if not self._speaker:
            missing.append("VOLCENGINE_TTS_SPEAKER")
        if missing:
            raise AdapterError(
                AdapterErrorCategory.CONFIG_OR_AUTH,
                safe_message="豆包语音合成配置缺失：" + "、".join(missing),
            )


class OpenAICompatibleSpeechSynthesisAdapter(SpeechSynthesisCapability):
    """OpenAI-compatible ``/audio/speech`` synthesis adapter.

    Kept as the non-Doubao fallback transport so the voice workflow keeps a
    provider-replaceable deployment default without domain logic.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        voice: str,
        timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url or ""
        self._model = model or ""
        self._voice = voice or ""
        self._timeout_seconds = int(timeout_seconds or DEFAULT_REQUEST_TIMEOUT_SECONDS)

    @classmethod
    def from_settings(cls, settings: Any) -> "OpenAICompatibleSpeechSynthesisAdapter":
        return cls(
            api_key=getattr(settings, "tts_api_key", "") or "",
            base_url=getattr(settings, "tts_base_url", "") or "",
            model=getattr(settings, "tts_model", "") or "",
            voice=getattr(settings, "tts_voice", "") or "",
        )

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(role=self.role, provider="openai_compatible", model=self._model)

    def synthesize(self, request: SpeechSynthesisRequest) -> SpeechSynthesisResult:
        self._require_config()
        payload: dict[str, Any] = {
            "model": self._model,
            "voice": request.voice_profile.strip() or self._voice,
            "input": request.text,
            "response_format": request.output_format,
        }
        if request.speed and abs(request.speed - 1.0) > 0.001:
            payload["speed"] = request.speed
        if request.emotion.strip():
            payload["instructions"] = f"Use a {request.emotion.strip()} narrator delivery."
        http_request = urllib.request.Request(
            f"{self._base_url.rstrip('/')}/audio/speech",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise _map_network_error(exc) from exc
        if not content:
            raise AdapterError(
                AdapterErrorCategory.INVALID_PROVIDER_RESPONSE,
                safe_message="TTS 接口返回空音频。",
            )
        return SpeechSynthesisResult(
            provider="openai_compatible",
            model=self._model,
            audio_base64=base64.b64encode(content).decode("ascii"),
            mime_type="audio/mpeg",
            parameters={"voice": payload["voice"], "format": payload["response_format"]},
            result_summary={"bytes": len(content)},
        )

    def _require_config(self) -> None:
        missing: list[str] = []
        if not self._api_key:
            missing.append("CHENFLOW_TTS_API_KEY")
        if not self._base_url:
            missing.append("CHENFLOW_TTS_BASE_URL")
        if not self._model:
            missing.append("CHENFLOW_TTS_MODEL")
        if not self._voice:
            missing.append("CHENFLOW_TTS_VOICE")
        if missing:
            raise AdapterError(
                AdapterErrorCategory.CONFIG_OR_AUTH,
                safe_message="语音合成配置缺失：" + "、".join(missing),
            )


class DoubaoPresetVoiceDesignAdapter(VoiceDesignCapability):
    """Doubao preset voice design: select a curated preset speaker.

    Reference-audio voice cloning is deliberately not implemented because the
    provider clone contract is unverified; requesting it raises an actionable
    error instead of silently faking a designed clone. The design result is
    always ``pending_approval``; synthesis must wait for creator approval.
    """

    def __init__(self, *, preset_speakers: tuple[str, ...] = ()) -> None:
        self._preset_speakers = tuple(item.strip() for item in preset_speakers if item.strip())

    @classmethod
    def from_settings(cls, settings: Any) -> "DoubaoPresetVoiceDesignAdapter":
        raw = getattr(settings, "volcengine_tts_preset_speakers", "") or ""
        speakers = [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
        return cls(preset_speakers=tuple(speakers))

    def declaration(self) -> CapabilityDeclaration:
        return CapabilityDeclaration(
            role=self.role,
            provider="volcengine_doubao",
            model="preset",
            flags={"design_kind": "preset_speaker"},
        )

    def design(self, request: VoiceDesignRequest) -> VoiceDesignResult:
        if request.reference_audio_base64:
            raise AdapterError(
                AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                safe_message="基于参考音频的音色克隆尚未实现（提供方克隆契约未验证）；请使用预设音色设计。",
            )
        preset = request.preset_speaker.strip()
        if not preset:
            raise AdapterError(
                AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                safe_message="预设音色设计需要 preset_speaker。",
            )
        if self._preset_speakers and preset not in self._preset_speakers:
            raise AdapterError(
                AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED,
                safe_message="该 preset_speaker 不在已配置的 VOLCENGINE_TTS_PRESET_SPEAKERS 音色库中。",
                provider_code="preset_not_in_library",
            )
        return VoiceDesignResult(
            provider="volcengine_doubao",
            model="preset",
            voice_ref=preset,
            status="pending_approval",
            parameters={"character_name": request.character_name},
            result_summary={"design_kind": "preset_speaker"},
        )


def build_speech_synthesis_capability(settings: Any, *, provider_hint: str = "") -> SpeechSynthesisCapability:
    """Select the configured speech-synthesis adapter without leaking provider logic."""

    provider = (provider_hint or getattr(settings, "tts_provider", "") or "openai_compatible").strip().lower()
    if provider == "minimax":
        return MiniMaxSpeechSynthesisAdapter.from_settings(settings)
    if provider == "volcengine_doubao":
        return DoubaoSpeechSynthesisAdapter.from_settings(settings)
    return OpenAICompatibleSpeechSynthesisAdapter.from_settings(settings)


def build_voice_design_capability(settings: Any, *, provider_hint: str = "") -> VoiceDesignCapability:
    """Select the voice-design adapter; only the Doubao preset design is supported."""

    provider = (provider_hint or getattr(settings, "tts_provider", "") or "").strip().lower()
    if provider == "minimax":
        return MiniMaxVoiceDesignAdapter.from_settings(settings)
    if provider == "volcengine_doubao":
        return DoubaoPresetVoiceDesignAdapter.from_settings(settings)
    raise AdapterError(
        AdapterErrorCategory.CONFIG_OR_AUTH,
        safe_message="音色设计需要 CHENFLOW_TTS_PROVIDER=volcengine_doubao。",
    )
