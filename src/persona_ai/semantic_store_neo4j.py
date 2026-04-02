from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from .models import L3ProfileVersion, MemoryMetadata


@dataclass
class GraphEdgeFact:
    trait_name: str
    trait_value: str
    confidence: float
    updated_at: datetime
    evidence_count: int


class Neo4jSemanticGraphStore:
    """Neo4j-like semantic store abstraction with local fallback graph state."""

    def __init__(self) -> None:
        self._latest_version: Dict[str, int] = {}
        self._facts: Dict[str, Dict[str, GraphEdgeFact]] = {}

    def upsert_profile_version(self, version: L3ProfileVersion, metadata: MemoryMetadata) -> None:
        _ = metadata
        user_facts = self._facts.setdefault(version.user_id, {})
        for field_name, field in version.fields.items():
            user_facts[field_name] = GraphEdgeFact(
                trait_name=field_name,
                trait_value=str(field.value),
                confidence=field.confidence,
                updated_at=field.updated_at,
                evidence_count=len(field.evidence),
            )
        self._latest_version[version.user_id] = version.version

    def latest_profile_version(self, user_id: str) -> Optional[int]:
        return self._latest_version.get(user_id)

    def delete_user_scope(self, user_id: str, scope: str) -> int:
        if scope not in {"complete", "profile_only", "l3", "partial"}:
            return 0
        facts = self._facts.pop(user_id, {})
        self._latest_version.pop(user_id, None)
        return len(facts)
