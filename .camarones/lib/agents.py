"""Interactive agent sessions on the plan: a unit (the wizard's "next unit") or the docs update, opened in its own
terminal window in the workspace, so the agent sees every repo and cam-docs. The wizard asks its questions and then
builds the same command; the desktop app calls `launch_unit` / `launch_update` through /api/app/agent. A unit's window
runs the agent inside lib/session_run.py, so the board knows whether it is still open (lib/sessions.py).

The prompt goes to docs/.work/next-prompt.md and the agent gets a one-line pointer to it: multi-line arguments do not
survive Windows .cmd shims."""
from __future__ import annotations

import uuid
from pathlib import Path

from .common import PREFS, WORK, WORKSPACE, load_json, save_json, which, ws_rel
from . import docs, env, plan, sessions
from .adapters import runners
from .harness import routing
from .harness.ports import RunRequest

CODEX_MODEL_DEFAULT = "gpt-5.6-terra"          # Codex's model slugs rotate, so this is just a starting default, not a fixed list
PROMPT = "docs/.work/next-prompt.md"


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


def request(agent: str, lang: str, prefs: dict, resume: bool = False, session: str | None = None,
            uid: str | None = None) -> RunRequest:
    short = f"Follow the instructions in {ws_rel(PROMPT)}" if lang == "en" else f"Sigue las instrucciones de {ws_rel(PROMPT)}"
    return RunRequest(prompt=short, cwd=WORKSPACE, model=model_for(agent, prefs, uid), interactive=True, resume=resume,
                      session=session)


def write_prompt(prompt: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "next-prompt.md").write_text(prompt, encoding="utf-8")


def _open(prompt: str, agent: str, lang: str, resume: bool, uid: str | None = None, session: str | None = None,
          route: str | None = None) -> dict:
    """uid: the plan unit whose session this is; route: whose model it takes, when that is not a unit (`update`)."""
    if agent not in {a["id"] for a in installed()}:
        raise ValueError(f"{agent} is not installed on this machine")
    prefs = load_json(PREFS, {})
    prefs["last_agent"] = agent
    save_json(PREFS, prefs)
    write_prompt(prompt)
    if agent == "claude" and resume and not session and not claude_history(WORKSPACE):
        resume = False                               # nothing to continue here: `--continue` would just error out
    req = request(agent, lang, prefs, resume, session, uid=uid or route)
    cmd = runners.get(agent).build(req).argv
    if uid:
        cmd = sessions.wrap(sessions.start(uid, agent, session), cmd)
    if not env.open_new_terminal(cmd, WORKSPACE):
        raise RuntimeError(f"no terminal window could be opened on this machine: the prompt is in {ws_rel(PROMPT)}")
    return {"launched": True, "agent": agent, "model": req.model, "prompt": ws_rel(PROMPT)}


def launch_unit(uid: str, agent: str, lang: str = "es", mode: str = "new") -> dict:
    """mode: new (a fresh session), continue (the agent's last conversation, for a unit in progress), restart (the
    unit's notes are put aside and it starts over)."""
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
    rec = sessions.load(uid)
    if sessions.running(rec):
        raise ValueError(f"{uid}: its session is already open in its own terminal window")
    session = None
    if agent == "claude":                            # its own conversation: the board reads it, Continue reopens it
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
    plan.set_status(uid, "doing")                    # so a closed window still knows what was in progress
    return {**_open(plan.prompt(uid, lang=lang), agent, lang, resume=mode == "continue", uid=uid, session=session),
            "unit": uid}


def launch_update(agent: str, lang: str = "es") -> dict:
    return {**_open(plan.prompt("update", lang=lang), agent, lang, resume=False, route="update"), "unit": "update"}


def launch_prompt(prompt: str, agent: str, lang: str = "es") -> dict:
    """A fresh agent session on a prompt that is not a plan unit (the C4 refinement of the first run)."""
    return _open(prompt, agent, lang, resume=False)
