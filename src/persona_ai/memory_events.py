from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MemoryMutationEvent:
    layer: str
    operation: str
    user_id: str
    session_id: str
    turn_id: int
    trace_id: str
    timestamp: datetime
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)


class MemoryEventBus:
    def __init__(self) -> None:
        self._events: List[MemoryMutationEvent] = []

    @property
    def events(self) -> List[MemoryMutationEvent]:
        return list(self._events)

    def publish(self, event: MemoryMutationEvent) -> None:
        if not event.trace_id or not event.session_id or event.turn_id < 0:
            raise ValueError("invalid mutation event identifiers")
        self._events.append(event)

    def for_turn(self, session_id: str, turn_id: int) -> List[MemoryMutationEvent]:
        return [
            e
            for e in self._events
            if e.session_id == session_id and e.turn_id == turn_id
        ]

    def replay_turn(self, session_id: str, turn_id: int) -> List[MemoryMutationEvent]:
        events = self.for_turn(session_id=session_id, turn_id=turn_id)
        events.sort(key=lambda e: e.timestamp)
        return events

    def publish_distillation_requested(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_id: int,
        trace_id: str,
        trigger: str,
    ) -> None:
        self.publish(
            make_event(
                layer="L3",
                operation="distillation_requested",
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                trace_id=trace_id,
                after={"trigger": trigger},
            )
        )

    def publish_distillation_completed(
        self,
        *,
        user_id: str,
        session_id: str,
        turn_id: int,
        trace_id: str,
        updated_fields: List[str],
        evidence_count: int,
    ) -> None:
        self.publish(
            make_event(
                layer="L3",
                operation="distillation_completed",
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                trace_id=trace_id,
                after={
                    "updated_fields": sorted(updated_fields),
                    "evidence_count": evidence_count,
                },
            )
        )


def make_event(
    layer: str,
    operation: str,
    user_id: str,
    session_id: str,
    turn_id: int,
    trace_id: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
) -> MemoryMutationEvent:
    return MemoryMutationEvent(
        layer=layer,
        operation=operation,
        user_id=user_id,
        session_id=session_id,
        turn_id=turn_id,
        trace_id=trace_id,
        timestamp=utc_now(),
        before=before or {},
        after=after or {},
    )
