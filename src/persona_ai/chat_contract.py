from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ErrorCategory(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    MODEL = "model"
    TRANSPORT = "transport"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    user_id: str
    session_id: str
    turn_id: int
    trace_id: str
    model: str
    messages: List[ChatMessage]
    stream: bool = True
    max_tokens: int = 256
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenChunk:
    trace_id: str
    index: int
    text: str
    done: bool = False


@dataclass(frozen=True)
class ProviderError:
    category: ErrorCategory
    message: str
    retryable: bool
    provider_code: str = ""


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class ChatResponse:
    provider: str
    model: str
    trace_id: str
    output_text: str
    usage: Usage = field(default_factory=Usage)
    error: Optional[ProviderError] = None


class ProviderAdapter:
    provider_name: str

    def generate(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    def stream(self, request: ChatRequest) -> Iterable[TokenChunk]:
        raise NotImplementedError
