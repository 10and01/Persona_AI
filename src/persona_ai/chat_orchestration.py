from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from .audit import ImmutableAuditLog
from .chat_contract import ChatMessage, ChatRequest, ProviderAdapter, TokenChunk
from .extraction import EvidenceIngestionPipeline, ExtractionInput
from .memory_events import MemoryEventBus
from .models import L1DialogRecord, L2SessionContext, L3ProfileVersion, WorkingTurn
from .profile_manager import ProfileManager
from .storage import MemoryStore


@dataclass
class OrchestrationResult:
    trace_id: str
    assistant_output: str
    tokens: List[TokenChunk]
    memory_prompt: str = ""
    retrieval: Dict[str, object] = field(default_factory=dict)


class ConversationOrchestrator:
    def __init__(
        self,
        provider: ProviderAdapter,
        store: MemoryStore,
        profile_manager: ProfileManager,
        event_bus: MemoryEventBus,
        audit: ImmutableAuditLog,
        extractor: EvidenceIngestionPipeline | None = None,
    ) -> None:
        self.provider = provider
        self.store = store
        self.profile_manager = profile_manager
        self.event_bus = event_bus
        self.audit = audit
        self.extractor = extractor or EvidenceIngestionPipeline()

    def process_turn(
        self,
        user_id: str,
        session_id: str,
        turn_id: int,
        user_input: str,
        model: str,
        profile_field: str = "response_style",
    ) -> OrchestrationResult:
        trace_id = str(uuid4())
        previous_ctx = self.store.get_l2(session_id)
        latest_profile = self.store.latest_l3(user_id)
        episodic_hits = self.store.search_l1(user_id=user_id, query=user_input, limit=3)
        memory_prompt, retrieval_meta = self._build_memory_prompt(
            previous_ctx=previous_ctx,
            latest_profile=latest_profile,
            episodic_hits=episodic_hits,
        )

        messages: List[ChatMessage] = []
        if memory_prompt:
            messages.append(ChatMessage(role="system", content=memory_prompt))
        messages.append(ChatMessage(role="user", content=user_input))

        req = ChatRequest(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            model=model,
            messages=messages,
            stream=True,
            metadata={"retrieval": retrieval_meta},
        )

        chunks = list(self.provider.stream(req))
        assistant_output = "".join(chunk.text for chunk in chunks)
        signals = self.extractor.extract_turn_signals(user_input)
        sentiment = str(signals.get("sentiment", "neutral"))
        entities = [str(item) for item in signals.get("entities", [])]

        l1 = L1DialogRecord(
            record_id=f"{session_id}:{turn_id}",
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            user_input=user_input,
            assistant_output=assistant_output,
            occurred_at=datetime.now(timezone.utc),
            metadata={
                "trace_id": trace_id,
                "provider": self.provider.provider_name,
                "sentiment": sentiment,
                "entities": entities,
            },
        )
        self.store.append_l1(l1)

        context = dict(previous_ctx.context) if previous_ctx else {}
        working_turns = list(previous_ctx.working_turns) if previous_ctx else []
        working_turns.append(
            WorkingTurn(
                turn_id=turn_id,
                user_input=user_input,
                assistant_output=assistant_output,
                occurred_at=l1.occurred_at,
                sentiment=sentiment,
                entities=entities,
            )
        )
        working_turns = working_turns[-6:]
        summary = self._summarize_working_turns(working_turns)
        entity_focus = sorted({entity for turn in working_turns for entity in turn.entities})
        context.update(
            {
                "last_user_input": user_input,
                "last_assistant_output": assistant_output,
                "trace_id": trace_id,
                "working_summary": summary,
            }
        )

        self.store.upsert_l2(
            L2SessionContext(
                session_id=session_id,
                user_id=user_id,
                updated_at=datetime.now(timezone.utc),
                context=context,
                working_turns=working_turns,
                summary=summary,
                task_state=dict(previous_ctx.task_state) if previous_ctx else {},
                entity_focus=entity_focus,
            ),
            turn_id=turn_id,
            trace_id=trace_id,
        )

        evidence = self.extractor.ingest(ExtractionInput(text=user_input, source="chat", metadata={"value": user_input}))
        if evidence:
            self.profile_manager.aggregate_fields(
                user_id=user_id,
                field_name=profile_field,
                evidence=evidence,
                session_id=session_id,
                turn_id=turn_id,
                trace_id=trace_id,
            )

        if turn_id > 0 and turn_id % 50 == 0:
            self.event_bus.publish_distillation_requested(
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                trace_id=trace_id,
                trigger="turn_count_50",
            )

        self.audit.append(
            event_type="turn_trace",
            actor="system",
            result="ok",
            details={
                "trace_id": trace_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "token_chunks": len(chunks),
                "provider": self.provider.provider_name,
                "retrieval": retrieval_meta,
            },
        )
        return OrchestrationResult(
            trace_id=trace_id,
            assistant_output=assistant_output,
            tokens=chunks,
            memory_prompt=memory_prompt,
            retrieval=retrieval_meta,
        )

    def replay_turn(self, session_id: str, turn_id: int):
        return self.event_bus.replay_turn(session_id=session_id, turn_id=turn_id)

    def _build_memory_prompt(
        self,
        *,
        previous_ctx: Optional[L2SessionContext],
        latest_profile: Optional[L3ProfileVersion],
        episodic_hits: List[L1DialogRecord],
    ) -> tuple[str, Dict[str, object]]:
        profile_facts: List[str] = []
        profile_version = None
        if latest_profile:
            profile_version = latest_profile.version
            for name, field in latest_profile.fields.items():
                if field.confidence >= 0.60:
                    profile_facts.append(f"{name}={field.value} (confidence={field.confidence:.2f})")

        episodic_lines = [
            f"T{record.turn_id}: user={self._clip(record.user_input)}"
            for record in episodic_hits[:3]
        ]
        working_summary = previous_ctx.summary if previous_ctx else ""

        sections: List[str] = []
        if profile_facts:
            sections.append("Long-term profile: " + "; ".join(profile_facts))
        if episodic_lines:
            sections.append("Relevant episodic history: " + " | ".join(episodic_lines))
        if working_summary:
            sections.append("Current working-memory summary: " + working_summary)

        retrieval_meta: Dict[str, object] = {
            "semantic_version": profile_version,
            "semantic_fields": sorted(latest_profile.fields.keys()) if latest_profile else [],
            "episodic_record_ids": [record.record_id for record in episodic_hits[:3]],
            "working_summary_present": bool(working_summary),
        }

        if not sections:
            return "", retrieval_meta

        prompt = "Use the following memory context when it is relevant and safe.\n" + "\n".join(sections)
        return prompt, retrieval_meta

    def _summarize_working_turns(self, turns: List[WorkingTurn]) -> str:
        if not turns:
            return ""
        snippets: List[str] = []
        for turn in turns[-3:]:
            snippets.append(
                f"T{turn.turn_id} user={self._clip(turn.user_input)} assistant={self._clip(turn.assistant_output)}"
            )
        return " | ".join(snippets)

    @staticmethod
    def _clip(text: str, size: int = 80) -> str:
        trimmed = " ".join(text.split())
        if len(trimmed) <= size:
            return trimmed
        return trimmed[: size - 3] + "..."
