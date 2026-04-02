## MODIFIED Requirements

### Requirement: Export and audit governance
The system MUST require explicit consent for profile export and MUST keep immutable audit logs for access, delete, export, and policy-denied operations.
The system MUST apply policy filtering and redaction before any persona preview or visualization export payload is returned.

#### Scenario: Consented profile export
- **WHEN** a user explicitly approves an export request
- **THEN** the system exports only allowed fields in configured format and logs export metadata

#### Scenario: Visualization preview with field filtering
- **WHEN** preview data is requested for cards or word cloud
- **THEN** the system returns only policy-approved fields and excludes denied fields from render payloads

#### Scenario: Missing consent for visualization export
- **WHEN** an export request for persona visuals is made without explicit consent
- **THEN** the system denies export and records an immutable audit event with denial reason
