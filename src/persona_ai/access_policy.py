from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Set


DEFAULT_PURPOSE_POLICY: Dict[str, Set[str]] = {
    "response_formatting": {"response_style", "tone", "language"},
    "memory_injection": {"response_style", "tone", "language", "focus_area"},
    "persona_preview": {"response_style", "tone", "language", "focus_area"},
}


@dataclass
class PurposePolicy:
    allowed_by_purpose: Dict[str, Set[str]] = field(default_factory=dict)

    def is_allowed(self, purpose: str, field_name: str) -> bool:
        # Deny by default.
        return field_name in self.allowed_by_purpose.get(purpose, set())

    def allowed_fields(self, purpose: str, requested: Iterable[str]) -> Set[str]:
        approved = self.allowed_by_purpose.get(purpose, set())
        return {field for field in requested if field in approved}


def build_default_policy() -> PurposePolicy:
    return PurposePolicy(allowed_by_purpose={k: set(v) for k, v in DEFAULT_PURPOSE_POLICY.items()})
