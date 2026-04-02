## ADDED Requirements

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

### Requirement: Layer retention policy
The system MUST support configurable retention windows per layer and enforce policy-driven cleanup without violating auditability requirements.

#### Scenario: L1 retention expiry
- **WHEN** L1 records exceed configured retention window
- **THEN** the system deletes or archives expired L1 records according to policy

#### Scenario: L3 version retention
- **WHEN** L3 profile versions exceed configured history limit
- **THEN** the system retains the current active version and applies configured archival/deletion policy to older versions

### Requirement: Layer access control
The system MUST enforce deny-by-default access across layers and expose only authorized fields to plugins.

#### Scenario: Unauthorized L1 access attempt
- **WHEN** a plugin requests direct L1 raw dialog access without explicit authorization
- **THEN** the system denies the request and logs an audit event

#### Scenario: Authorized L3 filtered access
- **WHEN** a plugin requests L3 fields with an approved purpose
- **THEN** the system returns only approved fields and omits redacted fields
