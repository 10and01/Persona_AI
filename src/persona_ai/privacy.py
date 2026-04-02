from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from .access_policy import PurposePolicy
from .audit import ImmutableAuditLog
from .storage import MemoryStore


@dataclass
class AccessDecision:
    approved_fields: set[str]
    denied_fields: set[str]


class PrivacyController:
    def __init__(self, policy: PurposePolicy, store: MemoryStore, audit: ImmutableAuditLog) -> None:
        self.policy = policy
        self.store = store
        self.audit = audit

    def authorize(self, purpose: str, requested_fields: Iterable[str], actor: str) -> AccessDecision:
        requested = set(requested_fields)
        approved = self.policy.allowed_fields(purpose, requested)
        denied = requested - approved
        result = "ok" if not denied else "partial"
        self.audit.append(
            event_type="access_check",
            actor=actor,
            result=result,
            details={"purpose": purpose, "approved": sorted(approved), "denied": sorted(denied)},
        )
        return AccessDecision(approved_fields=approved, denied_fields=denied)

    def redact(self, data: Dict[str, Any], approved_fields: set[str]) -> Dict[str, Any]:
        return {k: v for k, v in data.items() if k in approved_fields}

    def delete_scope(self, user_id: str, scope: str, actor: str) -> Dict[str, Any]:
        deleted = self.store.delete_user_scope(user_id=user_id, scope=scope)
        event = self.audit.append(
            event_type="delete",
            actor=actor,
            result="ok",
            details={"user_id": user_id, "scope": scope, "deleted": deleted},
        )
        return {"deleted": deleted, "proof_hash": event.hash}

    def export_profile(self, user_id: str, consent: bool, actor: str) -> str:
        if not consent:
            self.audit.append(
                event_type="export",
                actor=actor,
                result="denied",
                details={"user_id": user_id, "reason": "consent_required"},
            )
            raise PermissionError("explicit consent required")

        latest = self.store.latest_l3(user_id)
        payload: Dict[str, Any] = {}
        if latest:
            payload = {name: {"value": field.value, "confidence": field.confidence} for name, field in latest.fields.items()}

        self.audit.append(
            event_type="export",
            actor=actor,
            result="ok",
            details={"user_id": user_id, "field_count": len(payload)},
        )
        return json.dumps(payload, ensure_ascii=True)

    def preview_profile(self, user_id: str, purpose: str, requested_fields: Iterable[str], actor: str) -> Dict[str, Any]:
        decision = self.authorize(purpose=purpose, requested_fields=requested_fields, actor=actor)
        latest = self.store.latest_l3(user_id)
        profile: Dict[str, Any] = {}
        if latest:
            full = {name: {"value": field.value, "confidence": field.confidence} for name, field in latest.fields.items()}
            profile = self.redact(full, decision.approved_fields)
        self.audit.append(
            event_type="preview",
            actor=actor,
            result="ok" if profile else "partial",
            details={
                "user_id": user_id,
                "purpose": purpose,
                "approved": sorted(decision.approved_fields),
                "denied": sorted(decision.denied_fields),
                "field_count": len(profile),
            },
        )
        return profile
