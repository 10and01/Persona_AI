from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, Iterable

from .audit import ImmutableAuditLog
from .confidence import compute_confidence, is_actionable
from .conflict_resolution import ConflictResolver
from .models import DistillStatus, Evidence, EvidenceRef, L3ProfileField, L3ProfileVersion
from .storage import MemoryStore


class ProfileManager:
    def __init__(self, store: MemoryStore, audit_log: ImmutableAuditLog) -> None:
        self.store = store
        self.audit_log = audit_log
        self.conflict_resolver = ConflictResolver()

    def aggregate_fields(
        self,
        user_id: str,
        field_name: str,
        evidence: Iterable[Evidence],
        contradiction: bool = False,
        session_id: str = "",
        turn_id: int = -1,
        trace_id: str = "",
    ) -> L3ProfileVersion:
        latest = self.store.latest_l3(user_id)
        fields: Dict[str, L3ProfileField] = dict(latest.fields) if latest else {}

        current = fields.get(field_name, L3ProfileField(name=field_name, value=None, confidence=0.0))
        new_evidence = list(current.evidence) + list(evidence)
        new_refs = list(current.evidence_ref)
        if session_id and turn_id >= 0:
            new_refs.append(EvidenceRef(source_layer="L1", source_id=f"{session_id}:{turn_id}", source_turn_id=turn_id))
        resolution = self.conflict_resolver.resolve(current_value=current.value, evidence=new_evidence)
        contradictions = list(current.contradictions)
        if contradiction or resolution.contradiction_detected:
            contradictions.extend(list(evidence))

        confidence = compute_confidence(new_evidence, contradiction_count=len(contradictions))
        selected_value = resolution.selected_value if new_evidence else current.value
        updated = replace(
            current,
            value=selected_value,
            confidence=confidence,
            evidence=new_evidence,
            evidence_ref=new_refs,
            contradictions=contradictions,
            updated_at=datetime.now(timezone.utc),
        )
        fields[field_name] = updated

        version_num = (latest.version + 1) if latest else 1
        version = L3ProfileVersion(
            user_id=user_id,
            version=version_num,
            created_at=datetime.now(timezone.utc),
            fields=fields,
            previous_version=latest.version if latest else None,
            metadata={"session_id": session_id, "turn_id": turn_id, "trace_id": trace_id},
            distill_status=DistillStatus.COMPLETED if new_evidence else DistillStatus.SKIPPED,
        )
        self.store.append_l3_version(version)
        self.audit_log.append(
            event_type="profile_update",
            actor="system",
            result="ok",
            details={
                "user_id": user_id,
                "field_name": field_name,
                "version": version_num,
                "actionable": is_actionable(confidence),
                "conflict_rationale": resolution.rationale,
                "preference_shift": resolution.preference_shift,
            },
        )
        return version

    def rollback_field(self, user_id: str, field_name: str, threshold: float = 0.50) -> bool:
        versions = self.store.l3_versions(user_id)
        if len(versions) < 2:
            return False

        latest = versions[-1]
        field = latest.fields.get(field_name)
        if field is None:
            return False

        prev_field = versions[-2].fields.get(field_name)
        drift_violated = bool(field.contradictions) and prev_field is not None and field.confidence < prev_field.confidence
        below_threshold = field.confidence < threshold
        if not (below_threshold or drift_violated):
            return False

        for candidate in reversed(versions[:-1]):
            old = candidate.fields.get(field_name)
            if old and old.confidence >= threshold:
                new_fields = dict(latest.fields)
                new_fields[field_name] = old
                rollback_version = L3ProfileVersion(
                    user_id=user_id,
                    version=latest.version + 1,
                    created_at=datetime.now(timezone.utc),
                    fields=new_fields,
                    previous_version=latest.version,
                )
                self.store.append_l3_version(rollback_version)
                self.audit_log.append(
                    event_type="profile_rollback",
                    actor="system",
                    result="ok",
                    details={"user_id": user_id, "field_name": field_name, "to_version": candidate.version},
                )
                return True

        return False
