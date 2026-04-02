## Context

Persona AI already provides local-first core components for L1/L2/L3 memory, extraction confidence, plugin portability, and privacy governance. However, current usage is library-centric and lacks:
- a standard provider interface for OpenAI-compatible and Anthropic-compatible APIs,
- a conversational UI to watch memory changes while chatting,
- visual profile outputs for stakeholder review and export.

This change introduces a specification baseline for these product-facing capabilities while preserving existing governance and local-first principles.

## Goals / Non-Goals

**Goals:**
- Standardize provider integration for OpenAI/Anthropic-style APIs behind one internal contract.
- Provide a real-time chat experience that visualizes L1/L2/L3 memory transitions during each turn.
- Provide persona preview as cards and word cloud, plus governed export.
- Preserve policy-first privacy behavior for every preview/export output.

**Non-Goals:**
- Building a production multi-tenant cloud deployment architecture.
- Defining billing/rate-limit strategy for external model providers.
- Replacing existing confidence/evaluation algorithms in this change.
- Committing to a single frontend framework beyond required capability behaviors.

## Decisions

### Decision 1: Provider-neutral chat interface with adapter mapping
- Choice: introduce a provider abstraction that normalizes messages, streaming chunks, usage metadata, and error types.
- Why: avoids host lock-in and allows OpenAI/Anthropic-compatible endpoints to be swapped via config.
- Alternative considered: direct per-provider calls in business logic.
- Rejected because: duplicates orchestration logic and makes testing brittle.

### Decision 2: Streaming-first conversation orchestration
- Choice: model output and memory mutation events are emitted in one ordered event stream per dialog turn.
- Why: users must observe how each response token and memory mutation contribute to profile formation in real time.
- Alternative considered: post-turn batch refresh only.
- Rejected because: cannot demonstrate evolution process during the conversation.

### Decision 3: Normalized memory mutation events
- Choice: all L1/L2/L3 writes emit normalized mutation events (`layer`, `operation`, `before`, `after`, `turn_id`, `timestamp`).
- Why: enables deterministic replay, frontend observability, and audit correlation.
- Alternative considered: UI reads stores directly and diffs locally.
- Rejected because: inconsistent across backends and hard to test.

### Decision 4: Dual persona visual outputs (cards + word cloud)
- Choice: support both structured card view and keyword-weighted word cloud using the same underlying profile snapshot.
- Why: cards serve operational review, word cloud serves intuitive communication/demo.
- Alternative considered: cards only.
- Rejected because: weaker interpretability for non-technical stakeholders.

### Decision 5: Export as governed artifacts
- Choice: exports must run through policy filtering and consent checks before generating JSON and image/vector artifacts.
- Why: visualization outputs are still personal data and must obey least-privilege/privacy constraints.
- Alternative considered: unrestricted client-side export.
- Rejected because: bypasses server-side policy enforcement and audit logging.

### Decision 6: Compatibility and determinism test strategy
- Choice: add cross-provider contract tests and turn-level determinism assertions for emitted mutation events.
- Why: the feature value depends on same memory semantics regardless of provider.
- Alternative considered: unit tests only per module.
- Rejected because: misses integration-level regressions.

## Risks / Trade-offs

- [Risk] Streaming protocol differences between providers create inconsistent chunk ordering. -> Mitigation: define strict event sequencing and provider adapter conformance tests.
- [Risk] Real-time UI increases complexity and may introduce latency. -> Mitigation: decouple token stream and memory events with bounded queues and lightweight payloads.
- [Risk] Word cloud may over-amplify low-confidence fields. -> Mitigation: default confidence threshold and visual confidence indicators.
- [Risk] Export artifacts may expose restricted fields. -> Mitigation: mandatory privacy filter before render/export plus immutable audit events.
- [Risk] Demo-first interface could diverge from core contracts. -> Mitigation: UI consumes only published contracts used by tests.

## Migration Plan

1. Define and freeze spec deltas for provider compatibility, memory observability, visualization/export, and privacy/lifecycle modifications.
2. Implement provider adapters and unified chat orchestration with streaming support.
3. Introduce memory mutation event publisher in storage/profile orchestration paths.
4. Build chat frontend with live timeline panels for L1/L2/L3 mutation events.
5. Add persona card and word cloud preview with policy-filtered export pipeline.
6. Add integration/e2e tests for provider parity, memory event determinism, and export governance.
7. Update operational and host integration docs with new interfaces and expected workflows.

Rollback strategy:
- Disable external provider adapters and route to existing local/no-op mode.
- Disable real-time event streaming while retaining core memory writes.
- Keep export endpoints blocked unless governance checks pass.

## Open Questions

- Should Anthropic support prioritize Messages API only, or include legacy completion compatibility?
- Which transport should be normative for live events (SSE, WebSocket, or both)?
- Should word cloud weights use confidence only, or confidence multiplied by recency?
- Which export formats are mandatory for MVP image artifacts (PNG only vs. PNG + SVG)?
