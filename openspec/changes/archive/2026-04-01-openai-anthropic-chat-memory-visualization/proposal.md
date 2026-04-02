## Why

Current Persona AI capabilities define memory, extraction, privacy, and evaluation contracts, but there is no standardized integration for OpenAI/Anthropic-compatible APIs and no interactive interface to observe memory evolution during real conversation turns. This gap makes it hard to validate end-user value, explain profile formation, and demo policy-safe personalization behavior.

## What Changes

- Add a provider-compatibility capability for OpenAI-compatible and Anthropic-compatible chat APIs through one host-neutral provider interface.
- Add a chat experience capability that streams model responses and real-time memory mutations (L1 append, L2 update, L3 version write) in a single session view.
- Add persona visualization and export capability to preview the final profile as cards and word cloud views.
- Extend layered memory lifecycle requirements to expose auditable memory mutation events for observability.
- Extend privacy governance requirements to enforce consent, redaction, and policy checks for visualization exports.

## Capabilities

### New Capabilities
- `llm-provider-compatibility`: Defines provider-neutral request/response contracts, OpenAI/Anthropic API mapping, and streaming/error semantics.
- `memory-evolution-observability`: Defines real-time memory mutation event contracts and turn-to-memory traceability.
- `persona-visualization-export`: Defines persona card/word-cloud rendering requirements and export formats with governance.

### Modified Capabilities
- `layered-memory-lifecycle`: Adds requirements for normalized mutation events emitted per layer operation.
- `persona-privacy-governance`: Adds requirements for consented, policy-filtered persona visualization/export.

## Impact

- Product surface: introduces an interactive chat+memory demo flow for local persona evolution.
- Integrations: adds adapter work for OpenAI-compatible and Anthropic-compatible API endpoints.
- Data governance: expands export controls from raw profile export to visualization-aware export artifacts.
- Testing: adds parity tests across providers, streaming event consistency checks, and export policy validation tests.
- Documentation: requires updated host integration and E2E scenario docs for chat visualization and export workflows.
