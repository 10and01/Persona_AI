## ADDED Requirements

### Requirement: Persona card preview
The system SHALL provide a persona card view showing profile fields, values, confidence, evidence class summary, and last-updated metadata.

#### Scenario: Card preview render
- **WHEN** a valid profile snapshot is available
- **THEN** the UI renders cards for each visible field with confidence indicators

#### Scenario: Low-confidence field indicator
- **WHEN** a field is below configured preview threshold
- **THEN** the UI marks it as low confidence and excludes it from default highlight sections

### Requirement: Word cloud preview
The system SHALL provide a word cloud view derived from the same profile snapshot and weighted by configured confidence/recency strategy.

#### Scenario: Word cloud generation
- **WHEN** preview data is requested
- **THEN** the system generates weighted terms from allowed profile fields and returns render-ready data

#### Scenario: Word cloud/data parity
- **WHEN** card and word cloud previews are generated for the same snapshot
- **THEN** both views reference the same profile version identifier

### Requirement: Governed preview/export artifacts
The system MUST support export of profile and visualization artifacts only after policy filtering and explicit consent checks.

#### Scenario: Export with consent
- **WHEN** a user confirms export and policy checks pass
- **THEN** the system exports allowed profile JSON and requested visual artifact format with audit metadata

#### Scenario: Export denied by policy
- **WHEN** requested fields violate policy or consent is missing
- **THEN** the system blocks export, returns denial reason, and appends immutable audit logs
