from __future__ import annotations

import base64
import json
import unittest
import urllib.error
from unittest.mock import patch

from app.capabilities import AdapterError, AdapterErrorCategory, SpeechSynthesisRequest, VoiceDesignRequest
from app.voice_capability import (
    DoubaoPresetVoiceDesignAdapter,
    DoubaoSpeechSynthesisAdapter,
    OpenAICompatibleSpeechSynthesisAdapter,
    build_speech_synthesis_capability,
)


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def _http_error(status: int, body: str = "") -> urllib.error.HTTPError:
    import io as _io

    return urllib.error.HTTPError(
        "https://example.test/tts",
        status,
        "error",
        {},
        _io.BytesIO(body.encode("utf-8")),
    )


def _request_headers(request) -> dict[str, str]:
    """Case-insensitive view of urllib header storage (keys are capitalized)."""
    return {key.lower(): value for key, value in request.headers.items()}


class _FakeSettings:
    tts_provider = "volcengine_doubao"
    volcengine_tts_app_id = "app-1"
    volcengine_tts_access_key = "access-1"
    volcengine_tts_api_key = ""
    volcengine_tts_resource_id = "seed-tts-2.0"
    volcengine_tts_endpoint = "https://example.test/tts"
    volcengine_tts_speaker = "preset_default"
    volcengine_tts_model = ""
    volcengine_tts_sample_rate = 24000
    volcengine_tts_preset_speakers = "preset_a,preset_b"
    tts_api_key = "k"
    tts_base_url = "https://example.test/v1"
    tts_model = "tts-1"
    tts_voice = "voice_default"


def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


class DoubaoSpeechSynthesisAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DoubaoSpeechSynthesisAdapter.from_settings(_FakeSettings())

    def test_declaration_uses_tts_2_0_resource_id(self) -> None:
        declaration = self.adapter.declaration()
        self.assertEqual(declaration.provider, "volcengine_doubao")
        self.assertEqual(declaration.model, "seed-tts-2.0")
        self.assertTrue(declaration.flags["tts_version"] == "2.0")

    def test_synthesize_sends_tts_2_0_payload_and_headers(self) -> None:
        chunk = b"\x00\x01fake-audio"
        lines = (
            json.dumps({"code": 20000000, "data": _b64(chunk)})
            + "\n"
            + json.dumps({"code": 0, "data": _b64(b"\x02")})
        ).encode("utf-8")
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse(lines)

        with patch("app.voice_capability.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.adapter.synthesize(
                SpeechSynthesisRequest(text="你好", voice_profile="", speed=1.1, emotion="平静")
            )

        request = captured["request"]
        self.assertEqual(request.full_url, "https://example.test/tts")
        self.assertEqual(request.get_method(), "POST")
        headers = _request_headers(request)
        self.assertEqual(headers["x-api-app-id"], "app-1")
        self.assertEqual(headers["x-api-access-key"], "access-1")
        self.assertEqual(headers["x-api-resource-id"], "seed-tts-2.0")
        self.assertNotIn("x-api-model", headers)
        self.assertIn("x-api-request-id", headers)

        payload = json.loads(request.data.decode("utf-8"))
        req_params = payload["req_params"]
        self.assertEqual(req_params["text"], "你好")
        self.assertEqual(req_params["speaker"], "preset_default")
        self.assertEqual(req_params["audio_params"]["format"], "mp3")
        self.assertEqual(req_params["audio_params"]["sample_rate"], 24000)
        self.assertEqual(req_params["additions"]["speed_ratio"], "1.10")
        self.assertEqual(req_params["additions"]["emotion"], "平静")

        decoded = base64.b64decode(result.audio_base64)
        self.assertEqual(decoded, chunk + b"\x02")
        self.assertEqual(result.provider, "volcengine_doubao")
        self.assertEqual(result.model, "seed-tts-2.0")
        self.assertEqual(captured["timeout"], 180)

    def test_synthesize_injects_model_header_when_configured(self) -> None:
        adapter = DoubaoSpeechSynthesisAdapter(
            app_id="app-1",
            access_key="key",
            resource_id="seed-tts-2.0",
            endpoint="https://example.test/tts",
            speaker="s",
            model="custom-model",
        )
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return _FakeResponse(json.dumps({"data": _b64(b"x")}).encode("utf-8"))

        with patch("app.voice_capability.urllib.request.urlopen", side_effect=fake_urlopen):
            adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(_request_headers(captured["request"])["x-api-model"], "custom-model")

    def test_synthesize_uses_request_voice_profile_when_provided(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return _FakeResponse(json.dumps({"data": _b64(b"x")}).encode("utf-8"))

        with patch("app.voice_capability.urllib.request.urlopen", side_effect=fake_urlopen):
            self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile="speaker_x"))
        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertEqual(payload["req_params"]["speaker"], "speaker_x")

    def test_synthesize_whole_body_json_fallback(self) -> None:
        body = json.dumps({"code": 0, "data": _b64(b"\xaa\xbb")}).encode("utf-8")
        with patch(
            "app.voice_capability.urllib.request.urlopen", return_value=_FakeResponse(body)
        ):
            result = self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(base64.b64decode(result.audio_base64), b"\xaa\xbb")

    def test_provider_error_code_maps_to_invalid_provider_response(self) -> None:
        body = json.dumps({"code": 40001, "message": "bad"}).encode("utf-8")
        with patch(
            "app.voice_capability.urllib.request.urlopen", return_value=_FakeResponse(body)
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)
        self.assertEqual(ctx.exception.provider_code, "40001")

    def test_empty_audio_raises_invalid_provider_response(self) -> None:
        with patch(
            "app.voice_capability.urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps({"code": 0}).encode("utf-8")),
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)

    def test_garbage_base64_chunks_raise_invalid_provider_response(self) -> None:
        body = json.dumps({"code": 0, "data": "!!!"}).encode("utf-8")
        with patch(
            "app.voice_capability.urllib.request.urlopen", return_value=_FakeResponse(body)
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)

    def test_http_403_maps_to_config_or_auth(self) -> None:
        with patch(
            "app.voice_capability.urllib.request.urlopen", side_effect=_http_error(403, "forbidden")
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)

    def test_http_429_maps_to_rate_limit(self) -> None:
        with patch(
            "app.voice_capability.urllib.request.urlopen", side_effect=_http_error(429)
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.RATE_LIMIT_OR_QUOTA)

    def test_missing_config_raises_config_or_auth(self) -> None:
        adapter = DoubaoSpeechSynthesisAdapter(
            app_id="",
            access_key="",
            resource_id="",
            endpoint="",
            speaker="",
        )
        with self.assertRaises(AdapterError) as ctx:
            adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)
        self.assertIn("VOLCENGINE_TTS_APP_ID", str(ctx.exception))


class OpenAICompatibleSpeechSynthesisAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = OpenAICompatibleSpeechSynthesisAdapter.from_settings(_FakeSettings())

    def test_synthesize_sends_openai_compatible_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return _FakeResponse(b"\x01audio")

        with patch("app.voice_capability.urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.adapter.synthesize(
                SpeechSynthesisRequest(text="hello", voice_profile="v2", speed=0.9, emotion="")
            )
        request = captured["request"]
        self.assertEqual(request.full_url, "https://example.test/v1/audio/speech")
        self.assertEqual(_request_headers(request)["authorization"], "Bearer k")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "tts-1")
        self.assertEqual(payload["voice"], "v2")
        self.assertEqual(payload["input"], "hello")
        self.assertEqual(payload["response_format"], "mp3")
        self.assertEqual(payload["speed"], 0.9)
        self.assertNotIn("instructions", payload)
        self.assertEqual(base64.b64decode(result.audio_base64), b"\x01audio")

    def test_synthesize_adds_instructions_for_emotion(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            return _FakeResponse(b"x")

        with patch("app.voice_capability.urllib.request.urlopen", side_effect=fake_urlopen):
            self.adapter.synthesize(SpeechSynthesisRequest(text="hello", voice_profile="", emotion="温暖"))
        payload = json.loads(captured["request"].data.decode("utf-8"))
        self.assertIn("温暖", payload["instructions"])

    def test_empty_audio_raises_invalid_provider_response(self) -> None:
        with patch(
            "app.voice_capability.urllib.request.urlopen", return_value=_FakeResponse(b"")
        ):
            with self.assertRaises(AdapterError) as ctx:
                self.adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)

    def test_missing_config_raises_config_or_auth(self) -> None:
        adapter = OpenAICompatibleSpeechSynthesisAdapter(
            api_key="", base_url="", model="", voice=""
        )
        with self.assertRaises(AdapterError) as ctx:
            adapter.synthesize(SpeechSynthesisRequest(text="hi", voice_profile=""))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)
        self.assertIn("CHENFLOW_TTS_API_KEY", str(ctx.exception))


class VoiceDesignAdapterTests(unittest.TestCase):
    def test_preset_design_returns_pending_approval(self) -> None:
        adapter = DoubaoPresetVoiceDesignAdapter.from_settings(_FakeSettings())
        result = adapter.design(VoiceDesignRequest(character_name="小红", preset_speaker="preset_a"))
        self.assertEqual(result.provider, "volcengine_doubao")
        self.assertEqual(result.voice_ref, "preset_a")
        self.assertEqual(result.status, "pending_approval")

    def test_preset_design_rejects_reference_audio_clone(self) -> None:
        adapter = DoubaoPresetVoiceDesignAdapter()
        with self.assertRaises(AdapterError) as ctx:
            adapter.design(
                VoiceDesignRequest(
                    character_name="小红",
                    preset_speaker="preset_a",
                    reference_audio_base64="AAAA",
                )
            )
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED)

    def test_preset_design_enforces_configured_library(self) -> None:
        adapter = DoubaoPresetVoiceDesignAdapter.from_settings(_FakeSettings())
        with self.assertRaises(AdapterError) as ctx:
            adapter.design(VoiceDesignRequest(character_name="小红", preset_speaker="unknown"))
        self.assertEqual(ctx.exception.category, AdapterErrorCategory.INVALID_REQUEST_OR_UNSUPPORTED)
        self.assertEqual(ctx.exception.provider_code, "preset_not_in_library")

    def test_preset_design_requires_speaker(self) -> None:
        adapter = DoubaoPresetVoiceDesignAdapter()
        with self.assertRaises(AdapterError):
            adapter.design(VoiceDesignRequest(character_name="小红", preset_speaker=""))


class FactoryTests(unittest.TestCase):
    def test_factory_selects_doubao_by_provider_hint(self) -> None:
        capability = build_speech_synthesis_capability(_FakeSettings(), provider_hint="volcengine_doubao")
        self.assertIsInstance(capability, DoubaoSpeechSynthesisAdapter)

    def test_factory_falls_back_to_openai_compatible(self) -> None:
        capability = build_speech_synthesis_capability(_FakeSettings(), provider_hint="openai_compatible")
        self.assertIsInstance(capability, OpenAICompatibleSpeechSynthesisAdapter)


if __name__ == "__main__":
    unittest.main()
