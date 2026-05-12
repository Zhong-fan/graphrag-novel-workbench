from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


logger = logging.getLogger(__name__)
DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_LLM_MAX_ATTEMPTS = 3
DEFAULT_LLM_RETRY_BASE_SECONDS = 1.2
DEFAULT_LLM_RETRY_MAX_SLEEP_SECONDS = 120


@dataclass
class LLMResponse:
    text: str
    model: str


class APIHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str, details: str = "", endpoint: str = "") -> None:
        self.status_code = status_code
        self.details = details
        self.endpoint = endpoint
        super().__init__(message)


class APINetworkError(RuntimeError):
    def __init__(self, message: str, attempts: list[str]) -> None:
        self.attempts = attempts
        super().__init__(message)


class OpenAIResponsesLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        use_system_proxy: bool = False,
        use_responses: bool = True,
        stream_responses: bool = True,
        request_timeout_seconds: int = DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_LLM_MAX_ATTEMPTS,
        retry_max_sleep_seconds: int = DEFAULT_LLM_RETRY_MAX_SLEEP_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.base_url_candidates = self._build_base_url_candidates(self.base_url)
        self._opener = self._build_opener(use_system_proxy)
        self.use_responses = use_responses
        self.stream_responses = stream_responses
        self.request_timeout_seconds = max(1, request_timeout_seconds)
        self.max_attempts = max(1, max_attempts)
        self.retry_max_sleep_seconds = max(1, retry_max_sleep_seconds)

    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> LLMResponse:
        if not self.use_responses:
            return self._generate_via_chat_completions(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                event_callback=event_callback,
            )
        try:
            return self._generate_via_responses(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                event_callback=event_callback,
            )
        except APIHTTPError as exc:
            if self._should_fallback_to_chat_completions(exc):
                self._emit_event(
                    event_callback,
                    "warning",
                    "Responses 接口不可用，切换到 Chat Completions",
                    model=model,
                    status_code=exc.status_code,
                    error=str(exc),
                )
                return self._generate_via_chat_completions(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    event_callback=event_callback,
                )
            raise
        except APINetworkError as exc:
            try:
                self._emit_event(
                    event_callback,
                    "warning",
                    "Responses 网络失败，切换到 Chat Completions",
                    model=model,
                    error=str(exc),
                )
                return self._generate_via_chat_completions(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    event_callback=event_callback,
                )
            except (APIHTTPError, APINetworkError) as fallback_exc:
                raise RuntimeError(
                    f"{exc} Chat Completions fallback failed: {fallback_exc}"
                ) from fallback_exc

    def _generate_via_responses(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        event_callback: Callable[[dict[str, Any]], None] | None,
    ) -> LLMResponse:
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        if self.stream_responses:
            payload["stream"] = True
        body = self._post_json("/responses", payload, event_callback=event_callback)

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

    def _generate_via_chat_completions(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        event_callback: Callable[[dict[str, Any]], None] | None,
    ) -> LLMResponse:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        body = self._post_json("/chat/completions", payload, event_callback=event_callback)
        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI-compatible API returned no choices.")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return LLMResponse(text=content.strip(), model=str(body.get("model") or model))
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    candidate = item.get("text")
                    if candidate:
                        chunks.append(str(candidate))
            if chunks:
                return LLMResponse(text="\n".join(chunks), model=str(body.get("model") or model))

        raise RuntimeError("OpenAI-compatible chat/completions returned no text output.")

    def _post_json(
        self,
        path: str,
        payload: dict,
        *,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict:
        encoded_payload = json.dumps(payload).encode("utf-8")
        network_attempts: list[str] = []
        last_network_error: APINetworkError | None = None
        last_http_error: APIHTTPError | None = None
        model = str(payload.get("model") or "")

        for index, base_url in enumerate(self.base_url_candidates):
            has_next_base_url = index + 1 < len(self.base_url_candidates)
            headers = self._build_headers(base_url)
            if payload.get("stream"):
                headers["Accept"] = "text/event-stream"
            request = urllib.request.Request(
                url=f"{base_url}{path}",
                data=encoded_payload,
                headers=headers,
                method="POST",
            )
            try:
                return self._open(request, path=path, model=model, event_callback=event_callback)
            except APINetworkError as exc:
                last_network_error = exc
                network_attempts.extend(exc.attempts)
                self._emit_event(
                    event_callback,
                    "warning",
                    "模型接口网络失败，尝试下一个候选地址",
                    model=model,
                    endpoint=path.lstrip("/"),
                    base_url=base_url,
                    error=str(exc),
                )
                continue
            except APIHTTPError as exc:
                last_http_error = exc
                if has_next_base_url and self._should_try_alternate_base_url(base_url, exc):
                    self._emit_event(
                        event_callback,
                        "warning",
                        "模型网关临时不可用，尝试备用协议地址",
                        model=model,
                        endpoint=path.lstrip("/"),
                        base_url=base_url,
                        status_code=exc.status_code,
                        error=str(exc),
                    )
                    continue
                raise

        if last_http_error is not None:
            raise last_http_error
        if last_network_error is not None:
            raise APINetworkError(
                self._format_network_failure(path, network_attempts),
                network_attempts,
            ) from last_network_error
        raise RuntimeError(f"OpenAI API request failed before reaching {path}.")

    def _build_headers(self, base_url: str) -> dict[str, str]:
        parsed = urllib.parse.urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else base_url
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": origin,
            "Referer": f"{origin}/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
        }

    def _build_opener(self, use_system_proxy: bool) -> urllib.request.OpenerDirector:
        if use_system_proxy:
            return urllib.request.build_opener()
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _build_base_url_candidates(self, base_url: str) -> list[str]:
        candidates = [base_url.rstrip("/")]
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme == "https" and parsed.hostname and not self._is_official_openai_host(parsed.hostname):
            http_candidate = parsed._replace(scheme="http").geturl().rstrip("/")
            if http_candidate not in candidates:
                candidates.append(http_candidate)
        return candidates

    def _is_official_openai_host(self, hostname: str) -> bool:
        lowered = hostname.lower()
        return lowered == "api.openai.com" or lowered.endswith(".openai.com")

    def _should_try_alternate_base_url(self, base_url: str, error: APIHTTPError) -> bool:
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.hostname or self._is_official_openai_host(parsed.hostname):
            return False
        return error.status_code in {502, 503, 504}

    def _open(
        self,
        request: urllib.request.Request,
        *,
        path: str,
        model: str,
        event_callback: Callable[[dict[str, Any]], None] | None,
    ) -> dict:
        last_error: Exception | None = None
        network_attempts: list[str] = []
        for attempt in range(self.max_attempts):
            started_at = time.monotonic()
            attempt_number = attempt + 1
            self._emit_event(
                event_callback,
                "info",
                "开始调用模型接口，等待上游返回",
                model=model,
                endpoint=path.lstrip("/"),
                url=request.full_url,
                attempt=attempt_number,
                max_attempts=self.max_attempts,
                timeout_seconds=self.request_timeout_seconds,
            )
            try:
                with self._opener.open(request, timeout=self.request_timeout_seconds) as response:
                    raw_body = response.read().decode("utf-8", errors="replace")
                    body = (
                        self._parse_stream_response(raw_body)
                        if request.headers.get("Accept") == "text/event-stream"
                        else json.loads(raw_body)
                    )
                    self._emit_event(
                        event_callback,
                        "info",
                        "模型接口返回成功",
                        model=model,
                        endpoint=path.lstrip("/"),
                        url=request.full_url,
                        attempt=attempt_number,
                        elapsed_ms=round((time.monotonic() - started_at) * 1000),
                        response_model=body.get("model"),
                    )
                    return body
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                elapsed_ms = round((time.monotonic() - started_at) * 1000)
                formatted = self._format_http_error(exc.code, details)
                if exc.code in {502, 503, 504} and attempt_number < self.max_attempts:
                    last_error = APIHTTPError(exc.code, formatted, details, endpoint=path.lstrip("/"))
                    sleep_seconds = self._retry_sleep_seconds(
                        attempt_number,
                        details,
                        exc.headers.get("Retry-After") if exc.headers else None,
                    )
                    self._emit_event(
                        event_callback,
                        "warning",
                        "模型网关超时或临时不可用，准备重试",
                        model=model,
                        endpoint=path.lstrip("/"),
                        url=request.full_url,
                        attempt=attempt_number,
                        max_attempts=self.max_attempts,
                        status_code=exc.code,
                        elapsed_ms=elapsed_ms,
                        retry_after_seconds=round(sleep_seconds, 1),
                        error=formatted,
                    )
                    time.sleep(sleep_seconds)
                    continue
                self._emit_event(
                    event_callback,
                    "error",
                    "模型接口调用失败",
                    model=model,
                    endpoint=path.lstrip("/"),
                    url=request.full_url,
                    attempt=attempt_number,
                    max_attempts=self.max_attempts,
                    status_code=exc.code,
                    elapsed_ms=elapsed_ms,
                    error=formatted,
                )
                raise APIHTTPError(exc.code, formatted, details, endpoint=path.lstrip("/")) from exc
            except (urllib.error.URLError, http.client.RemoteDisconnected, TimeoutError, OSError) as exc:
                last_error = exc
                network_attempts.append(f"{request.full_url} ({type(exc).__name__}: {exc})")
                level = "warning" if attempt_number < self.max_attempts else "error"
                self._emit_event(
                    event_callback,
                    level,
                    "模型接口网络异常" + ("，准备重试" if attempt_number < self.max_attempts else ""),
                    model=model,
                    endpoint=path.lstrip("/"),
                    url=request.full_url,
                    attempt=attempt_number,
                    max_attempts=self.max_attempts,
                    elapsed_ms=round((time.monotonic() - started_at) * 1000),
                    error=f"{type(exc).__name__}: {exc}",
                )
                if attempt_number < self.max_attempts:
                    time.sleep(self._retry_sleep_seconds(attempt_number, ""))
                    continue

        raise APINetworkError(
            self._format_single_url_network_failure(request.full_url, network_attempts, last_error),
            network_attempts,
        ) from last_error

    def _emit_event(
        self,
        event_callback: Callable[[dict[str, Any]], None] | None,
        level: str,
        message: str,
        **details: Any,
    ) -> None:
        event = {"level": level, "message": message, **details}
        log_method = logger.warning if level == "warning" else logger.error if level == "error" else logger.info
        log_method(
            "LLM call event: level=%s message=%s model=%s endpoint=%s url=%s attempt=%s status=%s elapsed_ms=%s",
            level,
            message,
            details.get("model"),
            details.get("endpoint"),
            details.get("url"),
            details.get("attempt"),
            details.get("status_code"),
            details.get("elapsed_ms"),
        )
        if event_callback is not None:
            event_callback(event)

    def _parse_stream_response(self, raw_body: str) -> dict[str, Any]:
        chunks: list[str] = []
        final_response: dict[str, Any] | None = None
        final_payload: dict[str, Any] | None = None
        event_data: list[str] = []

        def flush_event() -> None:
            nonlocal final_response, final_payload
            if not event_data:
                return
            data = "\n".join(event_data).strip()
            event_data.clear()
            if not data or data == "[DONE]":
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                return
            if not isinstance(payload, dict):
                return
            final_payload = payload
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or error)
                raise RuntimeError(f"OpenAI stream returned an error: {message}")
            if isinstance(payload.get("delta"), str):
                chunks.append(str(payload["delta"]))
            choice_chunks = payload.get("choices")
            if isinstance(choice_chunks, list):
                for choice in choice_chunks:
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta")
                    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                        chunks.append(str(delta["content"]))
            response = payload.get("response")
            if isinstance(response, dict):
                final_response = response
            output_text = payload.get("output_text")
            if isinstance(output_text, str):
                chunks.append(output_text)

        for line in raw_body.splitlines():
            stripped = line.strip()
            if not stripped:
                flush_event()
                continue
            if stripped.startswith("data:"):
                event_data.append(stripped[5:].strip())
            elif stripped.startswith("{"):
                event_data.append(stripped)
        flush_event()

        if final_response is not None:
            if chunks and not final_response.get("output_text"):
                final_response = {**final_response, "output_text": "".join(chunks)}
            return final_response
        if chunks:
            result: dict[str, Any] = {"output_text": "".join(chunks)}
            if final_payload and final_payload.get("model"):
                result["model"] = final_payload.get("model")
            return result
        if final_payload is not None:
            return final_payload
        raise RuntimeError("OpenAI stream returned no text output.")

    def _retry_sleep_seconds(
        self,
        attempt_number: int,
        details: str,
        retry_after_header: str | None = None,
    ) -> float:
        retry_after = self._parse_retry_after_seconds(details, retry_after_header)
        if retry_after is None:
            retry_after = DEFAULT_LLM_RETRY_BASE_SECONDS * attempt_number
        return min(float(retry_after), float(self.retry_max_sleep_seconds))

    def _parse_retry_after_seconds(
        self,
        details: str,
        retry_after_header: str | None = None,
    ) -> float | None:
        for raw_value in (retry_after_header, self._retry_after_from_json(details)):
            if raw_value is None:
                continue
            try:
                parsed = float(raw_value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return None

    def _retry_after_from_json(self, details: str) -> object | None:
        try:
            payload = json.loads(details)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        if "retry_after" in payload:
            return payload.get("retry_after")
        error = payload.get("error")
        if isinstance(error, dict):
            return error.get("retry_after")
        return None

    def _should_fallback_to_chat_completions(self, error: APIHTTPError) -> bool:
        if error.status_code not in {400, 404, 405, 415, 422}:
            return False

        lowered = f"{error.endpoint} {error} {error.details}".lower()
        fallback_markers = (
            "responses",
            "not found",
            "unsupported",
            "unknown url",
            "invalid url",
            "no route",
            "chat/completions",
        )
        return any(marker in lowered for marker in fallback_markers)

    def _format_http_error(self, status_code: int, details: str) -> str:
        message = details.strip()
        try:
            payload = json.loads(details)
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                raw_message = str(error.get("message") or "").strip()
                if raw_message:
                    message = raw_message
        except json.JSONDecodeError:
            pass

        lowered = message.lower()
        if "upstream authentication failed" in lowered:
            return (
                "Model gateway upstream authentication failed. "
                "Check the upstream API key, model permission, or switch CHENFLOW_WRITER_MODEL "
                "(legacy alias: GRAPH_MVP_WRITER_MODEL) to a model that this gateway actually exposes."
            )
        if status_code in {502, 503, 504}:
            return f"Model gateway is temporarily unavailable or upstream timed out: {message}"
        return f"OpenAI API error: {status_code} {message}"

    def _format_single_url_network_failure(
        self,
        url: str,
        attempts: list[str],
        last_error: Exception | None,
    ) -> str:
        if attempts:
            return f"OpenAI API connection error via {url}: {' | '.join(attempts)}"
        return f"OpenAI API connection error via {url}: {last_error}"

    def _format_network_failure(self, path: str, attempts: list[str]) -> str:
        if attempts:
            return f"OpenAI API connection error for {path}: {' | '.join(attempts)}"
        return f"OpenAI API connection error for {path}."
