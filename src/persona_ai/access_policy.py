from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Set


@dataclass
class PurposePolicy:
    allowed_by_purpose: Dict[str, Set[str]] = field(default_factory=dict)

    def is_allowed(self, purpose: str, field_name: str) -> bool:
        # Deny by default.
        return field_name in self.allowed_by_purpose.get(purpose, set())

    def allowed_fields(self, purpose: str, requested: Iterable[str]) -> Set[str]:
        approved = self.allowed_by_purpose.get(purpose, set())
        return {field for field in requested if field in approved}
