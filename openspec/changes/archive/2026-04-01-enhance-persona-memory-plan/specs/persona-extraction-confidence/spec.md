## ADDED Requirements

### Requirement: Evidence-classified profile extraction
The system SHALL classify profile evidence as explicit declaration, direct user feedback, behavioral signal, or statistical inference before updating persona fields.

#### Scenario: Explicit declaration precedence
- **WHEN** a user explicitly declares a stable preference
- **THEN** the system records the evidence class as explicit declaration and prioritizes it over inferred signals

#### Scenario: Conflicting evidence capture
- **WHEN** new evidence contradicts existing field value
- **THEN** the system stores contradiction evidence and recalculates field confidence

### Requirement: Confidence scoring and activation threshold
The system MUST compute field confidence using evidence quality, sample support, and recency decay, and MUST activate a field only if threshold conditions are satisfied.

#### Scenario: Threshold not met
- **WHEN** a field confidence is below activation threshold
- **THEN** the system does not apply the field for runtime personalization

#### Scenario: Threshold met and recent
- **WHEN** a field confidence meets threshold and recency policy
- **THEN** the system marks the field as actionable for personalization

### Requirement: Safe rollback on low-confidence drift
The system MUST support field-level rollback to a prior L3 version when confidence drops below rollback threshold or drift policy is violated.

#### Scenario: Drift-triggered rollback
- **WHEN** drift detection flags a high-severity shift and confidence degrades below rollback threshold
- **THEN** the system reverts the affected field to the most recent valid prior version and records an audit event
