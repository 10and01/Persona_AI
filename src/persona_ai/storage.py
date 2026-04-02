from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime
import hashlib
from typing import Dict, List, Optional, Protocol, Tuple

from .memory_events import MemoryEventBus, make_event
from .models import L1DialogRecord, L2SessionContext, L3ProfileVersion, MemoryMetadata, RetentionPolicy


class EpisodicVectorStore(Protocol):
    def upsert_dialog(self, record: L1DialogRecord, metadata: MemoryMetadata, idempotency_key: str) -> None:
        raise NotImplementedError

    def search_dialogs(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
        sentiment: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[str]:
        raise NotImplementedError

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        raise NotImplementedError


class SemanticGraphStore(Protocol):
    def upsert_profile_version(self, version: L3ProfileVersion, metadata: MemoryMetadata) -> None:
        raise NotImplementedError

    def latest_profile_version(self, user_id: str) -> Optional[int]:
        raise NotImplementedError

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        raise NotImplementedError


class NoopEpisodicVectorStore:
    def upsert_dialog(self, record: L1DialogRecord, metadata: MemoryMetadata, idempotency_key: str) -> None:
        _ = (record, metadata, idempotency_key)

    def search_dialogs(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
        sentiment: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[str]:
        _ = (user_id, query, limit, sentiment, start_time, end_time)
        return []

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        _ = (user_id, scope)
        return 0


class NoopSemanticGraphStore:
    def upsert_profile_version(self, version: L3ProfileVersion, metadata: MemoryMetadata) -> None:
        _ = (version, metadata)

    def latest_profile_version(self, user_id: str) -> Optional[int]:
        _ = user_id
        return None

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        _ = (user_id, scope)
        return 0


class MemoryStore:
    def __init__(
        self,
        retention: Optional[RetentionPolicy] = None,
        event_bus: Optional[MemoryEventBus] = None,
        episodic_store: Optional[EpisodicVectorStore] = None,
        semantic_store: Optional[SemanticGraphStore] = None,
    ) -> None:
        self.retention = retention or RetentionPolicy()
        self.event_bus = event_bus
        self.episodic_store = episodic_store or NoopEpisodicVectorStore()
        self.semantic_store = semantic_store or NoopSemanticGraphStore()
        self._l1: List[L1DialogRecord] = []
        self._l2: Dict[str, L2SessionContext] = {}
        self._l3: Dict[str, List[L3ProfileVersion]] = defaultdict(list)

    @staticmethod
    def normalize_metadata(data: Dict[str, object]) -> MemoryMetadata:
        return MemoryMetadata.from_dict({
            "timestamp": data.get("timestamp"),
            "trace_id": data.get("trace_id", ""),
            "confidence": data.get("confidence", 0.0),
            "source_turn_id": data.get("source_turn_id", -1),
        })

    def append_l1(self, record: L1DialogRecord) -> None:
        self._l1.append(record)
        metadata = self.normalize_metadata(
            {
                "timestamp": record.occurred_at,
                "trace_id": record.metadata.get("trace_id", ""),
                "confidence": record.metadata.get("confidence", 0.0),
                "source_turn_id": record.turn_id,
            }
        )
        content_hash = hashlib.sha256(f"{record.user_input}|{record.assistant_output}".encode("utf-8")).hexdigest()[:16]
        idempotency_key = f"{record.user_id}:{record.session_id}:{record.turn_id}:{content_hash}"
        self.episodic_store.upsert_dialog(record, metadata, idempotency_key)
        if self.event_bus:
            trace_id = str(record.metadata.get("trace_id", ""))
            if trace_id:
                self.event_bus.publish(
                    make_event(
                        layer="L1",
                        operation="append",
                        user_id=record.user_id,
                        session_id=record.session_id,
                        turn_id=record.turn_id,
                        trace_id=trace_id,
                        after={"record_id": record.record_id},
                    )
                )

    def l1_records(self, user_id: Optional[str] = None) -> List[L1DialogRecord]:
        if user_id is None:
            return list(self._l1)
        return [r for r in self._l1 if r.user_id == user_id]

    def recent_l1(self, user_id: str, limit: int = 5) -> List[L1DialogRecord]:
        records = [r for r in self._l1 if r.user_id == user_id]
        records.sort(key=lambda r: r.occurred_at, reverse=True)
        return records[: max(0, limit)]

    def search_l1(self, user_id: str, query: str, limit: int = 5) -> List[L1DialogRecord]:
        terms = {term for term in query.lower().split() if len(term) > 1}
        if not terms:
            return self.recent_l1(user_id=user_id, limit=limit)

        scored: List[Tuple[int, datetime, L1DialogRecord]] = []
        for record in self._l1:
            if record.user_id != user_id:
                continue
            entities = " ".join(str(e) for e in record.metadata.get("entities", []))
            haystack = f"{record.user_input} {record.assistant_output} {entities}".lower()
            overlap = sum(1 for term in terms if term in haystack)
            if overlap:
                scored.append((overlap, record.occurred_at, record))

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [record for _, _, record in scored[: max(0, limit)]]

    def upsert_l2(self, ctx: L2SessionContext, turn_id: int = 0, trace_id: str = "") -> None:
        before = self._l2.get(ctx.session_id)
        self._l2[ctx.session_id] = replace(ctx)
        if self.event_bus and trace_id:
            self.event_bus.publish(
                make_event(
                    layer="L2",
                    operation="update",
                    user_id=ctx.user_id,
                    session_id=ctx.session_id,
                    turn_id=turn_id,
                    trace_id=trace_id,
                    before={"keys": sorted((before.context if before else {}).keys())},
                    after={"keys": sorted(ctx.context.keys())},
                )
            )

    def get_l2(self, session_id: str) -> Optional[L2SessionContext]:
        ctx = self._l2.get(session_id)
        return replace(ctx) if ctx else None

    def append_l3_version(self, version: L3ProfileVersion) -> None:
        versions = self._l3[version.user_id]
        previous = versions[-1] if versions else None
        versions.append(version)
        versions.sort(key=lambda v: v.version)
        metadata = self.normalize_metadata(
            {
                "timestamp": version.created_at,
                "trace_id": version.metadata.get("trace_id", ""),
                "confidence": max((f.confidence for f in version.fields.values()), default=0.0),
                "source_turn_id": version.metadata.get("turn_id", -1),
            }
        )
        self.semantic_store.upsert_profile_version(version, metadata)
        if self.event_bus:
            trace_id = str(version.metadata.get("trace_id", ""))
            session_id = str(version.metadata.get("session_id", ""))
            turn_id = int(version.metadata.get("turn_id", -1))
            if trace_id and session_id and turn_id >= 0:
                self.event_bus.publish(
                    make_event(
                        layer="L3",
                        operation="version_write",
                        user_id=version.user_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        trace_id=trace_id,
                        before={
                            "version": previous.version if previous else None,
                            "fields": sorted(previous.fields.keys()) if previous else [],
                        },
                        after={"version": version.version, "fields": sorted(version.fields.keys())},
                    )
                )

    def latest_l3(self, user_id: str) -> Optional[L3ProfileVersion]:
        versions = self._l3.get(user_id, [])
        if not versions:
            return None
        return versions[-1]

    def l3_versions(self, user_id: str) -> List[L3ProfileVersion]:
        return list(self._l3.get(user_id, []))

    def enforce_retention(self, now: datetime) -> None:
        l1_cutoff = self.retention.l1_cutoff(now)
        self._l1 = [r for r in self._l1 if r.occurred_at >= l1_cutoff]

        l2_cutoff = self.retention.l2_cutoff(now)
        self._l2 = {k: v for k, v in self._l2.items() if v.updated_at >= l2_cutoff}

        for user_id, versions in list(self._l3.items()):
            if len(versions) > self.retention.l3_history_limit:
                self._l3[user_id] = versions[-self.retention.l3_history_limit :]

    def delete_user_scope(self, user_id: str, scope: str) -> Dict[str, int]:
        deleted = {"l1": 0, "l2": 0, "l3": 0, "episodic": 0, "semantic": 0}
        if scope in {"complete", "l1"}:
            before = len(self._l1)
            self._l1 = [r for r in self._l1 if r.user_id != user_id]
            deleted["l1"] = before - len(self._l1)

        if scope in {"complete", "l2"}:
            keys = [sid for sid, ctx in self._l2.items() if ctx.user_id == user_id]
            for sid in keys:
                del self._l2[sid]
            deleted["l2"] = len(keys)

        if scope in {"complete", "profile_only", "l3"}:
            deleted["l3"] = len(self._l3.get(user_id, []))
            self._l3[user_id] = []

        deleted["episodic"] = self.episodic_store.delete_user_scope(user_id=user_id, scope=scope)
        deleted["semantic"] = self.semantic_store.delete_user_scope(user_id=user_id, scope=scope)

        return deleted
