## MODIFIED Requirements

### Requirement: Layer-specific lifecycle and access boundaries
The system SHALL implement three memory layers with distinct storage rules: L1 append-only raw dialog evidence, L2 mutable session context, and L3 versioned long-term persona profile.
The system SHALL additionally emit a normalized mutation event whenever L1, L2, or L3 is changed.

#### Scenario: L1 write behavior
- **WHEN** a conversation turn is processed
- **THEN** the system appends a new L1 record without mutating prior L1 records
- **AND** emits an L1 mutation event for observability

#### Scenario: L2 update behavior
- **WHEN** session context changes during an active session
- **THEN** the system updates only the active session context in L2
- **AND** emits an L2 mutation event containing changed keys metadata

#### Scenario: L3 update cadence
- **WHEN** profile aggregation runs
- **THEN** the system writes a new L3 version instead of in-place overwrite
- **AND** emits an L3 mutation event with version and field-delta metadata
