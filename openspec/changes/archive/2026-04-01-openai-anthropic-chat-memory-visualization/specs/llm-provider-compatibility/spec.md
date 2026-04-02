## ADDED Requirements

### Requirement: Provider-neutral chat contract
The system SHALL expose a provider-neutral chat generation contract that supports message input, streaming output chunks, usage metadata, and normalized error categories.

#### Scenario: Unified request accepted
- **WHEN** the host submits a contract-compliant chat request
- **THEN** the system routes it through the selected provider adapter without changing caller-facing schema

#### Scenario: Unified error mapping
- **WHEN** a provider returns a transport/auth/rate-limit/model error
- **THEN** the system maps it to normalized error categories and preserves provider diagnostics for logs

### Requirement: OpenAI-compatible adapter support
The system MUST support OpenAI-compatible APIs through configurable endpoint, key, model, and timeout settings.

#### Scenario: OpenAI-compatible completion success
- **WHEN** OpenAI-compatible credentials and endpoint are valid
- **THEN** the adapter returns streamed or non-streamed output in the normalized contract format

#### Scenario: OpenAI-compatible stream consistency
- **WHEN** stream mode is enabled
- **THEN** the adapter emits ordered chunk events and a terminal completion event

### Requirement: Anthropic-compatible adapter support
The system MUST support Anthropic-compatible APIs through equivalent configuration and contract-normalized responses.

#### Scenario: Anthropic-compatible completion success
- **WHEN** Anthropic-compatible credentials and endpoint are valid
- **THEN** the adapter returns output using the same normalized contract as other providers

#### Scenario: Cross-provider behavior parity
- **WHEN** equivalent prompts are run on supported providers
- **THEN** contract fields, stream event shapes, and terminal semantics remain consistent
