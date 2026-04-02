from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from persona_ai.audit import ImmutableAuditLog
from persona_ai.chat_contract import ChatMessage, ChatRequest, ErrorCategory
from persona_ai.chat_orchestration import ConversationOrchestrator
from persona_ai.config import MemoryRuntimeConfig
from persona_ai.distillation_worker import DistillationWorker
from persona_ai.confidence import compute_confidence, is_actionable
from persona_ai.extraction import EvidenceIngestionPipeline, ExtractionInput
from persona_ai.memory_events import make_event
from persona_ai.memory_events import MemoryEventBus
from persona_ai.models import Evidence, EvidenceClass, L1DialogRecord, L2SessionContext, RetentionPolicy
from persona_ai.profile_manager import ProfileManager
from persona_ai.provider_adapters import OpenAICompatibleAdapter
from persona_ai.prompt_builder import PromptBuilder
from persona_ai.storage import MemoryStore


def _openai_transport(url, headers, payload, timeout):
    _ = (url, headers, payload, timeout)
    return {
        "choices": [{"message": {"content": "stub response"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


class TestCore(unittest.TestCase):
    def test_l1_append_and_retention(self) -> None:
        store = MemoryStore(retention=RetentionPolicy(l1_days=1, l2_days=1, l3_history_limit=2))
        now = datetime.now(timezone.utc)
        old = L1DialogRecord("1", "u", "s", 1, "hello", "hi", now - timedelta(days=2))
        new = L1DialogRecord("2", "u", "s", 2, "hello2", "hi2", now)
        store.append_l1(old)
        store.append_l1(new)
        store.enforce_retention(now)
        self.assertEqual(len(store.l1_records("u")), 1)

    def test_confidence_and_actionable(self) -> None:
        evidence = [
            Evidence(EvidenceClass.EXPLICIT_DECLARATION, "detailed", 0.95, datetime.now(timezone.utc), "user"),
            Evidence(EvidenceClass.DIRECT_FEEDBACK, "detailed", 0.9, datetime.now(timezone.utc), "user"),
        ]
        score = compute_confidence(evidence)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 0.99)
        self.assertTrue(is_actionable(score, threshold=0.2))

    def test_pipeline_classes(self) -> None:
        pipeline = EvidenceIngestionPipeline()
        out = pipeline.ingest(ExtractionInput(text="I prefer short replies", source="chat", metadata={}))
        self.assertTrue(any(e.evidence_class == EvidenceClass.EXPLICIT_DECLARATION for e in out))

    def test_clean_text_and_core_semantics(self) -> None:
        pipeline = EvidenceIngestionPipeline()
        cleaned = pipeline.clean_text("  I   need   Python   help   with   VectorStore   ")
        self.assertEqual(cleaned, "I need Python help with VectorStore")
        terms = pipeline.extract_core_semantics(cleaned, max_terms=4)
        self.assertLessEqual(len(terms), 4)
        self.assertIn("python", terms)

    def test_profile_version_and_rollback(self) -> None:
        store = MemoryStore()
        audit = ImmutableAuditLog()
        mgr = ProfileManager(store, audit)

        e1 = Evidence(EvidenceClass.EXPLICIT_DECLARATION, "detailed", 0.95, datetime.now(timezone.utc), "chat")
        mgr.aggregate_fields("u1", "response_style", [e1])

        e2 = Evidence(EvidenceClass.STATISTICAL_INFERENCE, "short", 0.2, datetime.now(timezone.utc), "model")
        e3 = Evidence(EvidenceClass.BEHAVIORAL_SIGNAL, "short", 0.3, datetime.now(timezone.utc), "behavior")
        e4 = Evidence(EvidenceClass.DIRECT_FEEDBACK, "short", 0.2, datetime.now(timezone.utc), "feedback")
        mgr.aggregate_fields("u1", "response_style", [e2, e3, e4], contradiction=True)

        self.assertTrue(mgr.rollback_field("u1", "response_style", threshold=0.3))

    def test_episodic_search_returns_relevant_records(self) -> None:
        store = MemoryStore()
        now = datetime.now(timezone.utc)
        store.append_l1(L1DialogRecord("1", "u", "s", 1, "I use Python for data tasks", "ok", now))
        store.append_l1(L1DialogRecord("2", "u", "s", 2, "Let us discuss gardening", "ok", now))

        results = store.search_l1(user_id="u", query="python workflow", limit=2)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].record_id, "1")

    def test_turn_50_emits_distillation_requested_event(self) -> None:
        event_bus = MemoryEventBus()
        store = MemoryStore(event_bus=event_bus)
        audit = ImmutableAuditLog()
        manager = ProfileManager(store, audit)
        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=_openai_transport,
        )
        orchestrator = ConversationOrchestrator(
            provider=provider,
            store=store,
            profile_manager=manager,
            event_bus=event_bus,
            audit=audit,
            extractor=EvidenceIngestionPipeline(),
        )

        orchestrator.process_turn(
            user_id="u1",
            session_id="s1",
            turn_id=50,
            user_input="I prefer concise answers",
            model="mock-model",
        )

        events = event_bus.for_turn("s1", 50)
        self.assertTrue(any(evt.operation == "distillation_requested" for evt in events))

    def test_working_window_eviction_and_prompt_budget(self) -> None:
        event_bus = MemoryEventBus()
        store = MemoryStore(event_bus=event_bus)
        audit = ImmutableAuditLog()
        manager = ProfileManager(store, audit)
        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=_openai_transport,
        )
        orchestrator = ConversationOrchestrator(
            provider=provider,
            store=store,
            profile_manager=manager,
            event_bus=event_bus,
            audit=audit,
            extractor=EvidenceIngestionPipeline(),
            runtime_config=MemoryRuntimeConfig(working_window_k=2, working_summary_turns=2, memory_prompt_token_budget=18),
        )

        for turn in range(1, 4):
            result = orchestrator.process_turn(
                user_id="u-window",
                session_id="s-window",
                turn_id=turn,
                user_input="I prefer concise answers with Python and vector retrieval context details",
                model="mock-model",
            )

        ctx = store.get_l2("s-window")
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(len(ctx.working_turns), 2)
        self.assertLessEqual(len(result.memory_prompt.split()), 18)

    def test_conflict_resolution_suppresses_temporary_signal(self) -> None:
        store = MemoryStore()
        audit = ImmutableAuditLog()
        mgr = ProfileManager(store, audit)

        base = Evidence(EvidenceClass.EXPLICIT_DECLARATION, "concise", 0.95, datetime.now(timezone.utc), "chat")
        mgr.aggregate_fields("u-contrast", "response_style", [base])

        temporary = Evidence(EvidenceClass.STATISTICAL_INFERENCE, "detailed", 0.4, datetime.now(timezone.utc), "distillation")
        mgr.aggregate_fields("u-contrast", "response_style", [temporary])

        latest = store.latest_l3("u-contrast")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.fields["response_style"].value, "concise")

    def test_turn_50_with_worker_emits_distillation_completed_event(self) -> None:
        event_bus = MemoryEventBus()
        store = MemoryStore(event_bus=event_bus)
        audit = ImmutableAuditLog()
        manager = ProfileManager(store, audit)
        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=_openai_transport,
        )
        worker = DistillationWorker(
            store=store,
            profile_manager=manager,
            event_bus=event_bus,
            audit=audit,
            extractor=EvidenceIngestionPipeline(),
        )
        orchestrator = ConversationOrchestrator(
            provider=provider,
            store=store,
            profile_manager=manager,
            event_bus=event_bus,
            audit=audit,
            extractor=EvidenceIngestionPipeline(),
            distillation_worker=worker,
        )

        orchestrator.process_turn(
            user_id="u2",
            session_id="s2",
            turn_id=50,
            user_input="I prefer concise answers",
            model="mock-model",
        )

        events = event_bus.for_turn("s2", 50)
        operations = [event.operation for event in events]
        self.assertIn("distillation_requested", operations)
        self.assertIn("distillation_completed", operations)

    def test_prompt_builder_suppresses_outlier_and_respects_budget(self) -> None:
        builder = PromptBuilder(token_budget=16, max_episodic_items=2)
        prompt = builder.build(
            semantic_facts=[
                "response_style=concise (confidence=0.90)",
                "response_style=detailed (confidence=0.40)",
                "language=zh (confidence=0.80)",
            ],
            episodic_facts=["T1 user=ask short", "T2 user=ask short", "T3 user=ask long"],
            working_summary="T7 user asks concise answer",
        )
        self.assertLessEqual(len(prompt.split()), 16)
        self.assertIn("response_style", prompt)

    def test_metadata_normalization_contract(self) -> None:
        now = datetime.now(timezone.utc)
        normalized = MemoryStore.normalize_metadata(
            {
                "timestamp": now.isoformat(),
                "trace_id": "trace-1",
                "confidence": 0.88,
                "source_turn_id": 7,
            }
        )
        as_dict = normalized.to_dict()
        self.assertEqual(as_dict["trace_id"], "trace-1")
        self.assertEqual(as_dict["source_turn_id"], 7)
        self.assertAlmostEqual(float(as_dict["confidence"]), 0.88, places=6)

    def test_distillation_completed_payload_validation(self) -> None:
        bus = MemoryEventBus()
        with self.assertRaises(ValueError):
            bus.publish(
                make_event(
                    layer="L3",
                    operation="distillation_completed",
                    user_id="u1",
                    session_id="s1",
                    turn_id=1,
                    trace_id="trace-1",
                    after={"updated_fields": "response_style", "evidence_count": 1},
                )
            )

    def test_openai_adapter_supports_responses_wire_api(self) -> None:
        def responses_transport(url, headers, payload, timeout):
            _ = (headers, timeout)
            self.assertTrue(url.endswith("/responses"))
            self.assertIn("input", payload)
            self.assertNotIn("messages", payload)
            return {
                "output_text": "stub response",
                "usage": {"input_tokens": 7, "output_tokens": 4},
            }

        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            wire_api="responses",
            transport=responses_transport,
        )

        response = provider.generate(
            ChatRequest(
                user_id="u1",
                session_id="s1",
                turn_id=1,
                trace_id="t1",
                model="mock-model",
                messages=[ChatMessage(role="user", content="hello")],
                stream=False,
            )
        )

        self.assertEqual(response.output_text, "stub response")
        self.assertEqual(response.usage.prompt_tokens, 7)
        self.assertEqual(response.usage.completion_tokens, 4)

    def test_openai_adapter_maps_non_json_transport_error(self) -> None:
        def broken_transport(url, headers, payload, timeout):
            _ = (url, headers, payload, timeout)
            raise ValueError("OpenAI upstream returned non-JSON payload")

        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=broken_transport,
        )

        response = provider.generate(
            ChatRequest(
                user_id="u1",
                session_id="s1",
                turn_id=1,
                trace_id="t1",
                model="mock-model",
                messages=[ChatMessage(role="user", content="hello")],
                stream=False,
            )
        )

        assert response.error is not None
        self.assertEqual(response.error.category, ErrorCategory.UNKNOWN)
        self.assertIn("non-JSON payload", response.error.message)


if __name__ == "__main__":
    unittest.main()
