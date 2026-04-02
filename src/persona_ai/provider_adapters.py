from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List
from urllib import request
from urllib.error import HTTPError, URLError

from .chat_contract import (
    ChatRequest,
    ChatResponse,
    ErrorCategory,
    ProviderAdapter,
    ProviderError,
    TokenChunk,
    Usage,
)


HttpTransport = Callable[[str, Dict[str, str], Dict[str, Any], float], Dict[str, Any]]


def default_http_transport(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method="POST", data=body)
    for key, value in headers.items():
        req.add_header(key, value)
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        raw = response.read().decode("utf-8")
        if "application/json" not in content_type:
            preview = " ".join(raw.split())[:220]
            raise ValueError(
                f"OpenAI upstream returned non-JSON payload; endpoint={url}; "
                f"content-type={content_type or 'unknown'}; body={preview}"
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            preview = " ".join(raw.split())[:220]
            raise ValueError(f"Provider returned invalid JSON; endpoint={url}; body={preview}") from exc


def _map_error(exc: Exception) -> ProviderError:
    if isinstance(exc, HTTPError):
        status = exc.code
        if status in {401, 403}:
            return ProviderError(ErrorCategory.AUTH, str(exc), retryable=False, provider_code=str(status))
        if status == 429:
            return ProviderError(ErrorCategory.RATE_LIMIT, str(exc), retryable=True, provider_code="429")
        if status in {400, 404, 422}:
            return ProviderError(ErrorCategory.MODEL, str(exc), retryable=False, provider_code=str(status))
        return ProviderError(ErrorCategory.TRANSPORT, str(exc), retryable=True, provider_code=str(status))
    if isinstance(exc, URLError):
        return ProviderError(ErrorCategory.TRANSPORT, str(exc), retryable=True)
    return ProviderError(ErrorCategory.UNKNOWN, str(exc), retryable=False)


class OpenAICompatibleAdapter(ProviderAdapter):
    provider_name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        wire_api: str = "chat/completions",
        timeout_seconds: float = 30.0,
        transport: HttpTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.wire_api = self._normalize_wire_api(wire_api)
        self.timeout_seconds = timeout_seconds
        self.transport = transport or default_http_transport

    @staticmethod
    def _normalize_wire_api(wire_api: str) -> str:
        candidate = wire_api.strip().lower()
        if candidate in {"chat/completions", "chat_completions", "chat-completions"}:
            return "chat/completions"
        if candidate in {"responses", "/responses"}:
            return "responses"
        raise ValueError(f"Unsupported OpenAI wire API: {wire_api}")

    def _endpoint(self) -> str:
        return f"{self.base_url}/{self.wire_api}"

    def _parse_output_text(self, raw: Dict[str, Any]) -> str:
        if self.wire_api == "responses":
            output_text = raw.get("output_text")
            if isinstance(output_text, str):
                return output_text
            output = raw.get("output", [])
            chunks: List[str] = []
            if isinstance(output, list):
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for content_item in content:
                        if not isinstance(content_item, dict):
                            continue
                        text = content_item.get("text")
                        if isinstance(text, str):
                            chunks.append(text)
            return "".join(chunks)
        return str(raw.get("choices", [{}])[0].get("message", {}).get("content", ""))

    def _parse_usage(self, raw: Dict[str, Any]) -> Usage:
        usage_raw = raw.get("usage", {})
        if not isinstance(usage_raw, dict):
            usage_raw = {}
        if self.wire_api == "responses":
            return Usage(
                prompt_tokens=int(usage_raw.get("input_tokens", 0)),
                completion_tokens=int(usage_raw.get("output_tokens", 0)),
            )
        return Usage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=int(usage_raw.get("completion_tokens", 0)),
        )

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def generate(self, request_data: ChatRequest) -> ChatResponse:
        payload: Dict[str, Any] = {
            "model": request_data.model or self.model,
            "messages": [{"role": m.role, "content": m.content} for m in request_data.messages],
            "temperature": request_data.temperature,
            "stream": False,
        }
        if self.wire_api == "responses":
            payload["input"] = payload.pop("messages")
            payload["max_output_tokens"] = request_data.max_tokens
        else:
            payload["max_tokens"] = request_data.max_tokens
        try:
            raw = self.transport(self._endpoint(), self._headers(), payload, self.timeout_seconds)
        except Exception as exc:
            return ChatResponse(
                provider=self.provider_name,
                model=payload["model"],
                trace_id=request_data.trace_id,
                output_text="",
                error=_map_error(exc),
            )

        text = self._parse_output_text(raw)
        usage = self._parse_usage(raw)
        return ChatResponse(
            provider=self.provider_name,
            model=payload["model"],
            trace_id=request_data.trace_id,
            output_text=text,
            usage=usage,
        )

    def stream(self, request_data: ChatRequest) -> Iterable[TokenChunk]:
        response = self.generate(request_data)
        if response.error:
            yield TokenChunk(trace_id=request_data.trace_id, index=0, text="", done=True)
            return
        tokens = response.output_text.split()
        for i, token in enumerate(tokens):
            end = i == len(tokens) - 1
            suffix = "" if end else " "
            yield TokenChunk(trace_id=request_data.trace_id, index=i, text=f"{token}{suffix}", done=end)


class AnthropicCompatibleAdapter(ProviderAdapter):
    provider_name = "anthropic-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        transport: HttpTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or default_http_transport

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def generate(self, request_data: ChatRequest) -> ChatResponse:
        payload = {
            "model": request_data.model or self.model,
            "max_tokens": request_data.max_tokens,
            "temperature": request_data.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in request_data.messages],
            "stream": False,
        }
        try:
            raw = self.transport(f"{self.base_url}/messages", self._headers(), payload, self.timeout_seconds)
        except Exception as exc:
            return ChatResponse(
                provider=self.provider_name,
                model=payload["model"],
                trace_id=request_data.trace_id,
                output_text="",
                error=_map_error(exc),
            )

        content: List[Dict[str, Any]] = raw.get("content", [])
        text = "".join([item.get("text", "") for item in content if item.get("type") == "text"])
        usage_raw = raw.get("usage", {})
        usage = Usage(
            prompt_tokens=int(usage_raw.get("input_tokens", 0)),
            completion_tokens=int(usage_raw.get("output_tokens", 0)),
        )
        return ChatResponse(
            provider=self.provider_name,
            model=payload["model"],
            trace_id=request_data.trace_id,
            output_text=text,
            usage=usage,
        )

    def stream(self, request_data: ChatRequest) -> Iterable[TokenChunk]:
        response = self.generate(request_data)
        if response.error:
            yield TokenChunk(trace_id=request_data.trace_id, index=0, text="", done=True)
            return
        tokens = response.output_text.split()
        for i, token in enumerate(tokens):
            end = i == len(tokens) - 1
            suffix = "" if end else " "
            yield TokenChunk(trace_id=request_data.trace_id, index=i, text=f"{token}{suffix}", done=end)
