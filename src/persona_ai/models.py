from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceClass(str, Enum):
    EXPLICIT_DECLARATION = "explicit_declaration"
    DIRECT_FEEDBACK = "direct_feedback"
    BEHAVIORAL_SIGNAL = "behavioral_signal"
    STATISTICAL_INFERENCE = "statistical_inference"


class DistillStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class EvidenceRef:
    source_layer: str
    source_id: str
    source_turn_id: int


@dataclass(frozen=True)
class MemoryMetadata:
    timestamp: datetime = field(default_factory=utc_now)
    trace_id: str = ""
    confidence: float = 0.0
    source_turn_id: int = -1

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "MemoryMetadata":
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        if not isinstance(timestamp, datetime):
            timestamp = utc_now()
        return MemoryMetadata(
            timestamp=timestamp,
            trace_id=str(data.get("trace_id", "")),
            confidence=float(data.get("confidence", 0.0)),
            source_turn_id=int(data.get("source_turn_id", -1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "confidence": self.confidence,
            "source_turn_id": self.source_turn_id,
        }


@dataclass(frozen=True)
class Evidence:
    evidence_class: EvidenceClass
    value: Any
    confidence_hint: float
    occurred_at: datetime
    source: str


@dataclass(frozen=True)
class L1DialogRecord:
    record_id: str
    user_id: str
    session_id: str
    turn_id: int
    user_input: str
    assistant_output: str
    occurred_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    sentiment: str = "neutral"
    entities: List[str] = field(default_factory=list)
    evidence_ref: List[EvidenceRef] = field(default_factory=list)
    distill_status: DistillStatus = DistillStatus.PENDING


@dataclass(frozen=True)
class WorkingTurn:
    turn_id: int
    user_input: str
    assistant_output: str
    occurred_at: datetime
    sentiment: str = "neutral"
    entities: List[str] = field(default_factory=list)


@dataclass
class L2SessionContext:
    session_id: str
    user_id: str
    updated_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    working_turns: List[WorkingTurn] = field(default_factory=list)
    summary: str = ""
    task_state: Dict[str, Any] = field(default_factory=dict)
    entity_focus: List[str] = field(default_factory=list)
    distill_status: DistillStatus = DistillStatus.PENDING


@dataclass
class L3ProfileField:
    name: str
    value: Any
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    evidence_ref: List[EvidenceRef] = field(default_factory=list)
    contradictions: List[Evidence] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class L3ProfileVersion:
    user_id: str
    version: int
    created_at: datetime
    fields: Dict[str, L3ProfileField]
    previous_version: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    distill_status: DistillStatus = DistillStatus.PENDING


@dataclass(frozen=True)
class RetentionPolicy:
    l1_days: int = 30
    l2_days: int = 7
    l3_history_limit: int = 10

    def l1_cutoff(self, now: Optional[datetime] = None) -> datetime:
        now = now or utc_now()
        return now - timedelta(days=self.l1_days)

    def l2_cutoff(self, now: Optional[datetime] = None) -> datetime:
        now = now or utc_now()
        return now - timedelta(days=self.l2_days)


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor: str
    timestamp: datetime
    result: str
    details: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""
    hash: str = ""
