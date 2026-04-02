## Context

The current memory-system plan is architecture-oriented but not yet specified as testable requirements. The change introduces spec-level contracts so implementation across different personal-agent hosts can be consistent, portable, and auditable.

Current state:
- No formal capability specs exist in this repository.
- A high-level plan exists conceptually (L1/L2/L3, confidence, plugin portability, privacy, evaluation), but acceptance boundaries are not codified.
- /opsx apply requires tasks, which in turn depends on complete design and specs.

Constraints:
- The first implementation should be local-first and safe by default.
- Plugin portability must avoid host lock-in via a minimal common contract.
- Profile fields must not be auto-applied if confidence or recency is insufficient.
- Privacy controls (redaction, delete, export consent, audit) are mandatory, not optional.

Stakeholders:
- Personal-agent builders (host maintainers)
- Plugin developers
- End users (data owners)

## Goals / Non-Goals

**Goals:**
- Define enforceable requirements for three-layer memory lifecycle and data boundaries.
- Define deterministic profile-extraction and confidence-governance behavior.
- Define a portable plugin contract and host-adapter obligations.
- Define governance requirements for privacy, deletion rights, and auditability.
- Define rollout gates with measurable offline and online thresholds.

**Non-Goals:**
- Selecting a final runtime language/framework.
- Implementing UI/UX for profile review in this change.
- Defining cloud-vendor-specific infrastructure.
- Building production-scale distributed architecture in this phase.

## Decisions

### Decision 1: Layered memory with asymmetric mutability
- Choice: Keep L1 append-only, L2 mutable per session, L3 versioned and low-frequency updates.
- Why: Prevent accidental corruption of historical evidence while keeping session agility and stable long-term persona.
- Alternative considered: Single unified profile store.
- Rejected because: It blurs provenance and makes rollback/audit difficult.

### Decision 2: Confidence- and recency-gated profile activation
- Choice: A profile field is only actionable when confidence threshold and recency requirements are satisfied.
- Why: Reduces false personalization and drift-induced regressions.
- Alternative considered: Always apply latest inferred value.
- Rejected because: High risk of noisy/short-term behavior overriding stable preferences.

### Decision 3: Capability-first plugin portability
- Choice: Define a minimal contract (profile read, event hooks, telemetry append, capability declaration) and host adapter responsibilities.
- Why: Enables one plugin implementation to run across hosts with a thin adapter.
- Alternative considered: Host-specific plugin APIs.
- Rejected because: Creates lock-in and duplicate plugin logic.

### Decision 4: Least-privilege policy with purpose-based authorization
- Choice: Plugins must request profile fields by declared purpose and receive only approved fields.
- Why: Aligns with privacy-by-design and limits blast radius.
- Alternative considered: Full-profile read for all plugins.
- Rejected because: Violates data minimization and increases leakage risk.

### Decision 5: Gate release by measurable evaluation thresholds
- Choice: Require offline and online metrics to pass before rollout expansion.
- Why: Prevents regressions from subjective confidence in personalization quality.
- Alternative considered: Manual sign-off without metrics.
- Rejected because: Non-repeatable and risky under drift.

## Risks / Trade-offs

- [Risk] Over-conservative thresholds reduce personalization coverage. -> Mitigation: support per-domain threshold tuning with audit trails.
- [Risk] Excessive field extraction increases privacy burden. -> Mitigation: strict field dictionary and deny-by-default storage.
- [Risk] Adapter abstraction may hide host-specific failures. -> Mitigation: compliance test suite for every adapter.
- [Risk] Drift detector false positives trigger frequent review churn. -> Mitigation: dual-signal confirmation (distribution shift + contradiction evidence).
- [Risk] Evaluation overhead slows release speed. -> Mitigation: phased gates (MVP thresholds first, stricter thresholds later).

## Migration Plan

1. Author specs for the five capabilities and freeze requirement wording.
2. Implement MVP contracts for memory layers, confidence scoring, and plugin adapter in local-first mode.
3. Add policy enforcement for field-level access, delete/export operations, and audit logs.
4. Add offline evaluator and baseline datasets; establish pass/fail thresholds.
5. Run canary rollout with online A/B instrumentation.
6. Promote by stage only when gate metrics pass.

Rollback strategy:
- Disable profile-based activation and revert to default behavior.
- Pin L3 to previous profile version if drift/quality gates fail.
- Keep L1 evidence immutable for post-incident analysis.

## Open Questions

- What is the initial default confidence threshold by field type (style vs. taboo constraints vs. role)?
- How long should L1 be retained by default in local-first deployment?
- Should purpose-based authorization be user-consent-once or per-plugin-session?
- What minimum adapter test matrix is required before declaring host compatibility?
