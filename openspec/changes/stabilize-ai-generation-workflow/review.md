# Review: Current OpenSpec And Implementation Gaps

## Scope

This review compares the current code and active OpenSpec changes with the intended quality-first, low-friction generation workflow. It records implementation evidence as of 2026-08-06. It does not modify runtime code.

## Highest-Risk Findings

### 1. Visual locks prove presence, not identity consistency

`CharacterReferenceProfile` records a locked turnaround asset, and video preflight can require that asset. The current quality result still reports visual stability and content consistency as requiring manual review. There is no automated comparison between the canonical character, the generated first frame, and sampled video frames.

Risk: a task can pass structural preflight and produce a live-action or visibly different character while still being treated as technically successful.

Required direction: add a visual-understanding gate with explicit `visual_medium_mismatch`, `character_identity_drift`, and multi-character identity-swap findings.

### 2. Previous-tail inheritance can accumulate identity drift

The current first-frame service may copy a previous shot's last-frame URI directly into the next shot's first-frame asset. The copied asset does not establish that the canonical turnaround was re-applied or revalidated.

Risk: each accepted generation becomes the source of truth for the next, allowing small errors to accumulate across a sequence.

Required direction: the canonical identity version remains authoritative. The previous tail supplies pose, motion, framing, and spatial continuity only. The next shot references both sources and passes identity validation before rendering.

### 3. The configured image capability and implementation disagree

Configuration exposes generic image fields, but `VisualAssetService` directly constructs `JimengImageClient`, checks Jimeng-specific settings, stores Jimeng-specific metadata, and uses Jimeng-specific tests.

Risk: changing the configured image model does not actually change the production path, and provider details leak into the asset domain.

Required direction: replace the direct dependency with one narrow image-generation port and a Seedream adapter. Keep provider-specific payloads and polling inside the adapter.

### 4. The video adapter does not yet expose the planned revision inputs

The Ark Seedance client currently submits text and an optional first-frame image. It does not model video reference, audio reference, multiple role-tagged references, video extension, or focused video revision.

Risk: the product concept of improving a first video into a second version cannot be implemented or audited through the current contract.

Required direction: introduce a typed video-generation request containing only currently supported inputs, validate adapter capability before submission, and add revision inputs only after provider-contract tests confirm them.

### 5. Local media and remote provider inputs lack a complete publication boundary

Generated and uploaded assets are commonly stored as local paths, while Ark image inputs require provider-readable URLs.

Risk: image-to-video works in tests with public example URLs but fails in local production, or developers add ad hoc uploads in business services.

Required direction: add one media-publication service that produces expiring provider-readable URLs, records publication provenance, and remains Docker-compatible.

### 6. Character data mixes story identity and voice settings but lacks a visual identity contract

`CharacterCard` captures name, age, gender, personality, story role, background, and voice settings. It does not version immutable visual identity, current costume or condition, forbidden visual changes, or canonical asset provenance.

Risk: prompts receive descriptive fragments but downstream outputs cannot declare exactly which identity and appearance version they used.

Required direction: add a canonical identity version and a separate appearance-state version. Keep the creator-facing requirement to one approved turnaround.

### 7. Prompt execution is centralized only partially and lacks PromptOps

Prompts are assembled in several services and helper modules. Text generation uses JSON-object mode with handwritten examples and permissive parsing rather than task-specific schema validation. Prompt identifiers, versions, model-contract versions, regression fixtures, and accepted/rejected outcome metrics are not consistently persisted.

Risk: prompt changes are hard to compare, malformed-but-parseable output is accepted, and quality regressions are discovered by users.

Required direction: add a prompt registry with typed output schemas, deterministic validators, trace persistence, and a small regression corpus. Permit at most one targeted repair for a failed stage.

### 8. Some fallback behavior is observable but product semantics remain ambiguous

The text transport may switch between Responses and Chat Completions and emits a warning. Story refinement failure preserves the unrefined draft and emits progress. These are protocol or optional-stage fallbacks, not necessarily provider fallbacks, but the product does not consistently distinguish them.

Risk: users cannot tell whether the same model used another protocol, an optional enhancement was skipped, or a different quality path was taken.

Required direction: classify fallbacks as protocol retry, optional-stage degradation, or provider/model substitution. Provider/model substitution is never implicit; optional degradation must be visible in the generation result.

### 9. Error types and retry semantics are too generic in new media integrations

The Ark client converts HTTP, network, parse, and provider failures into `RuntimeError`; it has a fixed timeout and no typed retryability signal. Broad exception wrapping can also include local programming errors.

Risk: the task runtime cannot reliably decide whether to retry, block for configuration, or ask the user for action.

Required direction: use typed adapter errors with category, provider code, retryability, safe message, and sanitized details. Retry policy belongs to orchestration, not the low-level adapter.

### 10. Current quality records overstate implementation maturity

The existing OpenSpec describes quality plans and results, but current plan content contains generic English placeholders and the result derives overall pass primarily from render completion while leaving key dimensions to manual review.

Risk: a stored quality result looks authoritative without measuring the qualities named by the contract.

Required direction: separate `render_completed` from `quality_passed`; calculate each quality dimension from evidence or mark it explicitly unverified. Final adoption requires all blocking dimensions to pass or an explicit user override.

### 11. The interaction model still exposes backend workflow duties

Existing controls ask the creator to manage context, storyboard, turnarounds, first frames, audio, preflight, and video tasks individually. The current workbench specification emphasizes intervention points but does not sufficiently constrain when the system should decide automatically.

Risk: improving transparency increases cognitive load instead of improving creative control.

Required direction: implement a deterministic production state machine with one recommended next action and an exception inbox. Preserve manual and technical controls behind progressive disclosure.

### 12. Current provider naming creates unnecessary migration coupling

Text transport, environment variables, error messages, and service initialization still use OpenAI terminology even when the configured endpoint is DeepSeek. The image path contains Jimeng names throughout domain code.

Risk: deleting obsolete providers may accidentally delete required protocol transport, while retaining names makes ownership unclear.

Required direction: rename by role and protocol deliberately. Preserve OpenAI-compatible HTTP mechanics needed by DeepSeek while removing obsolete GPT defaults and selectable runtime paths.

## Existing Strengths To Preserve

- Stable character card identifiers and shot-level character references.
- Lockable character turnaround assets and asset candidate versioning.
- Context Pack versions, source traces, and inherited generation inputs.
- First-frame requirements and explainable video preflight blocking.
- Last-frame extraction and shot dependency metadata.
- Generation prompt and provider metadata already persisted in several media paths.
- Issue-driven rework concepts in the existing quality-first workbench specification.
- Modular-monolith direction instead of premature microservices.

## Simplicity Review

The smallest sufficient architecture is a deterministic workflow coordinator plus narrow capability adapters, typed contracts, validators, and an exception inbox.

The implementation should not add a generic provider router, graph editor, autonomous multi-agent framework, visual embedding database, or provider marketplace in the first iteration. A visual embedding may be evaluated later only if semantic visual checks prove insufficient on a measured regression set.
