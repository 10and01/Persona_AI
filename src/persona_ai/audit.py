from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import List

from .models import AuditEvent


class ImmutableAuditLog:
    """Append-only hash-chained audit log."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []

    @property
    def events(self) -> List[AuditEvent]:
        return list(self._events)

    def append(self, event_type: str, actor: str, result: str, details: dict) -> AuditEvent:
        prev_hash = self._events[-1].hash if self._events else "genesis"
        payload = {
            "event_type": event_type,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "details": details,
            "prev_hash": prev_hash,
        }
        event_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
            result=result,
            details=details,
            prev_hash=prev_hash,
            hash=event_hash,
        )
        self._events.append(event)
        return event

    def verify_chain(self) -> bool:
        prev_hash = "genesis"
        for event in self._events:
            payload = {
                "event_type": event.event_type,
                "actor": event.actor,
                "timestamp": event.timestamp.isoformat(),
                "result": event.result,
                "details": event.details,
                "prev_hash": prev_hash,
            }
            expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            if event.hash != expected:
                return False
            prev_hash = event.hash
        return True
