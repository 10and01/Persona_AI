from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RetryRecord:
    key: str
    operation: str
    payload: Dict[str, Any]
    attempts: int
    last_error: str
    created_at: datetime
    updated_at: datetime


class RetryQueue:
    def __init__(self) -> None:
        self._records: Dict[str, RetryRecord] = {}

    def upsert_failure(self, key: str, operation: str, payload: Dict[str, Any], error: Exception) -> RetryRecord:
        now = datetime.now(timezone.utc)
        existing = self._records.get(key)
        attempts = existing.attempts + 1 if existing else 1
        record = RetryRecord(
            key=key,
            operation=operation,
            payload=payload,
            attempts=attempts,
            last_error=str(error),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._records[key] = record
        return record

    def mark_success(self, key: str) -> None:
        self._records.pop(key, None)

    def list_records(self, operation: Optional[str] = None) -> List[RetryRecord]:
        records = list(self._records.values())
        if operation:
            records = [r for r in records if r.operation == operation]
        records.sort(key=lambda r: r.updated_at)
        return records
