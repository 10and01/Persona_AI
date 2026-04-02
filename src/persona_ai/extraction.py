from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Dict, List

from .models import Evidence, EvidenceClass


@dataclass
class ExtractionInput:
    text: str
    source: str
    metadata: Dict[str, Any]


class EvidenceIngestionPipeline:
    """Simple rules-based ingestion for MVP."""

    POSITIVE_HINTS = {"great", "thanks", "love", "perfect", "好", "喜欢", "满意"}
    NEGATIVE_HINTS = {"bad", "hate", "wrong", "broken", "讨厌", "糟糕", "不行"}

    def ingest(self, item: ExtractionInput) -> List[Evidence]:
        text = item.text.lower()
        timestamp = datetime.now(timezone.utc)
        evidence: List[Evidence] = []

        if "i prefer" in text or "我更喜欢" in text:
            evidence.append(
                Evidence(
                    evidence_class=EvidenceClass.EXPLICIT_DECLARATION,
                    value=item.metadata.get("value", text),
                    confidence_hint=0.95,
                    occurred_at=timestamp,
                    source=item.source,
                )
            )

        if "too long" in text or "太长" in text or "too short" in text or "太短" in text:
            evidence.append(
                Evidence(
                    evidence_class=EvidenceClass.DIRECT_FEEDBACK,
                    value=item.metadata.get("value", text),
                    confidence_hint=0.85,
                    occurred_at=timestamp,
                    source=item.source,
                )
            )

        if item.metadata.get("behavioral_signal"):
            evidence.append(
                Evidence(
                    evidence_class=EvidenceClass.BEHAVIORAL_SIGNAL,
                    value=item.metadata["behavioral_signal"],
                    confidence_hint=0.70,
                    occurred_at=timestamp,
                    source=item.source,
                )
            )

        if item.metadata.get("statistical_inference"):
            evidence.append(
                Evidence(
                    evidence_class=EvidenceClass.STATISTICAL_INFERENCE,
                    value=item.metadata["statistical_inference"],
                    confidence_hint=0.60,
                    occurred_at=timestamp,
                    source=item.source,
                )
            )

        return evidence

    def extract_turn_signals(self, text: str) -> Dict[str, Any]:
        lower = text.lower()
        positive = sum(1 for word in self.POSITIVE_HINTS if word in lower)
        negative = sum(1 for word in self.NEGATIVE_HINTS if word in lower)

        if positive > negative:
            sentiment = "positive"
        elif negative > positive:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        code_entities = re.findall(r"`([^`]+)`", text)
        title_entities = re.findall(r"\b[A-Z][a-zA-Z0-9_]{2,}\b", text)
        entities = sorted(set(code_entities + title_entities))

        return {"sentiment": sentiment, "entities": entities}
