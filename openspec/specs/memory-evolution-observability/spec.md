## ADDED Requirements

### Requirement: Real-time memory mutation events
The system SHALL emit normalized memory mutation events for L1 append, L2 update, and L3 version-write operations during live conversation turns.

#### Scenario: L1 append event emission
- **WHEN** a user-assistant turn is written into L1
- **THEN** the system emits an L1 mutation event with `turn_id`, `record_id`, and timestamp

#### Scenario: L3 version event emission
- **WHEN** profile aggregation writes a new L3 version
- **THEN** the system emits an L3 mutation event with new version metadata and changed field names

### Requirement: Turn-to-memory traceability
The system MUST associate each emitted memory mutation event with the originating session and turn identifiers.

#### Scenario: Traceability lookup
- **WHEN** observability tooling queries a turn
- **THEN** it can retrieve all related L1/L2/L3 mutation events in causal order

#### Scenario: Missing trace identifier rejection
- **WHEN** a mutation event is produced without required trace identifiers
- **THEN** the event is rejected from the public stream and logged as an integrity error

### Requirement: Deterministic replay for diagnostics
The system MUST support deterministic replay of memory evolution for a completed turn from persisted event data.

#### Scenario: Replay successful
- **WHEN** a completed turn replay is requested
- **THEN** the system reconstructs the same layer transition sequence as originally emitted
