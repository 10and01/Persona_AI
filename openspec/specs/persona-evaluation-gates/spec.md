## ADDED Requirements

### Requirement: Offline quality gate
The system MUST define offline metrics for profile accuracy, confidence calibration error, drift detection precision, and constraint-adherence rate with explicit pass thresholds.

#### Scenario: Offline gate pass
- **WHEN** all offline metrics meet configured thresholds
- **THEN** the change is eligible for online experimentation

#### Scenario: Offline gate fail
- **WHEN** any offline metric falls below threshold
- **THEN** rollout is blocked and remediation actions are required

### Requirement: Online experiment gate
The system SHALL evaluate profile-enabled behavior using controlled online experiments with predefined success metrics and rollback triggers.

#### Scenario: Online experiment success
- **WHEN** treatment meets primary metric targets and does not violate latency/error guardrails
- **THEN** rollout may expand to the next stage

#### Scenario: Online guardrail violation
- **WHEN** treatment violates guardrail thresholds
- **THEN** rollout reverts to prior stage and incident review is triggered

### Requirement: Stage-based release governance
The system MUST enforce staged rollout with canary progression rules and version-pinned rollback capability.

#### Scenario: Canary progression
- **WHEN** canary stage metrics pass for required observation window
- **THEN** the system permits progression to the next rollout percentage

#### Scenario: Version-pinned rollback
- **WHEN** post-release regression is detected
- **THEN** the system restores previous validated profile policy/configuration version
