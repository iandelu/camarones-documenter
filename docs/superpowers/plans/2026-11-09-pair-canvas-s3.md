# Pair canvas S3 · Take and hand back — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The person takes a unit from the autopilot onto the canvas, corrects its agent in the same conversation, hands
it back, and the pilot carries on with it headless; the other units never stop.

**Architecture:** Every headless session gets a known conversation (`RunRequest.session`). A handoff is a file the
server writes and the run watches (`harness/handoff.py`, `runs/<run>/handoff/<unit>.json`), as `cancel` is today:
`_run_agent` ends its agent and returns which way it went, `_autopilot` logs `unit.finished {outcome: "handed"}` and
goes on. `lib/takeover.py` is the server's side: ask, wait, open the PTY on `--resume <id>`; `hand_back` closes it and
writes `{to: pilot}`, which the run adopts first in its queue. The bill counts only the person's stretches of a
conversation a run also wrote to (`since`, `spans`).

**Tech Stack:** Python stdlib, the agent CLIs' own flags, React 19, `@xyflow/react`, Vitest. No new dependency.

**Spec:** [docs/superpowers/specs/2026-10-27-pair-canvas-design.md](../specs/2026-10-27-pair-canvas-design.md) — slice
**S3** (§7): §3.1, §3.2, §3.4's takeover / handback / stop, §3.5, §4.2, §4.4, §4.5 and the §5 rows on handoffs.

**Not in S3** (S4): §4.3. The parallel scheduler keeps `_run_agent` without a watcher, so *Take control*, per-unit
*Stop* and *Hand back* are for autopilot runs only: the buttons do not show on a parallel run and the routes answer 409.

## Decisions this plan fixes (the spec leaves them to the builder or is silent)

- **The id travels as one event.** `_run_agent` emits `session {id}` for every runner that has one, Claude included,
  instead of a `session` field on `unit.started`: `unit.started` is emitted before `_run_agent` mints the id, and one
  reader (`runs.last_session`) then serves every runner. `unit.started.resume` stays as the spec has it.
- **The person speaks first.** A takeover resumes with no prompt (`RunRequest.prompt == ""` omits it): a prompt would
  set the agent working before the person typed. Its permissions are the interactive session's own, as every S2 session.
- **The bill bounds both ends.** §3.5 counts a transcript "from `since` on", but a handed-back session keeps appending
  to that same transcript and the run's `usage` counts that part too. So a stretch is `[since, ended]`, and earlier
  stretches stay in `spans: {sid: [[from, to], …]}`. Record without either (every 3.x/4.x one): counted whole.
- **A handed unit has `sessions.GRACE` s to get its session.** The run logs `handed` before the server opens the PTY.
  Until the record reads live the run treats the unit as taken, else with nothing else ready it would stop at once.
- **A unit that was with the person this run is not picked again** when closed unfinished (`available()` lists `doing`
  first): it is paused, and only a `{to: pilot}` brings it back.
- **SIGTERM unwinds the autopilot.** The agent now leads its own process group so a takeover can end its tree; the
  job's Stop signals the run's group only. So the run gets a SIGTERM handler that raises `SystemExit`: `_run_agent`
  ends its agent and the log gets `run.finished {interrupted}`.
- **The autopilot honours `runs/<run>/cancel`:** a CLI-started autopilot now waits on taken units, and the app's only
  Stop for it is that file.
- **Continue finds a dead run's conversation:** `launch_unit(mode="continue")` with no session on record uses the newest
  run log's, with `since`, instead of `--continue`, which can pick another conversation. This is also *Open with you* on
  a failed node. The Failed row's *Retry* is not added: nothing in the S3 row asks for it and blocked units already have
  it in the detail panel.
- **Values:** watcher tick 0.5 s; end the agent with SIGTERM, SIGKILL 3 s later; takeover waits at most 10 s; autopilot
  re-syncs every 5 s while waiting; handback waits for the PTY's end at most `CLOSE_GRACE + 2` s.

## Global Constraints

- macOS, Windows, Linux (AGENTS.md §2.1): `pathlib`, `encoding="utf-8"`, argv lists, processes through `lib/common.py`
  (`kill_tree`), branch on `IS_WIN`; handoff file names through `sessions.slug` (`discovery:api` is not a Windows name);
  `signal.SIGKILL` does not exist on Windows; atomic writes with `os.replace` and `retry_busy`.
- PR #3's `_conpty` restoring the std handles after `spawn()` stays as it is.
- Compatible (§3.7): every new field is optional; 3.x/4.x run logs, records and plans read as before; no CLI command,
  flag, `workspace.yaml` key or frontmatter field changes. `run.started` is unchanged.
- App token only on the new routes; the portal gains only a read-only label.
- Strings in `es` and `en`, no jokes on buttons, errors or the handoff (AGENTS.md §3).
- TDD; tests offline, with `make_workspace` / `isolated_env`; each owns its `tmp_path`, home and ports. The sandbox is
  off limits until the S2 walkthrough session reports back.
- Every commit that changes a UI's source commits its rebuilt `renderer-build/` or `app-build/`.
- Conventional commits, no Claude attribution. Bump `VERSIONS["kit"]` to 4.79.0 and the README badge.

## Review Focus

- The agent ends on its own just as *Take control* is pressed: the server sees `unit.finished {ok}`, not `handed`. A
  unit now done refuses (409); one still `doing` opens on its last conversation. Pinned in Task 6.
- The run dies between the request and its answer: at the 10 s deadline a free lock opens the PTY, a held one is 409. Task 6.
- `handed`, but the PTY never opens (server restarted, limit): the run must not wait forever. Task 4.
- Unit ids with `:`: through the URL (`encodeURIComponent`, `unquote`) and into a file name. Tasks 2 and 7.
- A second take over after a hand back: the unit reads as running, not paused (`headless` reads the last event, not a
  set difference), and the bill keeps both stretches. Tasks 2 and 5.

---

### Task 1: Runners know a conversation

**Files:** Modify `.camarones/lib/harness/ports.py`, `.camarones/lib/adapters/runners/{base,claude,codex}.py`; Test `tests/test_runners.py`.

**Interfaces — Produces:** `CliRunner.own_session: bool = False` (`Claude.own_session = True`: the kit gives the id);
normalised event `{"type": "session", "id": str}`; `RunRequest(prompt="")` on an interactive session omits the prompt.

- [ ] **Step 1: Write the failing tests** — pin argv: `claude -p <p> --dangerously-skip-permissions --output-format stream-json --verbose --session-id X` (`session="X"`); same with `--resume X` (`resume=True`); unchanged with no session; interactive `claude --resume X` with `prompt=""` has no empty argument. `codex exec resume X --approve-for-me --skip-git-repo-check --json <p>`; interactive `codex resume X`; interactive with no session `codex resume --last`; `Codex().parse('{"type":"thread.started","thread_id":"T"}') == [{"type":"session","id":"T"}]`; `thread.started` with no id → `[]`.
- [ ] **Step 2: Run** `uv run pytest tests/test_runners.py -q`. Expected: FAIL on the new tests.
- [ ] **Step 3: Implement.** The `RunRequest` comments for `resume` and `session` drop "interactive only"; the `Runner` docstring lists `session`.
- [ ] **Step 4: Run** the same. Expected: PASS.
- [ ] **Step 5: Commit** `feat(runners): a headless session has a known conversation`.

### Task 2: The handoff file and what a run log says

**Files:** Create `.camarones/lib/harness/handoff.py`; Modify `.camarones/lib/harness/runs.py`, `.camarones/lib/sessions.py` (`headless`); Test `tests/test_handoff.py`.

**Interfaces — Produces:**
- `handoff.request(run_id: str, uid: str, to: str, **fields) -> None`: atomic, payload `{"to", "unit", "at", **fields}`.
- `handoff.read(run_id, uid) -> dict | None`; `handoff.clear(run_id, uid) -> None`; `handoff.pending(run_id) -> dict[str, dict]` (by unit id, damaged files skipped).
- `runs.running(run_id: str, uid: str) -> bool`: its last `unit.started`/`unit.finished` is a start.
- `runs.last_session(uid: str, run_id: str | None = None) -> dict | None`: `{"id", "agent"}` from the last `session` event for the unit in that run (default the newest non-wiki run), `agent` being the runner of that event without its model; `{"id": None, "agent": …}` when the unit ran but has no id; `None` when it never ran.
- `runs.active() -> dict | None`: `{"run", "kind"}` while the run lock is held and the newest run has no `run.finished`.
- `summary()` gains `kind`: `"parallel"` when its `run.started` has `parallel`, `"autopilot"` when it has `agents`, else `None`; `failed` no longer counts `handed` or `cancelled`.

- [ ] **Step 1: Write the failing tests** — request/read/clear round trip for `discovery:api`, the file name holds no `:`, `pending` skips a damaged file; `running` across started → finished(handed) → started; `last_session` for Claude and for a runner with none and `codex:o5` → `codex`; `active` with a held `FileLock(RUN_LOCK)` and a free one; a `handed` run has `failed == 0` and `kind == "autopilot"`; `sessions.headless(True)` keeps a unit started again after a `handed` finish.
- [ ] **Step 2: Run** `uv run pytest tests/test_handoff.py -q`. Expected: FAIL (no module).
- [ ] **Step 3: Implement.** `headless` walks the events keeping the last start/finish per unit.
- [ ] **Step 4: Run** the same plus `tests/test_kpis.py tests/test_agent_sessions.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(harness): the handoff file and what a run log says of a unit`.

### Task 3: `_run_agent` can be taken

**Files:** Modify `.camarones/lib/plan.py`; Test `tests/test_run_agent_handoff.py` (a fake agent: a Python script printing one stream-json line, starting a child that writes its pid, then sleeping; the runner's `build` monkeypatched to run it).

**Interfaces — Consumes:** Task 1, `handoff.*`. **Produces:**
- `_run_agent(..., session: str | None = None)`: `session` resumes that conversation; otherwise a runner with `own_session` gets a new `uuid4`. Emits `session {id}` before starting. The result has `.handoff` (`"you"`, `"stop"`, `"cancel"` or absent) and `.session` (the id, Codex's as captured). Autopilot only (`_RUN` set and no `emit` passed): a watcher thread every `WATCH = 0.5` s, and `start_new_session=not IS_WIN`.
- `_end_agent(p) -> None`: `kill_tree(p.pid)`, wait `END_GRACE = 3` s, then SIGKILL.

- [ ] **Step 1: Write the failing tests** — a `{to: "you"}` file: process and its child are gone, `.handoff == "you"`, the request removed, a `session` event in the log; `{to: "stop"}` → `.handoff == "stop"`; a `cancel` file → `"cancel"`; a natural end → no `.handoff`, and a stale request is cleared; `session="X"` reaches `RunRequest(resume=True, session="X")`; the scheduler's call (with `emit`) starts no watcher; SIGTERM to a child running `run_autopilot` (POSIX only, `skipif IS_WIN`): the agent's group is gone and the log has `run.finished {interrupted: true}`.
- [ ] **Step 2: Run** `uv run pytest tests/test_run_agent_handoff.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**, with a context manager around `_recorded_autopilot`'s body installing the SIGTERM handler only on the main thread and off Windows, restoring it after.
- [ ] **Step 4: Run** the same plus `tests/test_autopilot.py tests/test_autopilot_events.py tests/test_scheduler.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(plan): a run's agent can be taken, stopped or cancelled by a file`.

### Task 4: The autopilot waits for you and takes units back

**Files:** Modify `.camarones/lib/plan.py`; Test `tests/test_autopilot_handoff.py`; Modify `tests/test_autopilot.py` (`test_with_only_open_units_left_it_stops_and_names_them` becomes "it waits", §4.2).

**Interfaces — Consumes:** Tasks 2–3. **Produces:** events `unit.finished {outcome: "handed", session}`, `unit.started {resume}`, `unit.waiting {units}`; constant `WAIT_TAKEN = 5`; `_resume_prompt(uid: str, lang: str) -> str`.

- [ ] **Step 1: Write the failing tests** (the `pilot` fixture's fake `_run_agent`, its result given `.handoff`) —
  - handed: `unit.finished {outcome: "handed", status: "doing"}`, not in `done`, not in `max_units`, the next unit runs;
  - handed and no session ever opens: with `sessions.GRACE` patched to 0 the run stops naming it `paused`;
  - empty queue with a taken unit: it sleeps, `unit.waiting` emitted once per change, and goes on when the unit is `done`;
  - the person closes without finishing: the run stops, "what is left needs you" and `<uid> paused`, and never picks it;
  - `{to: "pilot", session: "X", agent: "claude"}`: that unit runs first, `unit.started {resume: "X"}`, `session="X"`, counts towards `done`; a hand back on `codex` runs on `codex` even when routing prefers `claude`; with no session it runs the normal prompt; a `pilot` request on a done unit is dropped; a pilot request while its record still reads live waits;
  - stop: `outcome: "cancelled"`, status `todo`, skipped for the rest of the run, the others go on;
  - cancel file: the run ends while waiting and while running, `outcome: "cancelled"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_autopilot_handoff.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** in `_autopilot`, holding `held: set`, `stopped: set`, `handed: dict[uid, monotonic]`, `adopted: dict[uid, dict]`.
- [ ] **Step 4: Run** the same plus `tests/test_autopilot.py tests/test_autopilot_events.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(plan): the autopilot waits for you and takes a unit back`.

### Task 5: The bill counts the person's stretches

**Files:** Modify `.camarones/lib/sessions.py`, `.camarones/lib/harness/transcripts.py`, `.camarones/lib/harness/ledger.py`; Test `tests/test_ledger.py`, `tests/test_agent_sessions.py`.

**Interfaces — Produces:**
- `sessions.start(uid, agent, session, since: float | None = None)`: moves the old `[since, ended or now]` into `spans[old session]`; a session resumed whose `spans` already name it gets `since = now` unasked.
- `sessions.windows(rec: dict, sid: str) -> list | None`: `spans[sid]` plus the current `[since, ended]`; `None` = whole.
- `sessions.bound(uid) -> None`: a run will write to this conversation: a record with no `since` gets `since = 0.0`.
- `transcripts.read(path, windows: list | None = None)`: lines outside every window count neither tokens nor time, nor set `first`/`last`.
- `ledger.local_sessions` passes `windows`, keeps them on the entry (`spans`) and reuses a cached entry only when they match; an entry with no line in its windows is left out.

- [ ] **Step 1: Write the failing tests** — entries before `since` not counted; after `ended` not counted (the handed-back part); a 4.x record (no `since`) counted whole and its cached entry reused; two takeovers keep both stretches; Continue on a session with `spans` is bounded; `previous` keeps its own spans; a Codex record is unaffected.
- [ ] **Step 2: Run** `uv run pytest tests/test_ledger.py tests/test_agent_sessions.py -q`. Expected: FAIL on the new tests.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same. Expected: PASS.
- [ ] **Step 5: Commit** `feat(ledger): a conversation a run also wrote to counts only the person's stretches`.

### Task 6: `lib/takeover.py`

**Files:** Create `.camarones/lib/takeover.py`; Modify `.camarones/lib/agents.py`, `.camarones/lib/terminals.py`; Test `tests/test_takeover.py`, `tests/test_agent_terminals.py`.

**Interfaces — Consumes:** Tasks 2, 5. **Produces:**
- `takeover.take(uid: str, lang: str = "es", size=(80, 24)) -> dict`: `{"terminal", "where", "fresh": bool, "unit"}`; `fresh` when no conversation could be resumed. Raises `agents.AlreadyOpen`, `terminals.Limit`, `Refused`.
- `takeover.hand_back(uid: str) -> dict` and `takeover.stop(uid: str) -> dict`; raise `Refused`.
- `class Refused(RuntimeError)` with `.code`: `no-run`, `parallel`, `no-answer`, `finished`, `no-terminal`.
- `agents._open(..., since=None)`, with `prompt=None` meaning the person speaks first; the canvas terminal gets `env={"CAMARONES_ROOT": str(ROOT)}`.
- `terminals.close_wait(tid: str, timeout: float) -> dict`.

- [ ] **Step 1: Write the failing tests** (a fake run: a thread answering the request by emitting `unit.finished` into a real log, holding `RUN_LOCK`) —
  - take: request written, answered, PTY open on `--resume X`, no prompt, record `since` set, unit still `doing`, request gone;
  - a run that does not answer: `Refused("no-answer")` after the (patched) deadline, request removed, nothing opened;
  - lock free: no wait, opens on the newest log's session;
  - natural end during the wait: status done → `Refused("finished")`; still doing → opens on its session;
  - already live → `AlreadyOpen` with its terminal; at the limit → `Limit`, no request written;
  - a runner with no id: `fresh`, the unit's prompt, the same `cwd` and `CAMARONES_ROOT`;
  - parallel run → `Refused("parallel")`;
  - two threads at once: one terminal, the other `AlreadyOpen`;
  - hand_back: PTY ended, then `{to: "pilot", session, agent}`; no run → `no-run` and the PTY stays; no terminal → `no-terminal`; a by-hand record with no `since` gets bound;
  - stop: request written; a unit the run is not on → `no-run`;
  - `launch_unit(mode="continue")` with no record uses the log's session with `since`, Codex uses `resume <id>`.
- [ ] **Step 2: Run** `uv run pytest tests/test_takeover.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same plus `tests/test_agent_terminals.py tests/test_agents.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(takeover): take a unit from the run onto a terminal and hand it back`.

### Task 7: The routes

**Files:** Modify `.camarones/lib/serve.py`; Test `tests/test_terminals_api.py`.

**Interfaces — Produces:** `POST /api/app/units/<uid>/takeover {cols, rows, lang}`, `/handback`, `/stop` through `app_unit(uid, action, b) -> tuple[dict, int]`. 409 bodies: `{"error", "code"}`; `{"error", "terminal"}` already open; `{"error", "limit"}` at the limit. 404 unknown unit, 400 bad size.

- [ ] **Step 1: Write the failing tests** — add the three to `ROUTES` (403 with the portal token and none); `discovery%3Aapi` decodes; 400 on `cols: 1`; 404 unknown unit; each 409; a full take over and hand back over HTTP with a fake run thread.
- [ ] **Step 2: Run** `uv run pytest tests/test_terminals_api.py -q`. Expected: FAIL on the new tests.
- [ ] **Step 3: Implement**, the route matched before `by` (it runs git).
- [ ] **Step 4: Run** the same. Expected: PASS.
- [ ] **Step 5: Commit** `feat(serve): the app's routes to take, hand back and stop a unit`.

### Task 8: The canvas

**Files:** Modify `.camarones/desktop/renderer/src/{canvas.js,plan.js,i18n.js,app.css}`, `src/sections/{Canvas.jsx,Terms.jsx,Plan.jsx}` and their tests, rebuild `renderer-build/`; `.camarones/portal/app/src/{board.js,Pipeline.jsx,i18n.js}`, `board.test.js`, rebuild `app-build/`.

**Interfaces — Consumes:** Task 7, `run.kind`. **Produces:**
- `feed`: `fu.session`; `f.waiting: string[]` (from `unit.waiting`, emptied by `unit.started` and `run.finished`).
- `takeable(run) -> boolean`: a live autopilot run.
- `takeOver(srv, uid, go) -> res` in `plan.js`, as `openSession`; `refusal` says `code` in the app's language.
- `useTerminals()` gains `handBack(uid, id)` (posts, then its screen goes as after `close`).
- `TermNode` data `onTake`, `onStop`, `canTake`, `taking`; `PtyNode` data `onHandBack`, `canHandBack`, `taken`.
- Strings `cv.take`, `cv.taking`, `cv.stop`, `cv.openYou`, `cv.noSession`, `cv.st.handed`, `cv.waitingYou`, `pty.handBack`, `pty.leavePilot`, and refusals `hand.no-run`, `hand.parallel`, `hand.no-answer`, `hand.finished`, `hand.no-terminal`; portal `pipe.handed`.

- [ ] **Step 1: Write the failing tests** — `feed` keeps `session`, `waiting`; `handed` folds with its label, is not an error; running node shows Stop and Take control only with `canTake`; no session says a new session opens; a failed node offers *Open with you*; `PtyNode` shows *Hand back to the pilot* when `taken`, *Leave to the pilot* otherwise, neither without `canHandBack` nor once ended; es and en; `takeOver` lands on the terminal and a 409 with one focuses it; the portal reducer keeps a handed unit `doing` through `run.finished`.
- [ ] **Step 2: Run** `( cd .camarones/desktop/renderer && npx vitest run )`. Expected: FAIL on the new tests.
- [ ] **Step 3: Implement**, following `.claude/skills/cofundo-design-system/CAMARON.md`.
- [ ] **Step 4: Run** the same and `( cd .camarones/portal/app && npx vitest run )`; then `npm run build` in both. Expected: PASS, builds written.
- [ ] **Step 5: Commit** `feat(canvas): take control, stop and hand back on a unit's node`, with both builds.

### Task 9: Docs, version, verification, pull request

**Files:** `README.md`, `.camarones/lib/common.py`, guides `templates/docs/guides/{app,internals,tutorial}.md` and `i18n/es` twins, `lib/tutorial.py`, `.camarones/TUTORIAL.md`, `AGENTS.md` (repo map), `docs/handoff` untouched.

- [ ] **Step 1:** Bump to 4.79.0 and the badge; describe take control, stop, hand back and the wait in README, guides and tutorial; regenerate `TUTORIAL.md`; note in the commit that existing projects keep their copy of the shipped guide.
- [ ] **Step 2: Run** `uv run pytest -n auto`, `( cd .camarones/desktop/renderer && npx vitest run )`, `( cd .camarones/portal/app && npx vitest run )`, `( cd .camarones/desktop && node --test "test/*.test.cjs" )`. Expected: all green; say otherwise with the output.
- [ ] **Step 3: Commit** `docs(canvas): take a unit from the autopilot and hand it back; kit 4.79.0`.
- [ ] **Step 4:** Merge `origin/main` if S2 fixes landed, push, open the PR, read CI on macOS, Ubuntu and Windows through the ccd_pr tools.
