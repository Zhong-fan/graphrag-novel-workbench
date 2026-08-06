# Prompt Quality Lifecycle Specification

## ADDED Requirements

### Requirement: Production Prompts Are Versioned Contracts

The system SHALL assign every production prompt contract a stable identifier, version, task role, compatible model contract, and validation policy.

#### Scenario: Prompt wording changes

- **WHEN** a production prompt changes in a way that can affect output behavior
- **THEN** the system SHALL create a new prompt version
- **AND** subsequent generation traces SHALL identify that version

### Requirement: Structured Outputs Use Task-Specific Validation

The system SHALL validate structured model output against the task's schema and deterministic rules before adopting it.

#### Scenario: Model returns parseable but incomplete JSON

- **GIVEN** a response is a valid JSON object but omits a required task field
- **WHEN** the response is validated
- **THEN** the system SHALL reject it as a schema failure
- **AND** it SHALL NOT silently fill the missing mandatory field from arbitrary fallback text

### Requirement: Automatic Repair Is Bounded And Targeted

The system SHALL limit automatic repair of a failed generation stage to at most one targeted attempt unless the user explicitly requests another attempt.

#### Scenario: Repaired output still violates a blocking rule

- **WHEN** the single automatic repair attempt fails validation
- **THEN** the system SHALL stop automatic generation for that stage
- **AND** it SHALL create an actionable failure or exception record

### Requirement: Prompt Changes Pass Regression Evaluation

The system SHALL evaluate prompt or model-contract changes against a maintained regression corpus before they become the production default.

#### Scenario: Candidate prompt regresses a mandatory case

- **GIVEN** a candidate prompt fails a mandatory character, medium, schema, or story-boundary case that the current baseline passes
- **WHEN** regression results are evaluated
- **THEN** the candidate SHALL NOT become the production default

### Requirement: Generation Evidence Is Inspectable

The system SHALL persist sanitized prompt inputs, rendered prompt, provider and model, raw output or provider response summary, validation evidence, and adoption outcome for each major generation stage.

#### Scenario: User investigates an incorrect output

- **WHEN** the user expands technical generation details
- **THEN** the system SHALL show the exact prompt version, inherited asset versions, model, validation findings, and repair outcome
- **AND** it SHALL NOT expose API keys or authentication headers
