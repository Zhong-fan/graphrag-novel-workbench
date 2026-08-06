# Media Publication Specification

## ADDED Requirements

### Requirement: Provider Media Access Uses One Publication Boundary

The system SHALL route publication of local media for remote providers through one media-publication service rather than ad hoc uploads in generation services.

#### Scenario: Video provider requires a public first-frame URL

- **GIVEN** the durable first-frame asset is stored locally
- **WHEN** the video adapter requires a provider-readable URL
- **THEN** the publication service SHALL create an expiring reference linked to the local asset and its checksum
- **AND** the video request SHALL record that publication reference as input provenance

### Requirement: Media Accessibility Is Checked Before Expensive Submission

The system SHALL verify that required provider media references are valid and unexpired before submitting a material-cost generation request.

#### Scenario: Published reference has expired

- **WHEN** preflight detects that a required reference has expired
- **THEN** the system SHALL republish or block with an actionable reason before submitting the generation request

### Requirement: Publication Is Docker-Compatible And Secret-Safe

The system SHALL publish media without depending on developer-specific local paths and SHALL keep credentials out of persisted traces.

#### Scenario: Workflow runs in Docker

- **GIVEN** media is stored in a mounted container volume
- **WHEN** a provider-readable reference is required
- **THEN** the service SHALL resolve the mounted asset through configured storage settings
- **AND** stored publication diagnostics SHALL NOT contain storage credentials or signed-query secrets
