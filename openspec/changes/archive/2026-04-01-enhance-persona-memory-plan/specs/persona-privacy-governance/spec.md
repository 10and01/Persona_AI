## ADDED Requirements

### Requirement: Least-privilege profile data access
The system MUST enforce purpose-based authorization and return only minimally required profile fields to plugins.

#### Scenario: Approved purpose request
- **WHEN** a plugin requests fields under an approved purpose policy
- **THEN** the system returns only policy-approved fields and redacts all others

#### Scenario: Unapproved purpose request
- **WHEN** a plugin requests fields without policy approval
- **THEN** the system denies access and records an audit entry

### Requirement: User deletion rights by scope
The system SHALL support deletion requests scoped to complete data, profile-only data, or policy-defined partial scopes.

#### Scenario: Complete deletion request
- **WHEN** a user submits a complete deletion request
- **THEN** the system removes applicable L1, L2, and L3 records and emits deletion proof metadata

#### Scenario: Profile-only deletion request
- **WHEN** a user submits a profile-only deletion request
- **THEN** the system deletes L3 profile data while preserving non-deletable records required by policy

### Requirement: Export and audit governance
The system MUST require explicit consent for profile export and MUST keep immutable audit logs for access, delete, export, and policy-denied operations.

#### Scenario: Consented profile export
- **WHEN** a user explicitly approves an export request
- **THEN** the system exports only allowed fields in configured format and logs export metadata

#### Scenario: Audit trail query
- **WHEN** governance tooling queries operation history
- **THEN** the system returns immutable audit records with operation type, actor, timestamp, and result
