"""Interactive agent sessions on the plan: a unit (the wizard's "next unit") or the docs update, opened in its own
terminal window in the workspace, so the agent sees every repo and cam-docs. The wizard asks its questions and then
builds the same command; the desktop app calls `launch_unit` / `launch_update` through /api/app/agent. A unit's window
runs the agent inside lib/session_run.py, so the board knows whether it is still open (lib/sessions.py).

The prompt goes to a file and the agent gets a one-line pointer to it: multi-line arguments do not survive Windows
.cmd shims. A unit's session and the docs update each have a file of their own in the cache (`prompts/<unit>.md`), so
sessions open side by side never read one another's; a prompt that is no unit's, and the wizard, use the shared
docs/.work/next-prompt.md.

`where="canvas"` opens the same command as a terminal the project server holds (lib/terminals.py) instead of a window;
a machine with no PTY opens the window as before. The wizard never asks for the canvas."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from .common import CACHE, PREFS, WORK, WORKSPACE, load_json, save_json, which, ws_rel
from . import docs, env, plan, sessions, terminals
from .adapters import runners
from .harness import routing
from .harness.ports import RunRequest

CODEX_MODEL_DEFAULT = "gpt-5.6-terra"          # Codex's model slugs rotate, so this is just a starting default, not a fixed list
PROMPT = "docs/.work/next-prompt.md"

_opening = threading.Lock()                    # a session's check and its opening at once: two quick clicks cannot both pass


class AlreadyOpen(ValueError):
    """The unit's session, or the docs update, is open already; `terminal` is its id when it is a canvas terminal."""

    def __init__(self, message: str, terminal: str | None = None):
        super().__init__(message)
        self.terminal = terminal


def claude_history(cwd: Path) -> bool:
    """Whether Claude Code has a saved conversation for `cwd` (its projects dir is the path with / and . → -)."""
    return any(sessions.claude_dir(cwd).glob("*.jsonl"))


def installed() -> list[dict]:
    return [{"id": r.id, "label": r.label} for r in runners.all() if which(r.command or r.id)]


def model_for(agent: str, prefs: dict, uid: str | None = None) -> str | None:
    """The model a session asks for: the first route to this agent for the unit (its pipeline node's runner, then its
    tier's routing) when it names one, else this machine's model for the agent. `update` is agentic-heavy work."""
    default = {"claude": prefs.get("model", "sonnet"), "codex": prefs.get("codex_model", CODEX_MODEL_DEFAULT)
               }.get(agent, prefs.get(f"{agent}_model"))
    if uid:
        s = plan.settings(uid)
        tier = s["tier"]
        targets = ([s["runner"]] if s.get("runner") else []) + routing.table(docs.workspace(), prefs)[tier]
        keep, _ = routing.candidates(tier, {tier: targets}, bool(s.get("allow_local")))
        route = next((r for r in keep if r.runner == agent), None)
        if route and route.model:
            return route.model
    return default or None


def own_prompt(name: str) -> Path:
    """Where the session of a unit (or of `update`) reads its prompt."""
    return CACHE / "prompts" / f"{sessions.slug(name)}.md"


def prompt_ref(file: Path | None) -> str:
    """How the agent and the app name a prompt file: from the workspace when it lies inside, else in full. None: the
    shared one."""
    if file is None:
        return ws_rel(PROMPT)
    try:
        return file.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return str(file)


def request(agent: str, lang: str, prefs: dict, resume: bool = False, session: str | None = None,
            uid: str | None = None, prompt_file: Path | None = None) -> RunRequest:
    ref = prompt_ref(prompt_file)
    short = f"Follow the instructions in {ref}" if lang == "en" else f"Sigue las instrucciones de {ref}"
    return RunRequest(prompt=short, cwd=WORKSPACE, model=model_for(agent, prefs, uid), interactive=True, resume=resume,
                      session=session)


def write_prompt(prompt: str, file: Path | None = None) -> None:
    file = file or WORK / "next-prompt.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(prompt, encoding="utf-8")


def _place(where: str) -> tuple[str, str | None]:
    """Where a session really opens, and why not on the canvas when it was asked for."""
    if where not in ("canvas", "window"):
        raise ValueError("where: canvas or window")
    if where == "canvas" and not terminals.available():
        return "window", "no-pty"
    return where, None


def _open(prompt: str, agent: str, lang: str, resume: bool, uid: str | None = None, session: str | None = None,
          route: str | None = None, where: str = "window", size: tuple[int, int] = (80, 24),
          fallback: str | None = None) -> dict:
    """uid: the plan unit whose session this is; route: whose model it takes, when that is not a unit (`update`).
    where: as `_place` answered, `fallback` its reason when that was not the canvas asked for."""
    if agent not in {a["id"] for a in installed()}:
        raise ValueError(f"{agent} is not installed on this machine")
    prefs = load_json(PREFS, {})
    prefs["last_agent"] = agent
    save_json(PREFS, prefs)
    file = own_prompt(uid or route) if uid or route else None
    write_prompt(prompt, file)
    if agent == "claude" and resume and not session and not claude_history(WORKSPACE):
        resume = False                               # nothing to continue here: `--continue` would just error out
    req = request(agent, lang, prefs, resume, session, uid=uid or route, prompt_file=file)
    cmd = runners.get(agent).build(req).argv
    record = sessions.start(uid, agent, session) if uid else None       # before the terminal: its end closes this record
    done = {"launched": True, "agent": agent, "model": req.model, "prompt": prompt_ref(file)}
    if where == "canvas":
        try:
            term = terminals.spawn(sessions.wrap(record, cmd), WORKSPACE, kind="unit" if uid else "update", unit=uid,
                                   agent=agent, session=session, cols=size[0], rows=size[1])
        except terminals.Unavailable:
            where, fallback = "window", "no-pty"
        else:
            return {**done, "where": "canvas", "terminal": term}
    if uid:
        cmd = sessions.wrap(record, cmd)
    if not env.open_new_terminal(cmd, WORKSPACE):
        raise RuntimeError(f"no terminal window could be opened on this machine: the prompt is in {prompt_ref(file)}")
    return {**done, "where": where, **({"fallback": fallback} if fallback else {})}


def launch_unit(uid: str, agent: str, lang: str = "es", mode: str = "new", where: str = "window",
                size: tuple[int, int] = (80, 24)) -> dict:
    """mode: new (a fresh session), continue (the agent's last conversation, for a unit in progress), restart (the
    unit's notes are put aside and it starts over). where: a window or a terminal on the canvas of `size` (cols, rows);
    AlreadyOpen when the unit's session is open in either, Limit when the canvas has no room (nothing has changed)."""
    if mode not in ("new", "continue", "restart"):
        raise ValueError("mode: new, continue or restart")
    data = plan.sync()
    u = plan.get(data, uid)
    if u["runner"] != "agent":
        raise ValueError(f"{uid} is not done by an agent session")
    if u["status"] != "doing" and uid not in {x["id"] for x in plan.available(data)}:
        waits = [d for d in u.get("deps") or [] if plan.get(data, d)["status"] not in ("done", "dropped")]
        raise ValueError(f"{uid} is {u['status']}" + (f": it waits for {', '.join(waits)}" if waits else ""))
    if u["type"] in plan.INTERVIEW_TYPES and "interviews" not in docs.workspace()["project"] and \
            plan.get(data, "interview-context")["status"] != "done":
        raise ValueError("choose first how the interviews run (team questionnaire or live): `camaron interview mode`")
    if agent not in {a["id"] for a in installed()}:
        raise ValueError(f"{agent} is not installed on this machine")
    where, fallback = _place(where)
    with _opening:
        rec = sessions.load(uid)
        term = terminals.find("unit", uid)
        if term or sessions.running(rec):
            raise AlreadyOpen(f"{uid}: its session is already open in " +
                              (f"terminal {term['id']}" if term else "its own terminal window"), term and term["id"])
        if where == "canvas":
            terminals.room()
        session = None
        if agent == "claude":                        # its own conversation: the board reads it, Continue reopens it
            old = (rec or {}).get("session") if (rec or {}).get("agent") == "claude" else None
            if mode == "continue" and old and (sessions.claude_dir(WORKSPACE) / f"{old}.jsonl").exists():
                session = old
            elif mode != "continue":
                session = str(uuid.uuid4())
        if mode == "restart":
            f = plan.note_file(uid)
            if f.exists():
                f.replace(f.with_suffix(".old.md"))
            plan.set_status(uid, "todo")
        plan.set_status(uid, "doing")                # so a closed window still knows what was in progress
        return {**_open(plan.prompt(uid, lang=lang), agent, lang, resume=mode == "continue", uid=uid, session=session,
                        where=where, size=size, fallback=fallback), "unit": uid}


def launch_update(agent: str, lang: str = "es", where: str = "window", size: tuple[int, int] = (80, 24)) -> dict:
    """The docs update, opened as `launch_unit` opens a unit. It has no session record, so only a terminal on the
    canvas tells that one is open already (AlreadyOpen)."""
    where, fallback = _place(where)
    with _opening:
        term = terminals.find("update")
        if term:
            raise AlreadyOpen(f"the docs update is already open in terminal {term['id']}", term["id"])
        if where == "canvas":
            terminals.room()
        return {**_open(plan.prompt("update", lang=lang), agent, lang, resume=False, route="update", where=where,
                        size=size, fallback=fallback), "unit": "update"}


def launch_prompt(prompt: str, agent: str, lang: str = "es") -> dict:
    """A fresh agent session on a prompt that is not a plan unit (the C4 refinement of the first run)."""
    return _open(prompt, agent, lang, resume=False)
