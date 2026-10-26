# The board (Tablero) — design of the first delivery

Requirements: [dev-harness-requirements.md](../../research/dev-harness-requirements.md) (IDs V/W/U/T/K cited below).
Format reference: Backlog.md **v1.55.3** (MIT), read from its source (`src/markdown/serializer.ts`, `parser.ts`,
`structured-sections.ts`, `types/index.ts`, `constants/index.ts`, `utils/task-path.ts`, `core/reorder.ts`).

## 1. Intent

The first step towards a harness that executes code changes (V1) is a place to say **what** should change, linked to
the knowledge that says **why**. The board gives that with no AI and no network (V5, AGENTS.md priority 1): epics and
stories in cam-docs, linked to doc pages, moved by the whole team through the portal, the app and the CLI. Execution,
risk and verification come in later minors and hook onto its fixed columns.

**Goals:** items versioned with the docs; one board the team shares through git; Backlog.md opens the same files;
every item can point at the docs it touches and see when they change.

**Non-goals (this delivery):** running agents, plans, evidence, risk; Jira API or two-way sync; a shared server
portal (U6); story translation (W12); CI validation (U17); the `feature` doc type (piece 2).

**Anti-goals — a failure even if it works:** losing a card move or a field when two people sync; Backlog.md silently
dropping our fields; a 3.x/4.x project changing without being asked; confusing the Kanban with the whiteboards.

## 2. Files in cam-docs

```
cam-docs/
  backlog/                       Backlog.md layout (W1)
    config.yml                   Backlog.md config, written by the kit
    board.yaml                   kit: authoritative column, order, assignee (W2)
    tasks/wi-42 - <title>.md     one item (epic, story, bug, spike, task); Backlog.md lower-cases the id in names
    drafts/draft-3 - <title>.md  items proposed by agents (U4), not on the board until accepted
    archive/tasks/…              archived items (W11)
    .suggestions.yaml            dismissed suggestions (U15)
  .gitattributes                 + `backlog/board.yaml merge=camaron-board`
```

Backlog.md's `docs/`, `decisions/` and `milestones/` are not used (W14); the board check warns if files appear there.

### 2.1 `config.yml`

Written on `board init` and re-asserted on every repair (keys below only; other keys a person adds are kept).
Backlog.md does **not** read this file as YAML: scalars are found line by line as top-level `key: value`, and only the
list keys go through a YAML parse. So the kit writes flat scalars and block lists, never nested maps:

```yaml
project_name: "<workspace project name>"
task_prefix: "WI"
statuses:
  - Backlog
  - Ready
  - In Progress
  - In Review
  - Done
  - Blocked
types: [epic, story, bug, spike, task]
priorities: [P0, P1, P2, P3]
definition_of_done:
  - <kit defaults + project extras, project language>
check_active_branches: false
auto_commit: false
```

`statuses` are fixed (W5); `check_active_branches: false` because the kit allocates ids and repairs collisions itself
(W4); `auto_commit: false` because commits come from checkpoint/share (W7).

The UI shows the statuses translated (es: Backlog, Listo, En curso, En revisión, Hecho, Bloqueado); files always hold
the English ids, so Backlog.md and every language read the same board. *(Call: English ids in files.)*

Default DoD in this delivery (execution items come later): "acceptance criteria met", "linked docs updated and
confirmed", "PR reviewed". Projects add theirs in `workspace.yaml → board.definition_of_done`.

### 2.2 An item

```markdown
---
id: WI-42
title: Idempotent PaymentRequested handling
status: Ready                 # mirror of board.yaml
assignee: [ana]               # mirror of board.yaml
created_date: '2026-10-24 10:12'
labels: [payments]
priority: P1
type: story
parent_task_id: WI-3          # its epic (W3)
dependencies: [WI-40]
documentation: [FLOW-k3f9#retries@1a2b3c4d, DEC-0004]   # doc links by x-id (W6, K2)
ordinal: 3000                 # mirror of board.yaml
x-uid: 01jb7q3m               # hidden unique id (W4)
x-repos: [payments]           # affected repos (W6)
x-jira: PAY-118               # only when imported (T6)
---

## Description
<!-- SECTION:DESCRIPTION:BEGIN -->
As … I want … so that …
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A duplicate message has no second effect
- [ ] #2 After 3 retries the message goes to the DLQ
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 acceptance criteria met
<!-- DOD:END -->
```

- Field names, section headers and markers are Backlog.md's, unchanged. Our additions are `x-` fields, which
  Backlog.md keeps verbatim when it rewrites a file (`preserveUnknownFrontmatter`).
- Criteria are shown as `WI-42/AC-1` from Backlog.md's `#1` index. The kit never renumbers them; Backlog.md's CLI may
  when one is removed. *(Call: accept that until criteria are linked to tests in piece 4.)*
- Doc links go in Backlog.md's own `documentation` list as `<x-id>[#<section-slug>][@<hash>]`; the hash is the
  section's body hash when it was linked, so the card can say "changed since linked" (U12). *(Call: reuse
  `documentation` instead of a new field.)*
- Epics: `type: epic`; stories point at it with `parent_task_id`; the kit keeps the epic's `subtasks` list in step for
  Backlog.md.
- File name: `<id in lower case> - <title>.md` (`wi-42 - Idempotent PaymentRequested handling.md`), title sanitised
  as Backlog.md's `sanitizeFilename` does, plus Windows rules (no `<>:"/\|?*`, no trailing
  dot or space) and a length cap so `.cw/` worktree paths stay under MAX_PATH. Renaming a title renames the file.
- Templates per type (W12) fill the Description with headed blocks (story: as/want/so; bug: steps, expected, actual,
  environment; spike: question, timebox, output; epic: goal, linked feature). In `templates/board/{es,en}/`, chosen
  by the project language; items are never translated.

### 2.3 `board.yaml`

The kit's state; never edited by hand. One line per card, sorted by id, so git merges per card (W8):

```yaml
version: 1
cards:
  WI-3:  {uid: 01jb7p0a, status: In Progress, ordinal: 1000, assignee: [], t: {status: '2026-10-20T09:00:00Z luis@x'}}
  WI-42: {uid: 01jb7q3m, status: Ready, ordinal: 3000, assignee: [ana], t: {status: '2026-10-24T10:12:00Z ana@x', assignee: '2026-10-24T10:12:00Z ana@x'}}
```

- `t` holds, per field, when and by whom (the machine's git `user.email`, U10) it last changed — the merge driver's
  input.
- `ordinal` follows Backlog.md (step 1000, midpoint between neighbours, rebalance a column when there is no room)
  (W9). *(Call: Backlog.md's numeric ordinal is the "rank between neighbours".)*
- Archived cards leave `board.yaml`; their file moves to `archive/tasks/`.

**Authority (W2).** `board.yaml` wins for status, ordinal and assignee. Every kit write updates both `board.yaml` and
the item's mirror fields at once. A repair pass (§4) rewrites mirrors that differ, warning which ones (a move made
with Backlog.md's CLI is undone). The one exception: an item file with **no card** (created by Backlog.md or by hand)
is adopted — its card is created from the file's status.

The mirror means each move changes one line of the item file too; content diffs stay readable, not untouched.

## 3. Merge driver

`.gitattributes` in cam-docs: `backlog/board.yaml merge=camaron-board`. The kit registers the driver in each clone's
local git config on install, `board init` and `doctor --repair` (recorded by `install_state`, removed by
`uninstall`):

```
git config merge.camaron-board.name  "Camarón board (per card)"
git config merge.camaron-board.driver "<kit launcher> board merge-driver %O %A %B"
```

The launcher path is quoted for spaces; git runs drivers through its own `sh` on every OS. Algorithm (pure, in
`lib/kanban.py`, unit tested): parse base/ours/theirs; per card, per field — changed on one side → take it; changed on
both → latest `t` wins, ties broken by author then value so every machine picks the same; card added on both sides
with the same id and different `uid` → keep both under a temporary key, the repair renumbers the newer; removed on one
side and changed on the other → keep the change and log it. Write the result to `%A`, exit 0. Unparsable input →
exit 1, git shows a normal conflict. Without the kit installed, git falls back to a normal conflict (a known limit).

## 4. Repair pass

`board repair` runs before every checkpoint/share commit and on `board sync`. Idempotent, in this order:

1. Adopt item files without a card; give items without `x-uid` one.
2. Duplicate ids (two branches made `WI-42`): the item with the newer `created_date` (then higher uid) gets the next
   free N — computed over tasks, archive and board — its file is renamed and every `parent_task_id`, `dependencies`,
   `subtasks` and card reference to it is rewritten by uid. Logged.
3. Rewrite mirrors that differ from `board.yaml` (warn).
4. Archive cards in Done for more than `board.archive_after_days` (default 14). *(Call: 14.)*
5. Re-assert the kit keys in `config.yml`.
6. Warn on Backlog.md `docs/`, `decisions/`, `milestones/` content, links to unknown x-ids, unknown statuses.

New ids are allocated by the kit as max+1 over everything it can see locally; collisions from other branches are
step 2's job.

## 5. Doc links and `x-id`

A page gets `x-id` in its frontmatter **the first time an item links it** (K2); a body edit is not involved, so
`x-confirmed.body_sha` stays valid and confirmed pages stay confirmed (checked by a test that starts from a confirmed
page). Format: a type prefix and four base32 characters (`FLOW-k3f9`, `DOM-…`, `ARCH-…`, `DOC-…`); decisions use
their file number (`DEC-0004`). Random suffixes need no repair across branches; the UI always shows the page title
next to it. *(Call: random suffix, unlike items, because nothing in the requirement asks for readable doc numbers.)*
Lookups go through an index built from frontmatter on demand (hundreds of pages, no cache).

## 6. CLI: `camaron board`

| Command | Does |
|---|---|
| `board init` | create `backlog/`, config, `.gitattributes` line, register the driver (also run by install for new projects, U5) |
| `board add <type> "<title>" [--epic WI-3] [--repo r] [--label l] [--priority P1] [--doc FLOW-k3f9#retries]` | new item from the template |
| `board list [--status] [--epic] [--repo] [--label] [--docs suspect\|unconfirmed]` | the filters of U13 |
| `board show WI-42` | item + linked docs with their trust state |
| `board move WI-42 <status> [--before WI-40\|--after WI-40]` | column and order |
| `board assign WI-42 <who>` · `board link WI-42 <x-id>[#section]` · `board archive WI-42` | |
| `board drafts` · `board accept draft-3` · `board reject draft-3` | agent proposals (U4) |
| `board suggestions` · `board dismiss <key>` · `board promote <key>` | the tray (U15) |
| `board import-jira <file.csv>` · `board export-jira <file.csv> [--epic WI-3]` | T2–T6 |
| `board repair` · `board merge-driver %O %A %B` | §4, §3 (the second is for git) |

Every command takes `--json`. Registered in `catalog.py` (verdict: portal + app + CLI) so `catalog --check` stays
green. Shrimp voice only on success and empty states, never on errors or `--json` (AGENTS.md §3).

## 7. Portal and app

- Navigation: new zone **Tablero / Board**; the whiteboards' tab label becomes **Pizarras / Whiteboards** (U3). Routes
  and files of the whiteboards do not change.
- Views (U11): Kanban (drag and drop, keyboard: arrows to pick, space to grab, arrows to move, Enter to drop), list
  (sortable table), by epic (stories and progress as counts).
- Card detail (U12): goal, criteria, DoD; **Knowledge** — linked docs, their trust state (confirmed / draft /
  needs-reconfirm / suspect / stale) and "changed since linked"; **History** — card changes from `board.yaml`'s `t`
  and `git log` of the item; **Plan / Runs / Evidence** tabs shown empty with the version that brings them.
- Filters (U13): repo, epic, label, docs state.
- "Create item" on each doc section (U14), next to the anchored-comment action: opens the add form with the link
  filled in; saving gives the page its x-id.
- Suggestions tray (U15): pages `suspect`/`stale` (freshness), `TODO(question)` markers, OSV findings. Each has a
  stable key (kind + target + fingerprint); dismissing writes the key to `.suggestions.yaml`, and it shows again when
  the fingerprint changes.
- "Since last time" (U18): on open, a summary of cards moved, created or archived since this browser's last visit
  (last-seen time in localStorage, guarded with try/catch).
- Writes (U19): every board write is a POST that needs the machine token. The app already sends it; `camaron
  portal`/`up` started from the CLI now also creates a token and opens the browser with it in the URL fragment, which
  the page keeps in sessionStorage and sends as a header. Without it the board is read-only and says why. Doc edits
  keep today's behaviour.
- Writes land in the files at once; the next checkpoint or **Sincronizar** (share: checkpoint, pull, push) commits
  them, after the repair pass (W7).
- UI follows the `cofundo-design-system` skill and `CAMARON.md`; `app-build/` rebuilt and committed.

## 8. Agents (MCP)

Read tools: `board_list`, `board_show` (items, criteria, linked docs — docs still behind the freshness gate). One write
tool: `board_propose` writes a Backlog.md draft in `backlog/drafts/`; a person accepts it (it gets a WI id and a card)
or rejects it. Agents never move cards (U4).

## 9. Jira CSV (T2–T6)

- **Import** a Jira Data Center CSV export. Default column mapping: `Issue key` → `x-jira`, `Summary` → title,
  `Issue Type` (Epic/Story/Bug/Task/Sub-task) → type, `Status` → status through a mapping table, `Priority`
  (Highest…Lowest → P0…P3), every `Labels` column → labels (Jira repeats the header), `Assignee` → assignee,
  `Description` → description (Jira wiki markup kept as text), `Custom field (Epic Link)` or `Parent` → epic.
  Overrides in `workspace.yaml → board.jira` (status map, extra columns). Re-importing a key that already exists
  skips it (one-way, once: T3). A report lists what was skipped or unmapped.
- **Export** writes a CSV with the same standard headers for Jira's CSV import wizard; nothing is tracked afterwards
  (T5).
- Python's `csv` module, UTF-8 with BOM detection; no new dependency.

## 10. Compatibility and lifecycle

- New `workspace.yaml` keys only, all optional: `board: {archive_after_days, definition_of_done, jira}`. Projects
  without `backlog/` behave exactly as before; `board init` enables it (U5). New projects get it from install.
- `uninstall` asks: keep or delete `backlog/` (U9); it always removes the driver registration and the
  `.gitattributes` line it added. `traces` must stay clean either way.
- `VERSIONS["kit"]` minor bump; `VERSIONS["backlog_md"] = "1.55.3"`: the format version we target, used by the e2e
  test (we do not install it).
- `README.md`, `lib/tutorial.py` (+ regenerated `TUTORIAL.md`) and both `templates/docs/…/guides/tutorial.md` gain a
  board section (U16); the commit says existing projects keep their old tutorial copy.
- `usage.py` counts items created and moved per week by surface (portal, app, CLI, MCP) (§9 success).

## 11. Module layout

`lib/kanban.py` (items, board.yaml, repair, merge, CLI handlers), `lib/kanban_jira.py` (CSV), templates in
`templates/board/`. The name avoids `lib/boards.py` (whiteboards). Portal: `src/Kanban.jsx` + pure helpers in
`src/kanban.js` (node tests), separate from the existing `board.js`/`Boards.jsx`. *(Call: names.)*

## 12. Tests

TDD, offline, `make_workspace` + `isolated_env`:

- Round trip of an item file (our writer, Backlog.md field order, `x-` fields, markers) against fixtures copied from
  Backlog.md v1.55.3 output.
- Merge driver: one side, both sides (time, tie), same id on both sides, delete vs change, unparsable → exit 1; run
  through a real `git merge` in a temp repo on each OS (CI matrix).
- Repair: adopt, renumber with reference rewrite, mirror, archive, idempotence (run twice, no diff).
- x-id on a confirmed page: trust stays `confirmed`.
- Jira CSV golden files (repeated `Labels`, BOM, unknown status).
- Portal: board POSTs without token → 403; with token → writes; read-only view without token.
- 3.x/4.x fixture project without `backlog/`: nothing changes until `board init`.
- `e2e` marker: `npx backlog.md@1.55.3` lists our board, edits a card, and our `x-` fields survive.
- Sandbox (PetClinic): the success scenario in the requirements §9, then `uninstall` + `traces`.

## 13. Delivery split

Two minors, each green and documented on its own:

- **1a:** files and config (§2), `board.yaml`, merge driver (§3), repair (§4), x-id on link (§5), CLI except
  drafts/suggestions/Jira (§6), portal Kanban + card detail + filters + "create item" from a doc section + token
  writes (§7), compatibility and uninstall (§10), usage counts.
- **1b:** list and by-epic views, Suggestions tray, "since last time", MCP read + propose with drafts (§8), Jira CSV
  import/export (§9), the matching CLI commands.

## 14. Known limits

- The merge driver only runs in clones where the kit registered it (§3).
- "Latest wins" uses each machine's clock; clock skew between machines can pick the older change. Acceptable for
  card moves; the History tab shows both.
- Backlog.md releases almost daily; we target 1.55.3 and the e2e test is the alarm when its format moves.
- After a cross-branch id collision the repair pass renumbers by uid, but uid-less references such as
  `dependencies: [WI-5]` are not rewritten: only explicit `WI-5~uid` references and the renumbered item's own
  subtasks follow it.
- Any new card field in board.yaml must bump board.yaml's `version`: 1a drops unknown card keys on load, so an older
  kit would silently lose the field on its next write.
- An `x-id` written into OpenWiki pages (`repos/<n>/…`) may be lost when the wiki is regenerated; the board's links
  to them then show as missing.

## 15. Left to the builder

Exact JSON shapes of the portal API; the Kanban component's internals; wording of messages (es/en, AGENTS.md §3);
how the "since last time" summary is laid out; Jira status map defaults beyond the obvious ones.
