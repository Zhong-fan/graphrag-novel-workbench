# Character Identity Continuity Specification

## ADDED Requirements

### Requirement: One Approved Turnaround Defines A Canonical Identity Version

The system SHALL allow a creator to establish a character's canonical visual identity by approving one valid turnaround image.

#### Scenario: Creator approves a turnaround

- **GIVEN** a turnaround passes basic asset validation
- **WHEN** the creator approves it for a character
- **THEN** the system SHALL create an immutable canonical identity version linked to that turnaround
- **AND** it MAY derive internal crops or supplemental references without requiring the creator to prepare them manually

### Requirement: Identity, Appearance, And Continuity State Remain Separate

The system SHALL version canonical identity independently from current appearance and shot-local continuity state.

#### Scenario: Character changes costume

- **GIVEN** the character's face and body identity remain unchanged
- **WHEN** the story introduces a new costume
- **THEN** the system SHALL create or select a new appearance-state version
- **AND** it SHALL retain the existing canonical identity version

### Requirement: Tail Frames Cannot Replace Canonical Identity

The system SHALL treat a preceding shot's tail frame as a continuity reference and SHALL NOT use it as the sole character identity source.

#### Scenario: Next shot inherits previous motion

- **GIVEN** a shot continues from a previous shot's tail frame
- **WHEN** the system prepares the next first frame or video request
- **THEN** it SHALL include the canonical identity version and current appearance version
- **AND** it SHALL use the tail frame only for pose, motion, framing, lighting, or spatial continuity

### Requirement: Character-Bearing Frames Pass Blocking Visual Checks

The system SHALL validate expected visual medium and character identity before submitting a character-bearing first frame to video generation.

#### Scenario: Anime project produces a live-action first frame

- **GIVEN** the project requires a two-dimensional anime visual medium
- **WHEN** a generated first frame is classified as live action
- **THEN** the system SHALL record a `visual_medium_mismatch` finding
- **AND** it SHALL block video submission for that frame

#### Scenario: Two characters exchange identities

- **GIVEN** a shot binds two character identities to separate references
- **WHEN** visual comparison detects that their defining traits are exchanged
- **THEN** the system SHALL record an identity-swap finding
- **AND** it SHALL reject the candidate from automatic adoption

### Requirement: Rendered Segments Are Checked Before Their Tails Are Reused

The system SHALL compare sampled rendered frames against canonical identity and continuity expectations before accepting a segment for downstream continuation.

#### Scenario: Character drifts near the end of a segment

- **GIVEN** the first frame passes identity checks
- **WHEN** a later sampled frame exceeds the configured blocking identity threshold
- **THEN** the segment SHALL NOT be marked quality-passed
- **AND** its tail SHALL NOT become an accepted downstream continuity reference

### Requirement: Canonical Identity Changes Require Confirmation

The system SHALL require explicit creator confirmation before a generated result becomes a new canonical identity version.

#### Scenario: First successful video contains a useful character frame

- **WHEN** the system proposes the frame as a supplemental identity reference
- **THEN** it SHALL keep the existing canonical version authoritative until the creator confirms the change
- **AND** the confirmation SHALL create a traceable new version instead of overwriting the previous version
