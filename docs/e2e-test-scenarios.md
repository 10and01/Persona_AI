# End-to-End Test Scenarios

## Provider Compatibility

1. Run equivalent prompt through OpenAI-compatible and Anthropic-compatible adapters; assert normalized response schema parity.
2. Validate normalized error category mapping for auth and rate-limit failures.
3. Validate stream chunk ordering and terminal completion behavior.

## Layered Memory Lifecycle

1. L1 append-only: process two turns and assert old L1 records remain unchanged.
2. L2 update: mutate active session context and assert only the target session is updated.
3. L3 versioning: run aggregation twice and assert version increments.
4. Real-time mutation events: assert L1 -> L2 -> L3 ordering for a complete turn.
5. Replay integrity: replay a turn and assert event sequence equals original emitted order.

## Extraction And Confidence

1. Explicit declaration precedence over inference.
2. Below-threshold field is not activated.
3. Drift-triggered rollback restores previous valid field version.

## Plugin Portability

1. Same plugin runs on two compliant host adapters.
2. Missing host adapter method blocks plugin loading.
3. Schema mismatch fails compliance validation.

## Privacy And Governance

1. Approved purpose returns only approved fields.
2. Unapproved request denied with audit event.
3. Complete delete removes L1/L2/L3 according to policy.
4. Export denied without consent.
5. Preview payload excludes denied fields before card/word-cloud render.

## Persona Visualization

1. Persona cards render value, confidence, evidence class, and updated timestamp.
2. Word cloud generates weighted terms from the same profile snapshot version.
3. Export manifest includes actor, consent, policy version, and field count.

## Evaluation Gates

1. Offline gate blocks rollout when one metric fails.
2. Online guardrail failure triggers rollback.
3. Canary progression only advances when all guardrails pass.
