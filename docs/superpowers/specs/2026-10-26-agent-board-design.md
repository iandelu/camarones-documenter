# Agent board: pick a story, let Claude implement it task by task, watch every task live — design (MVP)

Builds on the board ([2026-10-24-board-design.md](2026-10-24-board-design.md)) and takes the shared base of user
stories ([2026-10-26-user-stories-design.md](2026-10-26-user-stories-design.md) §4.3 split and §4.5). Asked by the
user on 2026-10-26: "an editable board, Linear-style, where you pick a story and Claude implements it with subagents,
and you see what is being done, what is being tested and what is ready to merge; each task in its own terminal. Let's
see the MVP, and use this development to try the user story and task functionality."

## 1. Intent

Today the board says *what* should be done; doing it with an agent means copying the story into a terminal, watching a
wall of output and moving cards by hand. This piece puts the doing **on the board**: a story is split into vertical
slices, each slice is implemented by its own headless Claude run in the story's worktree, the kit runs the tests and
commits, and the person watches each task's live terminal until the story is a pull request.

**Done when:** in the desktop app's *Board*, a developer opens a story, clicks *Planificar*, approves 3–8 vertical-slice
tasks, clicks *Implementar*, and sees each task go `implementando → probando → hecha` with a one-line live activity and
its own terminal; when every task is done, *Abrir PR* opens a GitHub PR, and when it is merged the story and its tasks
land in Done.

**MVP scope: one developer on one machine.** No sync between developers' apps; nothing of a run is shared through git.

**Anti-goals — a failure even if it works:** the agent writing outside the story's worktree; a task marked done whose
tests the kit did not see pass; a commit or push the person did not start (Implementar starts the commits, Abrir PR the
push); the portal gaining a machine action; a 3.x/4.x board changing without being asked; the board being unusable
with no agent installed; a run's output lost because the app was closed.

### 1.1 Decisions taken with the user (2026-10-26)

| Question | Decision |
|---|---|
| Where it lives | The **desktop app** gets an editable *Board* section; the portal stays the reader (its current token edit is untouched) |
| The "terminal" | A **live, read-only view** of the headless agent's stream (tools, text, test output) with Stop — not a PTY |
| Phases | The 6 columns stay; a **phase pill** on the card carries the agent's work. Deploy is out of the MVP |
| Merge | **Open a PR** with `gh`; merged is read back from GitHub |
| Orchestration | **The kit runs one Claude per task**, in series, in one worktree per story (approach A; parallel later) |
| User stories | Take only the **shared base** (§4.5 parent=story, §4.3 split); the full Stories wizard is a later piece |
| Who uses it | **One developer, locally**; run state lives in the machine's cache |
| Tasks | **Vertical slices**: each task delivers something usable end to end and is testable on its own |
| Build order | This MVP is built in vertical slices S1–S5 (§8), tracked as story WI-14 and its tasks on this board |

## 2. User flow (desktop app, section *Board*)

```
┌ Board ─────────────────────────────────────────────────────────────┐
│ Backlog      Ready        In Progress          In Review    Done    │
│ ┌────────┐  ┌────────┐   ┌───────────────────┐                      │
│ │WI-20 … │  │WI-18 … │   │WI-14 story        │                      │
│ └────────┘  └────────┘   │Board de agentes   │                      │
│                          │● implementando 2/5│                      │
│                          └───────────────────┘                      │
├ WI-14 · Board de agentes ─────────────── [Planificar] [Implementar]─┤
│ ✓ WI-15 Base de historias      hecha    3m · $0.41  a1b2c3d         │
│ ● WI-16 Una task en vivo       probando ▶ uv run pytest tests/…     │
│ ○ WI-17 Tests y commit         pendiente                            │
├ WI-16 terminal ──────────────────────────────────────────── [Parar]─┤
│ ✎ Edit  .camarones/lib/work.py                                      │
│ ⌕ Grep  "start_job"                                                 │
│ ▶ Bash  uv run pytest tests/test_work.py -q                         │
│   ....F.                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Columns** (top): the board's six columns, drag and drop and keyboard moves as in the portal's Kanban; cards show
   `↳ WI-14` for a story's tasks and, while a run exists, the phase pill and `done/total` tasks.
2. **Story panel** (a story is picked): its tasks in order, each with status icon, phase, **live activity line**
   (§5.3), elapsed time, cost and commit. Buttons by phase (§4.4).
3. **Terminal** (a task is picked; the running one by default): dark, monospace, one row per event, raw test output,
   autoscroll that pauses when the person scrolls up, *Parar*. A finished task keeps its terminal (replayed from disk).
4. **Planificar** opens a list of proposed tasks as checkboxes with editable titles, ✕ to drop, *Añadir* by hand; the
   primary button names what it creates (*Añadir 4 tareas a WI-14*).
5. **Implementar**, the first time on this machine, asks once: "Claude va a editar y ejecutar comandos en
   `.cw/w1` sin preguntarte en cada paso" — *Entendido* is stored in machine prefs. If the story names no repo, the
   panel asks for one (workspace repos only); if the repo has no test command, the detected one is shown to confirm
   (§5.4).

## 3. Files and state

### 3.1 In cam-docs (git) — only what the board already has

- Tasks are normal items (`type: task`, `parent_task_id: WI-14`), created through `ops.add(parent=…)` (§4.1).
- Status moves are normal `ops.move` calls (surface `app`). No new frontmatter field.
- The PR URL is added to the story's `references` (an existing Backlog.md field) when the PR opens.
- `workspace.yaml` gains an optional per-repo key `test:` (a command list, e.g. `[uv, run, pytest, -q]`), written only
  when the person confirms a detected command. Old workspaces without it keep working (detected each time).

### 3.2 In the machine's cache (not in git): `cam-docs/.camarones/.cache/work/<STORY>/`

| File | Holds |
|---|---|
| `run.json` | `{story, repo, worktree, branch, base, tasks: [id…], current, phase, pid, started, pr, updated}` |
| `<TASK>.json` | `{phase, attempt, started, ended, commit, tests: {cmd, rc}, cost_usd, tokens_in, tokens_out, activity}` |
| `<TASK>.jsonl` | every event of the task, one JSON per line: runner events (§5.3), `test.out` lines, `phase` changes |

Written atomically (temp + `os.replace`, as the board does) under `cache/locks/work.lock`. Deleting the folder loses
the history of a run, never work: the code is in the worktree and its branch.

### 3.3 Phases

| Level | Phases | Board effect |
|---|---|---|
| Task | `pendiente → implementando → probando → hecha` · `falló` · `interrumpida` · `saltada` | `implementando`: task → In Progress; `hecha`: task → Done |
| Story | `implementando` (any task running) → `para mergear` (all done or skipped) → `en PR` → `mergeada` | Implementar: story → In Progress; `en PR`: → In Review; `mergeada`: story and its done tasks → Done |

Phases are derived from the cache files; the board columns are the only thing written to cam-docs.

## 4. Backend

### 4.1 Shared base of user stories (`lib/kanban/ops.py`)

Exactly user-stories §4.5: `ops.add(parent=…)` next to `epic=` (alias kept); allowed pairs epic → story/bug/spike/
task and story → task, anything else `BoardError`; `description=` and `criteria=` fill the template blocks; the repair
pass keeps `subtasks` in step for any parent; `list_items(parent=…)`; the card's `↳ WI-14`. No change to
`board.yaml`, the merge driver, `config.yml` or ids. The full Stories wizard later builds on this unchanged.

### 4.2 Planificar (`lib/stories.py`, new — only `split` and its helpers now)

User-stories §4.3 *Split* as specified there (route, model, context from `mcp.ask`, validation, caps, `usage.record
("stories:split")`, `stories: {ai: false}` turns it off), with one addition to the prompt: **each subtask must be a
vertical slice** — usable end to end, testable on its own, in the order it should be built; never a layer ("modelo",
"API", "UI"). Input: the story's description and criteria as they are on the board (no review step in the MVP).
Approved proposals are created with `ops.add(type="task", parent=story, description=note, criteria=[])` in the order
shown, then the story's `subtasks` is written (user-stories §4.4 step 3 ordering).

### 4.3 Worktrees for code repos (`lib/harness/worktrees.py`)

`Worktrees` today is cam-docs only (`ctx.state_root`). It gains an optional `repo: Path` and `prefix: str` so a code
repo gets `<workspace>/.cw/w<n>` on branch `cam/<story-id-lower>-<slug>` (e.g. `cam/wi-14-board-de-agentes`), from
the repo's `branch` in `workspace.yaml` (fallback: its current HEAD), with its own registry
`cache/worktrees-code.json`. The cam-docs behaviour, paths and registry are unchanged (existing tests stay as they are).

### 4.4 The orchestrator (`lib/work.py`, new)

| Function | Does |
|---|---|
| `plan(story_id, lang) -> {subtasks, missing}` | §4.2 proposals (no write) |
| `accept(story_id, tasks, by) -> [rows]` | §4.2 creation |
| `start(story_id, repo, lang) -> run` | checks (§6), worktree, `run.json`, story → In Progress, runs the pending tasks in order in a background thread; a second call returns the running one |
| `stop(story_id)` | kills the current task's process tree; task → `interrumpida`; the run stops |
| `resume(story_id)` / `retry(task_id)` / `skip(task_id)` | continue from the current task (fresh attempt counter) / one more attempt / mark `saltada` and go on |
| `open_pr(story_id) -> url` | §5.5 |
| `refresh(story_id)` | reads the PR state (§5.5) and a dead `pid` (→ `interrumpida`) |
| `state(story_id) -> dict` · `events(task_id, offset)` | for the API: phases, activity, costs; events from `<TASK>.jsonl` after `offset` |

One story runs at a time on a machine (MVP): `start` on another story while one runs is refused with its id.

### 4.5 API (`lib/serve.py`, app token only)

| Route | Does |
|---|---|
| `GET /api/app/work?story=WI-14` | `state()` (and `refresh()` at most once a minute) |
| `GET /api/app/work/events?task=WI-16&offset=N` | SSE of the task's events from `offset`, live while it runs, then `end` (same shape and loop as `stream_job`) |
| `POST /api/app/work/{plan,accept,start,stop,resume,retry,skip,pr}` | §4.4 |
| `POST /api/kanban/*` | unchanged; the app's token already writes the board |

`is_app()` only: the portal token gets 403, like every other machine action (AGENTS.md §4). `400` on bad input,
`409` when another story is running, `503` with the setup message when `claude` or `gh` is missing.

### 4.6 CLI

`camaron board work WI-14 [--plan | --start --repo R | --stop | --pr | --status] [--json]` — the same functions, for
scripting and tests; registered in `catalog.py` (verdict: app + CLI) so `catalog --check` stays green.

## 5. Running a task

### 5.1 The agent call

Through the runner port (`adapters/runners/claude.py`), headless, `cwd` = the worktree, `stream=True`,
`allow_tools=("Read","Edit","Write","Glob","Grep","Bash","mcp__camarones__search_docs","mcp__camarones__read_doc")`
(→ `--permission-mode acceptEdits --allowedTools …`), and `--mcp-config <cam-docs>/.mcp.json` because the worktree
is outside cam-docs and would not find the `camarones` server on its own (a new optional `mcp_config` field on
`RunRequest`; other runners ignore it). Model from `work.model` in prefs, else the runner's default.
No `--dangerously-skip-permissions`. The process is started and killed through `lib/common.py` helpers (tree kill on
Windows). Timeout per attempt: 30 min (pref `work.timeout`).

### 5.2 The prompt (written to `<TASK>.prompt.md` in the cache; the agent gets a one-line pointer, as `agents.py`)

The story (title, description, criteria), the task (title, description, criteria), the tasks already done with their
commit subjects, the repo's brief path in cam-docs and the instruction to look things up with the `camarones` MCP
tools first, and the rules: work only in this folder; do not commit, push or switch branches (the kit does); finish
when the slice works and its tests are written; last line a JSON `{"summary": "…"}`. On a retry the prompt adds the
failing test command and the last 200 lines of its output.

### 5.3 Events and the activity line

Runner events (`parse_event`) are appended to `<TASK>.jsonl` as they arrive, plus the kit's own: `phase`,
`test.start {cmd}`, `test.out {text}`, `test.end {rc}`, `commit {sha, subject}`. The activity line is the last
meaningful event, pure in `desktop/renderer/src/board.js` (unit-tested):

| Event | Line |
|---|---|
| `tool.call` Edit/Write | `✎ Editando <path>` |
| `tool.call` Read/Glob/Grep | `⌕ Leyendo <path>` / `⌕ Buscando "<pattern>"` |
| `tool.call` Bash | `▶ <command>` (first 80 chars) |
| `tool.call` mcp camarones | `⌕ Buscando en la doc…` |
| `log` | the text's first line |
| `test.start` | `▶ Probando: <cmd>` |
| `usage` | (updates cost, not the line) |

### 5.4 Testing and committing (the kit, not the agent)

1. When the agent ends with rc 0, phase → `probando`; the kit runs the repo's test command in the worktree, streaming
   its output into the task's events. The command is the repo's `test:` key, else detected from the repo's files
   (`pyproject.toml`/`pytest.ini` → `uv run pytest -q` or `pytest -q`; `package.json` with a `test` script →
   `npm test`; `mvnw`/`pom.xml` → `./mvnw -q test`; `gradlew` → `./gradlew test`), else the run stops asking for one.
2. Tests pass (rc 0): `git add -A` and `git commit -m "<type>(<scope>): <task title> (<TASK>)"` in the worktree
   (type `feat`, scope = the repo; the person can amend later); task → `hecha`, card → Done; next task.
3. Tests fail, or the agent exits non-zero: one retry (§5.2 with the output). Fails again → `falló`, the run stops,
   the panel offers *Reintentar*, *Saltar* and *Parar*. Nothing is committed for a failed task.

### 5.5 Pull request and merge

*Abrir PR* (story `para mergear`): `git push -u origin <branch>` from the worktree, then
`gh pr create --head <branch> --base <base> --title "<story title> (<STORY>)" --body <body>`; the body is the story's
description and criteria, the task list with commit SHAs, and a line saying it was implemented with the kit's agent
board. URL saved in `run.json` and in the story's `references`; story → In Review. `refresh` runs
`gh pr view <url> --json state,mergedAt`: `MERGED` → story and its done tasks → Done, worktree and local branch
removed, phase `mergeada`; `CLOSED` → phase back to `para mergear` (the person decides).

## 6. Errors and limits

- **No `claude`:** *Planificar* and *Implementar* disabled with how to install it; the board works by hand.
- **No `gh` or not logged in:** *Abrir PR* explains `gh auth login`; the branch is still there to push by hand.
- **App closed mid-run:** on reopen `refresh` sees the dead `pid` → task `interrumpida`; *Reanudar* runs it again on
  the worktree as the agent left it.
- **Second *Implementar*:** opens the running run (same as `start_job`); another story while one runs → 409.
- **Branch or worktree already exist:** reused (`Worktrees.add` already does this for killed runs).
- **Story with no tasks:** *Implementar* disabled, pointing at *Planificar*.
- **Repo not in `workspace.yaml`:** refused; only workspace repos can be picked.
- **macOS, Windows, Linux:** processes through `lib/common.py`; tree kill per OS; short `.cw/w<n>` paths and
  `core.longpaths` on Windows; test commands as lists, never through a shell.
- No jokes in any of these messages (AGENTS.md §3); es and en strings.

**Known limits (accepted for the MVP):** two developers can run the same story on two machines and nothing stops
them; tasks run in series; deploy is not modelled; the agent's Bash is allowed inside the worktree, so a command it
runs can still reach outside it (the one-time notice says so).

## 7. Tests

TDD, offline, `make_workspace` + `isolated_env`, a fixture git repo with a bare `origin`:

- `ops.add(parent=…)`: allowed and refused pairs, `description`/`criteria`, repair keeps a story's `subtasks` in step;
  a 4.x fixture board opens and lists the same as before.
- `stories.split`: the user-stories §7 split cases, plus the vertical-slice instruction present in the prompt.
- `Worktrees` with `repo=`: new worktree and branch from the base; reuse after a kill; cam-docs behaviour unchanged.
- `work.py` with a fake runner that emits canned stream-json (as `test_ask_ai.py` fakes runners) and a fake test
  command: events → `.jsonl`; phases in order; pass → commit with the right subject → Done; fail → one retry → `falló`,
  nothing committed; stop → process gone → `interrumpida` → resume; skip; one-run-at-a-time 409; dead pid on refresh.
- `open_pr` / `refresh` with a fake `gh` on `PATH`: push to the bare origin, create, MERGED → Done + cleanup, CLOSED.
- API: 403 for the portal token and no token; 400 bad input; SSE from an offset replays then follows.
- Renderer (Vitest): `board.js` activity line table, phase → buttons, `↳` and phase pill on cards; the terminal's
  autoscroll pause.
- Sandbox (PetClinic): a small story → Planificar → Implementar → PR with `gh` faked; `uninstall` + `traces`.

## 8. Delivery in vertical slices (tracked on this board)

Once S1 lands, this development is story **WI-14 "Board de agentes en la app"** with one task per slice, created with
the new `parent=` and moved through the columns as each slice merges.

| Slice | End to end | Done when |
|---|---|---|
| **S1** | Shared base §4.1 + the app's *Board* section (columns, cards, `↳`, drag/keyboard moves through the app token) | WI-14 and its tasks S1–S5 exist on the board, created with `parent=`, and move from the app |
| **S2** | One task by hand: worktree §4.3, agent call §5.1–5.2, events and SSE, story panel, **live terminal and activity line**, Stop | *Implementar* on one task (the only button in S2) shows Claude working live in its terminal |
| **S3** | Tests and commit §5.4, retry, skip, resume, all tasks in series, phases on cards | A story's tasks go `implementando → probando → hecha`, each with its commit |
| **S4** | *Planificar* §4.2 with vertical slices, approve and create | A story with no tasks gets them from the AI and they appear under it |
| **S5** | *Abrir PR* and merge detection §5.5, cleanup | The story ends in Done after its PR is merged |

Each slice ships with its tests, README/tutorial updates (AGENTS.md §5.1) and a `VERSIONS["kit"]` minor bump when
visible.

## 9. Later (not in the MVP)

Parallel tasks (one worktree per task with `scheduler`/`integrate`); the full Stories wizard (lint, INVEST, rewrite);
phases and runs visible in the portal; sharing run state between developers; deploy as a phase; a real PTY terminal to
take over a task; Codex and other runners behind the same port.

## 10. Left to the builder

Exact prompt wording within §5.2, JSON field names inside `state()`, the panel's layout details within the mock-up, the
detection order of test commands, toast and error wording (es/en, AGENTS.md §3).
