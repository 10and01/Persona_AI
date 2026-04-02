## 1. Core Domain And Contracts

- [x] 1.1 Define L1/L2/L3 data schemas and persistence interfaces with retention metadata.
- [x] 1.2 Implement layer access-policy model (deny-by-default, field-level allow list).
- [x] 1.3 Implement profile field dictionary with evidence class enum and provenance fields.
- [x] 1.4 Add profile versioning model and immutable history references.

## 2. Extraction And Confidence Engine

- [x] 2.1 Implement evidence ingestion pipeline for explicit declaration, feedback, behavioral, and statistical signals.
- [x] 2.2 Implement confidence scoring function using evidence quality, sample support, and recency decay.
- [x] 2.3 Implement activation gating to apply only threshold-satisfied and recent fields.
- [x] 2.4 Implement contradiction handling and field-level rollback trigger logic.

## 3. Plugin Portability Layer

- [x] 3.1 Define host-agnostic plugin contract (profile read, event hooks, telemetry append, capability declaration).
- [x] 3.2 Implement host adapter interface and contract validator for required methods.
- [x] 3.3 Build adapter compliance tests for schema conformance and error semantics.
- [x] 3.4 Add one reference plugin that consumes contract-compliant profile fields.

## 4. Privacy And Governance Controls

- [x] 4.1 Implement purpose-based authorization evaluator for plugin field requests.
- [x] 4.2 Implement redaction pipeline for unauthorized or policy-restricted fields.
- [x] 4.3 Implement scoped deletion workflow (complete, profile-only, policy-defined partial).
- [x] 4.4 Implement consented export flow with operation-level immutable audit logging.

## 5. Evaluation Gates And Rollout

- [x] 5.1 Implement offline evaluator for accuracy, calibration error, drift precision, and constraint adherence.
- [x] 5.2 Define threshold configuration and pass/fail gate evaluator.
- [x] 5.3 Implement online experiment harness with treatment/control metrics and guardrails.
- [x] 5.4 Implement canary stage progression and version-pinned rollback controller.

## 6. Verification And Documentation

- [x] 6.1 Create end-to-end test scenarios mapped to every SHALL/MUST requirement scenario in specs.
- [x] 6.2 Create host integration guide for adapter implementers and plugin developers.
- [x] 6.3 Add operational runbook for incident rollback, drift response, and audit queries.
- [x] 6.4 Record baseline metrics and release checklist for first /opsx:apply execution.
