from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from persona_ai.access_policy import PurposePolicy
from persona_ai.audit import ImmutableAuditLog
from persona_ai.chat_contract import ChatMessage, ChatRequest
from persona_ai.chat_orchestration import ConversationOrchestrator
from persona_ai.extraction import EvidenceIngestionPipeline
from persona_ai.memory_events import MemoryEventBus
from persona_ai.models import L3ProfileField, L3ProfileVersion
from persona_ai.persona_visualization import build_persona_cards, build_word_cloud, export_visual_manifest
from persona_ai.privacy import PrivacyController
from persona_ai.profile_manager import ProfileManager
from persona_ai.provider_adapters import AnthropicCompatibleAdapter, OpenAICompatibleAdapter
from persona_ai.storage import MemoryStore


def _openai_transport(url, headers, payload, timeout):
    _ = (url, headers, timeout)
    return {
        "choices": [{"message": {"content": "Hello from adapter"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def _anthropic_transport(url, headers, payload, timeout):
    _ = (url, headers, payload, timeout)
    return {
        "content": [{"type": "text", "text": "Hello from adapter"}],
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


class TestChatMemoryVisualization(unittest.TestCase):
    def test_provider_contract_parity(self) -> None:
        request = ChatRequest(
            user_id="u1",
            session_id="s1",
            turn_id=1,
            trace_id="trace-1",
            model="mock-model",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
        )
        openai = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=_openai_transport,
        )
        anthropic = AnthropicCompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=_anthropic_transport,
        )
        o = openai.generate(request)
        a = anthropic.generate(request)

        self.assertEqual(o.output_text, a.output_text)
        self.assertEqual(o.usage.prompt_tokens, a.usage.prompt_tokens)
        self.assertEqual(o.usage.completion_tokens, a.usage.completion_tokens)

    def test_turn_memory_events_and_replay(self) -> None:
        event_bus = MemoryEventBus()
        audit = ImmutableAuditLog()
        store = MemoryStore(event_bus=event_bus)
        profile = ProfileManager(store, audit)

        payloads = []

        def transport_with_capture(url, headers, payload, timeout):
            _ = (url, headers, timeout)
            payloads.append(payload)
            return {
                "choices": [{"message": {"content": "Hello from adapter"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }

        provider = OpenAICompatibleAdapter(
            base_url="https://example.invalid/v1",
            api_key="k",
            model="mock-model",
            transport=transport_with_capture,
        )
        orchestrator = ConversationOrchestrator(
            provider=provider,
            store=store,
            profile_manager=profile,
            event_bus=event_bus,
            audit=audit,
            extractor=EvidenceIngestionPipeline(),
        )

        result = orchestrator.process_turn(
            user_id="u1",
            session_id="s1",
            turn_id=1,
            user_input="I prefer concise answers",
            model="mock-model",
        )
        self.assertTrue(result.trace_id)
        self.assertIn("Hello", result.assistant_output)

        events = event_bus.for_turn("s1", 1)
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual([events[0].layer, events[1].layer, events[2].layer], ["L1", "L2", "L3"])

        replay = orchestrator.replay_turn("s1", 1)
        self.assertEqual([e.layer for e in replay[:3]], ["L1", "L2", "L3"])

        second = orchestrator.process_turn(
            user_id="u1",
            session_id="s1",
            turn_id=2,
            user_input="Please keep it concise again",
            model="mock-model",
        )
        self.assertTrue(second.memory_prompt)
        self.assertTrue(second.retrieval.get("working_summary_present"))
        self.assertTrue(payloads[-1]["messages"][0]["role"] == "system")

        latest_ctx = store.get_l2("s1")
        self.assertIsNotNone(latest_ctx)
        assert latest_ctx is not None
        self.assertTrue(latest_ctx.summary)
        self.assertLessEqual(len(latest_ctx.working_turns), 6)

    def test_preview_redaction_and_export_manifest(self) -> None:
        store = MemoryStore()
        audit = ImmutableAuditLog()
        policy = PurposePolicy({"persona_preview": {"response_style"}})
        privacy = PrivacyController(policy, store, audit)

        version = L3ProfileVersion(
            user_id="u1",
            version=1,
            created_at=datetime.now(timezone.utc),
            fields={
                "response_style": L3ProfileField("response_style", "concise", 0.91),
                "language": L3ProfileField("language", "zh", 0.95),
            },
        )
        store.append_l3_version(version)

        preview = privacy.preview_profile(
            user_id="u1",
            purpose="persona_preview",
            requested_fields=["response_style", "language"],
            actor="ui",
        )
        self.assertEqual(set(preview.keys()), {"response_style"})

        manifest_text = export_visual_manifest(
            actor="ui",
            consent=True,
            policy_version="v1",
            approved_field_count=len(preview),
            artifact_names=["persona.json", "cloud.svg"],
        )
        manifest = json.loads(manifest_text)
        self.assertEqual(manifest["approved_field_count"], 1)

    def test_card_and_word_cloud_from_same_snapshot(self) -> None:
        version = L3ProfileVersion(
            user_id="u1",
            version=3,
            created_at=datetime.now(timezone.utc),
            fields={
                "response_style": L3ProfileField("response_style", "concise", 0.9),
                "tone": L3ProfileField("tone", "friendly", 0.8),
            },
        )
        cards = build_persona_cards(version, min_confidence=0.0)
        cloud = build_word_cloud(version)

        self.assertEqual(len(cards), 2)
        self.assertEqual(len(cloud), 2)
        self.assertTrue(all(item.weight >= 0 for item in cloud))


if __name__ == "__main__":
    unittest.main()
