from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.capabilities import AdapterError, AdapterErrorCategory, CapabilityRole, ImageGenerationRequest
from app.image_capability import (
    ArkSeedreamImageAdapter,
    JimengImageAdapter,
    OpenAICompatibleImageAdapter,
    build_image_capability,
)
from app.jimeng_image_client import JimengImageResult


class AdapterErrorTests(unittest.TestCase):
    def test_rate_limit_is_retryable_by_default(self) -> None:
        error = AdapterError(
            AdapterErrorCategory.RATE_LIMIT_OR_QUOTA,
            safe_message="限流",
            provider_code="429",
        )
        self.assertTrue(error.retryable)
        self.assertEqual(error.category, AdapterErrorCategory.RATE_LIMIT_OR_QUOTA)
        self.assertEqual(error.provider_code, "429")
        self.assertEqual(error.safe_message, "限流")

    def test_config_or_auth_is_not_retryable_by_default(self) -> None:
        error = AdapterError(AdapterErrorCategory.CONFIG_OR_AUTH, safe_message="配置缺失")
        self.assertFalse(error.retryable)

    def test_retryable_can_be_overridden_explicitly(self) -> None:
        error = AdapterError(
            AdapterErrorCategory.CONFIG_OR_AUTH,
            safe_message="配置缺失",
            retryable=True,
        )
        self.assertTrue(error.retryable)


class FactoryRoutingTests(unittest.TestCase):
    def test_jimeng_model_selects_jimeng_adapter(self) -> None:
        settings = SimpleNamespace(
            image_model="jimeng_t2i_v40",
            image_base_url="https://visual.volcengineapi.com",
            jimeng_access_key="ak",
            jimeng_image_req_key="jimeng_t2i_v40",
        )
        capability = build_image_capability(settings)
        self.assertIsInstance(capability, JimengImageAdapter)
        declaration = capability.declaration()
        self.assertEqual(declaration.role, CapabilityRole.IMAGE)
        self.assertEqual(declaration.provider, "jimeng")
        self.assertTrue(declaration.supports_reference_images)

    def test_jimeng_config_without_base_url_selects_jimeng_adapter(self) -> None:
        settings = SimpleNamespace(
            image_model="",
            image_base_url="",
            jimeng_access_key="ak",
            jimeng_image_req_key="req",
        )
        capability = build_image_capability(settings)
        self.assertIsInstance(capability, JimengImageAdapter)

    def test_openai_compatible_model_selects_openai_adapter(self) -> None:
        settings = SimpleNamespace(
            image_model="gpt-image-2",
            image_base_url="http://ainami.it.com/v1",
            image_api_key="sk-test",
            image_size="1024x1024",
            jimeng_access_key="",
            jimeng_image_req_key="",
        )
        capability = build_image_capability(settings)
        self.assertIsInstance(capability, OpenAICompatibleImageAdapter)
        declaration = capability.declaration()
        self.assertEqual(declaration.provider, "openai_compatible")
        self.assertEqual(declaration.model, "gpt-image-2")
        self.assertFalse(declaration.supports_reference_images)

    def test_missing_config_raises_typed_error(self) -> None:
        settings = SimpleNamespace(image_model="", image_base_url="", jimeng_access_key="", jimeng_image_req_key="")
        with self.assertRaises(AdapterError) as raised:
            build_image_capability(settings)
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)


class FakeJimengClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.submit_calls: list[dict] = []
        self.result_calls: list[str] = []

    def submit_text_to_image(self, **kwargs):
        self.submit_calls.append(kwargs)
        return "task-1", {"code": 10000, "message": "ok", "data": {"task_id": "task-1", "status": "queued"}}

    def get_image_result(self, *, task_id):
        self.result_calls.append(task_id)
        return JimengImageResult(
            status="done",
            image_urls=["https://example.com/generated.png"],
            image_base64=[],
            raw={"code": 10000, "data": {"status": "done"}},
        )


class JimengImageAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = JimengImageAdapter(
            access_key="ak",
            secret_key="sk",
            endpoint="https://example.com",
            region="cn",
            service="image",
            req_key="req",
            width=1024,
            height=1024,
            poll_timeout_seconds=1,
            poll_interval_seconds=0,
        )

    def test_generate_submits_and_polls(self) -> None:
        fake = FakeJimengClient()
        with patch("app.image_capability.JimengImageClient", return_value=fake):
            result = self.adapter.generate(
                ImageGenerationRequest(
                    prompt="一个角色",
                    reference_images=("https://example.com/ref.png",),
                )
            )
        self.assertEqual(fake.submit_calls[0]["prompt"], "一个角色")
        self.assertEqual(fake.submit_calls[0]["reference_images"], ["https://example.com/ref.png"])
        self.assertEqual(fake.result_calls, ["task-1"])
        self.assertEqual(result.provider, "jimeng")
        self.assertEqual(result.kind, "url")
        self.assertEqual(result.value, "https://example.com/generated.png")
        self.assertEqual(result.provider_ref, "task-1")
        self.assertEqual(result.parameters["req_key"], "req")

    def test_generate_maps_http_429_to_rate_limit(self) -> None:
        class RaisingClient(FakeJimengClient):
            def submit_text_to_image(self, **kwargs):
                raise urllib.error.HTTPError(
                    "https://example.com",
                    429,
                    "Too Many Requests",
                    {},
                    io.BytesIO(b"rate limited"),
                )

        with patch("app.image_capability.JimengImageClient", RaisingClient):
            with self.assertRaises(AdapterError) as raised:
                self.adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.RATE_LIMIT_OR_QUOTA)
        self.assertTrue(raised.exception.retryable)

    def test_generate_requires_config(self) -> None:
        adapter = JimengImageAdapter(access_key="", secret_key="", endpoint="", region="", service="", req_key="")
        with self.assertRaises(AdapterError) as raised:
            adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)


class FakeHTTPResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


class OpenAICompatibleImageAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = OpenAICompatibleImageAdapter(
            api_key="sk-test",
            base_url="http://ainami.it.com/v1",
            model="gpt-image-2",
            size="1024x1024",
        )

    def test_generate_posts_correct_payload_and_parses_b64(self) -> None:
        b64 = "aW1hZ2VieXRlcw=="
        payload = json.dumps({"data": [{"b64_json": b64}]}).encode("utf-8")
        with patch("app.image_capability.urllib.request.urlopen", return_value=FakeHTTPResponse(payload)) as urlopen:
            result = self.adapter.generate(ImageGenerationRequest(prompt="a red apple", count=1))
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "http://ainami.it.com/v1/images/generations")
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "gpt-image-2")
        self.assertEqual(sent["prompt"], "a red apple")
        self.assertEqual(sent["size"], "1024x1024")
        self.assertEqual(sent["n"], 1)
        self.assertEqual(result.provider, "openai_compatible")
        self.assertEqual(result.kind, "base64")
        self.assertEqual(result.value, b64)

    def test_generate_maps_401_to_config_or_auth(self) -> None:
        error = urllib.error.HTTPError(
            "http://ainami.it.com/v1/images/generations",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"invalid key"}'),
        )
        with patch("app.image_capability.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(AdapterError) as raised:
                self.adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)
        self.assertFalse(raised.exception.retryable)

    def test_generate_requires_config(self) -> None:
        adapter = OpenAICompatibleImageAdapter(api_key="", base_url="", model="")
        with self.assertRaises(AdapterError) as raised:
            adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)



class ArkSeedreamImageAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = ArkSeedreamImageAdapter(
            api_key="ark-test-key",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            model="doubao-seedream-5-0-lite-260128",
            size="1024x1024",
        )

    def test_factory_routes_ark_seedream_provider(self) -> None:
        settings = SimpleNamespace(
            image_provider="ark_seedream",
            image_model="",
            image_base_url="",
            ark_api_key="ark-key",
            ark_base_url="https://ark.example.com/api/v3",
            ark_image_model="doubao-seedream-x",
            ark_image_size="1024x1024",
            jimeng_access_key="",
            jimeng_image_req_key="",
        )
        capability = build_image_capability(settings)
        self.assertIsInstance(capability, ArkSeedreamImageAdapter)

    def test_from_settings_maps_ark_settings(self) -> None:
        settings = SimpleNamespace(
            ark_api_key="ark-key",
            ark_base_url="https://ark.example.com/api/v3/",
            ark_image_model="doubao-seedream-x",
            ark_image_size="768x768",
        )
        adapter = ArkSeedreamImageAdapter.from_settings(settings)
        self.assertEqual(adapter._api_key, "ark-key")
        self.assertEqual(adapter._base_url, "https://ark.example.com/api/v3")
        self.assertEqual(adapter._model, "doubao-seedream-x")
        self.assertEqual(adapter._size, "768x768")

    def test_declaration_contract(self) -> None:
        declaration = self.adapter.declaration()
        self.assertEqual(declaration.role, CapabilityRole.IMAGE)
        self.assertEqual(declaration.provider, "ark_seedream")
        self.assertEqual(declaration.model, "doubao-seedream-5-0-lite-260128")
        self.assertTrue(declaration.supports_reference_images)
        self.assertIn("reference_image", declaration.supported_input_roles)
        self.assertEqual(declaration.flags.get("reference_contract"), "content-array-url-role")

    def test_generate_without_reference_uses_prompt_payload(self) -> None:
        payload = json.dumps({"data": [{"url": "https://example.com/img.png"}]}).encode("utf-8")
        with patch("app.image_capability.urllib.request.urlopen", return_value=FakeHTTPResponse(payload)) as urlopen:
            result = self.adapter.generate(ImageGenerationRequest(prompt="???????", count=1))
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://ark.cn-beijing.volces.com/api/v3/images/generations")
        self.assertEqual(request.get_header("Authorization"), "Bearer ark-test-key")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "doubao-seedream-5-0-lite-260128")
        self.assertEqual(sent["prompt"], "???????")
        self.assertEqual(sent["size"], "1024x1024")
        self.assertEqual(sent["response_format"], "url")
        self.assertEqual(sent["n"], 1)
        self.assertNotIn("content", sent)
        self.assertEqual(result.provider, "ark_seedream")
        self.assertEqual(result.kind, "url")
        self.assertEqual(result.value, "https://example.com/img.png")

    def test_generate_with_reference_uses_content_array(self) -> None:
        payload = json.dumps({"data": [{"url": "https://example.com/gen.png"}]}).encode("utf-8")
        ref_url = "https://example.com/ref.png"
        with patch("app.image_capability.urllib.request.urlopen", return_value=FakeHTTPResponse(payload)) as urlopen:
            result = self.adapter.generate(
                ImageGenerationRequest(prompt="??????", reference_images=(ref_url,))
            )
        request = urlopen.call_args[0][0]
        sent = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("prompt", sent)
        content = sent["content"]
        self.assertEqual(content[0], {"type": "text", "text": "??????"})
        self.assertEqual(
            content[1],
            {"type": "image_url", "role": "reference", "image_url": {"url": ref_url}},
        )
        self.assertEqual(result.kind, "url")
        self.assertEqual(result.value, "https://example.com/gen.png")
        self.assertEqual(result.parameters["reference_image_count"], 1)

    def test_generate_maps_403_to_config_or_auth(self) -> None:
        error = urllib.error.HTTPError(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"error":"forbidden"}'),
        )
        with patch("app.image_capability.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(AdapterError) as raised:
                self.adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)
        self.assertFalse(raised.exception.retryable)

    def test_generate_requires_config(self) -> None:
        adapter = ArkSeedreamImageAdapter(api_key="", base_url="", model="")
        with self.assertRaises(AdapterError) as raised:
            adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.CONFIG_OR_AUTH)

    def test_generate_missing_data_is_invalid_provider_response(self) -> None:
        payload = json.dumps({"error": {"message": "no data"}}).encode("utf-8")
        with patch("app.image_capability.urllib.request.urlopen", return_value=FakeHTTPResponse(payload)):
            with self.assertRaises(AdapterError) as raised:
                self.adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)

    def test_generate_entry_without_url_is_invalid_provider_response(self) -> None:
        payload = json.dumps({"data": [{"foo": "bar"}]}).encode("utf-8")
        with patch("app.image_capability.urllib.request.urlopen", return_value=FakeHTTPResponse(payload)):
            with self.assertRaises(AdapterError) as raised:
                self.adapter.generate(ImageGenerationRequest(prompt="p"))
        self.assertEqual(raised.exception.category, AdapterErrorCategory.INVALID_PROVIDER_RESPONSE)


if __name__ == "__main__":
    unittest.main()