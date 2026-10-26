# Agent board — S1: the Board in the desktop app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The desktop app gets an editable *Board* section (columns, cards with `↳ WI-n` for a story's tasks, drag and
keyboard moves, a story panel listing its tasks, an add form that creates a task under a story), so this development
can be tracked as story WI-14 with tasks S1–S5 created and moved from the app.

**Architecture:** No new backend logic: the section reads `GET /api/kanban` and `GET /api/kanban/item` and writes
`POST /api/kanban/{init,add,move}` with the app token, which already writes the board. The Kanban's pure helpers that
both apps need move to `@camaron/ui` (as `libs.js` did); the app's own pure helpers live in
`desktop/renderer/src/board.js`. Story parents come from the user-stories work (its plan's Task 4), not from here.

**Tech Stack:** React 19 + Vite + Vitest (`.camarones/desktop/renderer`, `.camarones/portal/app`), `@camaron/ui`;
Python stdlib HTTP server (`lib/serve.py`) + pytest.

**Spec:** [docs/superpowers/specs/2026-10-26-agent-board-design.md](../specs/2026-10-26-agent-board-design.md) (§2, §4.1,
§8 S1). Prerequisite plan: `docs/superpowers/plans/2026-10-26-user-stories.md` Task 4 (in the main checkout).

## Global Constraints

- Runs in the worktree `.claude/worktrees/agent-board` on branch `feat/agent-board`. Git refuses this repo for
  "dubious ownership": every git command is `git -c safe.directory=* …`; never change global git config.
- **Do not edit** `lib/kanban/ops.py`, `lib/kanban/repair.py`, `lib/kanban/items.py`, `portal/app/src/Kanban.jsx`
  or add to `portal/app/src/kanban.js` beyond Task 1's re-export: the user-stories session owns them.
- macOS, Windows, Linux (AGENTS.md §2.1). TDD: failing test first. Python: `uv run pytest -n auto` from the repo root;
  renderer: `npm test` in `.camarones/desktop/renderer`; portal: `npm test` in `.camarones/portal/app`; Electron
  helpers: `node --test "test/*.test.cjs"` in `.camarones/desktop`.
- `renderer-build/` and `app-build/` are committed and CI fails if they differ from their source: rebuild
  (`npm run build`) in the same commit as the source change. On a merge conflict in a build folder, rebuild; never
  hand-merge bundles.
- Statuses are the English ids `Backlog, Ready, In Progress, In Review, Done, Blocked`; labels by language come from
  `STATUS_LABELS`. Types `epic, story, bug, spike, task`; priorities `P0–P3`.
- Allowed parents (user-stories §4.5): epic → story/bug/spike/task; story → task. A card's parent is
  `card.parent ?? card.epic` (both hold `parent_task_id`; `parent` arrives with the prerequisite).
- Section id `board`, hash `#/board`, shortcut `g b`, placed right after `summary` in `PROJECT`. i18n prefix `bd.`;
  `nav.board`: es `Tablero`, en `Board`. Every string in es and en; no jokes in errors, confirmations or empty-board
  prompts (AGENTS.md §3); one light line allowed on the empty column state.
- UI follows the `cofundo-design-system` skill and `CAMARON.md` (via `@camaron/ui` components and theme tokens), like
  the app's other sections.
- Conventional commits; stage only this plan's files. README (Spanish), `lib/tutorial.py` + regenerated
  `TUTORIAL.md`, `templates/docs/guides/tutorial.md` and its es twin move with the code (Task 5); bump
  `VERSIONS["kit"]` minor from whatever `main` has when Task 5 runs.

## Review Focus

- A card whose parent id is not on the board (archived, deleted, typo) still renders, with `↳ WI-n` as plain text —
  no crash, no link. Test in Task 3 (`parentLabel`).
- A move the server refuses: a 409 with `blocked_by` (the user-stories start gate, once it lands) asks to confirm and
  re-sends with `force: true`; any other error puts the card back where it was and shows the message. Test in Task 3.
- A project with no `backlog/` (`enabled: false`) shows an empty state with *Activar el tablero* (POST
  `kanban/init`), never a blank or broken section. Test in Task 3.
- A hand-edited item with no type, no priority or a non-list field arrives as a row with empty/odd values: the card
  renders its id and title and nothing else breaks. Test in Task 3.
- The add form refused by the server (400, e.g. a bad parent pair) keeps what the person typed and shows the server's
  message in the form. Test in Task 4.

---

### Task 0: Prerequisite — story parents are on `main`

**Files:** none.

- [ ] **Step 1: Bring `main` in:** `git -c safe.directory=* merge main` in the worktree. Expected: clean merge (only
  the spec and this plan differ on the branch).
- [ ] **Step 2: Check the interface:**
  `cd .camarones && uv run python -c "import inspect; from lib.kanban import ops; print('parent' in inspect.signature(ops.add).parameters)"`
  Expected: `True`.
- [ ] **Step 3: If `False`, stop** and ask the user whether to wait for the user-stories session or implement that
  plan's Task 4 here exactly as its Interfaces block says. Do not start Task 1 with a different `ops.add`.

### Task 1: Shared Kanban helpers in `@camaron/ui`

**Files:**
- Create: `.camarones/ui/src/kanban.js`, `.camarones/ui/src/kanban.test.js`
- Modify: `.camarones/portal/app/src/kanban.js` (keeps `applyFilters`, `parseNewArg`; re-exports the rest),
  `.camarones/portal/app/src/kanban.test.js` (drop the moved tests), `.camarones/portal/app-build/` (rebuild)

**Interfaces:**
- Produces in `@camaron/ui/kanban.js`, unchanged in behaviour: `STATUS_LABELS`, `columns(cards, statuses)`,
  `dropAnchor(columnCards, index, movedId)`, `keyMove(state, key, cols)`.
- `portal/app/src/kanban.js` starts with `export { STATUS_LABELS, columns, dropAnchor, keyMove } from '@camaron/ui/kanban.js'`
  so `Kanban.jsx` imports keep working untouched.

- [ ] **Step 1: Move the tests** of the four functions from `portal/app/src/kanban.test.js` to
  `ui/src/kanban.test.js`, importing from `./kanban.js`. Run `npm test` in `portal/app` (its config includes
  `../../ui/**/*.test.*`). Expected: the moved tests FAIL (module not found).
- [ ] **Step 2: Move the four functions** (and their private `idNum`, `byOrdinal`, `clamp`) to `ui/src/kanban.js`; add
  the re-export line in the portal file.
- [ ] **Step 3: Run** `npm test` in `portal/app` and in `desktop/renderer`. Expected: PASS.
- [ ] **Step 4: Rebuild** `npm run build` in `portal/app`; `git status` shows only `app-build/` and the files above.
- [ ] **Step 5: Commit** `refactor(ui): the Kanban's columns, drop and keyboard helpers shared by both apps`.

### Task 2: `POST /api/kanban/add` takes a parent

**Files:**
- Modify: `.camarones/lib/serve.py` (`Handler.kanban_post`, the `add` branch only)
- Test: `tests/test_portal_kanban.py`

**Interfaces:**
- Consumes: `ops.add(..., parent=None, ...)` from the prerequisite.
- Produces: body field `parent` (text, optional) passed as `parent=_text(b, "parent") or None`; `epic` kept as is.

- [ ] **Step 1: Failing tests** (reuse the file's `server`/`call` fixtures and the app token):
  - `test_add_task_under_a_story_with_the_app_token`: add story → `WI-1`; add `{type: "task", title: "S1", parent:
    "WI-1"}` → 200, the task file has `parent_task_id: WI-1`, `GET kanban` row of the task has `epic == "WI-1"`.
  - `test_add_with_a_refused_parent_pair_is_400_and_writes_nothing`: `{type: "story", parent: <a story>}` → 400 and
    the tasks folder is unchanged.
  - `test_add_with_parent_and_a_different_epic_is_400`.
- [ ] **Step 2: Run** `uv run pytest tests/test_portal_kanban.py -v` — Expected: the three FAIL.
- [ ] **Step 3: Implement** the one-line pass-through.
- [ ] **Step 4: Run** it plus `tests/test_portal_actions.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): adding a board item can name its parent`.

### Task 3: The *Board* section — columns, cards, moves

**Files:**
- Create: `.camarones/desktop/renderer/src/board.js`, `board.test.js`, `sections/Board.jsx`, `Board.test.jsx`
- Modify: `src/nav.js` + `nav.test.js` (`PROJECT`), `src/palette.js` + `palette.test.js` (`GO.b = 'board'`),
  `src/App.jsx` (`SECTIONS.board`), `src/i18n.js` (es/en `nav.board`, `bd.*`), `src/app.css`, `../renderer-build/`

**Interfaces:**
- Consumes: `STATUS_LABELS, columns, dropAnchor, keyMove` from `@camaron/ui/kanban.js`; `srv.get/post` (`server.js`).
- Produces in `board.js` (pure):
  - `parentOf(card) -> string | null` — `card.parent ?? card.epic ?? null`, upper-cased.
  - `parentLabel(card, byId) -> string` — `'↳ WI-14'` when the parent is a story **or not on the board**; `''` when it
    is an epic or there is none (`byId`: `Map` id → row).
  - `childrenOf(cards, id) -> row[]` — cards whose `parentOf` is `id`, by `ordinal`, then numeric id.
  - `moveOutcome(err) -> {kind: 'gate', blockedBy: string[]} | {kind: 'error', message: string}` — a thrown error
    from `srv.post` with `status === 409` and `blocked_by` → `gate`; anything else → `error`.
  - `server.js` errors gain `status` and the response `data` (`Object.assign(new Error(…), {status, data})`) so
    `moveOutcome` can read them; existing callers only use `message`.
- Produces in `sections/Board.jsx`: default `Board({ srv })`, and exported `BoardView({ board, lang, kb, onMove,
  onOpen, onKey, dragging })` (pure render, used by the test).

- [ ] **Step 1: Failing pure tests** in `board.test.js`:
  - `parentLabel` table: parent story on the board → `'↳ WI-14'`; parent epic → `''`; parent missing from the board →
    `'↳ WI-99'`; no parent → `''`; lower-case `wi-14` in the row → `'↳ WI-14'`.
  - `childrenOf` keeps order by ordinal then id, ignores other parents.
  - `moveOutcome`: `{status: 409, data: {blocked_by: ['WI-3']}}` → gate `['WI-3']`; `{status: 409, data: {}}` →
    error; `{status: 400, message: 'x'}` → error `'x'`.
  - In `nav.test.js` / `palette.test.js`: `PROJECT[1] === 'board'`; `GO.b === 'board'`; `keyFor('board') === 'b'`.
  - In `server.test.js`: a fake fetcher answering 409 `{error: 'blocked', blocked_by: ['WI-3']}` → the rejected
    error has `message === 'blocked'`, `status === 409`, `data.blocked_by` `['WI-3']`.
- [ ] **Step 2: Failing render tests** in `Board.test.jsx` (`renderToStaticMarkup`, es and en):
  - six columns with their labels (`Listo`/`Ready`…), a card shows id, type, priority, title and `↳ WI-14`.
  - a hand-edited row `{id: 'WI-9', title: 'x', type: '', priority: null, labels: 'p', assignee: null}` renders id
    and title (Review Focus).
  - `board.enabled === false` → the empty state with the *Activar el tablero* / *Turn the board on* button.
- [ ] **Step 3: Run** `npm test` in `desktop/renderer` — Expected: the new tests FAIL.
- [ ] **Step 4: Implement `board.js`, `server.js`'s error fields and `Board.jsx`.** `Board` loads `GET kanban` on
  mount and after every write; drag and drop as the portal's (`draggable`, `dropAnchor` over the column as drawn);
  keyboard through `keyMove` (Tab to a card, Space grab, arrows, Enter drop, Escape put back); a move is shown at
  once and reverted on error; `moveOutcome` gate → `confirm` with the blocking ids (`bd.gate`) → re-POST with
  `force: true`; error → the message in a `role="alert"` line above the columns. `enabled: false` → `EmptyState`
  whose button POSTs `kanban/init` and reloads.
- [ ] **Step 5: Run** `npm test` in `desktop/renderer` — Expected: PASS.
- [ ] **Step 6: Try it** from the repo root: `uv run --script .camarones/camarones.py app`, open the sandbox project
  (`uv run scripts/sandbox.py open` if it needs creating), go to *Tablero*, move a card by mouse and by keyboard;
  the move shows in the portal's Kanban after a reload.
- [ ] **Step 7: Rebuild** `npm run build` in `desktop/renderer`.
- [ ] **Step 8: Commit** `feat(app): the Board section — columns, cards and moves with the app token`.

### Task 4: Story panel and the add form

**Files:**
- Modify: `.camarones/desktop/renderer/src/board.js` + `board.test.js`, `sections/Board.jsx` + `Board.test.jsx`,
  `src/i18n.js`, `src/app.css`, `../renderer-build/`

**Interfaces:**
- Consumes: Task 3's `childrenOf`, `parentOf`; `GET kanban/item?id=` (`{title, type, status, description, criteria:
  [{n, text, done}], dod, links, history}`); `POST kanban/add {type, title, parent?, priority?}` → the new row.
- Produces in `board.js`: `allowedParents(type, cards) -> row[]` — `task` → stories and epics; `story|bug|spike` →
  epics; `epic` → none; archived/Done parents included, sorted by id.
- Produces in `Board.jsx`: exported `StoryPanel({ item, children, lang, onAddTask, onOpen })` and
  `AddForm({ cards, prefill, busy, error, onSubmit, onClose })`.

- [ ] **Step 1: Failing tests:**
  - `allowedParents` table: task → stories + epics; story → epics only; epic → `[]`.
  - `StoryPanel` render: a story with two children lists both with their status labels; the *Añadir tarea* / *Add a
    task* button is there; a non-story item shows description and criteria with no children block.
  - `AddForm` render with `prefill: {type: 'task', parent: 'WI-14'}` has the parent selected; with
    `error: 'bad parent'` shows it in `role="alert"` and keeps the typed title (Review Focus).
- [ ] **Step 2: Run** `npm test` in `desktop/renderer` — Expected: FAIL.
- [ ] **Step 3: Implement.** Clicking or Enter on a card opens the panel beside the columns (`aria-label` = id,
  Escape closes it and the focus goes back to the card, like the portal's `useDrawer`). *Añadir* in the section header
  opens `AddForm` empty; *Añadir tarea* in a story's panel opens it with `{type: 'task', parent: <story>}`. On success
  the board reloads, the form closes and the new card takes the focus; on error the form stays filled.
- [ ] **Step 4: Run** `npm test` in `desktop/renderer` — Expected: PASS.
- [ ] **Step 5: Try it** in the sandbox app: add a story, add two tasks from its panel, see `↳` on them and both in
  the panel.
- [ ] **Step 6: Rebuild** `npm run build` in `desktop/renderer`.
- [ ] **Step 7: Commit** `feat(app): a story's panel lists its tasks and adds one under it`.

### Task 5: Docs, version and the whole suite

**Files:**
- Modify: `README.md`, `.camarones/lib/tutorial.py`, `.camarones/TUTORIAL.md` (regenerated),
  `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`,
  `.camarones/lib/common.py` (`VERSIONS["kit"]` minor + 1, README badge), `AGENTS.md` §4 desktop row (the app has a
  Board that writes the board with its token; the portal is still the reader)

- [ ] **Step 1:** README: under the app's sections, *Tablero*: columns, moves, story panel and *Añadir tarea*; tutorial
  pages es/en with the same in two or three lines each. Regenerate `TUTORIAL.md` (command in AGENTS.md §5.1). The
  templates' commit body says existing projects keep their old tutorial copy.
- [ ] **Step 2: Run everything:** `uv run pytest -n auto`; `npm test` in `desktop/renderer` and `portal/app`;
  `node --test "test/*.test.cjs"` in `.camarones/desktop`; `uv run --script .camarones/camarones.py catalog --check`.
  Expected: all green; report the output, or what failed.
- [ ] **Step 3: Commit** `docs: the Board in the desktop app; kit <new version>`.

### Task 6: Dogfood — this development on its own board

**Files:** `cam-docs/backlog/` of the `camaron-dev` project (the user's own board; done with the user, who asked for
it).

- [ ] **Step 1:** Open the app from this worktree's kit on `camaron-dev`: `uv run --script .camarones/camarones.py app`.
- [ ] **Step 2:** In *Tablero*, add story **"Board de agentes en la app"** (WI-14 if that id is free; use whatever id it
  gets), description in the story template's three lines, repo `camarones-documenter`.
- [ ] **Step 3:** From its panel, *Añadir tarea* five times, in order: `S1 Tablero en la app`, `S2 Una task en vivo`,
  `S3 Tests y commit`, `S4 Planificar`, `S5 PR y merge`.
- [ ] **Step 4:** Move the story to *En curso* and S1 to *Hecho* from the app; check the five `↳` cards and the
  portal's Kanban showing the same after a reload.
- [ ] **Step 5:** Commit the board change in cam-docs only if the user says so (`camaron checkpoint` or their usual
  flow); write the story id in this plan's header for S2's plan.
