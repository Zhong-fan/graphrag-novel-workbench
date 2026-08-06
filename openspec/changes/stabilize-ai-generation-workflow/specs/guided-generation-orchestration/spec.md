# Guided Generation Orchestration Specification

## ADDED Requirements

### Requirement: The Normal Workflow Has One Recommended Next Action

The system SHALL present one recommended next action for the current production state while keeping advanced controls available through progressive disclosure.

#### Scenario: All first-frame dependencies are ready

- **GIVEN** the storyboard and required character identities are approved
- **AND** blocking first-frame checks pass
- **WHEN** the creator returns to the project
- **THEN** the system SHALL recommend continuing to the next production milestone
- **AND** it SHALL NOT require the creator to manually choose provider, model, prompt template, upload sequence, or retry parameters

### Requirement: User Decisions Are Reserved For Material Exceptions

The system SHALL request user input only when the decision materially changes creative identity, story meaning, quality acceptance, cost exposure, or irreversible state.

#### Scenario: Low-risk technical default is available

- **WHEN** the system can safely select a prompt version, dependency order, or low-cost validation parameter
- **THEN** it SHALL apply the configured default automatically
- **AND** it SHALL record the choice for later inspection

#### Scenario: Character identity remains ambiguous

- **WHEN** bounded automated checks cannot determine which character result should be adopted
- **THEN** the system SHALL add one exception with a recommended choice, reason, impact, and no more than three meaningful options

### Requirement: Automatic Adoption Is Reversible

The system SHALL preserve versions and dependency links for automatically adopted outputs so the user can return to a prior accepted state.

#### Scenario: User rejects an automatically selected first frame

- **WHEN** the user restores the prior accepted candidate
- **THEN** the system SHALL restore the corresponding downstream dependency selection
- **AND** it SHALL preserve the rejected candidate and its trace for audit unless the user explicitly deletes it

### Requirement: Costly Generation Is Budget-Aware

The system SHALL estimate material generation cost before submission and require approval when the configured project threshold would be exceeded.

#### Scenario: Planned video generation exceeds the threshold

- **WHEN** the estimated request cost exceeds the remaining automatic budget
- **THEN** the system SHALL pause before provider submission
- **AND** it SHALL show the estimate, affected shots, and lower-cost recommended option

### Requirement: Video Rework Uses Supported Inputs Only

The system SHALL include a prior video, image, or audio reference in a rework request only when the active adapter declares and verifies support for that input role.

#### Scenario: Active model cannot accept a prior video

- **GIVEN** a rendered segment needs correction
- **WHEN** the active adapter does not support video-reference revision
- **THEN** the coordinator SHALL use a supported shot regeneration path or request user action
- **AND** it SHALL NOT send an unverified payload or claim that video revision occurred
