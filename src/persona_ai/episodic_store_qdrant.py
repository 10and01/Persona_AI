from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .embedding import DeterministicHashEmbeddingProvider, EmbeddingProvider
from .models import L1DialogRecord, MemoryMetadata
from .retry_queue import RetryQueue


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class QdrantEpisodicVectorStore:
    """Qdrant-like episodic store abstraction with local fallback.

    The class keeps deterministic in-memory behavior for local runs and tests,
    while preserving the adapter surface for real Qdrant integration.
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        retry_queue: Optional[RetryQueue] = None,
    ) -> None:
        self.embedding_provider = embedding_provider or DeterministicHashEmbeddingProvider()
        self.retry_queue = retry_queue or RetryQueue()
        self._by_idempotency: Dict[str, str] = {}
        self._records: Dict[str, L1DialogRecord] = {}
        self._vectors: Dict[str, List[float]] = {}
        self._metadata: Dict[str, MemoryMetadata] = {}

    def upsert_dialog(self, record: L1DialogRecord, metadata: MemoryMetadata, idempotency_key: str) -> None:
        try:
            existing_id = self._by_idempotency.get(idempotency_key)
            record_id = existing_id or record.record_id
            self._records[record_id] = record
            self._metadata[record_id] = metadata
            self._vectors[record_id] = self.embedding_provider.embed(record.user_input)
            self._by_idempotency[idempotency_key] = record_id
            self.retry_queue.mark_success(idempotency_key)
        except Exception as exc:
            self.retry_queue.upsert_failure(
                key=idempotency_key,
                operation="episodic_upsert",
                payload={"record_id": record.record_id, "user_id": record.user_id},
                error=exc,
            )
            raise

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
        q = self.embedding_provider.embed(query)
        candidates: List[tuple[float, datetime, str]] = []

        for record_id, record in self._records.items():
            if record.user_id != user_id:
                continue
            if sentiment and record.sentiment != sentiment:
                continue
            if start_time and record.occurred_at < start_time:
                continue
            if end_time and record.occurred_at > end_time:
                continue
            score = _dot(self._vectors[record_id], q)
            candidates.append((score, record.occurred_at, record_id))

        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [record_id for _, _, record_id in candidates[: max(0, limit)]]

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        if scope not in {"complete", "l1", "partial"}:
            return 0
        keys = [record_id for record_id, record in self._records.items() if record.user_id == user_id]
        for record_id in keys:
            self._records.pop(record_id, None)
            self._vectors.pop(record_id, None)
            self._metadata.pop(record_id, None)
        self._by_idempotency = {
            idem: record_id for idem, record_id in self._by_idempotency.items() if record_id not in set(keys)
        }
        return len(keys)
