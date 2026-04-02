from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Thread
from time import perf_counter
from typing import Any, Dict, Iterable, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .access_policy import build_default_policy
from .audit import ImmutableAuditLog
from .chat_contract import ChatMessage, ChatRequest
from .chat_orchestration import ConversationOrchestrator
from .memory_events import MemoryEventBus
from .persona_visualization import build_persona_cards, build_word_cloud
from .privacy import PrivacyController
from .profile_manager import ProfileManager
from .provider_adapters import AnthropicCompatibleAdapter, OpenAICompatibleAdapter
from .storage import MemoryStore
from .episodic_store_qdrant import QdrantEpisodicVectorStore
from .semantic_store_neo4j import Neo4jSemanticGraphStore


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "backend.log"
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR / "web" / ".env.local")


def _init_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("persona_ai.backend")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


logger = _init_logger()


class IncomingMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatTurnRequest(BaseModel):
    provider: Literal["openai", "anthropic"] = "openai"
    user_id: str = Field(default="demo-user")
    session_id: str = Field(default="demo-session")
    turn_id: Optional[int] = Field(default=None, alias="turnId")
    user_text: str = Field(alias="userText")
    messages: List[IncomingMessage] = Field(default_factory=list)
    model: Optional[str] = None
    profile_field: str = Field(default="response_style", alias="profileField")

    model_config = {"populate_by_name": True}


class RollbackRequest(BaseModel):
    threshold: float = 0.5


def _raise_http_for_provider_error(exc: RuntimeError, provider: str, model: str) -> None:
    text = str(exc)
    match = re.search(r"^\[ProviderError:(?P<category>[^\]]+)\]\s*(?P<msg>.*)$", text)
    if not match:
        raise HTTPException(status_code=502, detail=text)

    category = match.group("category")
    raw_message = match.group("msg")
    status_code = 502
    error_code = "provider_error"

    if category == "auth":
        status_code = 401
        error_code = "provider_auth"
    elif category == "rate_limit":
        status_code = 429
        error_code = "provider_rate_limit"
    elif category == "model":
        status_code = 400
        error_code = "provider_model"

    raise HTTPException(
        status_code=status_code,
        detail={
            "code": error_code,
            "category": category,
            "message": raw_message,
            "provider": provider,
            "model": model,
        },
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    return value


def _env_or_default(name: str, default: str) -> str:
    value = (os.getenv(name) or "").strip()
    return value or default


def _build_chat_payload(
    *,
    req: ChatTurnRequest,
    provider: Any,
    turn_id: int,
    result: Any,
) -> Dict[str, Any]:
    l1_record = next(
        (r for r in runtime.store.l1_records(req.user_id) if r.session_id == req.session_id and r.turn_id == turn_id),
        None,
    )
    l2_ctx = runtime.store.get_l2(req.session_id)
    l3 = runtime.store.latest_l3(req.user_id)

    l3_profile: Dict[str, Any] = {}
    if l3:
        for name, field in l3.fields.items():
            evidence_class = field.evidence[-1].evidence_class.value if field.evidence else "unknown"
            l3_profile[name] = {
                "value": str(field.value),
                "confidence": field.confidence,
                "evidenceClass": evidence_class,
                "updatedAt": field.updated_at.isoformat(),
            }

    timeline = [
        {
            "turnId": ev.turn_id,
            "traceId": ev.trace_id,
            "action": f"{ev.layer}.{ev.operation}",
            "at": ev.timestamp.isoformat(),
        }
        for ev in runtime.event_bus.replay_turn(req.session_id, turn_id)
    ]

    l1_records = runtime.store.l1_records(req.user_id)
    id_to_record = {record.record_id: record for record in l1_records}
    episodic_ids = [str(item) for item in result.retrieval.get("episodic_record_ids", [])]

    retrieval = {
        "semanticVersion": int(result.retrieval.get("semantic_version") or 0),
        "semanticFields": result.retrieval.get("semantic_fields", []),
        "evidenceRefs": [],
        "retrievalSources": ["L1", "L2", "L3"],
        "distillationBatchStatus": "idle",
        "episodicHits": [
            {
                "messageIndex": id_to_record[record_id].turn_id - 1,
                "score": 1,
                "snippet": id_to_record[record_id].user_input[:120],
            }
            for record_id in episodic_ids
            if record_id in id_to_record
        ],
        "workingSummary": result.retrieval.get("working_summary_present") and (l2_ctx.summary if l2_ctx else "") or "",
        "injectedPrompt": result.memory_prompt,
    }

    governance = {
        "consent": True,
        "policyVersion": "v1",
        "fieldCount": len(l3_profile),
        "traceId": result.trace_id,
    }

    return {
        "assistantText": result.assistant_output,
        "traceId": result.trace_id,
        "provider": provider.provider_name,
        "memory": {
            "l1": {
                "turnId": l1_record.turn_id if l1_record else turn_id,
                "userText": req.user_text,
                "assistantText": result.assistant_output,
                "sentiment": l1_record.sentiment if l1_record else "neutral",
                "entities": l1_record.entities if l1_record else [],
            },
            "l2": {
                "lastUserInput": l2_ctx.context.get("last_user_input", "") if l2_ctx else "",
                "lastAssistantOutput": l2_ctx.context.get("last_assistant_output", "") if l2_ctx else "",
                "traceId": result.trace_id,
                "workingSummary": l2_ctx.summary if l2_ctx else "",
                "entityFocus": l2_ctx.entity_focus if l2_ctx else [],
            },
            "l3": l3_profile,
        },
        "retrieval": retrieval,
        "governance": governance,
        "timeline": timeline,
    }


class AppRuntime:
    def __init__(self) -> None:
        self.event_bus = MemoryEventBus()
        self.audit = ImmutableAuditLog()
        self.store = MemoryStore(
            event_bus=self.event_bus,
            episodic_store=QdrantEpisodicVectorStore(),
            semantic_store=Neo4jSemanticGraphStore(),
        )
        self.profile_manager = ProfileManager(store=self.store, audit_log=self.audit)
        self.privacy = PrivacyController(policy=build_default_policy(), store=self.store, audit=self.audit)
        self._connectivity_checked = False

    def provider_for(self, provider: str, model_override: Optional[str]):
        if provider == "anthropic":
            base_url = _env_or_default("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
            api_key = _env_or_default("ANTHROPIC_API_KEY", "")
            model = (model_override or "").strip() or _env_or_default("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
            if not api_key:
                raise HTTPException(status_code=500, detail="Missing ANTHROPIC_API_KEY")
            return AnthropicCompatibleAdapter(base_url=base_url, api_key=api_key, model=model)

        base_url = _env_or_default("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = _env_or_default("OPENAI_API_KEY", "")
        model = (model_override or "").strip() or _env_or_default("OPENAI_MODEL", "gpt-4o-mini")
        wire_api = _env_or_default("OPENAI_WIRE_API", "chat/completions")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY")
        return OpenAICompatibleAdapter(base_url=base_url, api_key=api_key, model=model, wire_api=wire_api)

    def log_provider_connectivity(self) -> None:
        if self._connectivity_checked:
            return
        self._connectivity_checked = True

        checks = [
            ("openai", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            ("anthropic", os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")),
        ]

        for provider_name, model_name in checks:
            try:
                provider = self.provider_for(provider_name, model_name)
            except HTTPException as exc:
                logger.error(
                    "startup_provider_config_failed provider=%s model=%s detail=%s",
                    provider_name,
                    model_name,
                    exc.detail,
                )
                continue

            probe_request = ChatRequest(
                user_id="startup-probe",
                session_id=f"startup-probe-{provider_name}",
                turn_id=0,
                trace_id=f"startup-{provider_name}",
                model=provider.model,
                messages=[ChatMessage(role="user", content="ping")],
                stream=False,
                max_tokens=8,
                temperature=0.0,
                metadata={"probe": True},
            )

            response = provider.generate(probe_request)
            if response.error:
                logger.error(
                    "startup_provider_connect_failed provider=%s model=%s category=%s message=%s",
                    provider_name,
                    response.model,
                    response.error.category.value,
                    response.error.message,
                )
                continue

            logger.info(
                "startup_provider_connect_ok provider=%s model=%s provider_name=%s prompt_tokens=%s completion_tokens=%s",
                provider_name,
                response.model,
                response.provider,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )


runtime = AppRuntime()
runtime.log_provider_connectivity()

app = FastAPI(
    title="Persona AI Bridge API",
    version="0.1.0",
    description="FastAPI bridge for Persona AI frontend and backend",
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = (perf_counter() - start) * 1000
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    except Exception:
        elapsed_ms = (perf_counter() - start) * 1000
        logger.exception(
            "request_failed method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_provider_check() -> None:
    runtime.log_provider_connectivity()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/providers/health")
def provider_health(provider: Literal["openai", "anthropic"] = "openai") -> Dict[str, Any]:
    try:
        selected = runtime.provider_for(provider, None)
    except HTTPException as exc:
        raise exc

    test_orchestrator = ConversationOrchestrator(
        provider=selected,
        store=runtime.store,
        profile_manager=runtime.profile_manager,
        event_bus=runtime.event_bus,
        audit=runtime.audit,
    )
    try:
        test_orchestrator.process_turn(
            user_id="provider-health",
            session_id=f"provider-health-{provider}",
            turn_id=1,
            user_input="ping",
            model=selected.model,
        )
        return {"ok": True, "provider": provider, "model": selected.model}
    except RuntimeError as exc:
        text = str(exc)
        match = re.search(r"^\[ProviderError:(?P<category>[^\]]+)\]\s*(?P<msg>.*)$", text)
        if not match:
            return {"ok": False, "provider": provider, "model": selected.model, "error": text}
        return {
            "ok": False,
            "provider": provider,
            "model": selected.model,
            "category": match.group("category"),
            "message": match.group("msg"),
        }


@app.post("/api/v1/chat/turn")
def chat_turn(req: ChatTurnRequest) -> Dict[str, Any]:
    logger.info(
        "chat_turn_request provider=%s user_id=%s session_id=%s turn_id=%s model=%s user_text=%s",
        req.provider,
        req.user_id,
        req.session_id,
        req.turn_id,
        req.model,
        req.user_text,
    )
    provider = runtime.provider_for(req.provider, req.model)
    orchestrator = ConversationOrchestrator(
        provider=provider,
        store=runtime.store,
        profile_manager=runtime.profile_manager,
        event_bus=runtime.event_bus,
        audit=runtime.audit,
    )

    turn_id = req.turn_id if req.turn_id is not None else len(runtime.store.l1_records(req.user_id)) + 1
    try:
        result = orchestrator.process_turn(
            user_id=req.user_id,
            session_id=req.session_id,
            turn_id=turn_id,
            user_input=req.user_text,
            model=req.model or provider.model,
            profile_field=req.profile_field,
        )
    except RuntimeError as exc:
        logger.exception(
            "chat_turn_provider_error provider=%s user_id=%s session_id=%s turn_id=%s error=%s",
            req.provider,
            req.user_id,
            req.session_id,
            turn_id,
            str(exc),
        )
        _raise_http_for_provider_error(exc, req.provider, req.model or provider.model)

    payload = _build_chat_payload(req=req, provider=provider, turn_id=turn_id, result=result)
    logger.info(
        "chat_turn_response provider=%s user_id=%s session_id=%s turn_id=%s trace_id=%s assistant_text=%s",
        req.provider,
        req.user_id,
        req.session_id,
        turn_id,
        payload.get("traceId", ""),
        payload.get("assistantText", ""),
    )
    return payload


@app.post("/api/v1/chat/stream")
def chat_stream(req: ChatTurnRequest) -> StreamingResponse:
    logger.info(
        "chat_stream_request provider=%s user_id=%s session_id=%s turn_id=%s model=%s user_text=%s",
        req.provider,
        req.user_id,
        req.session_id,
        req.turn_id,
        req.model,
        req.user_text,
    )
    provider = runtime.provider_for(req.provider, req.model)
    orchestrator = ConversationOrchestrator(
        provider=provider,
        store=runtime.store,
        profile_manager=runtime.profile_manager,
        event_bus=runtime.event_bus,
        audit=runtime.audit,
    )

    turn_id = req.turn_id if req.turn_id is not None else len(runtime.store.l1_records(req.user_id)) + 1

    def event_stream() -> Iterable[str]:
        queue: Queue[Any] = Queue()
        sentinel = object()
        state: Dict[str, Any] = {"result": None, "error": None}

        def _worker() -> None:
            try:
                result = orchestrator.process_turn(
                    user_id=req.user_id,
                    session_id=req.session_id,
                    turn_id=turn_id,
                    user_input=req.user_text,
                    model=req.model or provider.model,
                    profile_field=req.profile_field,
                    on_token=lambda chunk: queue.put(chunk),
                )
                state["result"] = result
            except RuntimeError as exc:
                state["error"] = exc
            finally:
                queue.put(sentinel)

        Thread(target=_worker, daemon=True).start()

        while True:
            try:
                item = queue.get(timeout=0.25)
            except Empty:
                continue

            if item is sentinel:
                break

            payload = {"index": item.index, "text": item.text, "done": item.done, "traceId": item.trace_id}
            logger.info(
                "chat_stream_token provider=%s user_id=%s session_id=%s turn_id=%s index=%s text=%s",
                req.provider,
                req.user_id,
                req.session_id,
                turn_id,
                item.index,
                item.text,
            )
            yield f"event: token\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"

        if state["error"] is not None:
            err = str(state["error"])
            match = re.search(r"^\[ProviderError:(?P<category>[^\]]+)\]\s*(?P<msg>.*)$", err)
            payload = {
                "category": match.group("category") if match else "unknown",
                "message": match.group("msg") if match else err,
                "provider": req.provider,
                "model": req.model or provider.model,
            }
            logger.error(
                "chat_stream_error provider=%s user_id=%s session_id=%s turn_id=%s payload=%s",
                req.provider,
                req.user_id,
                req.session_id,
                turn_id,
                json.dumps(payload, ensure_ascii=True),
            )
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
            return

        result = state["result"]
        if result is None:
            yield "event: error\ndata: {\"category\":\"unknown\",\"message\":\"stream worker failed\"}\n\n"
            return

        done_payload = _build_chat_payload(req=req, provider=provider, turn_id=turn_id, result=result)
        logger.info(
            "chat_stream_done provider=%s user_id=%s session_id=%s turn_id=%s trace_id=%s assistant_text=%s",
            req.provider,
            req.user_id,
            req.session_id,
            turn_id,
            done_payload.get("traceId", ""),
            done_payload.get("assistantText", ""),
        )
        yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/v1/profiles/{user_id}/current")
def get_current_profile(user_id: str) -> Dict[str, Any]:
    profile = runtime.store.latest_l3(user_id)
    if profile is None:
        return {"profile": None}
    return {"profile": _to_jsonable(profile)}


@app.get("/api/v1/profiles/{user_id}/versions")
def get_profile_versions(user_id: str) -> Dict[str, Any]:
    return {"versions": _to_jsonable(runtime.store.l3_versions(user_id))}


@app.get("/api/v1/profiles/{user_id}/visualization/cards")
def get_profile_cards(user_id: str, min_confidence: float = 0.5) -> Dict[str, Any]:
    profile = runtime.store.latest_l3(user_id)
    if profile is None:
        return {"cards": []}
    return {"cards": _to_jsonable(build_persona_cards(profile, min_confidence=min_confidence))}


@app.get("/api/v1/profiles/{user_id}/visualization/wordcloud")
def get_profile_wordcloud(user_id: str, recency_half_life_days: float = 7.0) -> Dict[str, Any]:
    profile = runtime.store.latest_l3(user_id)
    if profile is None:
        return {"entries": []}
    return {"entries": _to_jsonable(build_word_cloud(profile, recency_half_life_days=recency_half_life_days))}


@app.post("/api/v1/profiles/{user_id}/fields/{field_name}/rollback")
def rollback_profile_field(user_id: str, field_name: str, body: RollbackRequest) -> Dict[str, bool]:
    ok = runtime.profile_manager.rollback_field(user_id=user_id, field_name=field_name, threshold=body.threshold)
    return {"success": ok}


@app.get("/api/v1/memories/l1/{user_id}")
def search_l1_memories(user_id: str, query: str = "", limit: int = 5) -> Dict[str, Any]:
    if query.strip():
        records = runtime.store.search_l1(user_id=user_id, query=query, limit=limit)
    else:
        records = runtime.store.recent_l1(user_id=user_id, limit=limit)
    return {"records": _to_jsonable(records)}


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    session = runtime.store.get_l2(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": _to_jsonable(session)}


@app.delete("/api/v1/users/{user_id}")
def delete_user(user_id: str, scope: str = Query(default="complete")) -> Dict[str, Any]:
    if scope not in {"complete", "l1", "l2", "l3", "profile_only", "partial"}:
        raise HTTPException(status_code=400, detail="Invalid scope")
    return runtime.privacy.delete_scope(user_id=user_id, scope=scope, actor="api")
