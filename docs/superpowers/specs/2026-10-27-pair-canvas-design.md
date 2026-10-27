# Pair canvas: watch every plan unit live and take control of it — design

Asked by the user on 2026-10-27: "I have no visibility of the autopilot or of what is being done in each task of the
plan. I'd like it to be more *pair* and to see everything as if it were nodeterm." Builds on the desktop app's Plan
(`desktop/renderer/src/sections/Plan.jsx`), the run event log (`harness/events.py`, `runs/<run>/events.jsonl`) and
the interactive unit sessions (`lib/agents.py`, `lib/sessions.py`). The agent board's spec
([2026-10-26-agent-board-design.md](2026-10-26-agent-board-design.md) §9) left "a real PTY terminal to take over a
task" for later; this is that piece, for the documentation plan.

## 1. Intent

Today the autopilot and *Ejecutar* run each unit as a headless `claude -p` / `codex exec`. Every event (tool calls,
text, usage) is already written to `runs/<run>/events.jsonl`, but the desktop app's Plan only says "Autopilot on"
with a Stop button; its output appears only when it fails. Sessions opened by hand go to an OS terminal window outside
the app. The person cannot see what each unit's agent is doing, and cannot step in without stopping everything.

This piece puts every agent session of the plan **on a canvas in the desktop app**: the unit graph, where each running
unit opens as a live terminal node. A headless unit shows its event stream read-only; **Take control** turns that node
into a real terminal (PTY) on the same conversation, where the person types; **Hand back to the pilot** returns it to
the run, which continues headless with the person's corrections in context. Sessions opened by hand live on the
canvas too.

**Done when:** the person starts the autopilot from the app; the canvas shows the unit graph and each running unit as a
terminal with what it does (tools, text, cost, time); they press *Take control* on one, type a correction inside the
node, press *Hand back to the pilot*, and the autopilot carries on with that unit headless; the other units never
stopped.

**Anti-goals — a failure even if it works:** losing the conversation in a handoff; a handoff counted as a failure or
stopping the run; the portal gaining a machine action; a 3.x/4.x project, run log or session record changing meaning;
the external terminal window disappearing (it stays as a setting); anything that only works on macOS.

### 1.1 Decisions taken with the user (2026-10-27)

| Question | Decision |
|---|---|
| What "pair" means | **Watch live, read-only, and take control**: the headless stream per unit, and a button that hands the unit to the person |
| Where and how it looks | The **desktop app**, Plan section, a **nodeterm-like canvas**: the unit graph, running units open as terminal nodes |
| Where the person types after taking control | **Inside the same node**: a real PTY (xterm.js) on the resumed conversation |
| Scope | **Everything on the canvas**: autopilot, *Ejecutar* (parallel) and the sessions opened by hand (*Abrir unidad*, *Actualizar docs*); the external window stays as a setting |
| Approach | **A — headless by default, PTY on takeover, PTYs hosted by the project server** (not every unit as a PTY from the start; not `node-pty` in Electron; not delegating to nodeterm) |
| Who drives it | Only the desktop app (app token). The CLI gains no command; a CLI-started autopilot can still be taken over from the app, because the handoff is file-based |

### 1.2 Approaches considered

- **A (chosen).** Headless stream-json stays the unattended mode (reliable at night: usage limits, cost and failures
  are read from the stream), now with a known conversation id per unit. Take control = the run kills its headless
  process, the server opens `--resume <id>` in a PTY. One owner of interactive processes (the server); testable in
  pytest with a fake program. Costs `pywinpty` on Windows only; PTYs die with the app (the unit is then paused, as
  when a terminal window is closed today).
- **B. Every unit is a PTY from the start.** Closest to nodeterm, one primitive, no handoff. Rejected: end of unit and
  usage limits would be read from transcripts and `plan.yaml` instead of the stream; a permission prompt can block a
  night run; Codex and opencode TUIs differ. More fragile unattended.
- **C. `node-pty` in Electron.** A native module per Electron ABI × three OSes fails AGENTS.md §2.4 (install and
  integration cost), and neither the CLI nor the server would see the sessions. Delegating to nodeterm itself fails
  too: an external app not guaranteed on the three OSes, and its control endpoint only answers from inside its nodes.

## 2. The canvas (desktop app › Plan › view *Canvas*)

```
Plan   [Board] [Phases] [Canvas●]           autopilot ● 3/12 · 14 min · $1.20   [Stop run] [⤢ Fit] [Re-layout]
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [overview ✓ 2m $.31]──┐                                                                              │
│                       ├──▶┌ explain-api ── claude ● 4m · $.22 ─────── ⤢ ┐                            │
│ [repo-brief ✓ 3m]─────┘   │ ⌕ Grep "RestController"                     │                            │
│                           │ ✎ Edit cam-docs/repos/api/endpoints.md      │──▶[flows ○]                │
│                           │ » The public endpoints are in 3 control…    │                            │
│                           │ ▶ Bash rg -n "@GetMapping" src/             │                            │
│                           │                     [Stop] [Take control]   │                            │
│                           └─────────────────────────────────────────────┘                            │
│                           ┌ c4-context ── codex · you ✋ 1m ────────── ⤢ ┐                            │
│                           │ (xterm: codex's real TUI)                   │                            │
│                           │ > leave the gateway out of the context_     │                            │
│                           │            [Hand back to the pilot] [Close] │                            │
│                           └─────────────────────────────────────────────┘                            │
│ ┌ Loose ───────────────┐                                                                             │
│ │ update ── claude ✋  │   (sessions that are not a unit: Update docs, the C4 refinement)            │
│ └──────────────────────┘                                                                             │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **The graph.** The portal's graph (`@xyflow/react` at the version the portal pins, 12.12.0): columns by phase,
  arrows by dependency, the board's tone colours. Pan, zoom and drag nodes; positions kept per person in
  `localStorage` (try/catch, a per-viewer convenience); *Re-layout* returns to the automatic layout. The layout is a
  pure function (`desktop/renderer/src/canvas.js`) that knows two node sizes: **compact** (id, title, state, time and
  cost once done) and **terminal** (about 440×280), and never overlaps them.
- **Nodes by state:**

  | State | Node | Buttons |
  |---|---|---|
  | Ready, waiting, done | compact; click → the Plan's existing detail panel | *View terminal* if it ran: replayed from its events |
  | Running headless | terminal, **read-only**: one row per event (§2.1), autoscroll that pauses when the person scrolls up | Stop · Take control |
  | With you (PTY) | terminal, **xterm.js** with the agent's real TUI; a click gives it the keyboard and the canvas drops its shortcuts | Hand back to the pilot (only while a run is active) · Close |
  | Paused (no live session, unit `doing`) | compact with a note | Continue (reopens with `--resume`) |
  | Failed | terminal with its last output, in the error tone | Retry · Open with you |

- A finished node folds back to compact a few seconds later, with ✓, time and cost. **⤢** maximises a node to the
  whole canvas, **Esc** returns. **Fit** frames the running nodes.
- **Loose sessions** (*Update docs*, the C4 refinement prompt) are not plan units: they live in their own lane.
- **Default view:** the last one picked is remembered (`dk.planView`, as today); with none picked and something live,
  *Canvas* opens.
- **Keyboard and accessibility:** arrows/Tab move between nodes, Enter opens, Esc leaves. The read-only stream is
  `role="log"` with `aria-live="polite"`; xterm's screen reader mode is on. Every string in `es` and `en`
  (`desktop/renderer/src/i18n.js`); no jokes on buttons, errors or the handoff (AGENTS.md §3). UI work follows the
  `cofundo-design-system` skill and its `CAMARON.md`; terminal bodies are dark and monospace in both themes.

### 2.1 The read-only stream

One row per runner event of that unit (`plan._show` already maps them for the CLI; the renderer gets a pure twin in
`canvas.js`, unit-tested):

| Event | Row |
|---|---|
| `tool.call` Edit/Write, `file.changed` | `✎ <tool> <path>` |
| `tool.call` Read/Glob/Grep | `⌕ <tool> <path or pattern>` |
| `tool.call` Bash / `$` | `▶ <command>` |
| `tool.call` other (MCP) | `· <name> <arg>` |
| `log` | `» <text>` (raw lines as they are) |
| `error` | the error row, in the error tone |
| `usage` | updates the header's cost, no row |

The header shows title, runner, elapsed time and the unit's cost so far (sum of its `usage` events).

## 3. Backend

### 3.1 Every headless session has a known conversation

- **Claude:** `_run_agent` makes a `uuid4` per attempt and passes it as `RunRequest.session`. The runner, which today
  reads `session` only when interactive, adds `--session-id <id>` to `claude -p`; with `resume=True` it builds
  `claude -p --resume <id>` (hand back to the pilot). The `RunRequest` comments for `resume` and `session` drop
  "interactive only".
- **Codex:** cannot be given an id, so it is captured: `parse_event` maps `thread.started` to a new normalised event
  `{"type": "session", "id": …}`. Resume: `codex exec resume <id> --json …` headless, `codex resume <id>` interactive
  (today interactive resume is `resume --last`, which can pick another conversation; it becomes `resume <id>` when a
  session is known, `--last` otherwise).
- **Other runners** (opencode, command templates, local): no id. Take control opens a fresh interactive session on
  the unit's prompt and checkpoints, and the node says so.
- The id travels in the run's log: `unit.started {session}` (Claude) or the `session` event (Codex).
- `Runner` port docs list `session` among the normalised events; runners that never emit it keep working.

### 3.2 The handoff between processes

The headless process belongs to the run — the autopilot job, the parallel scheduler, or a CLI in a terminal — which may
be another process than the server. So the handoff is a file, as `cancel` is today (`scheduler.request_cancel`):

1. The app calls `POST /api/app/units/<uid>/takeover`; the server writes `runs/<run>/handoff/<unit>.json`
   `{"to": "you", "at": …}` (atomic: temp + `os.replace`).
2. In the run, a watcher thread per running unit (beside `_run_agent`'s heartbeat, every 0.5 s) sees it, kills the
   agent's process tree through the `lib/common.py` helpers, removes the request and emits
   `unit.finished {outcome: "handed", session}`. `_run_agent` returns that outcome; it is neither a failure nor a
   usage limit.
3. The server waits for that event (10 s at most) and opens the PTY on `--resume <id>` (§3.3), in the same `cwd` and
   `env` the headless agent had (its worktree for a worktree unit).
4. *Hand back to the pilot*: the server closes the PTY (its wrapper records `ended`) and writes
   `{"to": "pilot", "session": <id>}`; the run adopts it (§4).
5. *Stop* on a single unit is the same file with `{"to": "stop"}`: the process is killed, `unit.finished
   {outcome: "cancelled"}`, the unit goes back to `todo`, and the run skips it for the rest of this run and goes on
   with the others (the run-wide Stop is unchanged).

If the run lock (`scheduler.RUN_LOCK`) is free — the run that owned the unit is dead — the server does not wait: it
opens the PTY on the last session id found for that unit in the newest run log.

### 3.3 PTYs live in the project server (`lib/terminals.py`, new)

- **Start:** macOS/Linux `pty.openpty()` + `subprocess.Popen(..., start_new_session=True)` on the slave; Windows
  `winpty.PtyProcess.spawn` (ConPTY, Windows 10 1809+). Branch on `IS_WIN` from `lib/common.py`.
- **Command:** the agent runs inside `session_run.py`, exactly as in today's terminal window
  (`sessions.wrap(sessions.start(uid, agent, session), argv)`), so `lib/sessions.py` keeps knowing whether the session is
  live or paused, unchanged. Takeover writes `since` into that record (§3.5). Loose sessions (update, prompt) get no
  session record, as today, so the plan bill does not change for them; their terminal metadata is enough.
- **Output:** a reader thread appends the bytes to `<cache>/terminals/<id>.log` (cut to its last 5 MB) and to an
  in-memory ring of 256 KB for replay; metadata in `<cache>/terminals/<id>.json`
  `{id, unit, agent, session, pid, cwd, started, ended, code, cols, rows}`. Ids: `t-<slug(unit)>-<n>`.
- **Control:** write input (UTF-8 text), resize (`TIOCSWINSZ` through `fcntl` / `setwinsize`), close (tree kill).
- **Limits:** 8 live PTYs per project server; the ninth is refused (409).
- **Life:** the server kills its PTYs on exit (`atexit` and its signal handlers); their records get `ended`, so the
  unit reads as paused and *Continue* reopens it with `--resume`.
- **Dependency:** `pywinpty` pinned to an exact version in `camarones.py`'s uv header with
  `; sys_platform == 'win32'`, and recorded as passing in `docs/research/tooling-candidates.md` (AGENTS.md §2.4:
  wheels for every supported Python, no admin rights, MIT, local). If it does not import, interactive sessions fall
  back to the external window with a note; the read-only view keeps working.

### 3.4 API (`lib/serve.py`, app token only — `is_app()`; the portal token and no token get 403)

| Route | Does |
|---|---|
| `POST /api/app/units/<uid>/takeover` `{cols, rows}` | §3.2 → `{terminal}`; 409 if the unit already has a live session ("already with you"), if the run did not answer in 10 s, or at the PTY limit |
| `POST /api/app/units/<uid>/handback` | closes the PTY, writes `{to: pilot}`; 409 when no run is active |
| `POST /api/app/units/<uid>/stop` | §3.2 step 5 |
| `POST /api/app/terminals` `{unit \| update \| prompt, agent, mode, cols, rows}` | the sessions opened by hand, now on the canvas (`agents.launch_unit` / `launch_update` / `launch_prompt` build the argv; where it opens depends on the `sessions` setting, §3.6) |
| `POST /api/app/terminals/<id>/input` `{data}` · `/resize` `{cols, rows}` · `/close` | keys, size, close |
| `GET /api/app/terminals` | the PTYs, live and ended in this server's life |
| `GET /api/app/terminals/stream?from=<id>:<offset>,…` | **one SSE for every PTY**: `{t, d}` (`d` = base64 bytes, its SSE id `<t>:<offset>`) and `{t, end: code}`; replays from each offset, then follows; new PTYs join the stream as they open |
| `GET /api/runs/<run>/events` | today's route, unchanged: the canvas opens **one** and routes the events to their units |

One stream for every PTY because Chromium allows six HTTP/1.1 connections per host: four PTY streams plus the run's and
the jobs' would starve every other request. Bytes go as base64 because a PTY read can split a UTF-8 character; xterm
takes the bytes as they are. The renderer reads SSE through `fetch` as the portal's `api.js` does (an `EventSource`
cannot send the app token).

### 3.5 Cost without counting twice

The headless part is already counted from the run's `usage` events. When the person takes control, the session record
gets `since` (the handoff time); `ledger.local_sessions` counts only the transcript entries from `since` on. Records
without `since` (every 3.x/4.x record) are counted whole, as today. When the unit is handed back, the run's next
`usage` events count the headless part again; the transcript part stays counted once, through the record.

### 3.6 The `sessions` setting

`machine.DEFAULTS` gains `sessions: canvas | window` (default `canvas`), editable with `camaron config` and in the
app's Machine panel. `window` keeps today's behaviour for manual sessions: `env.open_new_terminal`. The wizard (a
terminal, not the app) keeps opening windows whatever the setting.

### 3.7 Compatibility (AGENTS.md §2.3)

All new fields are optional: `session` and `resume` in run events, `since` in session records, `handoff/` files, the
`sessions` setting. 3.x/4.x run logs, session records and plans read as before. `runs/<run>/events` keeps its shape;
the portal's reducer (`portal/app/src/board.js`) only gains the `handed` outcome's label ("with you"), read-only.
No CLI command, flag, `workspace.yaml` key or frontmatter field is renamed or dropped; `catalog --check` is unaffected
(the new routes are app routes, like `/api/app/agent`).

## 4. The run and the units taken over

### 4.1 One rule: a unit with a live session is not the run's

The source of truth is the unit's session record (`sessions.live(load(uid))`), not state in the run's memory. It
covers the PTY of a takeover, a session opened by hand on the canvas and today's external window. The autopilot and
the scheduler filter their queue with it. This also fixes a latent bug: today `plan.available()` returns `doing` units
first and neither loop checks for a live session, so the autopilot can pick a unit the person has open in a window.
The unit stays `doing` throughout; a handoff never touches `plan.yaml`.

### 4.2 Autopilot (one after another)

1. `_run_agent` returns `handed` → the event of §3.2; it does not add to `done` nor to `max_units`; the run goes on with
   the next ready unit.
2. **Empty queue while units are taken:** instead of stopping with "nothing ready", it **waits**, re-syncing every 5 s,
   while any taken unit's session is live, and emits `unit.waiting {units}` once per change. When the person closes a
   unit with `plan done`, its dependents become ready and the run continues.
3. **The person closes the PTY without closing the unit** (it is paused): the run stops waiting for it; with nothing
   else ready it stops with today's message, naming it ("what is left needs you: `<uid>` paused").
4. **Hand back to the pilot:** the run sees `{to: pilot}`, puts the unit **first in the queue** and resumes it headless
   (`RunRequest(resume=True, session=<id>)`) with a short prompt: the person corrected you in this same conversation;
   carry on with the unit and close it with `plan done`. This time it counts towards `done`.
5. **Stop run** with units taken: the run ends; the person's PTYs stay open.

### 4.3 Parallel (scheduler)

- A taken unit **frees its runner slot** (`--parallel`, `--per-runner`): it is the person's session now.
- **Exception:** a taken *in-place* unit still keeps other *in-place* units out, because they would edit the same
  cam-docs.
- **Worktree units:** the PTY opens **in the unit's worktree**, with the `cwd` and `CAMARONES_ROOT`/
  `CAMARONES_STATE_ROOT`/`CAMARONES_WORKSPACE` its headless agent had (`scheduler._work`). When the person closes it
  with `plan done`, the scheduler integrates it as today, noticing the status in its `sync` instead of waiting for the
  job's thread.
- The run does not finish while taken units have live sessions, as in the autopilot.

### 4.4 Sessions opened by hand while a run is active

The run skips them (§4.1). While a run is active their node also offers **Leave to the pilot**, which is the same
`{to: pilot}` request, adopted as in §4.2 step 4. With no run active, only *Close*.

### 4.5 Events (all optional, compatible)

New values: `unit.finished.outcome: "handed"`, `unit.started.resume: <session>`, `unit.waiting {units}`, and the
runner event `session {id}`. Readers that do not know them ignore them.

## 5. Errors and limits

Short and precise messages, `es` and `en`, no jokes (AGENTS.md §3).

| Case | What happens |
|---|---|
| The run does not answer a takeover in 10 s | Run lock free (run dead): the server opens the PTY itself on the last known session. Run alive: 409 "the run did not answer; try again" |
| The unit already has a live session | 409 "already with you"; the node focuses that PTY |
| `--resume` fails (transcript missing) | The node shows the agent's error and offers *Open a new session* on the unit's prompt and checkpoints |
| Runner with no session id | *Take control* says a new session opens without the conversation |
| Windows without ConPTY, or `pywinpty` does not import | Interactive sessions fall back to the external window with a note; the read-only view keeps working |
| Too many sessions | 8 PTYs per project; the ninth: 409 "close one first" |
| Huge output | 256 KB ring for replay; each terminal's `.log` cut to its last 5 MB |
| The app or the server closes | PTYs killed, records `ended`, units paused; *Continue* reopens them with `--resume` |
| No agent installed | The canvas still shows the graph and past runs; *Take control*, *Continue* and opening sessions are disabled with how to install one |

**Security:** every new route is app-token only, on `127.0.0.1`; commands are argv lists, never a shell; PTY input is
never accepted from the portal token.

**macOS, Windows, Linux:** stdlib `pty` on POSIX, ConPTY through `pywinpty` on Windows; `killpg` on POSIX, tree kill on
Windows, through `lib/common.py`; `pathlib` and `encoding="utf-8"` everywhere. Electron's main process does not change;
the renderer gains `@xterm/xterm` and `@xterm/addon-fit` (pinned exactly in `desktop/renderer/package.json`) and
`@xyflow/react` 12.12.0, all bundled into the committed `renderer-build/` (users never run npm).

**Known limits (accepted):** PTYs die with the app (the unit is then paused, never lost); one person per machine; no
canvas in the portal; no minimap; no manual node resizing; sessions on another machine cannot be controlled; the
interactive resume of Codex depends on the Codex version installed (the kit does not pin agent CLIs).

## 6. Tests

TDD, offline, `make_workspace` + `isolated_env`; each test owns its `tmp_path`, home and ports.

- **The latent bug first:** a test where the autopilot picks a unit open in a window (a session record with a live
  pid); then the rule of §4.1 for the autopilot and the scheduler.
- **Runners:** pinned argv for `claude -p --session-id`, `claude -p --resume`, `codex exec resume <id> --json`,
  `codex resume <id>` and the `--last` fallback; Codex `thread.started` → `session` event.
- **`_run_agent`:** a fake agent (a Python script that prints stream-json and sleeps) plus a `handoff` file → process
  tree killed, outcome `handed`, events emitted, request removed; `{to: stop}` → `cancelled`.
- **Autopilot:** skips the taken unit; waits while its session is live; goes on when it closes with `plan done`; a
  paused unit ends the wait with the message; hand back → first in the queue with `resume`; *Stop run* leaves PTYs
  open; `max_units` ignores handed units.
- **Scheduler:** the slot is freed; in-place exclusivity kept; a worktree unit closed by the person is integrated on
  `sync`.
- **`terminals.py`:** an echo program in a real PTY (through `pywinpty` on the Windows CI runner): input, resize,
  close, natural end, the `.log`, replay from the ring, tree kill, the 8-PTY limit, kill on server exit.
- **API:** 403 with the portal token and with none; 400 on bad input; the 409 cases; the single stream replays from
  offsets and carries base64; takeover with the run lock free.
- **`ledger`:** entries before `since` are not counted; 4.x records are counted whole.
- **`machine`:** the `sessions` setting, its choices, and the wizard ignoring it.
- **Renderer (Vitest):** the layout (two sizes, no overlap); unit + events + PTYs → node state and buttons; the row
  table of §2.1; the autoscroll pause; xterm focus turning the canvas shortcuts off; demultiplexing the stream; the
  default view.
- **Portal (Vitest):** the reducer accepts `handed`.
- **Sandbox (PetClinic):** autopilot with a fake agent on `PATH` through the app's routes: take control, type, hand
  back, finish; then `uninstall` + `traces` (exit 0).

## 7. Delivery in vertical slices

Each slice ships with its tests, the README (Spanish) and the tutorial in `es`/`en` (`lib/tutorial.py` →
`.camarones/TUTORIAL.md`, and the shipped `templates/docs/guides/tutorial.md` + its `es` twin, noting that existing
projects keep their copy), and a minor bump of `VERSIONS["kit"]` (AGENTS.md §5.1, §2.3).

| Slice | End to end | Done when |
|---|---|---|
| **S1 · See** | The *Canvas* view: graph, compact nodes, read-only terminal nodes fed by the run's SSE, the run bar with today's run-wide Stop (no per-unit buttons yet) | The person starts the autopilot and sees live what each unit does — **this alone fixes the missing visibility** |
| **S2 · Terminals on the canvas** | `terminals.py`, the terminal routes and single stream, xterm nodes; *Abrir unidad* and *Actualizar docs* open on the canvas (the `sessions` setting); the rule of §4.1 | The person opens a unit by hand and works with its agent inside the node |
| **S3 · Take and hand back** | Session ids (Claude, Codex), the file handoff, per-unit Stop, the autopilot's wait and hand back, `since` in the bill | The person takes a unit from the autopilot, corrects it, hands it back and the pilot carries on with it |
| **S4 · Parallel** | §4.3 in the scheduler: slots, PTY in the worktree, integration on close | Same as S3 with *Ejecutar* and 2–4 units at once |

## 8. Left to the builder

Exact wording of the resume prompt within §4.2 step 4; JSON field names inside the terminal metadata beyond those
listed; node sizes and spacing within §2; the debounce of resize; the exact `pywinpty` and xterm versions (pinned,
recorded); toast and error wording (`es`/`en`, AGENTS.md §3).
