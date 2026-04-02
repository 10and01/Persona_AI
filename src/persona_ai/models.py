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


@dataclass
class L3ProfileField:
    name: str
    value: Any
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
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
