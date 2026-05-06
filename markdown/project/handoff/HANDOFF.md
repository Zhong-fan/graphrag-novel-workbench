# Handoff

## Repo State

- Workspace: `E:\Computer\Wyc_Xc\MVP`
- Branch: `main`
- Working tree is dirty.
- Current changed files from `git status --short`:
  - `app/api.py`
  - `app/contracts.py`
  - `app/db.py`
  - `app/models.py`
  - `frontend/package-lock.json`
  - `frontend/package.json`
  - `frontend/src/App.vue`
  - `frontend/src/style.css`
  - `frontend/src/styles/workspace.css`
  - `frontend/src/types.ts`
  - `scripts/playwright_audit.mjs` is untracked

Do not assume the tree is clean. Review diffs before continuing.

## What The User Wants

Primary user direction tonight:

- Keep iterating directly, not just suggesting.
- Use Playwright repeatedly as a real user to find UX problems.
- `写作` and `作品编辑` must be conceptually separated.
- `作品编辑` means managing already published work.
- `写作` means creating new drafts.
- The editor sidebar navigation should not be pushed to the bottom.
- Frontend-only fallback is not acceptable as the long-term solution.
- Backend must contain a real project-to-published-work association.

Latest explicit request before sleep:

> 再用 Playwright 找一遍问题，然后写一个 handoff 文件，方便明天开始

## Playwright Findings Tonight

### Confirmed Fixed

- `我的小说` left sidebar is back to pure navigation only.
- Folder actions were moved out of the sidebar into the main content header.
- Editor back button is no longer stretched vertically.
- In the draft creation view, the editor sidebar nav is visible near the top instead of being crushed to the bottom.
- `草稿创作` page now has:
  - clearer naming
  - draft status strip
  - collapsed publish area by default
- `已发布作品` no longer shows a blank screen for the current dataset.
  - Playwright path used:
    - `首页 -> 打开工作区 -> 继续创作 -> 已发布作品`
  - Result:
    - The page rendered the current published work form for `雨停前的告白`
    - Fields visible:
      - title
      - author
      - tagline
      - summary
      - visibility
      - save/delete buttons

### Still Wrong / Risky

- `frontend/src/App.vue` is structurally messy right now.
- There are leftover dead template blocks accidentally inserted under the `home` branch area.
- Build currently passes, but the file contains obvious garbage blocks that should be cleaned immediately tomorrow.
- Exact suspicious area observed:
  - around `App.vue` lines `1254` to at least `1315`
  - multiple nested `template v-if="false"` / `section v-if="false" class="novel-editor"` blocks
  - one stray `section v-else class="novel-editor"` also exists in that area
- These dead blocks are not supposed to remain in the file even if they currently do not render.

## Backend Work Completed Tonight

A real backend association started replacing the frontend guesswork.

### Added Model Fields

In `app/models.py`:

- `Novel.project_id`
- `Novel.source_generation_id`
- `Project.published_novels`
- `GenerationRun.published_novels`

### Added API Contract Fields

In `app/contracts.py`:

- `NovelCardOut.project_id`
- `NovelCardOut.source_generation_id`

### Added Serialization

In `app/api.py`:

- `_novel_card_out()` now includes:
  - `project_id`
  - `source_generation_id`

### Added Publish Linking

In `app/api.py`, when publishing from generation:

- `Novel.project = project`
- `Novel.source_generation = generation`

So newly published works should now carry real associations.

### Added DB Migration

In `app/db.py`:

- `ALTER TABLE novels ADD COLUMN project_id`
- `ALTER TABLE novels ADD COLUMN source_generation_id`

Also added a best-effort backfill query:

- joins `novels`
- `novel_chapters` first chapter
- `generation_runs`
- tries to infer:
  - `novels.project_id`
  - `novels.source_generation_id`

Important:

- this backfill is heuristic, not guaranteed perfect
- it has not yet been fully verified against the running local DB through a full app restart + API inspection

## Frontend Work Completed Tonight

### Naming Split

In `frontend/src/App.vue`:

- `写作` became `草稿创作`
- `作品编辑` became `已发布作品`
- Home CTA copy was adjusted toward draft creation instead of ambiguous “write”

### Project / Draft Flow

- `我的小说` cards now point toward continuing draft creation
- draft view shows draft status and clearer publish actions

### Published Work Selection Logic

Frontend started moving away from “only one novel, just open it” logic.

In `frontend/src/types.ts`:

- `NovelCard.project_id`
- `NovelCard.source_generation_id`

In `frontend/src/App.vue`:

- `managedNovels` now prefers filtering by `activeProject.project.id`
- `openNovelEditor()` now tries to use the project-linked set instead of generic my-novels guessing

However:

- the final cleanup of the published-work branch in `App.vue` is not complete because the file structure became messy during iterative patching

## CSS / Layout Work Completed Tonight

In `frontend/src/styles/workspace.css`:

- `.editor-sidebar` was changed so it no longer uses the same row layout as the general sidebar
- current state:
  - `.sidebar` uses `grid-template-rows: auto 1fr auto`
  - `.editor-sidebar` uses `grid-template-rows: auto auto auto`

This is the reason the editor nav is no longer forced downward by a middle `1fr` row.

## Validation Run Tonight

### Passed

- `python -m compileall app`
- `npm run build`

These passed after:

- backend association field additions
- sidebar layout fix
- frontend type updates

### Browser Validation

Repeated Playwright checks were done on:

- home
- my novels
- draft creation
- published work editor

Key confirmed path:

1. `首页`
2. `打开工作区`
3. `继续创作`
4. `已发布作品`

Observed result:

- published work editor rendered a real form instead of a blank page

## Most Important Thing To Do First Tomorrow

Clean `frontend/src/App.vue` template structure before anything else.

Specifically:

1. Open around lines `1248-1315`
2. Remove all stray dead inserted blocks:
   - nested `template v-if="false"`
   - duplicated `section v-if="false" class="novel-editor"`
   - stray `section v-else class="novel-editor"` in the wrong branch
3. Ensure:
   - `home` template ends cleanly
   - `novelEditor` template contains exactly:
     - one `v-if` branch for an opened managed novel
     - one `v-else` branch for published-work selection / empty state
   - no published-work fallback UI remains under the `home` branch

Only after that should more UX polishing continue.

## Recommended Next Steps Tomorrow

1. Clean `frontend/src/App.vue` structure first.
2. Restart the backend so `init_db()` runs and applies the new migration.
3. Verify API responses now include real associations:
   - `/api/me/novels`
   - `/api/novels/{id}`
4. Use Playwright to re-run:
   - `首页 -> 打开工作区 -> 继续创作 -> 已发布作品`
   - `首页 -> 打开工作区 -> 新建项目`
   - `草稿创作 -> 发布这份草稿 -> 已发布作品`
5. If old published works still do not link correctly:
   - inspect actual DB rows
   - improve the backfill query instead of adding more frontend guesses
6. After association is stable:
   - simplify `openNovelEditor()`
   - remove any remaining frontend fallback behavior that was only there to mask missing backend linkage
7. Continue layout cleanup:
   - published work manager should look less like a raw form
   - draft editor should reduce the feeling of one enormous textarea wall
   - project cards in `我的小说` can still be denser and cleaner

## Commands To Run First Tomorrow

From `E:\Computer\Wyc_Xc\MVP\frontend`:

```powershell
git -C .. status --short
git -C .. diff -- app/api.py app/contracts.py app/db.py app/models.py frontend/src/App.vue frontend/src/style.css frontend/src/styles/workspace.css frontend/src/types.ts
```

Then after cleaning `App.vue`:

```powershell
python -m compileall ..\app
npm run build
```

Then run the app and re-check with Playwright.

## File Priority Tomorrow

Open in this order:

1. `frontend/src/App.vue`
2. `app/models.py`
3. `app/db.py`
4. `app/api.py`
5. `app/contracts.py`
6. `frontend/src/types.ts`
7. `frontend/src/styles/workspace.css`
8. `frontend/src/style.css`

## Notes

- Do not commit or push unless the user asks.
- `frontend/package.json` and `frontend/package-lock.json` are marked modified in the worktree; review whether those changes are intentional before staging anything.
- The backend association is the correct direction. Keep pushing that, and remove fallback logic rather than expanding it.
