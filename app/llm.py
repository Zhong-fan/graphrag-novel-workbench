from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str


class OpenAIResponsesLLM:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate(self, *, model: str, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        request = urllib.request.Request(
            url=f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error: {exc.code} {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API connection error: {exc}") from exc

        text = body.get("output_text")
        if text:
            return LLMResponse(text=text, model=model)

        output = body.get("output", [])
        chunks: list[str] = []
        for item in output:
            for content in item.get("content", []):
                candidate = content.get("text")
                if candidate:
                    chunks.append(candidate)

        if not chunks:
            raise RuntimeError("OpenAI API returned no text output.")
        return LLMResponse(text="\n".join(chunks), model=model)
