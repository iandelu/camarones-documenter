# Pair canvas S2 · Terminals on the canvas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The sessions a person opens by hand (*Empezar* / *Seguir* on a unit, *Actualizar docs*) open as real
terminals inside the Plan's canvas, where the person types to the agent; the external window stays as a setting; and
the autopilot and *Ejecutar* never take a unit that has a session open.

**Architecture:** `lib/terminals.py` (new) keeps PTYs in the project server: stdlib `pty` on POSIX, ConPTY through
`pywinpty` on Windows, a reader thread per PTY into a 256 KB ring and a `.log`, input, resize and close, 8 at most,
killed when the server exits. `agents.launch_unit` / `launch_update` gain `where`: `canvas` spawns the very argv a
window runs today (the agent inside `session_run.py`), `window` keeps today's window, and the wizard never passes it.
`lib/serve.py` adds app-token routes and **one** server-sent stream for every PTY. In the renderer, `useTerminals`
holds that stream and one xterm per terminal, `PtyNode` shows it on the canvas, and every place that opens a session
goes through `openSession`, which lands on `#/plan?term=<id>`.

**Tech Stack:** Python stdlib (`pty`, `select`, `fcntl`, `termios`), `pywinpty` 3.0.5 (Windows only), React 19,
`@xyflow/react` 12.12.0, `@xterm/xterm` 6.0.0, `@xterm/addon-fit` 0.11.0, Vite, Vitest (node environment,
`renderToStaticMarkup`).

**Spec:** [docs/superpowers/specs/2026-10-27-pair-canvas-design.md](../specs/2026-10-27-pair-canvas-design.md) — this
plan is its slice **S2 · Terminals on the canvas** (§7): §3.3, §3.4 without takeover / handback / per-unit stop, §3.6,
§4.1, the §5 rows that concern PTYs, and the three items S1 left for S2 (one run-lock probe per pipeline read, the
`ended` shadowing in `Canvas.jsx`, sessions back in the default view's trigger).

**Not in S2** (S3, S4): conversation ids for headless runs, the handoff files, *Take control*, *Hand back to the pilot*,
*Leave to the pilot*, per-unit Stop, the autopilot waiting for taken units, `since` in the bill, the scheduler's slot
rules and PTYs in a unit's worktree. The first run's C4 refinement (`launch_prompt`, opened from `#/start`) keeps its
window: it runs from the first-run wizard, not the Plan, so the new route takes `unit` (a unit id or `update`) only.

## Global Constraints

- macOS, Windows and Linux (AGENTS.md §2.1): `pathlib`, `encoding="utf-8"`, argv lists and no shell, processes through
  `lib/common.py` (`which`, `run`, the new `kill_tree`), branch on `IS_WIN`. `lib/terminals.py` imports no POSIX-only
  module (`pty`, `fcntl`, `termios`) at module level: Windows imports it too.
- Values from the spec: 8 live PTYs per project server, the ninth refused (409); a 256 KB ring per PTY for replay;
  `<cache>/terminals/<id>.log` cut to its last 5 MB; metadata `<cache>/terminals/<id>.json` with `{id, unit, agent,
  session, pid, cwd, started, ended, code, cols, rows}`; ids `t-<slug(unit)>-<n>`; stream messages `{t, d}` (`d` base64)
  with SSE id `<t>:<offset>`, and `{t, end: code}`; setting `sessions: canvas | window`, default `canvas`; every new
  route app-token only; units without a session record stay without one (`update`).
- Values this plan fixes: metadata also `kind` (`unit` | `update`) and `closed`; stream data messages also carry `o`
  (the offset after them), at most 64 KB each; keep-alive every 15 s; `started` / `ended` in epoch seconds; input at most
  256 KB a request, given 5 s to be taken; `cols` 10–500, `rows` 5–200, default 80×24; *Close* sends SIGHUP to the
  PTY's process group and SIGKILL 3 s later (`taskkill /T /F` on Windows); the `.log` is cut once it passes 5 MB + 1 MB;
  the newest 50 terminal files are kept; xterm scrollback 5000 lines, resize debounced 150 ms; an ended terminal stays on
  the canvas `FOLD_MS` (4000 ms) after a clean end, until removed after any other end, and not at all once closed.
- Dependencies pinned exactly: `pywinpty==3.0.5; sys_platform == 'win32'` in `camarones.py`'s uv header and in
  `pyproject.toml`'s dev group (with `uv.lock`); `"@xterm/xterm": "6.0.0"` and `"@xterm/addon-fit": "0.11.0"` (no `^`)
  in `desktop/renderer/package.json`. Both recorded in `docs/research/tooling-candidates.md` §K (AGENTS.md §2.4).
- Backward compatible (AGENTS.md §2.3): session records, run logs and plans keep their shape; `POST /api/app/agent`
  stays, as the old name of `POST /api/app/terminals`; `session_run.py`'s argv only gains `-` for "no record".
  Electron's main process does not change.
- Every user-facing string in `es` and `en`; no jokes on buttons, states, errors or the setting (AGENTS.md §3). UI work
  follows `.claude/skills/cofundo-design-system/CAMARON.md`: square radii, text glyphs, theme tokens, terminal bodies
  dark in both themes. `localStorage` only inside `try/catch`.
- Every commit that changes the renderer's source also commits a rebuilt `.camarones/desktop/renderer-build/`
  (`npm run build`); CI fails when the build differs from its source.
- Conventional commits, no `Co-Authored-By` line; other sessions may be editing the tree: stage only your own files.
- Commands run from the repo root; renderer commands inside `( … )` so the shell's folder does not change. Python tests
  that open PTYs end them in their fixture (`terminals.shutdown()`).

## Review Focus

1. **Keys typed in a terminal** (Esc, Ctrl+C, arrows, Space, Backspace — Esc interrupts Claude Code): they reach the
   agent, never the canvas or React Flow; Esc still leaves a maximised read-only log. Test: Task 9 `a key typed in a
   terminal belongs to the agent`.
2. **A UTF-8 character split between two reads** (ñ in a Spanish prompt, a TUI's box drawing): the bytes reach xterm
   untouched. Tests: Task 6 `the stream replays each terminal from its offset, in base64` (cut inside ñ) and Task 7
   `chunks decode to the very bytes the program wrote`.
3. **The app closes with sessions open:** no agent is left running, the units read as paused and *Seguir* reopens
   them. Tests: Task 3 `shutdown ends every terminal`, Task 4 `a unit terminal closes its session record`, Task 6 `the
   server's exit takes its terminals with it`.
4. **The same unit opened twice** (Summary and Plan, a double click) **or a ninth terminal:** refused before the plan
   or the session record change, and the open terminal is shown. Tests: Task 5 `a unit open on the canvas is not opened
   again`, `the ninth terminal is refused before the unit moves`; Task 7 `an already open session takes you to its
   terminal`.
5. **A paste bigger than the PTY's input buffer** (a stack trace pasted to the agent): written whole while the program
   reads, refused after 5 s when it does not, never holding the server. Tests: Task 3 `a big paste is written whole`
   and `input to a program that does not read gives up`.

---

### Task 1: The pipeline probes the run lock once

S1 left this: `api_pipeline` asks `scheduler.busy()` twice (through `sessions.headless()` and `run_stopped`), and a
probe holds the lock for an instant, so two probes can see each other and flicker a stopped run back to running; on
Windows a lock file still being deleted raises `PermissionError` out of the probe.

**Files:**
- Modify: `.camarones/lib/harness/scheduler.py` (`busy`), `.camarones/lib/sessions.py` (`headless`),
  `.camarones/lib/serve.py` (`run_stopped`, `api_pipeline`)
- Test: `tests/test_portal_pipeline.py`, `tests/test_agent_sessions.py`

**Interfaces:**
- Produces:
  - `scheduler.busy() -> dict | None` — a `PermissionError` from the probe (Windows: the last holder's file is being
    deleted) reads as free: `None`.
  - `sessions.headless(busy: bool | None = None) -> set[str]` — `None` probes `scheduler.busy()` as today.
  - `serve.run_stopped(run_id: str, busy: bool | None = None) -> bool` — `None` probes.
  - `api_pipeline` computes `busy = scheduler.busy() is not None` once and passes it to both.

- [ ] **Step 1: Write the failing tests**

In `tests/test_portal_pipeline.py` (it has `stopped_run`):

```python
def test_a_pipeline_read_probes_the_run_lock_once(kit, monkeypatch):
    from lib.harness import scheduler
    kit.plan.sync()
    stopped_run(kit)
    calls = []
    monkeypatch.setattr(scheduler, "busy", lambda: calls.append(1) or {"pid": 1})
    run = kit.serve.api_pipeline("es")["run"]
    assert calls == [1]
    assert run["finished"] is False                           # one answer, held: the run is on


def test_a_run_lock_windows_is_still_deleting_reads_as_free(kit, monkeypatch):
    from lib.harness import locks, scheduler

    def deleting(self):
        raise PermissionError(13, "delete pending")
    monkeypatch.setattr(locks.FileLock, "acquire", deleting)
    assert scheduler.busy() is None
```

In `tests/test_agent_sessions.py`, beside `test_a_run_that_died_does_not_keep_its_units_busy`:

```python
def test_headless_uses_the_lock_answer_it_is_given(wired, monkeypatch):
    from lib import sessions
    from lib.harness import scheduler
    from lib.harness.events import EventLog
    log = wired.common.CTX.runs / "2026-10-26-run" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    EventLog(log).emit("unit.started", unit="u1")
    monkeypatch.setattr(scheduler, "busy", lambda: pytest.fail("probed again"))
    assert sessions.headless(busy=True) == {"u1"}
    assert sessions.headless(busy=False) == set()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_portal_pipeline.py tests/test_agent_sessions.py -k "once or deleting or answer_it_is_given" -v`
Expected: FAIL — `calls == [1, 1]`; `PermissionError` raised; `headless() got an unexpected keyword argument 'busy'`.

- [ ] **Step 3: Implement the three changes** as in Interfaces; docstrings say why one probe (a probe holds the lock
  for an instant).

- [ ] **Step 4: Run the pipeline and session tests**

Run: `uv run pytest tests/test_portal_pipeline.py tests/test_agent_sessions.py tests/test_scheduler.py -n auto`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/harness/scheduler.py .camarones/lib/sessions.py .camarones/lib/serve.py \
  tests/test_portal_pipeline.py tests/test_agent_sessions.py
git commit -m "fix(serve): one probe of the run lock per pipeline read, and a lock being deleted reads as free"
```

### Task 2: A unit with a session open is not the run's (§4.1)

Today `plan.available()` puts `doing` units first and neither the autopilot nor the scheduler looks at sessions, so
either can start a unit the person has open in a window. With terminals on the canvas this gets common.

**Files:**
- Modify: `.camarones/lib/sessions.py` (`taken`), `.camarones/lib/plan.py` (`_autopilot`),
  `.camarones/lib/harness/scheduler.py` (`_run`)
- Test: `tests/test_autopilot.py`, `tests/test_scheduler.py`

**Interfaces:**
- Produces: `sessions.taken(units: list[dict]) -> list[str]` — the ids of `units` whose session record is live
  (`live(load(id))`), in their order. Both loops drop those ids from their queue. When the queue is empty and something
  was dropped, the stop line is the existing "what is left needs you — …" one, with one more reason:
  `f"{', '.join(taken)} open in a session (finish them there)"`. (Waiting for them instead of stopping is S3.)

- [ ] **Step 1: Write the failing tests** (the latent bug first)

In `tests/test_autopilot.py` (add `import os`):

```python
def test_a_unit_open_in_a_session_is_not_picked(kit, pilot):
    from lib import sessions
    first = next(u for u in kit.plan.available() if u["runner"] == "agent")
    kit.plan.set_status(first["id"], "doing")                   # doing: available() lists it first
    sessions.start(first["id"], "claude", None)
    sessions.update(first["id"], pid=os.getpid())               # its window is open
    pilot["run"](max_units=1)
    assert pilot["calls"] and first["id"] not in [uid for _, uid in pilot["calls"]]


def test_with_only_open_units_left_it_stops_and_names_them(kit, pilot, monkeypatch):
    from lib import sessions
    monkeypatch.setattr(sessions, "live", lambda rec: True)
    assert pilot["run"]() == 0 and pilot["calls"] == []
    assert any("needs you" in line and "open in a session" in line for line in pilot["echo"])
```

In `tests/test_scheduler.py` (add `import os`):

```python
def test_a_unit_open_in_a_session_is_not_the_runs(wired, fake):
    from lib import sessions
    fake["configure"](["fake"], sleep="0.2")
    wired.plan.set_status("setup", "done")
    wired.plan.set_status("discovery:api", "doing")
    sessions.start("discovery:api", "claude", None)
    sessions.update("discovery:api", pid=os.getpid())
    done, _ = run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=2)
    assert done == 2 and "discovery:api" not in spans(fake["entries"]())
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_autopilot.py tests/test_scheduler.py -k "open_in_a_session or only_open" -v`
Expected: FAIL — the open unit is picked; the stop line says "nothing ready".

- [ ] **Step 3: Implement `sessions.taken` and use it in both loops** (`plan._autopilot` right after `ready`,
  `scheduler._run` where it builds `queue`; both stop branches name the taken units).

- [ ] **Step 4: Run the autopilot and scheduler suites**

Run: `uv run pytest tests/test_autopilot.py tests/test_autopilot_events.py tests/test_scheduler.py -n auto`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/sessions.py .camarones/lib/plan.py .camarones/lib/harness/scheduler.py \
  tests/test_autopilot.py tests/test_scheduler.py
git commit -m "fix(plan): the autopilot and parallel runs leave alone a unit whose session is open"
```

### Task 3: PTYs in the project server

**Files:**
- Create: `.camarones/lib/terminals.py`, `tests/test_terminals.py`, `tests/fixtures/pty_echo.py`
- Modify: `.camarones/lib/common.py` (`kill_tree`), `.camarones/lib/appapi.py` (`cancel` uses `kill_tree`),
  `.camarones/camarones.py` (uv header), `pyproject.toml` and `uv.lock`, `docs/research/tooling-candidates.md` (K9)

**Interfaces:**
- Produces, in `lib/common.py`: `kill_tree(pid: int, sig: int | None = None) -> bool` — the process and what it
  started: POSIX `os.killpg(pid, sig or SIGTERM)` (the pid leads its own group: it was started with
  `start_new_session`), Windows `taskkill /PID <pid> /T /F` through `run` (`sig` ignored); `False` when it was already
  gone. `appapi.cancel` calls it and keeps its `pr.terminate()` fallback.
- Produces, in `lib/terminals.py`:
  - constants `MAX_LIVE = 8`, `RING = 256 * 1024`, `LOG_MAX = 5 * 1024 * 1024`, `LOG_SLACK = 1024 * 1024`,
    `KEEP = 50`, `INPUT_MAX = 256 * 1024`, `INPUT_WAIT = 5.0`, `COLS = (10, 500)`, `ROWS = (5, 200)`,
    `DIR = CACHE / "terminals"`; read from the module at each use, so tests can lower them
  - `class Unavailable(RuntimeError)` (no PTY on this machine: `pywinpty` does not import, or the PTY cannot be
    created), `class Ended(RuntimeError)` (input to a terminal that ended); an unknown id is a `KeyError`
  - `available() -> bool` — POSIX always; Windows when `winpty` imports (cached)
  - `spawn(argv: list[str], cwd: Path, *, kind: str, agent: str, unit: str | None = None,
    session: str | None = None, cols: int = 80, rows: int = 24, env: dict | None = None) -> dict` — the metadata
    `{id, kind, unit, agent, session, pid, cwd, started, ended: None, code: None, cols, rows, closed: False}`, also
    written to `DIR/<id>.json` (`common.save_json`)
  - `get(tid: str) -> dict`, `listing() -> list[dict]` (this server's terminals, live and ended, in start order)
  - `read(tid: str, offset: int) -> tuple[bytes, int]` — the bytes after `offset` still in the ring and the offset
    after them; an offset before the ring's start, or past the end (a client's stale offset), reads from the ring's
    start
  - `write(tid: str, data: str) -> None` — UTF-8; `Ended` once it ended; `TimeoutError` when the program does not take
    it within `INPUT_WAIT`
  - `resize(tid: str, cols: int, rows: int) -> dict` — `ValueError` outside `COLS` / `ROWS`
  - `close(tid: str) -> dict` — live: marks `closed`, `kill_tree(pid, SIGHUP)`, then `SIGKILL` if still alive after
    3 s (Windows: `kill_tree(pid)`); ended: forgets it (gone from `listing`, its files stay), answers
    `{**meta, "forgotten": True}`
  - `wait(seen: int, timeout: float) -> int` — blocks while nothing changed since generation `seen` (output, an end, a
    new terminal), at most `timeout` s; returns the current generation
  - `shutdown() -> None` — every live terminal: SIGHUP, SIGKILL for what is left after 2 s in all, ended; idempotent

**How it works** (what the signatures do not say):
- **POSIX:** `pty.openpty()`, the size set on it with `TIOCSWINSZ`, then
  `subprocess.Popen([sys.executable, "-c", CTTY, *argv], stdin=slave, stdout=slave, stderr=slave, cwd=…, env=…,
  start_new_session=True, close_fds=True)` and the server closes `slave` at once (holding it, the reader never sees the
  end). Popen gives no controlling terminal, and without one a resize sends no SIGWINCH and Ctrl+C no SIGINT, so a
  stdlib trampoline takes it and `exec`s the program (same pid, no `preexec_fn` in a threaded server):

  ```python
  CTTY = "import fcntl, os, sys, termios; fcntl.ioctl(0, termios.TIOCSCTTY, 0); os.execvp(sys.argv[1], sys.argv[1:])"
  ```

  `env` = `{**os.environ, **env, "TERM": "xterm-256color", "COLORTERM": "truecolor"}`.
- **Windows:** `winpty.PtyProcess.spawn(argv, cwd=str(cwd), env=…, dimensions=(rows, cols))`; reads come back as text,
  stored as UTF-8 bytes; the end is `EOFError`; size with `setwinsize(rows, cols)`. Check these calls against pywinpty
  3.0.5 before relying on them. A spawn that raises turns into `Unavailable`.
- **Reader thread** (daemon, one per PTY): POSIX `select` on the master every 0.5 s and `os.read(…, 65536)`; it ends on
  `b""` or `OSError` (EIO), or once the process has exited and 0.5 s pass with nothing to read (a grandchild can hold the
  PTY open). Each read goes to the ring (trimmed to `RING` from the front), to `DIR/<id>.log` (cut to its last `LOG_MAX`
  once it passes `LOG_MAX + LOG_SLACK`) and bumps the generation. At the end: `code` from the process, `ended` =
  `time.time()`, the `.json` rewritten, generation bumped.
- **Writes** to one terminal are serialised by its lock and run in a worker thread; the caller waits up to
  `INPUT_WAIT` for the lock and for the bytes to be taken, else `TimeoutError` (a write that gave up finishes on its
  own when the program reads again or ends). On POSIX a PTY's input buffer is a few KB, so a paste waits for the
  program to read.
- **Ids:** `t-<slug>-<n>`, slug = the unit id (or the kind, `update`) with every character outside
  `[A-Za-z0-9_.-]` turned into `_`; `n` = 1 + the highest `n` of that slug among `DIR`'s `.json` files and this
  server's terminals, so a new server never overwrites an earlier log.

- [ ] **Step 1: Write the test program** `tests/fixtures/pty_echo.py`:

```python
"""A small interactive program for the terminal tests: says it is ready and its size, echoes lines, answers `size`,
prints `bytes N` x's or a line with accents, exits 3 on `exit`. On a resize it says its new size (SIGWINCH, POSIX)."""
import os, signal, sys


def size():
    s = os.get_terminal_size(sys.stdout.fileno())
    return f"{s.columns}x{s.lines}"


if hasattr(signal, "SIGWINCH"):
    signal.signal(signal.SIGWINCH, lambda *_: print(f"winch {size()}", flush=True))
print(f"ready {size()}", flush=True)
for line in sys.stdin:
    word = line.strip()
    if word == "exit":
        sys.exit(3)
    if word == "size":
        print(f"size {size()}", flush=True)
    elif word.startswith("bytes "):
        print("x" * int(word[6:]), flush=True)
    elif word == "accents":
        print("año ─ fin", flush=True)
    else:
        print(f"echo {word} ({len(word)})", flush=True)
```

- [ ] **Step 2: Write the failing tests** in `tests/test_terminals.py`:

```python
"""PTYs in the project server (lib/terminals.py): a real terminal per session, on every OS (pywinpty on Windows)."""
from __future__ import annotations

import json, re, sys, time
from pathlib import Path
from types import SimpleNamespace

import pytest

ECHO = Path(__file__).parent / "fixtures" / "pty_echo.py"
ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\r")


def until(cond, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError("timed out")


def screen(t, tid) -> bytes:
    """What the program printed, without the terminal's escapes and carriage returns (ConPTY redraws with them)."""
    return ANSI.sub(b"", t.read(tid, 0)[0])


@pytest.fixture
def pty(kit):
    from lib import terminals

    def open_(argv=None, **kw):
        return terminals.spawn(argv or [sys.executable, str(ECHO)], kit.root, kind="update", agent="test", **kw)
    yield SimpleNamespace(t=terminals, open=open_)
    terminals.shutdown()


def test_a_program_runs_in_a_terminal_and_answers_what_is_typed(pty):
    m = pty.open(cols=90, rows=30)
    assert m["id"].startswith("t-update-") and m["pid"] and m["ended"] is None and (m["cols"], m["rows"]) == (90, 30)
    until(lambda: b"ready 90x30" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "hola\r")
    until(lambda: b"echo hola (4)" in screen(pty.t, m["id"]))
    assert pty.t.listing()[-1]["id"] == m["id"]


def test_a_resize_reaches_the_program(pty):
    m = pty.open()
    until(lambda: b"ready 80x24" in screen(pty.t, m["id"]))
    assert pty.t.resize(m["id"], 100, 40)["cols"] == 100
    pty.t.write(m["id"], "size\r")
    until(lambda: b"size 100x40" in screen(pty.t, m["id"]))
    with pytest.raises(ValueError):
        pty.t.resize(m["id"], 9, 40)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGWINCH is POSIX; ConPTY resizes the console itself")
def test_the_terminal_is_the_programs_own_so_a_resize_signals_it(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.resize(m["id"], 120, 33)
    until(lambda: b"winch 120x33" in screen(pty.t, m["id"]))


def test_the_end_of_a_program_is_kept_with_its_code(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "exit\r")
    until(lambda: pty.t.get(m["id"])["ended"])
    assert pty.t.get(m["id"])["code"] == 3
    saved = json.loads((pty.t.DIR / f"{m['id']}.json").read_text(encoding="utf-8"))
    assert (saved["code"], saved["unit"], saved["kind"]) == (3, None, "update")
    with pytest.raises(pty.t.Ended):
        pty.t.write(m["id"], "hola\r")


def test_output_is_kept_in_a_ring_and_a_log_both_bounded(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "RING", 16 * 1024)
    monkeypatch.setattr(pty.t, "LOG_MAX", 64 * 1024)
    monkeypatch.setattr(pty.t, "LOG_SLACK", 16 * 1024)
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    for _ in range(10):
        pty.t.write(m["id"], "bytes 20000\r")
    pty.t.write(m["id"], "hola\r")
    until(lambda: b"echo hola (4)" in screen(pty.t, m["id"]))      # everything before it is out too
    data, end = pty.t.read(m["id"], 0)
    assert len(data) <= 16 * 1024 and end > 200_000
    assert pty.t.read(m["id"], end) == (b"", end)
    assert pty.t.read(m["id"], end + 999)[0] == data                   # a stale offset reads from the ring's start
    log = (pty.t.DIR / f"{m['id']}.log").read_bytes()
    assert 64 * 1024 <= len(log) <= 80 * 1024 and log.endswith(data)


def test_accents_are_kept_as_the_program_wrote_them(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "accents\r")
    until(lambda: "año ─ fin".encode() in screen(pty.t, m["id"]))


def test_a_big_paste_is_written_whole(pty):
    m = pty.open()
    until(lambda: b"ready" in screen(pty.t, m["id"]))
    pty.t.write(m["id"], "a\r" * 20_000 + "end\r")                     # far more than a PTY's input buffer
    until(lambda: b"echo end (3)" in screen(pty.t, m["id"]), timeout=60)


@pytest.mark.skipif(sys.platform == "win32", reason="ConPTY keeps its own input buffer")
def test_input_to_a_program_that_does_not_read_gives_up(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "INPUT_WAIT", 0.5)
    m = pty.open([sys.executable, "-c", "import time; print('asleep', flush=True); time.sleep(60)"])
    until(lambda: b"asleep" in screen(pty.t, m["id"]))
    with pytest.raises(TimeoutError):
        pty.t.write(m["id"], "y" * 200_000)


def test_closing_kills_the_program_and_what_it_started_then_forgets_it(pty):
    from lib.harness.locks import pid_alive
    m = pty.open([sys.executable, "-c", "import subprocess, sys, time; "
                  "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                  "print('child', p.pid, flush=True); time.sleep(60)"])
    until(lambda: re.search(rb"child (\d+)", screen(pty.t, m["id"])))
    child = int(re.search(rb"child (\d+)", screen(pty.t, m["id"])).group(1))
    pty.t.close(m["id"])
    until(lambda: pty.t.get(m["id"])["ended"])
    assert pty.t.get(m["id"])["closed"] is True
    until(lambda: not pid_alive(child))
    assert pty.t.close(m["id"])["forgotten"] is True
    assert m["id"] not in [x["id"] for x in pty.t.listing()]


def test_shutdown_ends_every_terminal(pty):
    from lib.harness.locks import pid_alive
    a, b = pty.open(), pty.open()
    pty.t.shutdown()
    assert all(pty.t.get(x["id"])["ended"] for x in (a, b))
    until(lambda: not pid_alive(a["pid"]) and not pid_alive(b["pid"]))
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_terminals.py -v`
Expected: FAIL — `No module named 'lib.terminals'`.

- [ ] **Step 4: Add the dependency.** `camarones.py`'s header and `pyproject.toml`'s `dev` group gain
  `"pywinpty==3.0.5; sys_platform == 'win32'"`; then `uv lock`. Add row **K9** to
  `docs/research/tooling-candidates.md` §K: pywinpty 3.0.5 (MIT), ConPTY terminals for the app's sessions on Windows;
  the §2.4 check — (1) no overlap, the kit had no PTY on Windows and stdlib `pty` covers POSIX; (2) wheels for CPython
  3.10–3.14 on win_amd64 and win_arm64, installed by uv from the script header, no admin rights; (3) one module,
  optional: without it sessions open in a window as before; (4) local, MIT. `node-pty` in Electron was the alternative
  (a native build per Electron ABI × OS).

- [ ] **Step 5: Implement `common.kill_tree` (and `appapi.cancel` on it) and `lib/terminals.py`** as in Interfaces and
  How it works, with a module docstring in the style of `sessions.py`: where PTYs live, why the trampoline, what the ring
  and the log are for.

- [ ] **Step 6: Run the terminal tests, then the app API's**

Run: `uv run pytest tests/test_terminals.py tests/test_app_api.py -n auto`
Expected: PASS (on Windows the two POSIX-only tests skip).

- [ ] **Step 7: Commit**

```bash
git add .camarones/lib/terminals.py .camarones/lib/common.py .camarones/lib/appapi.py .camarones/camarones.py \
  pyproject.toml uv.lock docs/research/tooling-candidates.md tests/test_terminals.py tests/fixtures/pty_echo.py
git commit -m "feat(terminals): real terminals in the project server — stdlib pty on POSIX, ConPTY via pywinpty on Windows"
```

### Task 4: Terminals and the plan: the limit, one per unit, records closed, old files pruned

**Files:**
- Modify: `.camarones/lib/terminals.py`, `.camarones/lib/sessions.py` (`wrap`), `.camarones/lib/session_run.py`
- Test: `tests/test_terminals.py`, `tests/test_agent_sessions.py`

**Interfaces:**
- Consumes: `spawn`, `close`, `shutdown` (Task 3); `sessions.load`, `sessions.update` (today's).
- Produces:
  - `terminals.Limit(RuntimeError)`; `terminals.room() -> None` raises it while `MAX_LIVE` terminals are live; `spawn`
    calls it first.
  - `terminals.find(kind: str, unit: str | None = None) -> dict | None` — the live terminal of that kind and unit.
  - When a `kind="unit"` terminal ends (by itself, closed, or at shutdown), its unit's session record gets `ended` and
    `code`, unless the wrapper already wrote them or the record now belongs to another session (its `pid` is not this
    terminal's): a session killed with its terminal reads as paused, as a closed window does.
  - After the first `spawn` of a server writes its metadata, `DIR` keeps the newest `KEEP` `.json` files (by mtime),
    their `.log`s, and every live terminal's.
  - `sessions.wrap(record: Path | None, cmd: list[str]) -> list[str]` — `None` puts `-` where the record goes;
    `session_run.main(["-", "--", *cmd])` runs the command and writes no record (the docs update: a terminal, no record).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_terminals.py` (add `import os`):

```python
def test_the_ninth_terminal_is_refused(pty, monkeypatch):
    assert pty.t.MAX_LIVE == 8
    monkeypatch.setattr(pty.t, "MAX_LIVE", 2)
    a, _ = pty.open(), pty.open()
    with pytest.raises(pty.t.Limit):
        pty.open()
    pty.t.close(a["id"])
    until(lambda: pty.t.get(a["id"])["ended"])
    pty.open()                                                         # room again


def test_a_unit_terminal_closes_its_session_record(pty, kit):
    from lib import sessions
    rec = sessions.start("discovery:api", "claude", None)
    m = pty.t.spawn(sessions.wrap(rec, [sys.executable, str(ECHO)]), kit.root, kind="unit", unit="discovery:api",
                    agent="claude")
    assert m["id"].startswith("t-discovery_api-")
    until(lambda: sessions.running(sessions.load("discovery:api")))      # inside session_run, as in a window
    assert pty.t.find("unit", "discovery:api")["id"] == m["id"]
    pty.t.close(m["id"])
    until(lambda: (sessions.load("discovery:api") or {}).get("ended"))
    assert not sessions.live(sessions.load("discovery:api")) and pty.t.find("unit", "discovery:api") is None


def test_a_record_taken_by_a_newer_session_is_left_alone(pty, kit):
    from lib import sessions
    rec = sessions.start("discovery:api", "claude", None)
    m = pty.t.spawn(sessions.wrap(rec, [sys.executable, str(ECHO)]), kit.root, kind="unit", unit="discovery:api",
                    agent="claude")
    until(lambda: sessions.running(sessions.load("discovery:api")))
    sessions.start("discovery:api", "codex", None)                       # a new session took the record
    pty.t.close(m["id"])
    until(lambda: pty.t.get(m["id"])["ended"])
    assert "ended" not in sessions.load("discovery:api")


def test_old_terminal_files_are_pruned_when_the_first_one_opens(pty, monkeypatch):
    monkeypatch.setattr(pty.t, "KEEP", 3)
    pty.t.DIR.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        for ext in (".json", ".log"):
            f = pty.t.DIR / f"t-old-{i}{ext}"
            f.write_text("{}", encoding="utf-8")
            os.utime(f, (1000 + i, 1000 + i))
    m = pty.open()
    left = sorted(p.name for p in pty.t.DIR.glob("*.json"))
    assert left == sorted([f"{m['id']}.json", "t-old-3.json", "t-old-4.json"])
    assert not (pty.t.DIR / "t-old-0.log").exists()
```

Append to `tests/test_agent_sessions.py`:

```python
def test_the_wrapper_can_run_without_a_record(monkeypatch, tmp_path):
    from lib import session_run, sessions
    monkeypatch.chdir(tmp_path)
    assert sessions.wrap(None, ["agent", "x"])[-4:] == ["-", "--", "agent", "x"]
    assert session_run.main(["-", "--", sys.executable, "-c", "raise SystemExit(4)"]) == 4
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_terminals.py tests/test_agent_sessions.py -k "ninth or record or pruned or without_a_record" -v`
Expected: FAIL — `Limit` and `find` missing; the record has no `ended`; nothing pruned; `wrap(None, …)` breaks.

- [ ] **Step 3: Implement** `room`, `find`, the record's end, the prune, `wrap(None, …)` and `session_run`'s `-` (its
  docstring and usage line name it).

- [ ] **Step 4: Run the terminal and session suites**

Run: `uv run pytest tests/test_terminals.py tests/test_agent_sessions.py tests/test_agents.py -n auto`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/terminals.py .camarones/lib/sessions.py .camarones/lib/session_run.py \
  tests/test_terminals.py tests/test_agent_sessions.py
git commit -m "feat(terminals): at most 8, one per unit, a unit's record closed with its terminal, old files pruned"
```

### Task 5: Sessions opened by hand open on the canvas — the `sessions` setting

**Files:**
- Modify: `.camarones/lib/machine.py`, `.camarones/lib/agents.py`, `.camarones/camarones.py` (the `config` help line)
- Create: `tests/test_agent_terminals.py`
- Test: `tests/test_machine.py`, `tests/test_launch_argv.py`

**Interfaces:**
- Consumes: `terminals.available`, `spawn`, `room`, `find`, `Limit`, `Unavailable` (Tasks 3–4);
  `sessions.wrap(None, …)` (Task 4).
- Produces:
  - `machine.SESSIONS = ("canvas", "window")`; `DEFAULTS["sessions"] = "canvas"`; `set_setting("sessions", v)` refuses
    anything else with `sessions: one of canvas, window`. `machine.panel()` adds `"terminals": terminals.available()`
    and `"sessions": list(SESSIONS)`. The `config` line of `camarones.py`'s help names `sessions (canvas|window)`.
  - `agents.AlreadyOpen(ValueError)` with `.terminal: str | None` (the open terminal's id, when it is one).
  - `agents.launch_unit(uid, agent, lang="es", mode="new", where="window", size=(80, 24)) -> dict` and
    `agents.launch_update(agent, lang="es", where="window", size=(80, 24)) -> dict` — today's result keys plus
    `where: "canvas" | "window"`, `terminal: <metadata>` when it opened on the canvas, and `fallback: "no-pty"` when
    the canvas was asked for and a window opened. The wizard never passes `where`: it keeps opening windows.
  - On the canvas, `_open` spawns `sessions.wrap(record, cmd)` (`wrap(None, cmd)` for the update) in `WORKSPACE` with
    `kind="unit"` / `"update"`, `unit`, `agent`, the Claude `session` and `size`. `Unavailable` → today's window.
  - Under one module lock, before `plan.set_status` or any record is written: a unit whose record is running or that
    has a live terminal (`terminals.find("unit", uid)`), or a second live update, raises `AlreadyOpen`; on the canvas,
    `terminals.room()` raises `Limit`. The lock keeps two quick clicks from both passing.

- [ ] **Step 1: Write the failing tests**

`tests/test_agent_terminals.py`:

```python
"""Sessions opened by hand on the canvas (lib/agents.py with where="canvas"): the same agent inside session_run.py,
now in a terminal the project server holds instead of a window."""
from __future__ import annotations

import sys

import pytest

from test_agents import ready_agent_unit, term  # noqa: F401  (fixture)
from test_terminals import ECHO, until


@pytest.fixture
def canvas(wired, term, monkeypatch):                                    # noqa: F811
    from lib import terminals
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(ECHO)], req.cwd, req.env))
    yield term
    terminals.shutdown()


def test_a_unit_opens_as_a_terminal_on_the_canvas(wired, canvas):
    from lib import sessions
    u = ready_agent_unit(wired)
    r = canvas["agents"].launch_unit(u["id"], "claude", lang="en", where="canvas", size=(100, 30))
    assert r["where"] == "canvas" and canvas["cmds"] == []
    t = r["terminal"]
    assert (t["kind"], t["unit"], t["agent"], t["cols"], t["rows"]) == ("unit", u["id"], "claude", 100, 30)
    assert wired.plan.get(wired.plan.load(), u["id"])["status"] == "doing"
    until(lambda: sessions.running(sessions.load(u["id"])))


def test_the_docs_update_opens_as_a_loose_terminal_with_no_record(wired, canvas):
    from lib import sessions
    r = canvas["agents"].launch_update("claude", where="canvas")
    assert (r["terminal"]["kind"], r["terminal"]["unit"]) == ("update", None)
    assert sessions.load("update") is None
    with pytest.raises(canvas["agents"].AlreadyOpen) as e:
        canvas["agents"].launch_update("claude", where="canvas")
    assert e.value.terminal == r["terminal"]["id"]


def test_a_unit_open_on_the_canvas_is_not_opened_again(wired, canvas):
    u = ready_agent_unit(wired)
    first = canvas["agents"].launch_unit(u["id"], "claude", where="canvas")["terminal"]["id"]
    with pytest.raises(canvas["agents"].AlreadyOpen) as e:
        canvas["agents"].launch_unit(u["id"], "claude", mode="continue", where="canvas")
    assert e.value.terminal == first


def test_the_ninth_terminal_is_refused_before_the_unit_moves(wired, canvas, monkeypatch):
    from lib import sessions, terminals
    monkeypatch.setattr(terminals, "MAX_LIVE", 1)
    canvas["agents"].launch_update("claude", where="canvas")
    u = ready_agent_unit(wired)
    with pytest.raises(terminals.Limit):
        canvas["agents"].launch_unit(u["id"], "claude", where="canvas")
    assert wired.plan.get(wired.plan.load(), u["id"])["status"] == "todo" and sessions.load(u["id"]) is None


def test_without_a_terminal_here_the_canvas_falls_back_to_a_window(wired, canvas, monkeypatch):
    from lib import terminals
    monkeypatch.setattr(terminals, "available", lambda: False)
    r = canvas["agents"].launch_unit(ready_agent_unit(wired)["id"], "claude", where="canvas")
    assert (r["where"], r["fallback"]) == ("window", "no-pty") and len(canvas["cmds"]) == 1


def test_a_window_is_still_a_window(wired, canvas):
    from lib import terminals
    r = canvas["agents"].launch_unit(ready_agent_unit(wired)["id"], "claude")
    assert r["where"] == "window" and len(canvas["cmds"]) == 1 and terminals.listing() == []
```

In `tests/test_machine.py`: the expected dict of `test_config_reads_and_writes_the_wizard_settings` gains
`"sessions": "canvas"`, and the test sets `sessions window` and reads it back; `("sessions", "tab")` joins the
parametrize list of `test_config_refuses_what_the_wizard_would_not_offer`.

In `tests/test_launch_argv.py`:

```python
def test_the_wizard_opens_a_window_whatever_the_sessions_setting(launched):
    assert launched["make"](["claude"], sessions="canvas").launch_agent("prompt") == "bg"
    assert len(launched["cmds"]) == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_agent_terminals.py tests/test_machine.py tests/test_launch_argv.py -v`
Expected: FAIL — `launch_unit() got an unexpected keyword argument 'where'`; the config dict has no `sessions`. (The
wizard test passes already: it pins what must not change.)

- [ ] **Step 3: Implement the setting and `where`** as in Interfaces.

- [ ] **Step 4: Run the agent, machine and launch suites**

Run: `uv run pytest tests/test_agent_terminals.py tests/test_agents.py tests/test_agent_sessions.py tests/test_machine.py tests/test_launch_argv.py -n auto`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/machine.py .camarones/lib/agents.py .camarones/camarones.py \
  tests/test_agent_terminals.py tests/test_machine.py tests/test_launch_argv.py
git commit -m "feat(agents): sessions opened by hand open as terminals on the canvas, or in a window (sessions setting)"
```

### Task 6: The terminal routes and the single stream

**Files:**
- Modify: `.camarones/lib/serve.py`
- Create: `tests/test_terminals_api.py`

**Interfaces:**
- Consumes: Tasks 3–5.
- Produces (all under `/api/app/`, so the portal token and no token get 403 as today):
  - `POST /api/app/terminals` `{unit: <uid> | "update", agent, lang?, mode?, cols?, rows?}` — `app_session(b) ->
    tuple[dict, int]`: checks every field (`unit`, `agent` text; `mode` new / continue / restart; `cols`, `rows`
    integers, not booleans, within `COLS` / `ROWS`) → 400; `where` is `machine.settings()["sessions"]`;
    `AlreadyOpen` → 409 `{error, terminal}`; `Limit` → 409 `{error: f"{MAX_LIVE} terminals are open: close one
    first", limit: MAX_LIVE}`. `POST /api/app/agent` is the same handler (its old name).
  - `GET /api/app/terminals` → `{terminals: listing(), available: bool, limit: MAX_LIVE}`.
  - `POST /api/app/terminals/<id>/input` `{data}` → `{ok: true}`; `/resize` `{cols, rows}` → metadata; `/close` →
    `close()`'s answer. `data` not text or over `INPUT_MAX` → 400; an unknown id → 404; `Ended` or `TimeoutError` →
    409. Ids match `t-[\w.-]+-\d+`.
  - `GET /api/app/terminals/stream?from=<id>:<offset>,…` — `Handler.stream_terminals(q)`: a `from` piece that is not
    `<id>:<n>` → 400 before the stream starts; then for every terminal of `listing()`, from its offset (0 when not
    named): `id: <t>:<o>` + `data: {"t", "d", "o"}` per 64 KB at most; after the last bytes of an ended one, once per
    stream, `data: {"t", "end": <code>, "o"}`; terminals opened later join; `: keep-alive` every 15 s; it waits with
    `terminals.wait`, and ends when the client goes.
  - `api_pipeline`: every unit row gains `terminal` — the id of the unit's live terminal in this server, else `None`.
  - `run_server`: `atexit.register(terminals.shutdown)` and SIGTERM → `sys.exit(0)` (it is the main thread), so the
    app's stop kills the server's terminals first. On Windows the app's `taskkill /T /F` takes them with the server;
    their records keep a dead pid and read as paused.

- [ ] **Step 1: Write the failing tests** in `tests/test_terminals_api.py`:

```python
"""The terminals over HTTP (lib/serve.py): app token only, and one server-sent stream for every terminal."""
from __future__ import annotations

import base64, json, os, signal, subprocess, sys, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from test_agents import ready_agent_unit, term  # noqa: F401  (fixture)
from test_terminals import ECHO, until

TOKEN, PORTAL = "app-tok", "portal-tok"
ROUTES = [("GET", "/api/app/terminals"), ("GET", "/api/app/terminals/stream"), ("POST", "/api/app/terminals"),
          ("POST", "/api/app/terminals/t-x-1/input"), ("POST", "/api/app/terminals/t-x-1/resize"),
          ("POST", "/api/app/terminals/t-x-1/close")]


@pytest.fixture
def app(wired, term, monkeypatch):                                       # noqa: F811
    from lib import terminals
    from lib.adapters.runners.claude import Claude
    from lib.harness.ports import Invocation
    monkeypatch.setattr(Claude, "build", lambda self, req: Invocation([sys.executable, str(ECHO)], req.cwd, req.env))
    monkeypatch.setattr(wired.serve, "APP_TOKEN", TOKEN)
    monkeypatch.setattr(wired.serve, "PORTAL_TOKEN", PORTAL)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{srv.server_address[1]}", term=term, t=terminals)
    srv.shutdown()
    terminals.shutdown()


def call(url, body=None, token=TOKEN) -> tuple[int, dict]:
    """As `call` in tests/test_machine.py: GET without a body, POST with one, X-Camarones always."""


def sse(url, until_, timeout=20) -> list[tuple[str, dict]]:
    """The stream's messages as (id, data), read line by line with the app token, until `until_(messages)` holds;
    AssertionError when the stream ends first. `timeout` is the socket's: the stream sends a keep-alive every 15 s."""


def out(msgs, tid) -> bytes:
    return b"".join(base64.b64decode(d["d"]) for _, d in msgs if d["t"] == tid and "d" in d)


def open_unit(app, wired, **extra):
    u = ready_agent_unit(wired)
    code, r = call(app.url + "/api/app/terminals", {"unit": u["id"], "agent": "claude", **extra})
    assert code == 200, r
    return u, r


@pytest.mark.parametrize("method,path", ROUTES)
def test_terminals_answer_only_the_app(app, method, path):
    for token in (None, PORTAL):
        assert call(app.url + path, {} if method == "POST" else None, token=token)[0] == 403


def test_a_unit_opens_on_the_canvas_and_answers_through_the_stream(app, wired):
    u, r = open_unit(app, wired, cols=90, rows=30)
    tid = r["terminal"]["id"]
    assert r["where"] == "canvas" and app.term["cmds"] == []
    assert call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "hola\r"}) == (200, {"ok": True})
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: b"echo hola (4)" in out(m, tid))
    assert all(i == f"{d['t']}:{d['o']}" for i, d in msgs if "d" in d)
    assert call(app.url + "/api/app/terminals")[1]["terminals"][0]["id"] == tid
    row = next(x for x in call(app.url + "/api/pipeline")[1]["units"] if x["id"] == u["id"])
    assert row["terminal"] == tid and row["session"]["live"] is True


def test_the_stream_replays_each_terminal_from_its_offset_in_base64(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "accents\r"})
    until(lambda: "año".encode() in app.t.read(tid, 0)[0])
    data, end = app.t.read(tid, 0)
    cut = data.index("ñ".encode()) + 1                                  # inside the ñ
    msgs = sse(f"{app.url}/api/app/terminals/stream?from={tid}:{cut}", lambda m: out(m, tid).endswith(data[-8:]))
    assert out(msgs, tid)[: end - cut] == data[cut:]


def test_a_terminal_opened_while_streaming_joins_the_stream(app, wired):
    got = {}
    threading.Thread(target=lambda: got.setdefault("m", sse(app.url + "/api/app/terminals/stream",
                                                            lambda m: any(d["t"].startswith("t-update-") for _, d in m))),
                     daemon=True).start()
    call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    until(lambda: "m" in got)


def test_an_ended_terminal_says_its_code_after_its_last_bytes(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "exit\r"})
    msgs = sse(app.url + "/api/app/terminals/stream", lambda m: any(d.get("end") is not None for _, d in m))
    mine = [d for _, d in msgs if d["t"] == tid]
    assert mine[-1]["end"] == 3 and all("d" in d for d in mine[:-1])
    assert call(f"{app.url}/api/app/terminals/{tid}/input", {"data": "x"})[0] == 409


def test_bad_input_is_a_400_and_an_unknown_terminal_a_404(app, wired):
    _, r = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    tid = r["terminal"]["id"]
    for path, body in [("resize", {"cols": 9, "rows": 30}), ("resize", {"cols": True, "rows": 30}),
                       ("input", {"data": 5}), ("input", {"data": "y" * (256 * 1024 + 1)})]:
        assert call(f"{app.url}/api/app/terminals/{tid}/{path}", body)[0] == 400
    assert call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude", "rows": "x"})[0] == 400
    assert call(app.url + "/api/app/terminals/t-nope-1/input", {"data": "x"})[0] == 404
    assert call(app.url + "/api/app/terminals/stream?from=garbage")[0] == 400


def test_opening_twice_or_a_ninth_is_a_409_that_says_why(app, wired, monkeypatch):
    u, r = open_unit(app, wired)
    code, body = call(app.url + "/api/app/terminals", {"unit": u["id"], "agent": "claude"})
    assert code == 409 and body["terminal"] == r["terminal"]["id"]
    monkeypatch.setattr(app.t, "MAX_LIVE", 1)
    code, body = call(app.url + "/api/app/terminals", {"unit": "update", "agent": "claude"})
    assert code == 409 and body["limit"] == 1


def test_with_the_window_setting_it_opens_a_window_and_the_old_route_too(app, wired):
    from lib import machine
    machine.set_setting("sessions", "window")
    code, r = call(app.url + "/api/app/agent", {"unit": "update", "agent": "claude"})
    assert code == 200 and r["where"] == "window" and len(app.term["cmds"]) == 1 and app.t.listing() == []


@pytest.mark.skipif(sys.platform == "win32", reason="the app stops the server with taskkill /T /F, which takes the tree")
def test_the_servers_exit_takes_its_terminals_with_it(wired, tmp_path):
    from lib import sessions
    from lib.harness.locks import pid_alive
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    bin_ = tmp_path / "bin"                    # first on PATH; HOME is a temp folder, so no real agent comes before it
    bin_.mkdir()
    fake = bin_ / "claude"
    fake.write_text(f"#!{sys.executable}\nimport runpy; runpy.run_path({str(ECHO)!r}, run_name='__main__')\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root), "CAMARONES_APP_TOKEN": TOKEN,
           "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}"}
    srv = subprocess.Popen([sys.executable, str(wired.kit_dir / "camarones.py"), "up", "--foreground", "--port", "0"],
                           env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        port = json.loads(srv.stdout.readline())["port"]
        uid = ready_agent_unit(wired)["id"]
        code, r = call(f"http://127.0.0.1:{port}/api/app/terminals", {"unit": uid, "agent": "claude"})
        assert code == 200, r
        until(lambda: sessions.running(sessions.load(uid)))
        srv.send_signal(signal.SIGTERM)
        srv.wait(timeout=20)
    finally:
        srv.kill()
    until(lambda: not pid_alive(r["terminal"]["pid"]))
    assert sessions.load(uid).get("ended") and not sessions.live(sessions.load(uid))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_terminals_api.py -v`
Expected: FAIL — 404 on every `/api/app/terminals` route; `/api/app/agent` has no `where`.

- [ ] **Step 3: Implement the routes, `app_session`, `stream_terminals`, the pipeline's `terminal` and the exit
  hooks** as in Interfaces. Catch `AlreadyOpen`, `Limit`, `Ended` and `TimeoutError` before the handler's generic
  `ValueError` / `RuntimeError` → 400.

- [ ] **Step 4: Run the server suites**

Run: `uv run pytest tests/test_terminals_api.py tests/test_app_api.py tests/test_portal_pipeline.py tests/test_machine.py -n auto`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/serve.py tests/test_terminals_api.py
git commit -m "feat(serve): terminal routes for the app and one server-sent stream for every terminal"
```

### Task 7: The renderer's terminal helpers: the stream, bytes, which terminals show, where a session lands

**Files:**
- Create: `.camarones/desktop/renderer/src/terminals.js`, `.camarones/desktop/renderer/src/terminals.test.js`
- Modify: `.camarones/desktop/renderer/src/plan.js`, `plan.test.js`, `nav.js`, `nav.test.js`

**Interfaces:**
- Consumes: `server(token).stream` and `post` (S1; a refusal throws with `status` and `data`); `FOLD_MS` from
  `canvas.js`; `Terminal` = the server's metadata (Task 3), `started` / `ended` in epoch seconds.
- Produces:
  - `terminals.js`: `STREAM = 'app/terminals/stream'`; `streamFrom(offsets: {[t]: number}) -> string | undefined`
    (`t-a-1:120,t-b-2:0`, `undefined` when empty); `bytes(b64: string) -> Uint8Array`;
    `followTerminals(srv, onEvent, { signal, offsets: () => object, retry = 2000, sleep }) -> Promise<void>` — streams
    `STREAM` from `streamFrom(offsets())`; when it ends or breaks, waits `retry` and opens it again from the offsets
    reached; a refusal with `status` 403 or 404, or an abort, ends it; `shown(terms, now) -> { units: Map<uid,
    Terminal>, loose: Terminal[] }` — closed ones never; per unit the newest by `started`; kept while live, for
    `FOLD_MS` after a code-0 end, and after any other end until it is removed; `loose` = `kind !== 'unit'` by the same
    rule, in start order; `elapsed(term, now) -> number` (seconds).
  - `plan.js`: `openSession(srv, body, go = (h) => { location.hash = h }) -> Promise<object>` — POSTs `app/terminals`;
    a result with `terminal` → `go('#/plan?term=' + id)`; a refusal with `data.terminal` → the same `go`, and resolves
    `{ already: true, terminal: { id } }`; any other refusal throws. `sessionNote(res, label) -> { key, vars }`:
    `pty.already` · `next.onCanvas` · `next.noPty` (window with `fallback`) · `next.opened`, with
    `vars.agent = openedWith(label, res)`. `unitAction` for a live session → `{ kind: 'live', term: u.terminal ?? null }`.
  - `nav.js`: `termOf(hash) -> string | null` — the `term` of `#/plan?term=<id>` when it matches
    `/^t-[\w.-]+-\d+$/`.

- [ ] **Step 1: Write the failing tests**

`terminals.test.js`:

```js
import { expect, test } from 'vitest'
import { bytes, elapsed, followTerminals, shown, streamFrom } from './terminals.js'

const b64 = (u8) => btoa(String.fromCharCode(...u8))

test('the stream asks for every terminal from where it got to', () => {
  expect(streamFrom({})).toBe(undefined)
  expect(streamFrom({ 't-a-1': 120, 't-update-2': 0 })).toBe('t-a-1:120,t-update-2:0')
})

test('chunks decode to the very bytes the program wrote, a character split between them included', () => {
  const all = new TextEncoder().encode('año ─ fin')
  for (let cut = 1; cut < all.length; cut++) {
    const joined = new Uint8Array([...bytes(b64(all.slice(0, cut))), ...bytes(b64(all.slice(cut)))])
    expect(new TextDecoder().decode(joined)).toBe('año ─ fin')
  }
})

test('a dropped terminal stream opens again from the offsets it reached', async () => {
  const calls = []
  const offsets = {}
  const ac = new AbortController()
  const srv = { stream: async (name, onEvent, opts) => {
    calls.push([name, opts.from])
    if (calls.length === 1) { onEvent({ t: 't-a-1', d: 'aGk=', o: 2 }); return { id: 't-a-1:2' } }
    ac.abort(); return { id: null } } }
  await followTerminals(srv, (ev) => { offsets[ev.t] = ev.o }, { signal: ac.signal, offsets: () => offsets, sleep: async () => {} })
  expect(calls).toEqual([['app/terminals/stream', undefined], ['app/terminals/stream', 't-a-1:2']])
})

test('a refused terminal stream stops following', async () => {
  let n = 0
  const srv = { stream: async () => { n += 1; throw Object.assign(new Error('no'), { status: 403 }) } }
  await followTerminals(srv, () => {}, { offsets: () => ({}), sleep: async () => {} })
  expect(n).toBe(1)
})

test('which terminals show: live, a clean end for a moment, a failed end until removed, never a closed one', () => {
  const T = (id, f = {}) => ({ id, kind: 'unit', unit: 'a', started: 100, ended: null, code: null, closed: false, ...f })
  const now = 200_000
  expect(shown([T('t-a-1', { started: 50, ended: 60, code: 1 }), T('t-a-2')], now).units.get('a').id).toBe('t-a-2')
  expect(shown([T('t-a-1', { ended: 199, code: 0 })], now).units.has('a')).toBe(true)
  expect(shown([T('t-a-1', { ended: 190, code: 0 })], now).units.has('a')).toBe(false)
  expect(shown([T('t-a-1', { ended: 10, code: 127 })], now).units.has('a')).toBe(true)
  expect(shown([T('t-a-1', { ended: 199, code: -1, closed: true })], now).units.size).toBe(0)
  const up = T('t-update-1', { kind: 'update', unit: null })
  expect(shown([up], now).loose).toEqual([up])
  expect(elapsed(T('t-a-1', { started: 100 }), 160_000)).toBe(60)
  expect(elapsed(T('t-a-1', { started: 100, ended: 130 }), 999_000)).toBe(30)
})
```

`plan.test.js` (append; `openSession` and `sessionNote` join the file's import from `./plan.js`, which has
`unitAction` already — every import of these test files sits at the top):

```js
test('a session opened on the canvas takes you to its terminal', async () => {
  const went = []
  const srv = { post: async (name, body) => ({ where: 'canvas', terminal: { id: 't-a-1' }, model: 'opus', name, body }) }
  const res = await openSession(srv, { unit: 'a', agent: 'claude' }, (h) => went.push(h))
  expect([res.name, res.body.unit]).toEqual(['app/terminals', 'a'])
  expect(went).toEqual(['#/plan?term=t-a-1'])
  expect(sessionNote(res, 'Claude Code')).toEqual({ key: 'next.onCanvas', vars: { agent: 'Claude Code (opus)' } })
})

test('an already open session takes you to its terminal', async () => {
  const went = []
  const srv = { post: async () => { throw Object.assign(new Error('open'), { status: 409, data: { terminal: 't-a-1' } }) } }
  const res = await openSession(srv, { unit: 'a' }, (h) => went.push(h))
  expect(went).toEqual(['#/plan?term=t-a-1'])
  expect(sessionNote(res, 'x').key).toBe('pty.already')
  const full = { post: async () => { throw Object.assign(new Error('8 terminals are open'), { status: 409, data: { limit: 8 } }) } }
  await expect(openSession(full, {}, () => {})).rejects.toThrow('8 terminals are open')
})

test('a window, and a window instead of the canvas, say which', () => {
  expect(sessionNote({ where: 'window' }, 'Codex').key).toBe('next.opened')
  expect(sessionNote({ where: 'window', fallback: 'no-pty' }, 'Codex').key).toBe('next.noPty')
})

test('a unit open on the canvas offers its terminal', () => {
  const u = { id: 'a', status: 'doing', runner: 'agent', session: { live: true }, terminal: 't-a-1' }
  expect(unitAction(u)).toEqual({ kind: 'live', term: 't-a-1' })
  expect(unitAction({ ...u, terminal: null })).toEqual({ kind: 'live', term: null })
})
```

`nav.test.js` (append; `termOf` joins the file's import from `./nav.js`):

```js
test('an address can ask the Plan for one terminal', () => {
  expect(termOf('#/plan?term=t-explain_api-2')).toBe('t-explain_api-2')
  expect(termOf('#/plan')).toBe(null)
  expect(termOf('#/plan?term=../x')).toBe(null)
  expect(termOf('#/board?term=t-a-1')).toBe(null)
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/terminals.test.js src/plan.test.js src/nav.test.js)`
Expected: FAIL — `./terminals.js` not found; `openSession`, `sessionNote`, `termOf` not exported.

- [ ] **Step 3: Implement the helpers** in `terminals.js` (header comment: what the canvas's terminals are and that
  these helpers are pure, the stream aside), `plan.js` and `nav.js`.

- [ ] **Step 4: Run them to verify they pass**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/terminals.test.js src/plan.test.js src/nav.test.js)`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/terminals.js .camarones/desktop/renderer/src/terminals.test.js \
  .camarones/desktop/renderer/src/plan.js .camarones/desktop/renderer/src/plan.test.js \
  .camarones/desktop/renderer/src/nav.js .camarones/desktop/renderer/src/nav.test.js
git commit -m "feat(desktop): the canvas's terminal stream, which terminals show, and where an opened session lands"
```

### Task 8: xterm on a node

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/Terms.jsx`, `.camarones/desktop/renderer/src/Terms.test.jsx`
- Modify: `.camarones/desktop/renderer/package.json` and `package-lock.json`, `src/i18n.js` (es and en, every `pty.*`
  key), `src/app.css`, `docs/research/tooling-candidates.md` (K10), `.camarones/desktop/renderer-build/`

**Interfaces:**
- Consumes: `STREAM`, `bytes`, `followTerminals`, `elapsed` (Task 7); `tone` from `plan.js`; `fmtDuration` from
  `@camaron/ui`; the routes of Task 6.
- Produces:
  - `useTerminals(srv) -> { list: Terminal[], available: boolean, attach(id, el) -> () => void, focus(id),
    close(id) -> Promise, refresh() }` — the list from `GET app/terminals` on mount, again when the stream brings an id
    it does not know or an `end`, and after `close`; one `followTerminals` for the hook's life, each `{t, d, o}` written
    to that terminal's xterm and its offset kept. One xterm per terminal, created at its first bytes or attach (the
    `@xterm/xterm` and `@xterm/addon-fit` modules imported dynamically once): `scrollback: 5000`,
    `screenReaderMode: true`, `fontSize: 12`, font, background and foreground read from the slot's computed style (so
    S1's dark body holds in both themes); opened once into a detached host `div` with classes
    `dk-pty-screen nowheel nodrag nokey`; `onData` → `POST app/terminals/<id>/input`, one request after another;
    `onResize` → `POST …/resize`, debounced 150 ms. `attach(id, el)` pushes `el` on that terminal's stack of slots,
    moves the host into it and fits (a `ResizeObserver` on the slot fits again, debounced 150 ms); its cleanup pops
    `el` and moves the host back to the slot below — the node and its maximised copy share one screen. Unmount aborts
    the stream and disposes every xterm.
  - `PtyNode({ data: { unit, term, now, attach, onClose, onMax, onSession, canStart } })` — header: the unit's title
    (or `t('pty.update')`), the agent, `t('pty.you')` while live or `t('pty.ended', { code })`,
    `fmtDuration(elapsed(term, now))`; live → `t('pty.close')`, ended → `t('pty.remove')` (both
    `onClose(term.id)`); a unit's terminal that ended with a code other than 0 → `t('pty.fresh')` →
    `onSession(unit.id, 'new')`, disabled without `canStart`; `⤢` (`aria-label` `cv.max`) → `onMax(nodeId)`. Tone:
    live `running`, a non-zero end `blocked`, else `tone(unit)` (`done` for a loose one). Body:
    `<div className="dk-term-body dk-pty-slot nowheel nodrag nokey" role="group" aria-label={t('pty.label', { name })}>`
    attached in an effect. Ports (handles) as `TermNode`'s.
  - `LaneNode({ data: { label } })` — the loose lane's title, an eyebrow, not interactive.
  - `i18n.js`, es / en: `pty.you` contigo / with you · `pty.ended` terminó ({code}) / ended ({code}) · `pty.close`
    Cerrar / Close · `pty.remove` Quitar / Remove · `pty.fresh` Abrir una sesión nueva / Open a new session ·
    `pty.show` Ver su terminal / Show its terminal · `pty.update` Actualizar docs / Update docs · `pty.label` Terminal
    de {name} / Terminal: {name} · `pty.loose` Sesiones sueltas / Loose sessions · `pty.already` Ya tiene una sesión
    abierta: aquí está su terminal. / It already has an open session: here is its terminal. · `next.onCanvas` Abierta
    en el lienzo del plan con {agent}. / Opened on the plan's canvas with {agent}. · `next.noPty` Abierta en una
    ventana con {agent}: esta máquina no puede abrir terminales dentro de la app. / Opened in a window with {agent}:
    this machine cannot open terminals inside the app.
  - `app.css`: `.dk-pty-slot` fills the node under its header (`flex: 1; min-height: 0`), the S1 terminal body
    colours; `.dk-pty-screen` and xterm's `.xterm` fill it with a 4px inset; `.dk-cv-lane`; the `@xterm/xterm` CSS
    imported in `Terms.jsx`.

- [ ] **Step 1: Write the failing tests** in `Terms.test.jsx`:

```jsx
import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { PtyNode } from './sections/Terms.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))
const html = (el) => renderToStaticMarkup(<ReactFlowProvider>{el}</ReactFlowProvider>)
const unit = { id: 'explain:api', title: 'Explicar la API', status: 'doing', runner: 'agent', phase: 2, deps: [] }
const live = { id: 't-explain_api-1', kind: 'unit', unit: 'explain:api', agent: 'claude', started: 0, ended: null, code: null }
const on = { attach: () => () => {}, onClose() {}, onMax() {}, onSession() {}, canStart: true }

test('a session with you shows its agent, its time and how to close it', () => {
  const out = html(<PtyNode data={{ unit, term: live, now: 120000, ...on }} />)
  for (const s of ['Explicar la API', 'claude', 'contigo', '2 min', 'Cerrar']) expect(out).toContain(s)
  expect(out).toMatch(/class="[^"]*dk-pty-slot[^"]*nowheel[^"]*nodrag[^"]*nokey/)
  expect(out).toContain('aria-label="Terminal de Explicar la API"')
  expect(out).not.toContain('Abrir una sesión nueva')
})

test('a session that failed keeps its screen and offers a new one', () => {
  const out = html(<PtyNode data={{ unit, term: { ...live, ended: 60, code: 1 }, now: 90000, ...on }} />)
  for (const s of ['terminó (1)', 'Quitar', 'Abrir una sesión nueva', 'tone-blocked']) expect(out).toContain(s)
})

test('the docs update is a loose session, in English too', () => {
  setLang('en')
  const term = { ...live, id: 't-update-1', kind: 'update', unit: null }
  const out = html(<PtyNode data={{ term, now: 0, ...on }} />)
  for (const s of ['Update docs', 'with you', 'Close']) expect(out).toContain(s)
})
```

- [ ] **Step 2: Add the dependencies and run the tests to verify they fail**

Run: `(cd .camarones/desktop/renderer && npm install --save-exact @xterm/xterm@6.0.0 @xterm/addon-fit@0.11.0 && npx vitest run src/Terms.test.jsx)`
Expected: FAIL — `./sections/Terms.jsx` not found.

- [ ] **Step 3: Implement `useTerminals`, `PtyNode`, `LaneNode`, the keys and the CSS**; add row **K10** to
  `tooling-candidates.md` §K: xterm.js 6.0.0 and its fit addon 0.11.0 (MIT), the terminal of the canvas nodes —
  build-time only, bundled into `renderer-build/` in a chunk loaded with the first terminal, users never run npm.

- [ ] **Step 4: Run the whole renderer suite and build**

Run: `(cd .camarones/desktop/renderer && npx vitest run && npm run build)`
Expected: all PASS (`i18n.test.js` checks es/en parity); `renderer-build/` rebuilt with an xterm chunk.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/sections/Terms.jsx .camarones/desktop/renderer/src/Terms.test.jsx \
  .camarones/desktop/renderer/src/i18n.js .camarones/desktop/renderer/src/app.css \
  .camarones/desktop/renderer/package.json .camarones/desktop/renderer/package-lock.json \
  docs/research/tooling-candidates.md .camarones/desktop/renderer-build
git commit -m "feat(desktop): a real terminal in a canvas node (xterm.js), one stream for all of them"
```

### Task 9: The canvas hosts the terminals, and every session opens there

**Files:**
- Modify: `.camarones/desktop/renderer/src/canvas.js`, `canvas.test.js`, `src/sections/Canvas.jsx`,
  `src/Canvas.test.jsx`, `src/sections/Plan.jsx`, `src/parts.jsx`, `src/sections/Summary.jsx`,
  `src/sections/Quality.jsx`, `src/sections/Machine.jsx`, `src/i18n.js`, `src/app.css`,
  `.camarones/desktop/renderer-build/`

**Interfaces:**
- Consumes: Tasks 7–8; `machine.panel()`'s `terminals` and `sessions` (Task 5); the pipeline row's `terminal`
  (Task 6).
- Produces:
  - `canvas.js`: `openUnits(units, f, viewed, now, ptys = new Set())` — a unit in `ptys` is open too.
    `layout(units, open, { pty = new Set(), loose = [] } = {})` — an open unit in `pty` is a node of type `pty` at the
    terminal size; with `loose` terminals, a `lane` node (`id: 'lane:loose'`, `SIZE.term.w` × 24, `selectable`,
    `draggable` and `focusable` false) under the lowest node, then one `pty` node per loose terminal
    (`{ id: term.id, data: { term } }`) in a row under it; never overlapping; without `loose`, no lane.
    `planLive(run, pilot, units) -> boolean` = `runLive(run, pilot)` or a unit whose `session.live`.
    `canvasKey(key, { inTerminal, inLog, maxed, node, self, mods }) -> 'leave' | 'open' | 'left' | 'right' | 'up' |
    'down' | null` — in a terminal, nothing is the canvas's; Escape leaves a maximised node (also from a read-only
    log); in a log, nothing else; Enter or Space on the node itself opens it; arrows inside a node, without modifiers,
    move.
  - `Canvas({ srv, units, run, pilot, onOpen, focus, onFocused, onSession, canStart, noAgent })` — `Flow` calls
    `useTerminals(srv)` and `shown(list, now)`; `NODE_TYPES = { unit, term, pty: PtyNode, lane: LaneNode }`;
    `deleteKeyCode={null}`; `onKeyDown` through `canvasKey` (`inTerminal` = target inside `.dk-pty-slot`, `inLog` =
    inside `.dk-term-log`); `neighbour` gets the nodes without the lane; `now` also ticks while a terminal is live.
    `focus` (a terminal id): once it is in the list, reveal its node (its unit's, or its own when loose), focus its
    xterm, `onFocused()`. `onSession(uid, mode)` errors show in an `Aviso` above the graph; `noAgent` shows
    `t('next.noAgent')` with `t('next.machine')` → `#/machine`. The module function `ended(fu, unit)` is renamed
    `endWord`, so `Flow`'s `ended` no longer shadows it.
  - `UnitNode`: a paused unit (`tone(unit) === 'paused'`) says `t('cv.paused')` and offers `t('unit.continue')` →
    `onSession(unit.id, 'continue')`, disabled without `canStart`. Keys: `cv.paused` En pausa: su sesión se cerró /
    Paused: its session was closed.
  - `Plan.jsx`: the default view's trigger is `arrivedLive(held, planLive(data.run, pilot, data.units))`; `termOf(hash)`
    (`useHash`) shows the canvas for the visit without storing a choice, passes `focus`, and replaces the address with
    `#/plan` (`history.replaceState`); `pick` ends that visit; `onSession` = `openSession(srv, { unit, agent: a.agent,
    lang: lang(), mode })` then `load()`; `canStart = Boolean(a.agent)`, `noAgent = a.agents?.length === 0`; the
    *Actualizar docs* card opens through `openSession` with `unit: 'update'` and its note from `sessionNote`. The header
    comment's sentence "a terminal opened by hand on one unit does not count" goes, and `runLive`'s comment in
    `canvas.js` says the Plan adds sessions through `planLive`.
  - `parts.jsx` `UnitActions`, `Summary.jsx`, `Quality.jsx`: open through `openSession` and say `sessionNote`;
    `UnitActions` for `{ kind: 'live', term }` with a term shows `t('pty.show')` → `#/plan?term=<id>` (without one,
    today's note).
  - `Machine.jsx` `Settings`: a select `mc-sessions` (`t('mc.sessions')`: `t('mc.sessCanvas')`, `t('mc.sessWindow')`)
    → `config set sessions <v>`; when `m.terminals === false`, a muted `t('mc.noPty')`. Keys: `mc.sessions` Dónde se
    abren las sesiones / Where sessions open · `mc.sessCanvas` En el lienzo del plan / On the plan's canvas ·
    `mc.sessWindow` En una ventana de terminal / In a terminal window · `mc.noPty` En esta máquina se abren en una
    ventana: la terminal de la app no está disponible. / On this machine they open in a window: the app's terminal is
    not available.

- [ ] **Step 1: Write the failing tests**

`canvas.test.js` (append; `canvasKey` and `planLive` join the file's import from `./canvas.js`; `units`, `overlap`,
`emptyFeed`, `layout`, `openUnits` and `SIZE` are there already):

```js
test('a terminal opened by hand opens its unit as a terminal node, and loose ones go under the graph', () => {
  const open = openUnits(units, emptyFeed(null), new Set(), 0, new Set(['d']))
  expect(open.has('d')).toBe(true)
  const loose = [{ id: 't-update-1', kind: 'update', unit: null }]
  const { nodes } = layout(units, open, { pty: new Set(['d']), loose })
  const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
  expect(at.d).toMatchObject({ type: 'pty', width: SIZE.term.w, height: SIZE.term.h })
  expect(at['t-update-1']).toMatchObject({ type: 'pty', data: { term: loose[0] } })
  const graph = nodes.filter((n) => !['t-update-1', 'lane:loose'].includes(n.id))
  expect(at['lane:loose'].position.y).toBeGreaterThan(Math.max(...graph.map((n) => n.position.y + n.height)))
  expect(at['t-update-1'].position.y).toBeGreaterThan(at['lane:loose'].position.y)
  for (const p of nodes) for (const q of nodes) if (p !== q) expect(overlap(p, q)).toBe(false)
  expect(layout(units, open).nodes.some((n) => n.type === 'lane')).toBe(false)
})

test('a key typed in a terminal belongs to the agent', () => {
  for (const key of ['Escape', 'Enter', ' ', 'ArrowLeft', 'Backspace']) {
    expect(canvasKey(key, { inTerminal: true, maxed: true, node: true, self: true })).toBe(null)
  }
  expect(canvasKey('Escape', { inLog: true, maxed: true, node: true })).toBe('leave')
  expect(canvasKey('ArrowRight', { inLog: true, node: true })).toBe(null)
  expect(canvasKey('Escape', { node: true, maxed: false })).toBe(null)
  expect(canvasKey('Enter', { node: true, self: true })).toBe('open')
  expect(canvasKey('Enter', { node: true, self: false })).toBe(null)
  expect(canvasKey('ArrowDown', { node: true })).toBe('down')
  expect(canvasKey('ArrowDown', { node: true, mods: true })).toBe(null)
})

test('a session open with you turns the plan to the canvas, as a run does', () => {
  expect(planLive(null, null, [{ id: 'a', session: { live: true } }])).toBe(true)
  expect(planLive(null, null, [{ id: 'a', session: { live: false } }, { id: 'b' }])).toBe(false)
  expect(planLive({ run: 'r', finished: false }, null, [])).toBe(true)
})
```

`Canvas.test.jsx` (append):

```jsx
test('a paused unit says so and offers to continue it', () => {
  const out = html(<UnitNode data={{ unit: { ...unit, status: 'doing', paused: true }, now: 0, canStart: true, onSession() {}, ...on }} />)
  expect(out).toContain('En pausa: su sesión se cerró')
  expect(out).toMatch(/<button[^>]*>Seguir<\/button>/)
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js src/Canvas.test.jsx)`
Expected: FAIL — `canvasKey` and `planLive` not exported; no `pty` nodes; no paused note.

- [ ] **Step 3: Implement** `canvas.js`, then `Canvas.jsx`, `Plan.jsx`, `parts.jsx`, `Summary.jsx`, `Quality.jsx`,
  `Machine.jsx`, the keys and the lane's CSS, as in Interfaces.

- [ ] **Step 4: Run the whole renderer suite and build**

Run: `(cd .camarones/desktop/renderer && npx vitest run && npm run build)`
Expected: all PASS; `renderer-build/` rebuilt.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/canvas.js .camarones/desktop/renderer/src/canvas.test.js \
  .camarones/desktop/renderer/src/sections/Canvas.jsx .camarones/desktop/renderer/src/Canvas.test.jsx \
  .camarones/desktop/renderer/src/sections/Plan.jsx .camarones/desktop/renderer/src/parts.jsx \
  .camarones/desktop/renderer/src/sections/Summary.jsx .camarones/desktop/renderer/src/sections/Quality.jsx \
  .camarones/desktop/renderer/src/sections/Machine.jsx .camarones/desktop/renderer/src/i18n.js \
  .camarones/desktop/renderer/src/app.css .camarones/desktop/renderer-build
git commit -m "feat(desktop): sessions opened by hand live on the plan's canvas, as terminals you type in"
```

### Task 10: Seen working end to end, documented, versioned

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"]` → the next free minor, `4.76.0` unless `main` took it),
  `README.md` (badge; the Plan row at ~252 and the `config` mention of the machine's settings), `.camarones/lib/tutorial.py`
  (the Plan page, es ~233 and en ~677), `.camarones/TUTORIAL.md` (regenerated),
  `.camarones/templates/docs/guides/tutorial.md` and `templates/docs/i18n/es/guides/tutorial.md` (the Plan row),
  `templates/docs/guides/app.md` and its es twin (Plan: *Keep it current*, the detail's buttons, the canvas paragraph;
  Machine: the *Language and models* row), `templates/docs/guides/internals.md` and its es twin (the HTTP API's app
  row and a paragraph on terminals)
- Scratch (not committed): a fake `claude` in the session's scratchpad

- [ ] **Step 1: Check it in the app on the sandbox.** In a scratch folder, an executable `claude` that runs the test
  program with this interpreter:

```bash
uv run python -c "import pathlib, sys; p = pathlib.Path(sys.argv[1]); p.write_text(f'#!{sys.executable}\nimport runpy; runpy.run_path({sys.argv[2]!r}, run_name=\"__main__\")\n', encoding='utf-8'); p.chmod(0o755)" "<scratch>/claude" "$PWD/tests/fixtures/pty_echo.py"
```

Run: `PATH="<scratch>:$PATH" uv run scripts/sandbox.py cli app` (if the plan has no ready agent unit, `uv run
scripts/sandbox.py reset` first and take the wizard's setup until it has one).
Expected, in the app:
1. Plan → a ready unit → *Empezar con Claude Code*: the Plan turns to *Lienzo* and that unit's node is a terminal
   with `ready …`, focused; `hola` + Enter shows `echo hola (4)`; Escape typed in it stays in it.
2. ⤢ maximises it and `size` answers the bigger size; *Volver al lienzo* returns and `size` answers the node's size.
3. *Cerrar*: the node folds into the compact card, *En pausa*; its *Seguir* opens it again.
4. *Actualizar docs* opens a node under *Sesiones sueltas*; Summary's start button lands on the canvas, on its
   terminal; starting a unit already open says *Ya tiene una sesión abierta* and shows it.
5. Machine › *Dónde se abren las sesiones* → *En una ventana de terminal*: *Empezar* opens a Terminal window; set it
   back to *En el lienzo del plan*.
6. Quit the app with a terminal open: no `pty_echo.py` process is left (`ps -ef | grep pty_echo`); reopened, the unit
   is paused and *Seguir* reopens it.
7. English and the dark theme: strings and the dark terminal hold. Screenshot as proof.

Then `uv run scripts/sandbox.py cli uninstall --yes --no-backup` and `uv run scripts/sandbox.py traces`
Expected: `traces` exits 0 (the terminals' files live in the project's cache); `uv run scripts/sandbox.py reset` to
leave the sandbox as it was.

- [ ] **Step 2: Bump the version and update the user docs** (AGENTS.md §5.1). README: the Plan row says that starting
  or continuing a unit and *Actualizar docs* open as terminals on the canvas, where you type to the agent (Cerrar,
  Quitar, sesiones sueltas), the setting `sessions` (`camaron config set sessions window` for a window), and that the
  autopilot and *Ejecutar* skip a unit open in a session. The tutorial's Plan page and the shipped tutorial guides say
  the same in es and en (existing projects keep their copy — say so in the commit body). The app guide (en and es): the
  canvas paragraph gains terminals with you (type in them; Escape and the arrows go to the agent; ⤢ and *Back to the
  canvas*; *Close*, *Remove*, *Open a new session*; the loose lane; paused with *Continue*), the default-view sentence
  counts sessions again, the detail's table says where *Start* and *Continue* open and that an open one offers *Show its
  terminal*, the Machine row names *Where sessions open*. Internals (en and es): the app row of the HTTP API gains
  `GET app/terminals`, `app/terminals/stream`; `POST app/terminals`, `app/terminals/<id>/input`, `resize`, `close`;
  and a paragraph: terminals live in the project server (stdlib `pty`, ConPTY through pywinpty on Windows), 8 at most,
  the last 256 KB replayed, a `.log` of the last 5 MB, killed with the server, the window as the `sessions` setting.

Run: `(cd .camarones && uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())")`
Expected: `TUTORIAL.md` regenerated.

- [ ] **Step 3: Run every suite**

Run: `uv run pytest -n auto`, `(cd .camarones/desktop/renderer && npx vitest run)` and `(cd .camarones/desktop && node --test "test/*.test.cjs")`
Expected: all PASS (`test_wizard.py`: the tutorial and `TUTORIAL.md` agree; `test_guide.py`: markers, links and both
languages match).

- [ ] **Step 4: Commit**

```bash
git add .camarones/lib/common.py README.md .camarones/lib/tutorial.py .camarones/TUTORIAL.md \
  .camarones/templates/docs/guides/tutorial.md .camarones/templates/docs/i18n/es/guides/tutorial.md \
  .camarones/templates/docs/guides/app.md .camarones/templates/docs/i18n/es/guides/app.md \
  .camarones/templates/docs/guides/internals.md .camarones/templates/docs/i18n/es/guides/internals.md
git commit -m "docs(plan): terminals on the canvas in the README, the tutorial and the guides (kit 4.76.0)

Existing projects keep their copy of the command guide; new ones get the terminals."
```
