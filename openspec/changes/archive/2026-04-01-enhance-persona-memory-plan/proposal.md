## Why

Current planning covers high-level architecture but does not yet define enforceable product requirements for cross-host portability, confidence-governed profile updates, and privacy-safe plugin access. We need a spec-driven baseline now so implementation can proceed with testable acceptance criteria and predictable integration behavior.

## What Changes

- Define a three-layer memory lifecycle with explicit retention, access boundaries, and update cadence for L1 (raw dialog), L2 (session context), and L3 (long-term persona profile).
- Standardize persona extraction and confidence scoring rules, including evidence classes, activation thresholds, recency decay, and rollback conditions.
- Introduce a portable plugin contract and host adapter contract so one persona plugin can run across different personal agent hosts with minimal host-specific code.
- Define privacy and governance requirements: least-privilege data access, consented export, field-level redaction, deletion rights, and auditable operations.
- Add measurable validation requirements for offline and online evaluation to gate rollout and regression control.

## Capabilities

### New Capabilities
- `layered-memory-lifecycle`: Specifies lifecycle, retention, access scope, and update behavior for L1/L2/L3 memory layers.
- `persona-extraction-confidence`: Specifies how user-profile fields are extracted, scored, activated, and revised over time.
- `persona-plugin-portability`: Specifies plugin contract, host adapter interface, event hooks, and compatibility expectations.
- `persona-privacy-governance`: Specifies privacy controls, deletion/export rights, auditability, and policy enforcement.
- `persona-evaluation-gates`: Specifies offline and online metrics, thresholds, and rollout/revert gates.

### Modified Capabilities
- None.

## Impact

- Documentation: new change artifacts under openspec/changes/enhance-persona-memory-plan.
- Product contracts: introduces normative requirements for memory, profile, plugin, privacy, and evaluation behavior.
- Integrations: affects agent host integration API and plugin development workflow.
- Operations: adds metric and audit dependencies for rollout governance.
