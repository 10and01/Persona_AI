from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .audit import ImmutableAuditLog
from .extraction import EvidenceIngestionPipeline, ExtractionInput
from .memory_events import MemoryEventBus
from .profile_manager import ProfileManager
from .storage import MemoryStore


@dataclass(frozen=True)
class DistillationRunResult:
    updated_fields: List[str]
    evidence_count: int


class DistillationWorker:
    def __init__(
        self,
        *,
        store: MemoryStore,
        profile_manager: ProfileManager,
        event_bus: MemoryEventBus,
        audit: ImmutableAuditLog,
        extractor: EvidenceIngestionPipeline | None = None,
    ) -> None:
        self.store = store
        self.profile_manager = profile_manager
        self.event_bus = event_bus
        self.audit = audit
        self.extractor = extractor or EvidenceIngestionPipeline()

    def distill_recent(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_id: int,
        trace_id: str,
        window_size: int = 50,
        profile_field: str = "response_style",
    ) -> DistillationRunResult:
        records = self.store.recent_l1(user_id=user_id, limit=window_size)
        evidence = []
        for record in records:
            extracted = self.extractor.ingest(
                ExtractionInput(
                    text=record.user_input,
                    source="distillation",
                    metadata={"value": record.user_input},
                )
            )
            evidence.extend(extracted)

        updated_fields: List[str] = []
        if evidence:
            self.profile_manager.aggregate_fields(
                user_id=user_id,
                field_name=profile_field,
                evidence=evidence,
                session_id=session_id,
                turn_id=turn_id,
                trace_id=trace_id,
            )
            updated_fields.append(profile_field)

        self.event_bus.publish_distillation_completed(
            user_id=user_id,
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            updated_fields=updated_fields,
            evidence_count=len(evidence),
        )
        self.audit.append(
            event_type="distillation_completed",
            actor="worker",
            result="ok",
            details={
                "trace_id": trace_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "updated_fields": updated_fields,
                "evidence_count": len(evidence),
            },
        )
        return DistillationRunResult(updated_fields=updated_fields, evidence_count=len(evidence))
