from __future__ import annotations

import unittest
from datetime import datetime, timezone

from persona_ai.access_policy import PurposePolicy
from persona_ai.adapter_validation import validate_host_adapter
from persona_ai.audit import ImmutableAuditLog
from persona_ai.evaluation import GateThresholds, OfflineMetrics, offline_gate_passed
from persona_ai.models import Evidence, EvidenceClass, L3ProfileField, L3ProfileVersion
from persona_ai.online import ExperimentResult, RolloutController
from persona_ai.privacy import PrivacyController
from persona_ai.storage import MemoryStore


class GoodAdapter:
    def load_profile(self, user_id: str):
        return {"user_id": user_id}

    def get_session_context(self, session_id: str):
        return {"session_id": session_id}

    def register_event_listener(self, event_name: str, callback):
        return None

    def append_telemetry(self, event_name: str, payload):
        return None


class BadAdapter:
    def load_profile(self, user_id: str):
        return "not-dict"


class TestPortabilityPrivacyEval(unittest.TestCase):
    def test_adapter_compliance(self) -> None:
        self.assertTrue(validate_host_adapter(GoodAdapter()).compatible)
        self.assertFalse(validate_host_adapter(BadAdapter()).compatible)

    def test_privacy_controls(self) -> None:
        store = MemoryStore()
        audit = ImmutableAuditLog()
        policy = PurposePolicy({"response_formatting": {"response_style"}})
        ctrl = PrivacyController(policy, store, audit)

        version = L3ProfileVersion(
            user_id="u1",
            version=1,
            created_at=datetime.now(timezone.utc),
            fields={
                "response_style": L3ProfileField("response_style", "detailed", 0.9),
                "language": L3ProfileField("language", "zh", 0.95),
            },
        )
        store.append_l3_version(version)

        decision = ctrl.authorize("response_formatting", ["response_style", "language"], actor="plugin")
        self.assertEqual(decision.approved_fields, {"response_style"})
        redacted = ctrl.redact({"response_style": "detailed", "language": "zh"}, decision.approved_fields)
        self.assertEqual(redacted, {"response_style": "detailed"})

        exported = ctrl.export_profile("u1", consent=True, actor="user")
        self.assertIn("response_style", exported)

    def test_offline_and_online_gates(self) -> None:
        metrics = OfflineMetrics(0.9, 0.04, 0.91, 0.999)
        self.assertTrue(offline_gate_passed(metrics, GateThresholds()))

        rollout = RolloutController(stages=[5, 25, 100], pinned_version="v1")
        stage = rollout.progress(ExperimentResult(True, True, True))
        self.assertEqual(stage, 25)
        rollback = rollout.rollback("v1")
        self.assertEqual(rollback["action"], "rollback")


if __name__ == "__main__":
    unittest.main()
