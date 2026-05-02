# Handoff

## Current Repo State

- Workspace: `E:\Computer\Wyc_Xc\MVP`
- Branch: `main`
- Remote: `origin` -> `https://github.com/Zhong-fan/graphrag-novel-workbench.git`
- Latest known pushed commit before this handoff: `64a50626a245726322b4c9d1e60e8e9fb8111a56`
- There are uncommitted changes in:
  - `app/api.py`
  - `app/contracts.py`
  - `frontend/src/App.vue`
  - `frontend/src/api.ts`
  - `frontend/src/stores/workbench.ts`
  - `frontend/src/style.css`
  - `frontend/src/types.ts`

Do not assume the working tree is clean. Review `git status --short` and `git diff` before continuing.

## User Direction

The user wants the novel site to feel less like a backend/admin tool and more like a simple reader/writer product.

Important product preferences:

- Avoid confusing technical terms in the UI.
- Prefer vertical/top-bottom layouts over left-right split layouts.
- Use floating toast messages for success/error feedback, not inline status text.
- Keep cards looking like cards, but allow users to switch between grid and list layout.
- For novel cards, clicking the card body should open the novel detail page. Like/favorite controls should stay fixed at the bottom-right of the card.
- The reading page can be wider than the normal app shell.
- Separate novel overview, reading, and editing into different pages.

Latest explicit request, translated:

> The novel detail overview page and the active reading page should be separate. The novel editing page should be a standalone top navigation page.

Meaning:

- Novel overview/detail page: metadata, summary, stats, actions, chapter index, and maybe comments.
- Reading page: chapter reading only, with top and bottom chapter navigation.
- Novel editor page: separate top navigation item, focused on owner editing for novel metadata and chapters.

## Work Completed In This Session

### Auth and Feedback

- Login/register were moved toward a standalone auth page instead of a small modal-like flow.
- Register form now includes:
  - confirm password
  - password visibility toggle
  - password/username requirement hints
  - copy changed from "open your writing space" to "create your writing space"
- Password visibility control uses a small eye-style icon instead of plain text.
- Error/success feedback was moved toward floating toast UI.
- Raw object errors such as `[object Object]` were addressed by normalizing displayed error messages.

### Background and Visual Polish

- Added animated page background work.
- User disliked the first obvious stripe-like ripple style and asked for a more natural, transparent water-like movement.
- The current style has been adjusted, but visual quality should still be checked in browser.

### Home, Store, Shelf, Cards

- The home hot/discussed novels layout was widened so it does not occupy only half the page.
- Home/store/shelf novel cards were adjusted.
- User later asked to restore card-like appearance while keeping a list option.
- Current direction implemented in progress:
  - `novelLayout = ref<"grid" | "list">("grid")`
  - layout toggle controls added for home/store/shelf
  - card/list CSS partially restored
- Shelf was split into:
  - favorites
  - likes
- Search was added over title/author/genre/tagline/summary/latest excerpt.
- Novel card body opens detail.
- Favorite/like buttons were fixed toward card bottom-right.

### My Novels / Creation / Writing

- "My Novels" was changed toward a management page instead of putting the whole creation workflow there.
- Creation/workflow moved toward a separate writing/workshop page.
- Added two writing modes:
  - simplified AI mode for users who only provide a paragraph and expect AI to infer/write more
  - advanced mode for users with more detailed ideas
- Added guidance/constraints/examples in project creation fields so users are not guessing required length and format.
- Some backend/system-level writing rules were moved out of user-facing prompt language:
  - dialogue should use corner brackets
  - nested quotes should use double corner brackets
  - character emotion should usually be conveyed through environment/action before dialogue, but not as a rigid rule

### Novel/Chapter Editing and Publishing

- Generated text can now be edited before being published/appended.
- Generated content can be assigned chapter metadata such as chapter number/title/summary.
- Backend additions include:
  - `UpdateNovelChapterRequest`
  - `PUT /api/novels/{novel_id}/chapters/{chapter_id}`
- Frontend API/store support added for updating a novel chapter.
- Current generated text is being split conceptually into:
  - novel body with chapters
  - temporary draft text that can be edited and appended into the novel

### Reading / Detail

- Chapter list became clickable/readable.
- Reading UI got top and bottom chapter navigation:
  - previous chapter
  - next chapter
  - chapter select dropdown
  - chapter number jump
- If there is only one chapter, navigation controls should not show.
- User then clarified that overview and reading should be separate pages.

## Important Current Code Context

Most of the frontend is still in `frontend/src/App.vue`.

Current `ViewKey` is still expected to look like:

```ts
type ViewKey = "home" | "store" | "detail" | "shelf" | "studio" | "workshop" | "profile" | "auth";
```

It still needs new views, likely:

```ts
type ViewKey =
  | "home"
  | "store"
  | "detail"
  | "reader"
  | "shelf"
  | "studio"
  | "workshop"
  | "novelEditor"
  | "profile"
  | "auth";
```

Relevant state/computed/functions already exist in `App.vue`:

- `currentNovel`
- `selectedChapterId`
- `chapterJumpNo`
- `chapterEditForm`
- `selectedChapter`
- `sortedChapters`
- `previousChapter`
- `nextChapter`
- `hasChapterNavigation`
- `selectChapterById`
- `jumpToChapterNo`
- `submitUpdateChapter`
- `submitAppendChapter`
- `submitUpdateNovel`
- `isManagingCurrentNovel`

The current `detail` template still mixes:

- novel overview hero/metadata/actions
- reader section
- chapter editor
- novel metadata editor
- append generated draft form
- comments

This is the main unfinished task.

## Recommended Next Implementation

1. Add `reader` and `novelEditor` to `ViewKey`.
2. Add top navigation item `Novel Editor` using the app's Chinese UI copy.
3. Keep `detail` as the overview page only:
   - title, author, genre, tagline, summary
   - chapter count/date/stat actions
   - like/favorite/comment count
   - compact chapter index
   - clicking a chapter should call something like `openReader(chapter.id)`
4. Create a `reader` view:
   - show current chapter title/summary/content only
   - include chapter navigation above and below content
   - include a back-to-detail action
   - include edit action only if the current user owns the novel
5. Create a `novelEditor` view:
   - if no editable current novel is selected, show an empty state telling the user to choose a novel from My Novels
   - if the user owns the current novel, show:
     - novel metadata edit form
     - chapter selector
     - chapter edit form
     - append generated draft form when a draft exists
6. Move wide layout styling away from generic `.novel-detail` and apply it to the reader page instead.
7. Run verification:
   - `npm run build`
   - `python -m compileall app`

## Suggested Helper Functions

Add functions similar to:

```ts
function openReader(chapterId?: number) {
  if (chapterId) {
    selectedChapterId.value = chapterId;
  }
  currentView.value = "reader";
}

function openNovelEditor() {
  currentView.value = "novelEditor";
}
```

When opening a novel detail:

```ts
selectedChapterId.value = currentNovel.value?.chapters[0]?.id ?? null;
currentView.value = "detail";
```

The chapter index on detail should not render the full chapter body.

## Files To Review First Next Time

- `frontend/src/App.vue`
- `frontend/src/style.css`
- `frontend/src/stores/workbench.ts`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `app/api.py`
- `app/contracts.py`

Useful commands:

```powershell
git status --short
git diff --stat
rg -n "type ViewKey|currentView|novel-detail|selectedChapter|submitUpdateChapter|submitAppendChapter|novelEditor" frontend/src/App.vue
rg -n "\.novel-detail|\.novel-reader|\.chapter-nav|\.reader" frontend/src/style.css frontend/src/App.vue
```

## Verification Status

Before the final split request, these passed earlier:

```powershell
npm run build
python -m compileall app
```

After the latest request, implementation was stopped by the user before code changes were made. Re-run both after continuing work.

## Notes

- Do not commit or push unless the user asks again.
- There may be unrelated/generated files in the workspace. Review before staging.
- Avoid reverting user changes. Work with the current dirty tree.
- If committing later, inspect `git status --short` carefully and stage only intended files.
