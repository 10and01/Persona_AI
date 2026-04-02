# Host Integration Guide

## Provider Adapter Configuration

Supported provider adapters:
- `OpenAICompatibleAdapter`
- `AnthropicCompatibleAdapter`

Required configuration:
- `base_url`
- `api_key`
- `model`
- `timeout_seconds`

Both adapters return normalized response contracts (`output_text`, `usage`, `error`) and support stream chunk iteration for real-time UI updates.

## Required Host Adapter Methods

A host adapter must implement:
- `load_profile(user_id) -> dict`
- `get_session_context(session_id) -> dict`
- `register_event_listener(event_name, callback)`
- `append_telemetry(event_name, payload)`

## Plugin Lifecycle

1. Host loads plugin manifest.
2. Host validates adapter contract.
3. Host resolves approved profile fields by purpose.
4. Host emits `on_profile_ready`.
5. Host emits `on_dialog_turn` and `on_profile_update` over time.

## Real-Time Memory Events

When integrating chat orchestration, hosts should subscribe to normalized memory mutation events:
- L1: `append`
- L2: `update`
- L3: `version_write`

Every event should include:
- `trace_id`
- `session_id`
- `turn_id`
- `layer`
- `operation`
- `timestamp`

This allows frontend timeline rendering and deterministic turn replay.

## Frontend Integration Points

Recommended data flow:
1. Start conversation turn and open token stream.
2. Render assistant token chunks incrementally.
3. Consume mutation events and update L1/L2/L3 panels.
4. Use replay endpoint/handler to rebuild timeline after reconnect.
5. Apply policy-filtered preview payloads for card/word-cloud views.

## Compatibility Checklist

- Contract methods present and callable.
- `load_profile` returns schema-compatible dictionary.
- Event callbacks receive expected payload shape.
- Telemetry failures do not crash host process.
