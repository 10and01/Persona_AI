## 1. Provider Compatibility Baseline

- [x] 1.1 Define provider-neutral request/response/stream event schemas for chat generation.
- [x] 1.2 Implement OpenAI-compatible adapter with configurable `base_url`, `api_key`, model, and timeout settings.
- [x] 1.3 Implement Anthropic-compatible adapter with equivalent capabilities and normalized error mapping.
- [x] 1.4 Add adapter contract tests ensuring output/event parity for equivalent prompts.

## 2. Chat Orchestration And Event Streaming

- [x] 2.1 Implement conversation orchestration that emits ordered token and memory mutation events per turn.
- [x] 2.2 Define and enforce a normalized `MemoryMutationEvent` contract for L1 append, L2 update, and L3 version changes.
- [x] 2.3 Add replay support for a completed turn to reconstruct memory evolution for diagnostics.
- [x] 2.4 Add trace identifiers linking provider response segments to memory updates and audit events.

## 3. Frontend Chat And Memory Evolution Visualization

- [x] 3.1 Build a frontend chat interface for multi-turn conversation with streaming assistant output.
- [x] 3.2 Implement a live three-layer memory panel showing L1/L2/L3 state transitions in real time.
- [x] 3.3 Add a timeline view mapping each user turn to emitted memory mutation events.
- [x] 3.4 Add resilient reconnect/reload behavior preserving current session visualization state.

## 4. Persona Card/Word Cloud Preview And Export

- [x] 4.1 Implement persona card rendering with field value, confidence, evidence class, and updated timestamp.
- [x] 4.2 Implement word cloud rendering weighted by configured confidence/recency strategy.
- [x] 4.3 Implement governed export for profile JSON and visualization artifacts (image/vector) with metadata.
- [x] 4.4 Add export manifest generation for traceability (actor, consent, policy version, field count).

## 5. Privacy, Governance, And Safety Controls

- [x] 5.1 Enforce purpose-based authorization and field redaction before preview/export rendering.
- [x] 5.2 Require explicit user consent for export actions in UI and service API.
- [x] 5.3 Append immutable audit events for preview access, export success/denial, and redaction results.
- [x] 5.4 Add policy regression tests ensuring no restricted field leaks to UI payloads or export files.

## 6. Validation And Documentation

- [x] 6.1 Add end-to-end scenarios covering OpenAI/Anthropic chat flow, real-time memory evolution, and final persona formation.
- [x] 6.2 Add deterministic tests for turn-level event ordering and layer transition integrity.
- [x] 6.3 Update host integration guide with provider adapter configs, event contracts, and frontend integration points.
- [x] 6.4 Update operations runbook with rollout checks, incident handling, and export governance verification.
