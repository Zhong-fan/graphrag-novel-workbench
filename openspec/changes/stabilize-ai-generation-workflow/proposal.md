# Change: Stabilize AI Generation Without Exposing Provider Complexity

## Why

The current workbench has useful source traces, visual locks, first-frame gates, and review records, but it still exposes too many production decisions to creators while leaving several important quality decisions unverified. A locked character turnaround can be present without proving that a generated frame still depicts the same character. A previous shot's last frame can preserve motion continuity while gradually replacing the canonical identity. A completed video task can still require manual review for every meaningful visual quality dimension.

The next change should make the default workflow easier to use and more reliable without fixing the product forever to one provider or model. Current providers are deployment defaults; durable requirements are expressed as capability contracts, quality gates, provenance, and bounded recovery behavior.

## What Changes

- Introduce explicit capability roles for creative text, utility text, image generation, video generation, visual understanding, voice design, speech synthesis, and embeddings.
- Keep current model choices in centralized configuration rather than mandatory product requirements.
- Treat one approved character turnaround as the creator-facing identity input and derive the internal reference package automatically.
- Version canonical character identity separately from story-time appearance and shot-local continuity state.
- Validate visual medium and character identity before video submission and across sampled rendered frames.
- Replace tail-frame-only continuation with canonical identity plus current appearance plus continuity references.
- Add a bounded video revision path that may use the failed video and a focused correction request when the configured video capability supports it.
- Add versioned prompt contracts, schema validation, deterministic checks, one targeted repair attempt, and regression evaluation.
- Make the normal workflow system-driven and route only material uncertainty, creative identity changes, or budget exceptions to the user.
- Preserve generation inputs, model identity, costs, quality results, and failure reasons for inspection.

## Current Deployment Defaults

These values describe the intended initial deployment and SHALL remain replaceable through centralized configuration after compatibility validation:

- creative text: `deepseek-v4-pro`
- utility text: `deepseek-v4-flash`
- image generation: `doubao-seedream-5-0-lite-260128`
- video generation: `doubao-seedance-2-0-mini`
- voice workflow: Doubao voice design with Doubao TTS 2.0
- embeddings: local BGE-M3

## Non-Goals

- Do not build a generic provider marketplace, plugin framework, or free-form agent runtime.
- Do not expose model selection and low-level parameters in the normal creator workflow.
- Do not promise mathematically perfect identity consistency from generative models.
- Do not require users to manually prepare multiple face crops, expression sheets, or per-shot reference bundles.
- Do not perform unlimited generation, hidden provider fallback, or unbounded critic-and-repair loops.
- Do not make model names or providers permanent OpenSpec invariants.
- Do not implement voice cloning in this change.

## Impact

- Character, media asset, generation trace, task, and quality-result contracts require versioned additions.
- Image, video, text, vision, and voice integrations require narrow role-specific adapters.
- Storyboard-to-video orchestration requires automated preflight, quality checks, targeted rework, and exception routing.
- Existing GPT and Jimeng implementations may be removed from the active runtime after data compatibility and replacement tests are complete; historical records remain readable.
- The default product flow becomes shorter while technical diagnostics remain available in an expanded view.
