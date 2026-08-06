# Design: Capability Contracts With Guided Production

## Decision

Use a deterministic production coordinator inside the existing modular monolith. Business domains depend on narrow capability interfaces. Adapters translate those requests to the configured provider. Model and provider names are deployment defaults, not permanent domain rules.

## Capability Roles

The initial implementation defines one configured adapter for each present role:

- creative text generation
- utility text generation and structured checking
- reference-aware image generation
- first-frame and reference-aware video generation
- visual understanding and comparison
- voice design
- speech synthesis
- embeddings

This is not a general plugin system. Each role has a typed input, typed output, declared capability flags, and adapter contract tests. A model change is accepted only when it satisfies the relevant contract and regression thresholds.

## Character Identity Model

The creator supplies or approves one turnaround image. The system stores it as an immutable canonical identity version and may derive crops or supplemental references automatically.

Three kinds of state remain distinct:

1. Canonical identity version
   - stable facial structure, hair, body proportions, signature marks, base palette, and canonical turnaround asset
   - changes require explicit creator confirmation and create a new version
2. Appearance-state version
   - costume, hairstyle state, injury, wetness, carried objects, and story-valid time range
   - may evolve through the story without rewriting canonical identity
3. Shot continuity state
   - pose, screen position, facing direction, lighting, camera, and motion inherited from the preceding shot
   - never becomes the canonical identity source

Every generated first frame and video segment records the identity version, appearance version, continuity source, prompt contract version, model, and generation attempt.

## Shot Generation Sequence

For a shot containing characters, the coordinator performs:

1. resolve locked canonical identity versions
2. resolve current appearance versions
3. resolve optional previous-tail continuity reference
4. assemble and persist a versioned first-frame prompt
5. generate one first-frame candidate
6. validate expected visual medium, character identity, character-to-reference assignment, and obvious structural defects
7. submit video only after blocking checks pass
8. sample start, quarter, middle, three-quarter, and end frames
9. compare sampled frames with canonical identity and adjacent-shot continuity expectations
10. accept the segment and register its tail only after blocking checks pass

Prompt priority is:

`canonical identity > current appearance > project visual medium > prior-shot continuity > required action > aesthetic preference`

## Bounded Rework

A failing first frame is regenerated without spending video tokens. A video with correct first frame but later identity drift may receive one focused revision or regeneration attempt. The adapter may include the failed video only when its declared capabilities and provider contract support video references.

After the bounded attempt fails, the coordinator creates an exception containing the finding, recommended action, expected cost, and at most three meaningful choices. It does not silently switch provider or model.

## Prompt Lifecycle

Each prompt contract has:

- stable prompt identifier and version
- task role and compatible model contract
- ordered input sections
- typed output schema when structured output is required
- deterministic validation rules
- semantic quality checks where deterministic validation is insufficient
- repair instruction for one targeted retry
- regression fixtures and acceptance metrics

Prompt assembly uses the following order:

1. system role
2. task objective
3. output contract
4. hard constraints
5. canonical character identity
6. current story and appearance state
7. locked assets
8. current input
9. requested change
10. forbidden outcomes
11. soft preferences

Model self-reported confidence is not an acceptance signal. Acceptance is derived from schema, deterministic, semantic, and human-review evidence.

## Guided Production UX

The default workflow offers one recommended next action for each milestone, such as generating a creative plan, generating the first version, applying recommended corrections, or producing the final render.

The system automatically handles provider selection, prompt selection, dependency order, media publication, low-cost validation, and bounded retry. It requests creator input only for:

- canonical character identity or voice approval
- material story or relationship changes
- unresolved conflicting constraints
- quality failures after bounded repair
- generation that exceeds the configured budget threshold
- destructive or irreversible actions

Technical prompts, parameters, traces, and quality evidence remain inspectable in an expanded diagnostic view.

## Media Publication

Local assets remain the durable source of truth. A media-publication boundary creates temporary provider-readable URLs when an adapter cannot consume local bytes or Base64. Publication records identify the source asset, checksum, expiry, provider purpose, and sanitized failure reason. The design must work in Docker without depending on developer-specific Windows paths.

## Failure Model

Adapter failures use typed categories:

- configuration or authentication
- invalid request or unsupported capability
- rate limit or quota
- retryable provider failure
- network timeout
- invalid provider response
- content-policy rejection
- local persistence or media-processing failure

Adapters translate errors but do not decide business retries. The coordinator applies bounded retry policy and persists user-action-required states. Secrets and full authentication headers are never stored in traces.

## Migration

1. Add new contracts and tables or version fields without deleting readable historical data.
2. Add role-specific adapters and contract tests alongside current integrations.
3. Switch the image path from the direct Jimeng dependency to the configured reference-aware image capability.
4. Add media publication and verify real image-to-video submission.
5. Add visual checks in shadow mode, calibrate against fixtures, then make medium and identity checks blocking.
6. Introduce the guided coordinator over existing domain services.
7. Remove obsolete active provider paths, configuration, documentation, and tests only after replacement tests pass.

## Rejected Alternatives

- A provider plugin marketplace is rejected because only one active adapter per capability is currently required.
- A free-form agent runtime is rejected because the workflow dependencies and quality gates are deterministic.
- Tail-frame-only continuation is rejected because it accumulates identity drift.
- Mandatory manual approval of every intermediate artifact is rejected because it transfers implementation responsibility to the creator.
- Hidden provider fallback is rejected because it weakens auditability, cost control, and output consistency.
