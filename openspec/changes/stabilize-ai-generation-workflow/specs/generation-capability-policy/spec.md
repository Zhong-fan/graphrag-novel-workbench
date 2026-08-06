# Generation Capability Policy Specification

## ADDED Requirements

### Requirement: Business Workflows Depend On Capability Contracts

The system SHALL route text, image, video, visual-understanding, voice-design, speech-synthesis, and embedding work through role-specific capability contracts rather than provider-specific calls in business services.

#### Scenario: Configured image model changes

- **GIVEN** a replacement image model satisfies the reference-aware image capability contract
- **WHEN** an administrator changes the centralized image configuration
- **THEN** the asset workflow SHALL use the configured adapter without changing storyboard or asset-domain logic

### Requirement: Provider Names Are Replaceable Deployment Defaults

The system SHALL treat configured providers and model names as deployment defaults rather than permanent product invariants.

#### Scenario: A model is upgraded

- **GIVEN** a candidate model passes its adapter contract and required regression thresholds
- **WHEN** the deployment configuration selects the candidate
- **THEN** the system SHALL record the selected provider and model on subsequent generation attempts
- **AND** it SHALL preserve the same domain-level capability contract

### Requirement: Runtime Substitution Is Explicit

The system SHALL NOT silently substitute a different provider or model after a generation failure.

#### Scenario: Configured provider is unavailable

- **GIVEN** the configured provider cannot complete a request
- **WHEN** bounded retries are exhausted
- **THEN** the generation SHALL enter a failed or user-action-required state with an actionable reason
- **AND** another provider or model SHALL NOT be used without an explicit configured policy and visible approval

### Requirement: Adapter Failures Are Actionable

The system SHALL translate provider failures into typed categories with retryability and sanitized diagnostic details.

#### Scenario: Provider returns a rate-limit response

- **WHEN** an adapter receives a provider rate-limit response
- **THEN** it SHALL return a rate-limit failure category and provider-safe detail
- **AND** the coordinator SHALL decide whether the request is eligible for a bounded retry
