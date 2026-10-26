# User stories: write, review, split into conflict-free subtasks — design

Builds on the board: [2026-10-24-board-design.md](2026-10-24-board-design.md) (files, `board.yaml`, ops, portal
Kanban) and on the code map (`lib/codemap.py`, graphify's per-repo graph folded to files and groups). Asked by the user
on 2026-10-26: "a user-stories module: you fill in *as a… / I want… / so that…*, it tells you whether it is right and
proposes subtasks that you approve into the backlog. User friendly." Revised the same day: "compute dependencies with
other tasks and do not launch agents that can block tasks, to avoid as many reconciliations as possible. The less AI
and the more scripts, tools, databases and determinism, the better."

## 1. Intent

Writing a good story and breaking it down is where a board's cards usually go wrong: vague roles, two goals in one
"I want", no acceptance criteria, subtasks that ignore how the code is built — and, once agents execute them, two
agents editing the same files at once and a merge to reconcile afterwards. This piece gives the team **one guided
place** to write a story, check it against INVEST, and turn it into subtasks whose **footprint** (files they touch),
**dependencies** and **conflicts** are computed from the code graph and the docs — so work can be handed out in
**waves** that never collide.

**Everything is deterministic by default.** Rules, templates, the code graph and a SQLite index do the work; the same
board always gives the same verdict, subtasks, dependencies and waves. AI is optional, off by default, and only
suggests wording (§7).

**Done when:** a person opens *Historias*, writes a story, picks the code it touches, sees an INVEST verdict with
reasons, gets subtasks with their files, dependencies and conflicts already worked out, approves them, and with one
click they are cards in Backlog; `camaron board next` then only ever hands out tasks that can start without colliding
with anything in progress.

**Anti-goals — a failure even if it works:** anything written to `backlog/` before the person approves it; two
agent-driven tasks in progress at once with overlapping footprints; a dependency or verdict that changes between two
runs on the same board; derived data (conflicts, waves) stored in git and causing merges; a story Backlog.md can no
longer open; a 3.x/4.x project changing without being asked; the screen needing an AI runner for anything; overwriting
a story someone else changed meanwhile.

### 1.1 Decisions taken with the user (2026-10-26)

| Question | Decision |
|---|---|
| Where it lives | Its own zone **Historias / Stories** |
| How subtasks land | Child cards: `type: task` with `parent_task_id` = the story, in Backlog |
| Scope | New stories **and** existing stories of the board |
| Dependencies | Computed, not guessed: from the code graph, the docs and footprint overlaps with every open task |
| "Agents that block tasks" | **Parallel without collisions**: agents only get tasks whose dependencies are done and whose footprint overlaps nothing in progress |
| AI | Optional, **off by default**; never decides footprints, dependencies, waves or the verdict |
| Where the data lives | Truth in the cards (git): `dependencies` + `x-touches`; a derived **SQLite index** (stdlib) for queries |

## 2. User flow

Three steps on one screen, opened in order (mock-up agreed in chat):

1. **Write** — *Como / quiero / para* (en: *As / I want / so that*), a title prefilled from the want, an optional
   epic, and **Toca** (touches): a search box over the code graph's files and groups and the doc pages, prefilled with
   the `x-sources` of any doc page linked. Hints appear as you type (§4.2).
2. **Review** — INVEST verdict (Bien / Mejorable / Mal) with one chip per letter and its reason (§4.3), the criteria
   editor (a *Dado / cuando / entonces* scaffold to start from), conflicts with other open stories, and the footprint
   summary ("3 grupos · 9 archivos · 1 repo · 2 páginas").
3. **Subtasks** — proposed by templates (§4.4): each with its title, group, files, *depende de* and *choca con*
   badges, and its **wave**. Checkboxes, editable titles, ✕ to drop, *Añadir subtarea* (pick its files in the same
   search box), *Fusionar* on two tasks. The waves update live as you change them. Primary button names what it will
   create: *Añadir historia + 3 subtareas al backlog* (or *Guardar WI-14 + 3 subtareas*).

- Editing step 1 after step 2/3 recomputes them at once (all deterministic and local, no waiting); tasks the person
  edited by hand are kept and flagged if their files left the footprint.
- After saving: toast "WI-14 y 3 subtareas añadidas" with a link to the Board filtered by that story.
- Work in progress is kept in `localStorage` per story (try/catch, optional); nothing of it is written to the project.

**Left list:** every `type: story` item (not archived) with its verdict (recomputed, never stale), subtask progress
`done/total`, and a conflict badge when it overlaps another open story. Choosing one opens it filled: clauses parsed
from its description (§4.1), its criteria, footprint and subtasks as already on the board.

## 3. Files

No new folders in cam-docs; everything stays a Backlog.md item. Two frontmatter fields carry the new truth.

### 3.1 The story

```markdown
---
id: WI-14
title: Exportar una página de la doc a PDF
type: story
parent_task_id: WI-1                 # optional epic, as today
subtasks: [WI-15, WI-16, WI-17]       # kept in step by the kit, as for epics
documentation: [DOC-k3f9]             # doc pages linked, as today
x-touches:                            # the footprint: what this story changes
  - portal:app/src/views/Doc.jsx
  - portal:lib/exporters.py
  - cam-docs:docs/guides/exporting.md
...
---

## Description
<!-- SECTION:DESCRIPTION:BEGIN -->
Como responsable de un servicio,
quiero exportar una página de la doc a PDF,
para enviarla a quien no tiene acceso al portal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dado una página con un diagrama, cuando la exporto, entonces el PDF muestra el diagrama
<!-- AC:END -->
```

- Description: the existing story template, three lines; text after them (a person's notes) is kept on save.
- **Title** of a new story: the want, first letter upper-cased, cut at 80 characters on a word boundary; editable.
- **`x-touches`** (new, optional): sorted, de-duplicated list of `<repo>:<path>` (POSIX path relative to the repo;
  `cam-docs:` for doc pages). Files only — groups are derived from the code map, never stored, so a re-grouped code map
  does not rewrite cards. A story's footprint is the union of what the person picked; a task's is its own subset.
- Criteria: appended to the AC block in order; existing criteria are never renumbered or removed.
- No verdict is stored: it is recomputed from rules (§4.3), so it can never be stale and never causes a merge.

### 3.2 A subtask

A normal item: `type: task`, `parent_task_id: WI-14`, `status: Backlog`, `x-touches` its files, `dependencies` (the
Backlog.md field, list of ids) the dependencies the person kept, `x-repos` the repos of its files, a one-line
description from its template. Its card goes to the end of Backlog.

### 3.3 Derived, never in git

Conflicts, waves, groups, graph edges and verdicts are computed. They live in the index (§5) and in API responses only.

## 4. Deterministic engine — `lib/stories.py` and `lib/kanban/deps.py`

### 4.1 Parsing (`stories.py`)

| Function | Does |
|---|---|
| `parse(text, lang) -> {as_, want, so, rest}` | the three clauses; tolerant of `Como/quiero/para` and `As a/I want/so that`, case, commas, line breaks; anything else → `rest` |
| `compose(as_, want, so, lang) -> str` | the three-line description |
| `title_for(want) -> str` | §3.1 rule |

### 4.2 Hints while typing (no AI)

`lint(as_, want, so, lang) -> list[Hint]`, `Hint = {code, field, message}`, stable codes, word lists in
`templates/board/{es,en}/story-lint.yaml` (kit files, served to the UI so Python and JS never drift):

| Code | Rule |
|---|---|
| `empty` | a clause is blank |
| `generic-role` | role is only a generic word (usuario, user, cliente, persona, alguien…) |
| `two-goals` | the want joins two verbs with y/e/and/also/además (conjunction followed by an infinitive) |
| `so-repeats-want` | more than 60% of the so-that's content words appear in the want |
| `too-long` | the three clauses exceed 280 characters |
| `solution-in-want` | the want names UI/implementation pieces from the word list |
| `no-footprint` | nothing picked in *Toca* (dependencies cannot be computed) |

Hints never block.

### 4.3 INVEST verdict (no AI)

`invest(story, board) -> {verdict, letters: {I,N,V,E,S,T: {ok, reason, data}}}`, thresholds in `workspace.yaml →
stories.small` (defaults below):

| Letter | Passes when |
|---|---|
| **I** independent | its footprint overlaps no other open story (not Done, not archived) and it depends on no undone story |
| **N** negotiable | no `solution-in-want` hint |
| **V** valuable | `so` is present and no `so-repeats-want` hint |
| **E** estimable | it has a footprint and at least one criterion |
| **S** small | ≤ 3 groups, ≤ 15 files, ≤ 2 repos; when it fails, the reason offers *Partir por grupo* (one story per group) |
| **T** testable | ≥ 1 criterion, each either *Dado/cuando/entonces* (*Given/when/then*) or containing an observable verb from the word list |

`verdict` = `good` if all pass; `poor` if `empty` is present or 3+ letters fail; `improve` otherwise. Pure function
of the story and the index: same input, same output.

### 4.4 Subtasks by template (no AI)

`split(story, board) -> list[Proposal]`, rules in `templates/board/{es,en}/split.yaml` (a project can override in
`.camarones/board/split.yaml`):

1. Group the story's code files by `(repo, code-map group)`. Files with no graph go to a group named after their
   folder.
2. **Cycles:** if two groups use each other (file-level edges both ways in the code map), they become **one** task —
   splitting them would guarantee a collision. Strongly connected components over the group graph.
3. One **change task** per resulting group: title from the template (`"{group}: {want}"`, shortened), footprint = its
   files, criterion "tests for #1..#n written first" (TDD inside the task, not a task of its own).
4. One **docs task** per doc page in the footprint, or per page whose `x-sources` cite the story's files (found
   through the index): "Actualizar *{page title}*", footprint = that page.
5. Order of the list: by wave (§4.5), then group label.

The person can edit, drop, add (picking files) or merge; every change re-runs §4.5 on the edited list.

### 4.5 Dependencies, conflicts and waves (`lib/kanban/deps.py`, pure, unit tested)

Inputs: the proposed tasks (or any set of items), the open items of the board, file-level edges from the code map.

- **Code order** (within a story): task B depends on task A when any file of B has an edge (calls, imports,
  references, inherits, implements) to a file of A — provider first, consumer after. Edges come from
  `codemap.DEP_RELATIONS`. Cycles were merged in §4.4, so this is a DAG; a cycle created by hand edits is reported
  and blocks saving until merged or a dependency is removed.
- **Docs order:** a docs task depends on every change task whose files its page cites.
- **Conflicts** (with any open item on the board, any story): footprints share a file → `conflict`. Same code-map
  group without a shared file → `near` (shown, not enforced). An open item in **In Progress** that conflicts becomes
  a proposed **dependency** (wait for it).
- **Waves:** topological levels over dependencies; inside a level, tasks are placed greedily — by priority (P0 first,
  none last), then id — into the first wave where they conflict with nothing already placed. Deterministic by
  construction.
- What the person keeps is saved: `dependencies` per task. Conflicts and waves are never saved.

`deps.waves(items) -> [[id…]…]`, `deps.conflicts(item, items) -> [{id, kind, files}]`, `deps.order(tasks, edges) ->
{id: [dep ids]}`, `deps.ready(board) -> [id]` (§6).

### 4.6 Saving

`stories.save(story_id | None, clauses, title, epic, criteria, touches, tasks, base_sha, by, surface)`:

1. Validate everything before writing: clauses non-empty, epic is an epic, task titles valid (trimmed, non-empty,
   ≤ 120 chars, unique), every `x-touches` entry is valid (repo known; the file exists, or — for a file the task will
   create — its folder exists, and the UI marks it *nuevo*; such a file gets its group from its folder), no dependency
   cycle, dependencies point at existing items. Bad input → `BoardError` (400).
2. Existing story: if its description's fingerprint (sha256 of normalised clauses, first 8 hex) ≠ `base_sha` and
   differs from the new one → 409 "WI-14 cambió mientras la editabas: recárgala".
3. Under the board's `FileLock`: write the tasks (with `parent_task_id`, `x-touches`, `dependencies`), then the story
   (description, title, AC, `documentation`, `x-touches`, `subtasks`), then `board.yaml`; then refresh the index. A
   crash between leaves at worst tasks whose parent does not list them yet; the repair pass fixes that (§4.7).

### 4.7 Changes to `lib/kanban`

- `ops.add` gains `parent=` next to `epic=` (kept as an alias, same behaviour). Allowed: `epic` → story/bug/spike/task;
  `story` → task. Anything else → `BoardError`. It also gains `description=`, `criteria=`, `touches=` and
  `dependencies=`.
- The repair pass keeps `subtasks` in step for **any** parent (today: epics), and warns on `x-touches` entries whose
  file no longer exists (renamed/deleted code) and on dependency cycles.
- `list_items` gains `parent=`; the Kanban accepts `#/kanban?parent=WI-14` (a clearable filter chip), shows
  `↳ WI-14` on tasks of a story and a **wave** badge, and a **conflict** badge when the card overlaps something In
  Progress.
- **The start gate.** `ops.move(id, "In Progress", …)` checks `deps.ready`-style rules for that item: its
  dependencies are Done and its footprint conflicts with nothing In Progress.
  - Surfaces `cli`, `portal`, `app` (a person): refused with the reason unless `force=True` (`--force`, a
    "Mover igualmente" confirm in the UI). Forced moves are recorded in the card's `t` as today, plus a `forced` flag
    in the usage log.
  - Surfaces `mcp`, `harness` (an agent): refused, always; no force.
- No change to `board.yaml`'s format, the merge driver, `config.yml` or ids.

## 5. The index — `lib/kanban/index.py` (SQLite, stdlib)

A derived, rebuildable database at `<workspace>/.camarones/.cache/board.db` (git-ignored like the rest of the cache).
It answers the questions the screen and `next` ask on every interaction without re-reading every card and graph.

| Table | Columns |
|---|---|
| `meta` | `key`, `value` — `format`, `snapshot` (hash of `board.yaml` and every item file's name, size and mtime, plus each graph's `built_at_commit`) |
| `items` | `id` PK, `uid`, `type`, `status`, `priority`, `parent`, `title`, `archived` |
| `touches` | `id`, `repo`, `path`, `grp` — indexes on `(repo, path)` and `(repo, grp)` |
| `deps` | `id`, `dep` |
| `edges` | `repo`, `src`, `dst` — file-level code-map edges (DEP_RELATIONS), only for files that appear in `touches` or doc `x-sources` |
| `cites` | `page`, `repo`, `path` — doc pages' `x-sources`, so "which pages cite these files" is one query |

- **Freshness:** every read computes the snapshot (a directory listing and stats, no file reads) and rebuilds when it
  differs. A rebuild reads cards and graphs once; target < 1 s for 1 000 cards.
- **Safety:** one short-lived connection per call, `journal_mode=DELETE` (no WAL side files to leave behind on
  Windows), written to a temp file and moved into place (`os.replace`) so a crash never leaves a half-built db. Any
  `sqlite3.Error` → delete and rebuild once; if that fails, build in `:memory:` for this call and warn. Losing the
  file loses nothing.
- **Uninstall:** it lives under the cache the uninstall already removes; `traces` stays clean.
- The pure functions of §4.5 take plain data; `index.py` only feeds them. Tests run them without SQLite too.

## 6. Handing out work without collisions

- `deps.ready(board)` = items in Backlog/Ready whose dependencies are all Done and whose footprint conflicts with
  nothing In Progress, ordered by wave, then priority, then id.
- `camaron board next [--n 3] [--story WI-14] [--epic WI-1] [--json]` prints them, with a note per item left out
  ("espera a WI-15", "choca con WI-17 en `portal:lib/exporters.py`").
- `camaron board waves [--story|--epic] [--json]` prints the waves.
- MCP: read tools `board_next` and `board_waves`. Agents still never move cards through MCP (board spec U4); any
  future harness that executes board tasks takes them **only** from `ready` and moves them with surface `harness`, so
  the start gate (§4.7) refuses anything that would collide.
- Items without `x-touches` are treated as touching **everything** of their `x-repos` (or the whole workspace without
  repos) for agents: they are only handed out when nothing else of that repo is in progress. Conservative on purpose:
  an unknown footprint must not cause a reconciliation.

## 7. Optional AI (off by default)

`stories: {ai: true}` in `workspace.yaml` (and a bounded runner configured) shows a *Sugerir con IA* button in steps 1
and 3. Same route as Ask (`lib/answers.py`): bounded runner, cheap model, one headless call, no tools, empty folder,
JSON, 90 s.

- It may suggest: a rewrite of the clauses, criteria, extra subtask ideas. Each suggestion is shown apart, marked
  *IA*, and does nothing until accepted.
- It may **not** decide: footprints, dependencies, conflicts, waves, the verdict. A subtask idea comes without a
  footprint; files the AI names are kept only if they exist in the index, and the person confirms them.
- `usage.record("stories:suggest", channel="human", hit=…)`. Off → no button, no call, nothing else changes.

## 8. API, CLI, UI

### 8.1 API (portal server, `lib/serve.py`)

| Route | Does | Token |
|---|---|---|
| `GET /api/stories` | `{enabled, writable, ai, lint_words, stories: [row with verdict, progress, conflicts]}` | no |
| `GET /api/stories/item?id=WI-14` | clauses, rest, criteria, footprint with groups, subtasks with status/wave, `sha` | no |
| `GET /api/stories/files?q=…` | search over the index's files, groups and doc pages (for *Toca*) | no |
| `POST /api/stories/analyze` | given an unsaved story (+ optional edited tasks): hints, INVEST, proposals, deps, conflicts, waves — pure, writes nothing | no |
| `POST /api/stories/suggest` | §7 | yes (it spends) |
| `POST /api/stories/save` | §4.6 | yes |
| `GET /api/kanban/next`, `/api/kanban/waves` | §6 | no |

Without the token the zone is read-only and says why (board's message and `token: true` flag). 400 bad input, 409
conflict, 503 for `suggest` without a runner or on timeout. `POST /api/kanban/move` gains `force` and returns the
gate's reasons as `{error, blocked_by: [{id, kind, files}]}` (409) when refused.

### 8.2 CLI

| Command | Does |
|---|---|
| `camaron board story lint WI-14` · `story invest WI-14` | hints, verdict |
| `camaron board story split WI-14 [--accept]` | proposals with deps/conflicts/waves; `--accept` creates them all |
| `camaron board next …` · `board waves …` | §6 |
| `camaron board move WI-15 "In Progress" [--force]` | existing command, now with the gate |

All take `--json`. Registered in `catalog.py` (verdict both) so `catalog --check` stays green.

### 8.3 Portal and app

- `zones.js`: zone `stories` (`#/stories`, `live: true`) after `board`; `ROUTES` and `router.js`'s `NATIVE` gain it.
- `src/Stories.jsx` + `src/stories.js` (pure helpers, node tests): step state, local draft, primary button label,
  calling `analyze` on every change (debounced 200 ms; it is local and fast).
- Kanban: `parent` filter, wave and conflict badges, the gate's "Mover igualmente" confirm.
- i18n keys (es/en) in `i18n/portal.js`; UI follows `cofundo-design-system` and `CAMARON.md`; `app-build/` rebuilt.

## 9. Compatibility and lifecycle

- New optional keys only: `x-touches` in items; `stories: {ai, small}` in `workspace.yaml`. Projects without
  `backlog/` show the zone with the board's "enable the board" empty state.
- Existing cards have no `x-touches`: they open fine; for agents they count as touching their whole repo (§6); for
  people the gate only warns. The left list offers *Añadir huella* on them.
- The start gate is new behaviour for `board move`: people keep moving cards with one extra confirm when there is a
  collision. Documented in README and tutorial.
- Stories that do not follow Como/quiero/para open with empty fields and the old description in `rest`; saving writes
  the three lines above it and keeps it.
- `templates/board/{es,en}/{story-lint,split}.yaml` are kit files. Bump `VERSIONS["kit"]` (minor). README,
  `lib/tutorial.py` (+ regenerated `TUTORIAL.md`) and the tutorial templates gain a "Historias" section and the gate;
  existing projects keep their old tutorial copy.

## 10. Tests

TDD, offline, `make_workspace` + `isolated_env`:

- `parse/compose/title_for`: es/en table, odd punctuation, `rest` kept, round trip.
- `lint` and `invest`: one case per code/letter and its negative; verdict boundaries; same input → same output.
- `split`: grouping, a two-group cycle merged, docs tasks from `x-sources`, template override from the project.
- `deps`: order from edges (provider first), docs after code, conflicts vs near, In Progress conflict becomes a
  dependency, waves on a fixed fixture (golden), tie-breaks by priority then id, hand-made cycle reported, items
  without footprint treated as whole-repo.
- `index`: builds from a fixture board + fake graph; snapshot change triggers rebuild; corrupt file → rebuilt; a
  failing disk → `:memory:` fallback; uninstall leaves no trace.
- Gate: person refused without force, allowed with it; agent surfaces refused even with force; dependencies not Done
  refused.
- `ops.add` with `parent=` story, refused pairs, new fields; repair keeps a story's `subtasks` in step after a
  simulated crash; repair warns on missing `x-touches` files.
- `save`: new story + tasks; existing story keeps its title, old criteria and notes; 409 on concurrent change; nothing
  written when one entry is invalid.
- API: 403 without token on suggest/save; `analyze` pure (no file changes); move gate 409 with `blocked_by`.
- AI: off by default → no runner call even when one is configured; on → fake runner suggestion, invented files
  dropped; timeout → 503.
- A 4.x fixture board (no `x-touches`, epics only) opens and lists the same as before; `board move` of a card with no
  conflicts behaves exactly as before.
- Portal node tests: `stories.js` state, JS lint matches Python lint on one shared JSON case table, zone/route entries.
- `e2e`: the Backlog.md 1.55.3 check also edits a story with `x-touches` and a task with `dependencies`, and they
  survive.
- Sandbox (PetClinic): write a story touching `owners` and `vets`, split, save; `board next` gives the wave-1 tasks
  only; moving a conflicting one as harness is refused; `uninstall` + `traces`.

## 11. Known limits

- A footprint is a prediction: an agent can edit files outside it. A later piece can compare the task's diff with
  `x-touches` and flag it; not in this delivery.
- Code order follows static edges; runtime coupling (events, config, reflection) is invisible to the graph — cite it
  in the docs (`x-sources`) to make it count.
- The two-goals and repeats heuristics are word lists, not language understanding; they hint, they never block.
- File-level conflicts are conservative for big shared files (one `Constants.java` serialises everything touching it);
  that is the intended trade-off — fewer reconciliations over more parallelism.

## 12. Left to the builder

Exact template wording in `split.yaml`, word lists, JSON field names inside rows, the files search ranking, layout
within the agreed mock-up, toast and error wording (es/en, AGENTS.md §3).
