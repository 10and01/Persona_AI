# Operations Runbook

## Incident: Real-Time Memory Stream Breakage

1. Verify provider stream is healthy (token chunks arriving).
2. Verify mutation events include `trace_id`, `session_id`, and `turn_id`.
3. Compare emitted sequence against replay output for affected turn.
4. If ordering is broken, disable live timeline and switch to replay-only mode.
5. Record incident with impacted trace IDs and provider adapter name.

## Incident: Quality Gate Regression

1. Freeze rollout progression.
2. Compare latest offline metrics to thresholds.
3. If drift or calibration violation is confirmed, execute version-pinned rollback.
4. Keep L1 evidence immutable for investigation.
5. Record audit event and remediation owner.

## Incident: Privacy Policy Violation

1. Disable affected plugin access policy.
2. Query immutable audit trail for impacted operations.
3. Execute scoped delete if required by user request.
4. Rotate credentials and review purpose policy allow list.

## Incident: Persona Export Governance Failure

1. Block export actions if consent state is missing or stale.
2. Confirm preview/export payloads pass policy redaction checks.
3. Inspect immutable audit entries for `preview`, `export`, and denied operations.
4. Re-run policy regression tests before unblocking export.
5. Notify incident owner and attach export manifest evidence.

## Drift Response

1. Verify contradiction evidence and trend shift.
2. Apply field-level rollback for impacted profile fields.
3. Re-evaluate threshold configuration before re-enabling progression.
