# GraphRAG Refactor Plan

## Background

Current GraphRAG behavior has three core problems:

1. Draft generation and GraphRAG indexing are split into separate user actions.
2. The UI reports indexing progress poorly, and users cannot tell whether work is actually succeeding, still running, or already failed.
3. The current indexing path is too heavy for small local projects, especially when using local Ollama chat models.

The result is a bad workflow:

- users manually click GraphRAG review and indexing
- indexing may stall or time out
- draft generation is later blocked by `409 Conflict`
- the user still does not know where the real failure happened

## Product Direction

GraphRAG indexing and draft generation should be treated as one connected pipeline.

Target user experience:

1. User clicks `生成草稿`
2. System checks GraphRAG state
3. If graph data is outdated or missing, system prepares inputs and starts indexing automatically
4. User sees real indexing progress and real errors
5. Once indexing succeeds, system continues into retrieval and draft generation automatically

This removes the current manual split and makes indexing feel like part of the generation pipeline rather than a separate hidden prerequisite.

## Target Workflow

### Unified generation pipeline

Recommended pipeline stages:

1. `checking_graph`
2. `building_inputs`
3. `indexing`
4. `retrieving`
5. `writing`
6. `done`
7. `failed`

The user should see these stages directly in the draft-generation flow.

### Project graph state

Project-level GraphRAG state should remain explicit:

- `uninitialized`
- `dirty`
- `indexing`
- `ready`
- `failed`

These project states are different from task-level progress states and should not be merged.

## Refactor Goals

### Goal 1: Connect indexing to draft generation

Current behavior:

- draft generation requires project status `ready`
- if not ready, API returns `409`

Target behavior:

- if project is `ready`, go directly to retrieval and writing
- if project is `uninitialized`, `dirty`, `stale`, or `failed`, generation should first trigger:
  - GraphRAG input preparation
  - GraphRAG indexing
  - readiness polling
- once indexing succeeds, generation continues automatically
- if indexing fails, the generation pipeline stops and shows the real indexing error

This means users click one button and see one continuous process.

### Goal 2: Make indexing feedback real

Current behavior reports success too early.

Target behavior:

- task submission only reports `索引任务已启动`
- only project state `ready` reports `索引完成`
- state `failed` must surface `last_error`
- long-running tasks must continue showing active progress or waiting state

The UI must not treat background submission as success.

### Goal 3: Lightweight GraphRAG for small projects

Heavy GraphRAG behavior is not justified for early-stage or small projects.

High-priority signals to preserve:

- character cards
- character state changes
- relationship changes
- world rules and world-setting facts
- ongoing event progression
- environment / location changes
- foreshadowing and unresolved setups

Lower-priority or optional signals:

- community reports
- heavy cross-document summarization
- expensive global search dependencies
- graph-wide reporting not directly needed for next draft generation

The system should optimize for reliable local retrieval first, not maximum graph richness.

### Goal 4: First-time creation vs later updates

Target indexing policy:

- first run: full graph creation
- later runs: update-oriented indexing whenever possible

Desired behavior:

1. First index:
   - build workspace
   - create baseline graph
   - produce minimal artifacts needed for retrieval

2. Later updates:
   - refresh changed canonical inputs only
   - prefer GraphRAG update-style indexing
   - avoid rebuilding the whole graph if not necessary

Fallback:

- if update path fails, fall back to full rebuild

This is the long-term direction, but it is a later phase than the generation/indexing integration.

## Recommended Implementation Order

### Phase 1: Integrate indexing into draft generation

Priority: highest

Scope:

- change generation API flow to auto-trigger indexing when needed
- expand generation progress model to include GraphRAG phases
- show one end-to-end progress timeline in the UI
- surface indexing failures directly in the generation flow

Expected outcome:

- users no longer need to manually guess when indexing is needed
- users see where failure occurs

### Phase 2: Introduce lightweight indexing mode

Priority: highest

Scope:

- reduce or disable heavy community-report paths
- reduce expensive extraction concurrency
- keep only retrieval-critical canonical inputs
- optimize for local search quality over graph completeness
- allow small projects to finish indexing reliably on local models

Expected outcome:

- small projects become practically usable
- local Ollama-based indexing becomes more realistic

### Phase 3: Split first-time create from later updates

Priority: medium

Scope:

- detect changed canonical inputs
- distinguish full graph bootstrap from incremental refresh
- use update-oriented indexing methods where stable
- keep full rebuild as fallback path

Expected outcome:

- first index remains heavier
- later indices become meaningfully cheaper

### Phase 4: UI cleanup

Priority: medium

Scope:

- reduce emphasis on manual GraphRAG controls in project settings
- treat GraphRAG review as advanced/manual override, not primary flow
- improve progress visibility
- clean up ugly project-settings navigation buttons such as `人物卡` and `项目设定`

Expected outcome:

- the interface matches the new pipeline model

## Technical Constraints

### Constraint 1: GraphRAG model compatibility

GraphRAG indexing is stricter than normal writing inference.

It may require:

- `response_format` compatibility
- stable structured output behavior
- acceptable latency under extraction workloads

This means:

- a model usable for normal prose generation may still be unusable for GraphRAG indexing
- GraphRAG chat config should remain separate from writer config

### Constraint 2: Local Ollama performance

Small local models can be compatible but still too slow.

This means lightweight indexing is not just a quality tradeoff; it is required for practical runtime.

### Constraint 3: Current codebase behavior

The current code rebuilds inputs and reruns indexing in a heavyweight way.

This means “later runs are naturally cheap” is not currently true.

That behavior must be explicitly redesigned, not assumed.

## Success Criteria

This refactor is successful when:

1. Users can click `生成草稿` without manually managing GraphRAG as a separate prerequisite
2. Users can see real indexing progress, success, and failure states
3. Small projects can finish indexing reliably on practical local setups
4. GraphRAG can preserve core canonical signals without paying the full heavy-graph cost every time
5. Later updates become cheaper than the first graph build

## Non-goals for the first pass

These should not block the first refactor pass:

- maximizing graph-wide community analysis quality
- perfect cross-document summarization
- preserving every heavy GraphRAG feature in local mode
- building a universal one-size-fits-all indexing strategy

The first pass should optimize for usability and reliability.

## Immediate next step

When implementation resumes, start from:

1. Phase 1: integrate indexing into draft generation flow
2. Phase 2: add lightweight indexing path

Do not start with full incremental-update architecture first.
That is the highest-complexity piece and should come after the workflow is already usable.
