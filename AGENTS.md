# Personal Codex Instructions

- Always read and write files as UTF-8 unless the file clearly uses another encoding or the user explicitly asks for a different encoding.
- On Windows PowerShell, prefer commands and APIs that preserve UTF-8 encoding when reading, writing, or patching files.
- Do not treat my ideas, proposed solutions, or implementation preferences as automatically correct or as the highest-priority rule.
- Evaluate my ideas using engineering judgment: point out risks, simpler alternatives, tradeoffs, missing assumptions, and cases where the requested approach may be wrong.
- Be direct and factual when challenging an idea, and continue with the best practical solution after explaining the reasoning.

## Project Purpose

- This project exists to support film-style video continuation, novel creation, and video creation workflows.
- Product and engineering decisions should preserve the goal of helping creators turn story material into longer-form written works and video-ready creative assets.

## Runtime And Packaging Requirements

- The system must be able to run as Docker containers for stable local deployment and repeatable video generation workflows.
- Docker packaging should preserve the existing local-first product shape while making required services, environment variables, mounted data, FFmpeg access, database connectivity, and provider credentials explicit.
- Do not assume a developer's local Windows paths, shell state, globally installed tools, or manually started services when implementing containerized runtime behavior.

## Agent Generation Logic Constraints

- This section constrains Codex/Agent implementation behavior. It is not a user-facing product requirement.
- Do not hard-code generation strategy, workflow branching, provider routing, model selection, prompt variants, quality thresholds, retry behavior, or video-render decisions as scattered inline logic.
- Stable generation contracts may be fixed when they protect output quality, safety, auditability, or OpenSpec-defined behavior, such as required JSON schemas, prompt roles, continuity gates, preflight blockers, and generation transparency requirements.
- Keep generation rules centralized and traceable through prompt builders, typed service functions, configuration, database-backed settings, or explicit workflow contracts.
- When changing prompts or generation behavior, preserve OpenSpec's quality-first principles: visible generation inputs, inspectable technical details, explicit quality gates, and user-actionable rework paths.
- For video generation specifically, preserve stable first-frame/last-frame continuity, asset locking, video preflight, render context persistence, failure reasons, and rework routing before optimizing for automation speed.
- If a generation rule is temporary, provider-specific, or product-experimental, isolate it behind a clearly named function or configuration point so it can be reviewed and replaced later.

## Repository Boundaries

- Do not read, edit, move, delete, stage, commit, or upload anything under `E:\Computer\AAA_Wyc_Xc\Duanju\deleted`.
- Treat `deleted/` as a local-only holding area for unnecessary files.
- Do not stage, commit, or upload `docs/`; documentation drafts are local-only unless the user explicitly says otherwise.
