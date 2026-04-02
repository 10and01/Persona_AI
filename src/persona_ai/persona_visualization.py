from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import L3ProfileVersion


@dataclass(frozen=True)
class CardField:
    name: str
    value: Any
    confidence: float
    evidence_class: str
    updated_at: str


@dataclass(frozen=True)
class WordCloudEntry:
    term: str
    weight: float


def build_persona_cards(profile: L3ProfileVersion, min_confidence: float = 0.5) -> List[CardField]:
    cards: List[CardField] = []
    for name, field in profile.fields.items():
        evidence_class = field.evidence[-1].evidence_class.value if field.evidence else "unknown"
        cards.append(
            CardField(
                name=name,
                value=field.value,
                confidence=field.confidence,
                evidence_class=evidence_class,
                updated_at=field.updated_at.isoformat(),
            )
        )
    cards.sort(key=lambda c: c.confidence, reverse=True)
    return [c for c in cards if c.confidence >= min_confidence]


def build_word_cloud(profile: L3ProfileVersion, recency_half_life_days: float = 7.0) -> List[WordCloudEntry]:
    now = datetime.now(timezone.utc)
    out: List[WordCloudEntry] = []
    for name, field in profile.fields.items():
        age_days = max((now - field.updated_at).total_seconds() / 86400.0, 0.0)
        recency = 1.0 / (1.0 + (age_days / recency_half_life_days))
        weight = round(max(field.confidence, 0.0) * recency, 4)
        out.append(WordCloudEntry(term=f"{name}:{field.value}", weight=weight))
    out.sort(key=lambda entry: entry.weight, reverse=True)
    return out


def render_word_cloud_ascii(entries: List[WordCloudEntry]) -> str:
    lines = []
    for entry in entries:
        blocks = max(1, int(entry.weight * 20))
        lines.append(f"{entry.term} | {'#' * blocks} ({entry.weight:.2f})")
    return "\n".join(lines)


def export_visual_manifest(
    actor: str,
    consent: bool,
    policy_version: str,
    approved_field_count: int,
    artifact_names: List[str],
) -> str:
    payload: Dict[str, Any] = {
        "actor": actor,
        "consent": consent,
        "policy_version": policy_version,
        "approved_field_count": approved_field_count,
        "artifacts": artifact_names,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, ensure_ascii=True)
