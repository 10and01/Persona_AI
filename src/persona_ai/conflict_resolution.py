from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .confidence import BASE_WEIGHT, recency_factor
from .models import Evidence


@dataclass(frozen=True)
class ConflictResolutionResult:
    selected_value: Any
    contradiction_detected: bool
    preference_shift: bool
    rationale: str


class ConflictResolver:
    def resolve(
        self,
        *,
        current_value: Any,
        evidence: Iterable[Evidence],
        consistency_threshold: int = 2,
    ) -> ConflictResolutionResult:
        evidence_list = list(evidence)
        if not evidence_list:
            return ConflictResolutionResult(
                selected_value=current_value,
                contradiction_detected=False,
                preference_shift=False,
                rationale="no_evidence",
            )

        value_scores = self._score_by_value(evidence_list)
        ranked = sorted(value_scores.items(), key=lambda item: item[1], reverse=True)
        selected, _ = ranked[0]

        unique_values = {item.value for item in evidence_list}
        contradiction_detected = len(unique_values) > 1

        latest_value = evidence_list[-1].value
        latest_support = sum(1 for item in evidence_list[-6:] if item.value == latest_value)
        preference_shift = latest_value != current_value and latest_support >= consistency_threshold

        if preference_shift:
            selected = latest_value
            rationale = "preference_shift_detected"
        elif contradiction_detected and latest_value != selected:
            rationale = "temporary_signal_suppressed"
        elif contradiction_detected:
            rationale = "contradiction_weighted_resolution"
        else:
            rationale = "consistent_signal"

        return ConflictResolutionResult(
            selected_value=selected,
            contradiction_detected=contradiction_detected,
            preference_shift=preference_shift,
            rationale=rationale,
        )

    def _score_by_value(self, evidence: List[Evidence]) -> Dict[Any, float]:
        scored: Dict[Any, float] = {}
        for item in evidence:
            base = BASE_WEIGHT[item.evidence_class]
            recency = recency_factor(item.occurred_at)
            score = base * max(0.0, min(item.confidence_hint, 1.0)) * recency
            scored[item.value] = scored.get(item.value, 0.0) + score
        return scored
