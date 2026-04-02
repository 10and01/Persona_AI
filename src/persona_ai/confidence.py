from __future__ import annotations

from datetime import datetime, timezone
from math import exp

from .models import Evidence, EvidenceClass

BASE_WEIGHT = {
    EvidenceClass.EXPLICIT_DECLARATION: 0.95,
    EvidenceClass.DIRECT_FEEDBACK: 0.85,
    EvidenceClass.BEHAVIORAL_SIGNAL: 0.70,
    EvidenceClass.STATISTICAL_INFERENCE: 0.60,
}


def recency_factor(occurred_at: datetime, half_life_days: float = 7.0) -> float:
    now = datetime.now(timezone.utc)
    elapsed_days = max((now - occurred_at).total_seconds() / 86400.0, 0.0)
    return exp(-0.69314718056 * elapsed_days / half_life_days)


def compute_confidence(evidence: list[Evidence], contradiction_count: int = 0) -> float:
    if not evidence:
        return 0.0

    weighted = 0.0
    max_possible = 0.0
    for item in evidence:
        base = BASE_WEIGHT[item.evidence_class]
        quality = max(0.0, min(item.confidence_hint, 1.0))
        rec = recency_factor(item.occurred_at)
        score = base * quality * rec
        weighted += score
        max_possible += base

    # Keep low-sample fields usable while still rewarding larger evidence sets.
    support_factor = 0.4 + 0.6 * (len(evidence) / (len(evidence) + 5.0))
    contradiction_penalty = min(0.4, contradiction_count * 0.08)
    confidence = ((weighted / max_possible) * support_factor) - contradiction_penalty
    return max(0.0, min(confidence, 0.99))


def is_actionable(confidence: float, threshold: float = 0.70) -> bool:
    return confidence >= threshold
