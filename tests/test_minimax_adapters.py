import base64
import unittest
from unittest.mock import patch

from app.capabilities import ImageGenerationRequest, SpeechSynthesisRequest, VoiceDesignRequest, VideoGenerationRequest, AdapterError
from app.image_capability import MiniMaxImageAdapter
from app.minimax_text import MiniMaxTextAdapter
from app.voice_capability import MiniMaxSpeechSynthesisAdapter, MiniMaxVoiceDesignAdapter
from app.video_capability import MiniMaxVideoAdapter


class FakeMiniMaxClient:
    def __init__(self):
        self.posts = []

    def post_json(self, path, payload):
        self.posts.append((path, payload))
        if path.endswith("image_generation"):
            return {"data": {"image_base64": ["abc"]}}
        if path.endswith("chat/completions"):
            return {"model": "MiniMax-M3", "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"total_tokens": 3}}
        if path.endswith("voice_design"):
            return {"voice_id": "voice-1", "trial_audio": "00"}
        if path.endswith("t2a_v2"):
            return {"data": {"audio": "0001"}, "extra_info": {"audio_size": 2}}
        if path.endswith("video_generation"):
            return {"task_id": "task-1"}
        raise AssertionError(path)

    def poll_task(self, task_id):
        return type("Task", (), {"status": "Success", "response": {"content": {"url": "https://example/video.mp4"}}})()


class MiniMaxAdapterTests(unittest.TestCase):
    def test_image_uses_reference_contract(self):
        client = FakeMiniMaxClient()
        with patch("app.image_capability.MiniMaxClient", return_value=client):
            result = MiniMaxImageAdapter(api_key="key").generate(ImageGenerationRequest(prompt="hero", width=1024, height=576, reference_images=("https://example/ref.jpg",)))
        self.assertEqual(result.provider, "minimax")
        self.assertEqual(client.posts[0][1]["subject_reference"][0]["type"], "character")

    def test_image_rejects_multiple_references(self):
        with self.assertRaises(AdapterError):
            MiniMaxImageAdapter(api_key="key").generate(ImageGenerationRequest(prompt="hero", reference_images=("a", "b")))

    def test_video_preflight_rejects_invalid_duration_before_client(self):
        with self.assertRaises(AdapterError):
            MiniMaxVideoAdapter(api_key="key", client=FakeMiniMaxClient()).generate(VideoGenerationRequest(prompt="x", duration_seconds=3))

    def test_video_persists_task_and_download_url(self):
        client = FakeMiniMaxClient()
        result = MiniMaxVideoAdapter(api_key="key", client=client).generate(VideoGenerationRequest(prompt="x", mode="image_to_video", first_frame_url="https://example/frame.png"))
        self.assertEqual(result.task_id, "task-1")
        self.assertEqual(result.video_url, "https://example/video.mp4")

    def test_text_normalizes_response(self):
        client = FakeMiniMaxClient()
        result = MiniMaxTextAdapter(api_key="key", client=client).generate(system_prompt="system", user_prompt="user")
        self.assertEqual(result.text, "ok")
        self.assertEqual(result.usage["total_tokens"], 3)

    def test_voice_design_stays_pending_approval(self):
        client = FakeMiniMaxClient()
        with patch("app.voice_capability.MiniMaxClient", return_value=client):
            result = MiniMaxVoiceDesignAdapter(api_key="key").design(VoiceDesignRequest(character_name="hero", description="warm narrator", preview_text="Hello"))
        self.assertEqual(result.voice_ref, "voice-1")
        self.assertEqual(result.status, "pending_approval")

    def test_speech_decodes_hex_audio(self):
        client = FakeMiniMaxClient()
        with patch("app.voice_capability.MiniMaxClient", return_value=client):
            result = MiniMaxSpeechSynthesisAdapter(api_key="key").synthesize(SpeechSynthesisRequest(text="hi", voice_profile="voice-1"))
        self.assertEqual(base64.b64decode(result.audio_base64), b"\x00\x01")


if __name__ == "__main__":
    unittest.main()
