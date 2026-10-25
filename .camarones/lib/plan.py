"""Work plan: the documentation job split into session-sized units, persisted in docs/.work/plan.yaml.

Each unit is small enough for one agent session (fresh context). Agents and the wizard use:
  plan sync   (re)build units from workspace.yaml, keeping statuses
  plan next   units whose dependencies are done
  plan start/done/block/drop/add
and docs/.work/handoff.md carries the baton between sessions.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import functools
import json
import os
import subprocess
import threading
import time
from contextvars import ContextVar
from pathlib import Path

import yaml

from .common import CTX, KIT, PREFS, ROOT, load_json, WORK, CAM_LAYOUT, CAM_DIR, WORKSPACE, cli_cmd, ws_rel, rel_file, IS_WIN, which
from . import docs
from .adapters import runners
from .adapters.runners.base import LIMIT_HINTS  # noqa: F401  (kept for callers)
from .harness import awake, drafts, freshness, kpis, pipeline, routing
from .harness.events import EventLog
from .harness.locks import FileLock
from .harness.ports import RunRequest

PLAN = WORK / "plan.yaml"
PLAN_LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "plan.lock"   # git-ignored, shared by worktrees
HANDOFF = WORK / "handoff.md"
LOG = WORK / "log.md"
DONE = ("done", "dropped")
NO_WIKI = "No wiki for this repo (wizard → Wikis → choose repos)"
LIVE_INTERVIEWS = "Interviews are done live, not by team questionnaire"
OFF_PROFILE = "Not part of the selected profile"
DISABLED = "Disabled in .camarones/pipeline.yaml"
OVERRIDE = CTX.state_root / ".camarones" / "pipeline.yaml"   # the project's changes to the kit pipeline (R8), read from main


class PipelineError(RuntimeError):
    """The project's pipeline.yaml cannot be used; the stored plan is left as it was."""

# unit type → (phase, runner, title template, playbook section); the catalog lives in lib/pipelines/units.yaml
TYPES = {k: (v["phase"], v["runner"], v["title"], v["playbook"]) for k, v in pipeline.types().items()}


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def load() -> dict:
    if PLAN.exists():
        data = yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    data.setdefault("version", 1)
    data.setdefault("units", [])
    return data


def locked(fn):
    """Read-modify-write of plan.yaml under the plan lock, so parallel sessions never lose each other's updates."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with FileLock(PLAN_LOCK):
            return fn(*args, **kwargs)
    return wrapper


@locked
def save(data: dict) -> None:
    """Write the plan atomically: readers without the lock see the old file or the new one, never half of one."""
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = PLAN_LOCK.with_name(f"plan.{os.getpid()}.tmp")    # git-ignored if a crash leaves it; same disk as PLAN
    tmp.write_text("# Camarón work plan — one unit per agent session. Managed by the camarones CLI.\n"
                   + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8",
                   newline="\n")
    for attempt in range(50):
        try:
            os.replace(tmp, PLAN)
            return
        except PermissionError:              # Windows: a reader has the file open for a moment
            if attempt == 49:
                raise
            time.sleep(0.02)


def unit(uid: str, type_: str, deps: list[str], repo: str | None = None, slug: str | None = None, title: str | None = None,
         soft: list[str] | None = None) -> dict:
    """`deps` must be done before the unit starts; `soft` ones (the interviews) feed it but never block it: started
    without them, the unit is provisional and is reopened to refine once they are done."""
    phase, runner, tpl, section = TYPES[type_]
    return {"id": uid, "type": type_, "phase": phase, "runner": runner,
            "title": title or tpl.format(repo=repo or "", slug=slug or ""), "status": "todo",
            "deps": deps, **({"soft": soft} if soft else {}), "repo": repo, "notes": "", "updated": None}


def project_pipeline() -> tuple[dict, list[str]]:
    """The kit pipeline of the project's profile, with .camarones/pipeline.yaml applied when there is one."""
    default = "quick" if docs.workspace()["project"].get("profile") == "quick" else "full"
    if not OVERRIDE.exists():
        return pipeline.load(default), []
    try:
        override = yaml.safe_load(OVERRIDE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return pipeline.load(default), [f"pipeline.yaml is not valid YAML: {e}"]
    if not isinstance(override, dict):
        return pipeline.load(default), ["pipeline.yaml: expected a mapping (extends, nodes, patch)"]
    return pipeline.compose(override, default)


def pipeline_problems() -> list[str]:
    return project_pipeline()[1]


def pipeline_units() -> list[dict]:
    """The project's pipeline expanded for its repos, with how each unit runs (for `pipeline show`)."""
    out = []
    for n in _nodes(docs.repo_names()):
        t = pipeline.types().get(n["type"], {})
        s = {"tier": t.get("tier", "agentic-heavy"), "isolation": t.get("isolation", "none"), "runner": None,
             **n["settings"]}
        out.append({"id": n["id"], "type": n["type"], "needs": n["needs"], "soft": n["soft"], "tier": s["tier"],
                    "isolation": s["isolation"], "runner": s["runner"], "disabled": n["disabled"],
                    "approval": bool(s.get("approval"))})
    return out


def _nodes(repos: list[str]) -> list[dict]:
    spec, problems = project_pipeline()
    if problems:
        raise PipelineError("; ".join(problems))
    return pipeline.expand(spec, repos, {"team-interviews": docs.interview_mode() == "team"})


def blueprint(repos: list[str]) -> list[dict]:
    """The plan's units for these repos, from the project's pipeline (lib/pipelines/ + .camarones/pipeline.yaml)."""
    return [unit(n["id"], n["type"], n["needs"], repo=n["repo"], soft=n["soft"]) for n in _nodes(repos) if not n["disabled"]]


def plugin_guidance(uid: str) -> str:
    """The team plugin a node `uses` (R25): its prompts inline and where its skills are. Only an approved plugin with
    the pinned major version; anything else is a pipeline problem and adds nothing."""
    try:
        uses = settings(uid).get("uses")
    except Exception:  # noqa: BLE001 — a broken pipeline is reported elsewhere; the prompt still works
        return ""
    if not uses:
        return ""
    from .harness import plugins
    name, _, major = str(uses).partition("@")
    p = next((x for x in plugins.discover() if x.name == name), None)
    version = str(p.manifest.get("version", "")) if p else ""
    if not p or not p.active or (major and version.split(".")[0] != major):
        return ""
    rel = lambda f: ws_rel(rel_file(f))  # noqa: E731
    parts = [f"\nTeam guidance — plugin {name} {version} (`{rel(p.path)}`), follow it in this unit:"]
    for item in p.provides.get("prompts") or []:
        f = p.path / str(item)
        if f.is_file():
            parts.append(f.read_text(encoding="utf-8").strip())
    skills = [rel(p.path / str(s)) for s in p.provides.get("skills") or [] if (p.path / str(s)).exists()]
    if skills:
        parts.append("Skills to read before writing: " + ", ".join(f"`{s}`" for s in skills))
    return "\n".join(parts) + "\n"


def settings(uid: str) -> dict:
    """How a unit runs: its type's tier and isolation, then what the pipeline sets for that node."""
    try:
        node = next((n for n in _nodes(docs.repo_names()) if n["id"] == uid), None)
    except PipelineError:
        node = None
    type_ = node["type"] if node else next((u["type"] for u in load()["units"] if u["id"] == uid), "")
    t = pipeline.types().get(type_, {})
    return {"tier": t.get("tier", "agentic-heavy"), "isolation": t.get("isolation", "none"),
            **(node["settings"] if node else {})}


@locked
def sync() -> dict:
    """Merge the blueprint into the stored plan: keep statuses/notes, add units for new repos, drop removed repos."""
    data = load()
    old_profile = data.get('profile', 'full')
    profile = docs.workspace()['project'].get('profile', 'full')
    repos = docs.repo_names()
    try:
        nodes = _nodes(repos)
    except PipelineError:
        return data                        # a broken pipeline.yaml must not switch units on or off; `plan` says why
    disabled = {n["id"] for n in nodes if n["disabled"]}
    existing = {u["id"]: u for u in data["units"]}
    merged = []
    for bu in (unit(n["id"], n["type"], n["needs"], repo=n["repo"], soft=n["soft"]) for n in nodes if not n["disabled"]):
        cur = existing.pop(bu["id"], None)
        if cur:
            bu.update({k: cur[k] for k in ("status", "notes", "updated", "redo", "provisional", "refine") if k in cur})
            if cur.get("status") == "dropped" and bu.get("repo") in repos:
                bu["status"] = "todo"
            if cur.get('notes') in (OFF_PROFILE, DISABLED):
                bu['status'], bu['notes'] = 'todo', ''
            if old_profile != profile and bu['id'] in ('setup', 'portal', 'confirm', 'handover'):
                bu['status'] = 'todo'
        merged.append(bu)
    for leftover in existing.values():     # dynamic units (flows, splits) or units of removed repos
        if profile == 'quick' and leftover['type'] not in ('flow', 'doc-fixes', 'review-fixes', 'integrate', 'eval-questions', 'refresh-docs') and leftover['status'] == 'todo':
            leftover['status'], leftover['notes'] = 'dropped', OFF_PROFILE
        if leftover["status"] in ("todo", "blocked") and leftover["id"] in disabled:
            leftover["status"], leftover["notes"] = "dropped", DISABLED
        elif leftover["status"] in ("todo", "blocked") and OVERRIDE.exists() and leftover["type"] in pipeline.kit_types():
            leftover["status"], leftover["notes"] = "dropped", OFF_PROFILE     # left out by the project's pipeline
        if leftover.get("repo") and leftover["repo"] not in repos:
            leftover["status"] = "dropped"
        merged.append(leftover)
    # flows must finish before i18n/confirm consider flows complete
    flow_ids = [u["id"] for u in merged if u["type"] == "flow" and u["status"] != "dropped"]
    for u in merged:
        if u["id"] in ("i18n", "confirm", "diagrams"):
            u["deps"] = sorted(set(u["deps"]) | set(flow_ids))
    comps = docs.workspace()["project"].get("components")
    wiki_repos = docs.wiki_repos()
    for u in merged:
        if u["type"] != "repo-wiki":
            continue
        if comps is not None and "openwiki" not in comps:  # OpenWiki not installed → no repo-wiki units
            why = "OpenWiki not selected"
        elif u["repo"] not in wiki_repos:                  # a wiki only for the repos the user picked
            why = NO_WIKI
        else:
            if u.get("notes") == NO_WIKI:                  # chosen again
                u["status"] = "todo" if u["status"] == "dropped" else u["status"]
                u["notes"] = ""
            continue
        if u["status"] in ("todo", "blocked"):
            u["status"], u["notes"] = "dropped", why
    # questionnaire units only while the team answers it: not in live mode, nor once the interviews ran live
    team = docs.interview_mode() == "team"
    live_done = any(u["id"] == "interview-context" and u["status"] == "done" for u in merged)
    for u in merged:
        if u["type"] not in ("questionnaire", "answers"):
            continue
        if team and not live_done and u["status"] == "dropped" and u.get("notes") == LIVE_INTERVIEWS:
            u["status"], u["notes"] = "todo", ""
        elif (not team or live_done) and u["status"] in ("todo", "blocked"):
            u["status"], u["notes"] = "dropped", LIVE_INTERVIEWS
    data["units"] = merged
    data['profile'] = profile
    save(data)
    return data


@locked
def set_interview_mode(mode: str) -> dict:
    """Switch how the interviews run. In team mode a live interview that was already started goes back to todo: it now
    waits for the team's answers (its checkpoints stay, so the consolidation sees what was said live)."""
    docs.set_interview_mode(mode)
    data = sync()
    if mode == "team" and any(u["type"] in INTERVIEW_TYPES and u["status"] == "doing" for u in data["units"]):
        for u in data["units"]:
            if u["type"] in INTERVIEW_TYPES and u["status"] == "doing":
                u["status"] = "todo"
        save(data)
    return data


def get(data: dict, uid: str) -> dict:
    for u in data["units"]:
        if u["id"] == uid:
            return u
    raise KeyError(f"unknown unit '{uid}' — see `{cli_cmd()} plan`")


def available(data: dict | None = None) -> list[dict]:
    data = data or load()
    st = {u["id"]: u["status"] for u in data["units"]}
    redone = {u["id"] for u in data["units"] if u.get("redo")}
    links = {u["id"]: u["deps"] + (u.get("soft") or []) for u in data["units"]}

    def waits_on(u: dict) -> list[str]:
        if not u.get("redo"):
            return u["deps"]
        # a reopened unit also waits for a redo further up its chain (soft links too: an interview being redone),
        # never for an interview that has not happened yet
        up, frontier = set(), set(links[u["id"]])
        while frontier:
            up |= frontier
            frontier = {d for f in frontier for d in links.get(f, [])} - up
        return [d for d in up if d in redone or d in u["deps"]]
    ready = [u for u in data["units"] if u["status"] in ("todo", "doing", "blocked") and not awaiting(u)
             and all(st.get(d, "done") in DONE for d in waits_on(u))]
    order = {"doing": 0, "todo": 1, "blocked": 2}
    return sorted(ready, key=lambda u: (order[u["status"]], u["phase"]))


AWAITING = "awaiting approval"


def awaiting(u: dict) -> bool:
    """Finished, but its node asks a person to approve it before anything builds on it."""
    return u.get("status") == "blocked" and str(u.get("notes") or "").startswith(AWAITING)


def _needs_approval(uid: str) -> bool:
    try:
        return bool(settings(uid).get("approval"))
    except (PipelineError, KeyError):
        return False


@locked
def set_status(uid: str, status: str, note: str | None = None, record: bool = True, approved: bool = False) -> dict:
    """record=False puts a unit back where it was (a failed run) without logging it as a new transition. A unit whose
    node sets `approval: true` does not finish on its own: it waits, blocked, until approve()."""
    data = load()
    u = get(data, uid)
    if status == "done" and record and not approved and _needs_approval(uid):
        status, note = "blocked", (f"{AWAITING}: review its pages, then `{cli_cmd()} plan approve {uid}` (or Approve "
                                   "in the portal's Pipeline)") + (f" — {note}" if note else "")
    u["status"] = status
    if status in DONE:
        u.pop("redo", None)
    if status == "done":
        u.pop("refine", None)
    if status == "doing":
        st = {x["id"]: x["status"] for x in data["units"]}
        pending = [d for d in u.get("soft") or [] if st.get(d, "done") not in DONE]
        if pending:
            u["provisional"] = pending           # written without these: reopened to refine when they are done
        else:
            u.pop("provisional", None)
    if record:
        u["updated"] = now()
    if note:
        u["notes"] = note
    reopened = _refine_after(data, uid) if status == "done" else []
    save(data)
    if record and status == "done":
        try:
            drafts.snapshot(uid)              # the AI's version of its pages, to compare with what people confirm
            freshness.stamp_all()             # the pages it wrote reflect today's code
        except Exception:  # noqa: BLE001 — a measurement must never fail closing a unit
            pass
    if record and status in ("done", "blocked", "dropped"):
        WORK.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"- {u['updated']} **{uid}** → {status}" + (f": {note}" if note else "") + "\n")
    if reopened:
        WORK.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            for r in reopened:
                fh.write(f"- {now()} **{r}** → refine (written before {uid})\n")
        return {**u, "reopened": reopened}
    return u


def _refine_after(data: dict, uid: str) -> list[str]:
    """`uid` (an interview) is done: the units drafted without it get it as `refine`. Finished ones are reopened for a
    refine session (like a redo: nothing deleted, checkpoints archived); ones in progress take it into account."""
    stamp, reopened = now(), []
    for w in data["units"]:
        if uid not in (w.get("provisional") or []):
            continue
        w["provisional"] = [d for d in w["provisional"] if d != uid]
        if not w["provisional"]:
            w.pop("provisional")
        if w["status"] == "dropped":
            continue
        w["refine"] = sorted(set(w.get("refine") or []) | {uid})
        if w["status"] == "done":
            w["status"], w["redo"], w["updated"] = "todo", w.get("updated") or stamp, stamp
            _archive_notes(w["id"], stamp)
            reopened.append(w["id"])
    return reopened


def early_draft(u: dict, data: dict) -> bool:
    """Not finished and an interview that feeds it has not happened yet: it is (or will be) a provisional draft."""
    st = {x["id"]: x["status"] for x in data["units"]}
    return u["status"] in ("todo", "doing") and any(st.get(d, "done") not in DONE for d in u.get("soft") or [])


def approve(uid: str, by: str) -> dict:
    u = get(load(), uid)
    if not awaiting(u):
        raise ValueError(f"{uid} is not awaiting approval (it is {u['status']})")
    return set_status(uid, "done", f"approved by {by}", approved=True)


@locked
def add(uid: str, title: str, type_: str = "flow", deps: list[str] | None = None) -> dict:
    data = load()
    if any(u["id"] == uid for u in data["units"]):
        raise ValueError(f"unit {uid} already exists")
    slug = uid.split(":", 1)[1] if ":" in uid else uid
    nu = unit(uid, type_, deps if deps is not None else (["flows-catalog"] if type_ == "flow" else []), slug=slug, title=title)
    data["units"].append(nu)
    save(data)
    sync()
    return nu


@locked
def ensure(uid: str, type_: str, title: str | None = None) -> dict:
    """Add a dynamic unit, or put it back to todo if it was done (e.g. new review feedback arrived)."""
    data = load()
    for u in data["units"]:
        if u["id"] == uid:
            if u["status"] in DONE:
                u["status"], u["updated"] = "todo", now()
                save(data)
            return u
    nu = unit(uid, type_, [], title=title)
    data["units"].append(nu)
    save(data)
    return nu


def dependents(data: dict, uid: str) -> list[dict]:
    """Finished units built on `uid`, directly or through other units (plan order): what a redo may leave outdated."""
    found, frontier = set(), {uid}
    while frontier:
        frontier = {u["id"] for u in data["units"]
                    if u["id"] not in found and frontier & set(u["deps"] + (u.get("soft") or []))}
        found |= frontier
    return [u for u in data["units"] if u["id"] in found and u["status"] == "done"]


@locked
def redo(uid: str, also: list[str] | tuple = ()) -> list[dict]:
    """Reopen a finished unit (and the chosen dependents) for a review-and-update session: nothing is deleted,
    the old checkpoints are archived and `redo` keeps when it was finished so the prompt can say so."""
    data = load()
    targets = [get(data, i) for i in dict.fromkeys([uid, *also])]
    for u in targets:
        if u["status"] != "done":
            raise ValueError(f"{u['id']} is {u['status']}, not done — only finished units can be redone")
    stamp = now()
    for u in targets:
        u["status"], u["redo"], u["updated"] = "todo", u.get("updated") or stamp, stamp
        _archive_notes(u["id"], stamp)
    save(data)
    WORK.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        for u in targets:
            fh.write(f"- {stamp} **{u['id']}** → redo (was done {u['redo']})\n")
    return targets


UNITS_DIR = WORK / "units"


def _archive_notes(uid: str, stamp: str) -> None:
    """A reopened unit starts a fresh checkpoint file; the old one stays next to it for the prompt to point at."""
    f = note_file(uid)
    if f.exists():
        f.rename(f.with_name(f"{f.stem}.before-redo-{stamp.replace(':', '')}.md"))


def note_file(uid: str) -> Path:
    return UNITS_DIR / (uid.replace(":", "__").replace("/", "_") + ".md")


def handoff_file(uid: str) -> Path:
    """Where a unit that runs in its own worktree leaves its handoff; integration folds it into handoff.md."""
    f = note_file(uid)
    return f.with_name(f"{f.stem}.handoff.md")


def _at(path: Path) -> str:
    """Any path as seen from the workspace, where agents run."""
    return Path(os.path.relpath(path, WORKSPACE)).as_posix()


def old_notes(uid: str) -> list[Path]:
    """Checkpoints of earlier runs of a redone unit, oldest first."""
    f = note_file(uid)
    return sorted(f.parent.glob(f"{f.stem}.before-redo-*.md")) if f.parent.exists() else []


def note(uid: str, text: str) -> Path:
    """Checkpoint: append a timestamped line to the unit's notes so a closed session can be resumed."""
    f = note_file(uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        f.write_text(f"# Checkpoints — {uid}\n\n", encoding="utf-8")
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} {text.strip()}\n")
    return f


def last_note(uid: str) -> str:
    f = note_file(uid)
    if not f.exists():
        return ""
    lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    return lines[-1][2:] if lines else ""


def progress(data: dict | None = None) -> tuple[int, int]:
    data = data or load()
    live = [u for u in data["units"] if u["status"] != "dropped"]
    return sum(1 for u in live if u["status"] == "done"), len(live)


def next_step(data: dict | None = None, review: int = 0) -> dict:
    """What to do next, one rule for the wizard's default and the desktop app's Summary: finish the agent unit left
    half done, else the next ready unit, else the `review` pages waiting for a person, else nothing left."""
    data = data or load()
    brief = lambda u: {k: u[k] for k in ("id", "title", "runner", "type")}     # noqa: E731
    doing = [u for u in data["units"] if u["status"] == "doing" and u["runner"] == "agent"]
    if doing:
        return {"kind": "resume", "unit": brief(doing[0])}
    ready = [u for u in available(data) if u["status"] != "doing"]
    if ready:
        return {"kind": "next", "unit": brief(ready[0])}
    return {"kind": "review", "count": review} if review else {"kind": "done"}


def render(data: dict | None = None) -> str:
    data = data or load()
    icon = {"todo": "·", "doing": "▶", "done": "✔", "blocked": "✖", "dropped": "—"}
    ready = {u["id"] for u in available(data)}
    lines, phase = [], None
    for u in sorted(data["units"], key=lambda u: u["phase"]):   # stable: blueprint order within a phase
        if u["phase"] != phase:
            phase = u["phase"]
            lines.append(f"\nPhase {phase}")
        mark = ((" ← ready" if u["id"] in ready and u["status"] == "todo" else "")
                + (" ↻ refine" if u.get("refine") else " ↻ redo" if u.get("redo") else "")
                + (" ✎ draft (before its interview)" if early_draft(u, data) else ""))
        note = f"  ({u['notes']})" if u.get("notes") else ""
        lines.append(f"  {icon[u['status']]} {u['id']:<28} {u['title']}{mark}{note}")
    d, t = progress(data)
    return f"Progress: {d}/{t} units done" + "\n".join(lines)


# ---------- session prompts ----------
def prompt(uid: str, lang: str = "es", unattended: bool = False) -> str:
    from . import env                    # lazy: env imports plan
    env.sync_kit_docs()                  # the session reads the project's PLAYBOOK copy: bring it up to this kit
    data = load()
    u = get(data, uid) if uid != "update" else {"id": "update", "title": "Incremental update", "type": "update", "phase": "-"}
    cli = cli_cmd()
    section = TYPES.get(u["type"], (0, "", "", "update"))[3]
    talk = "Spanish" if lang == "es" else "English"
    ask = ("This is an unattended run: never ask questions; append them to docs/interview/open-questions.md."
           if unattended else
           f"When the unit is done, show the user `{cli} plan next` and ask what to do next (offer: continue with the next "
           "unit in this session only if your context is still light, otherwise recommend starting a new session from the "
           f"Camarón wizard: `{cli}`).")
    resume = ""
    notes = note_file(u["id"])
    if u.get("status") == "doing" or notes.exists():
        rel = ws_rel(rel_file(notes))
        resume = (f"\nRESUME — a previous session already worked on this unit and was closed before finishing. Do NOT start over:\n"
                  f"read its checkpoints in `{rel}`" + (f" (last: {last_note(u['id'])})" if last_note(u["id"]) else "") +
                  f", look at `git status` / `git diff` in `{ws_rel('.')}` for work that was written but not committed, "
                  "check which of the unit's output files already exist, and continue from there.\n")
    st = {x["id"]: x["status"] for x in data.get("units", [])}
    pending = [d for d in u.get("soft") or [] if st.get(d, "done") not in DONE]
    provisional = ""
    if pending:
        tags = " / ".join(f"`- [ ] (YYYY-MM-DD, {d.split('-', 1)[1]} · {u['id']}) <question> — <evidence>`" for d in pending)
        provisional = (f"\nPROVISIONAL — {', '.join(f'`{d}`' for d in pending)} has not happened yet. Do not wait for it: write "
                       "from the code and the discovery notes (`docs/interview/discovery/`) and never invent business intent, "
                       "names or decisions. Mark what you infer `TODO(question)` and add every question for that interview "
                       f"to `docs/interview/open-questions.md` as {tags}. ADRs stay `proposed`. When the "
                       "interview is done this unit is reopened to refine it.\n")
    refine_txt = ""
    if u.get("refine"):
        names = ", ".join(f"`{d}`" for d in u["refine"])
        refine_txt = (f"\nREFINE — this unit was written before {names}, which is done now. Do NOT start over and do not "
                      "rewrite pages a human confirmed without saying so: read what the interview recorded (the dated files "
                      "in `docs/interview/` for it, and the answered items of `docs/interview/open-questions.md`) and this "
                      "unit's outputs, then change only what the interview corrects or completes — resolve the "
                      "`TODO(question)` it answers, use the agreed terms, fix wrong assumptions. List what is still open "
                      "in the handoff.\n")
    redo_txt = ""
    if u.get("redo") and not u.get("refine"):
        olds = old_notes(u["id"])
        later = [d["id"] for d in dependents(data, u["id"])]
        interview = ("For an interview: show the user what `docs/interview/` already records for this unit and ask what changed "
                     "or was missing; write the new round to a new `docs/interview/<YYYY-MM-DD>-<unit>.md` (keep the old "
                     "file), close any answered item of `docs/interview/open-questions.md`, and update the pages that used "
                     "the old answers.\n") if u.get("type") in INTERVIEW_TYPES else ""
        redo_txt = (f"\nREDO — this unit was finished on {str(u['redo'])[:10]} and the user asked to go over it again. Do NOT "
                    "start from scratch and do not delete earlier work: read what it produced (its outputs per the playbook "
                    "section, the handoff" + (f", the previous checkpoints in `{ws_rel(rel_file(olds[-1]))}`" if olds else "") +
                    "), show the user what is there, find what is wrong, missing or has changed since, and update those files.\n"
                    + interview +
                    ("Units already finished on top of this one: " + ", ".join(f"`{i}`" for i in later) + ". If your changes "
                     "make any of them outdated, say which and why in the handoff's pending list (the user can redo them "
                     f"with `{cli} plan redo <unit>`).\n" if later else ""))
    extra = ""
    if u.get("type") == "review-fixes":
        extra = (f"\nInput: `{ws_rel('docs/.work/review-feedback.md')}` — every `- [ ]` line is a human review comment on a page. Apply each one "
                 "(verify against the code; if the human is right, fix the page; if the code says otherwise, explain it in the "
                 "page and ask the user), then tick it `- [x]` adding a short note of what changed.\n")
    elif u.get("type") == "doc-fixes":
        extra = (f"\nInput: run `{cli} check` and `{cli} status`. Fix every ERROR, orphaned `x-sources`, `needs-reconfirm` "
                 "pages (re-verify them against the code and summarise the change for the human — never write `x-confirmed`), "
                 f"outdated/missing translations (then `{cli} translated <files>`), generated-block WARNs (`{cli} blocks`) "
                 "and structure WARNs (CONVENTIONS §11). "
                 f"Finish with `{cli} llms` and a clean `check`.\n")
    elif u.get("type") in INTERVIEW_TYPES and docs.interview_mode() == "team":
        qdir = ws_rel("docs/interview/questionnaire")
        extra = (f"\nTEAM MODE — do not interview anyone: the team already answered a questionnaire. Input: "
                 f"`{qdir}/questionnaire.yaml` (this unit's questions are those with topic `{u['type'].split('-', 1)[1]}`) "
                 f"and every `{qdir}/responses/*.yaml` (one per person). `{cli} interview status` lists who answered, "
                 "what nobody answered and where people disagree. Consolidate the answers as the playbook section "
                 "\"interview\" (team mode) says: agreed answers to the dated interview file, citing who said what; "
                 "disagreements and unanswered questions to `docs/interview/open-questions.md`.\n")
    if u.get("type") in INTERVIEW_TYPES:
        topic = u["type"].split("-", 1)[1]
        extra += (f"\nDRAFT QUESTIONS — other units may already have drafted pages from the code without this interview. "
                  f"Start from the open items tagged `{topic} ·` in `docs/interview/open-questions.md`: they are concrete "
                  "questions grounded in the code. Tick each one you get answered (`- [x]`, with the answer or a pointer "
                  "to the dated interview file); finishing this unit reopens those drafts to refine them.\n")
    guidance = plugin_guidance(uid)
    extra += guidance
    in_tree = CTX.root != CTX.state_root          # a parallel unit in its own worktree of cam-docs
    if in_tree:                     # this exact kit: an older `camaron` on PATH would not find the shared plan
        cli = f'"{which("uv") or "uv"}" run --quiet --script "{KIT / "camarones.py"}"'
    layout = (f"\nLayout: you run in the workspace folder. This unit writes its docs in `{ws_rel('.')}/`, a private copy "
              f"of `{CAM_DIR}/` on its own branch: every `docs/…` or `.camarones/…` path in the playbook is relative to it. "
              f"Other units are working in parallel; the shared plan and handoff stay in `{CAM_DIR}/`, and the `{cli}` "
              "commands below reach them. Never edit files in another unit's folder or in "
              f"`{CAM_DIR}/docs/` directly, and do not commit: the kit commits and merges your folder when you are done. "
              "The service repos are siblings (`<repo>/`); never write kit files into them.\n") if in_tree else (
              f"\nLayout: you run in the workspace folder. Docs and agent config live in `{CAM_DIR}/` (its own git repo; every "
              f"`docs/…` or `.camarones/…` path in the playbook is relative to it); the service repos are its siblings (`<repo>/`). "
              "Never write kit files into the service repos.\n") if CAM_LAYOUT else (
              "\nLayout: this project uses the older single-folder layout — its docs are `docs/` and `.camarones/` of "
              f"this folder ({ROOT}). Ignore the playbook's `{CAM_DIR}/` prefix and any other `{CAM_DIR}/` folder you see.\n")
    sections = ("objective, Verified (with evidence), Not verified / assumptions, Commands run, decisions, remaining, "
                "Next action, files to read first next time")
    finish = (f"""write your handoff ({sections}) to
   `{_at(handoff_file(u['id']))}`, run `{cli} check` and fix what it reports on your pages, then
   `{cli} plan done {u['id']} --note "<one line>"` (or `plan block … --note "why"`).""" if in_tree else
              f"""`{cli} plan done {u['id']} --note "<one line>"` (or `plan block … --note "why"`), rewrite the
   "Last session" section of `{_at(HANDOFF)}` ({sections}),
   run `{cli} check` and `{cli} checkpoint "{u['id']}"` (local commit of the docs so nothing is lost).""")
    return f"""Camarón session — unit `{u['id']}`: {u['title']}
{redo_txt}{refine_txt}{resume}{provisional}{extra}{layout}
You are documenting this project with the Camarón kit (works the same in Claude Code and Codex).
1. Read `{ws_rel('.camarones/PLAYBOOK.md')}` → sections "Session protocol" and "{section}", and `{ws_rel('.camarones/CONVENTIONS.md')}` (binding).
2. Read `{_at(HANDOFF)}` (what previous sessions did and left pending). Do not redo finished work.
3. Run `{cli} plan start {u['id']}`, then do ONLY this unit, as deep as the playbook asks. The CLI is `{cli}`
   (`{cli} help` lists commands). Write docs in English; talk to the user in {talk}.
   Save progress as you go (the user may close the session at any time): after each significant step run
   `{cli} plan note {u['id']} "<what is done / what is next>"` and write findings to their files immediately.
4. Write for agents first, people second (CONVENTIONS §11): start each page from its skeleton in
   `{ws_rel('.camarones/skeletons/')}`; `> **TL;DR:** …` under the H1; every `##` section reads alone (no "see above");
   exact identifiers in backticks; tables for facts, commands in fenced blocks; evidence next to the claim; unknown →
   `TODO(question): …`. `{cli} check` must show no structure WARN on your pages before you finish.
5. Finish: {finish}
6. {ask}
"""


# ---------- autopilot ----------
INTERVIEW_TYPES = {"interview-context", "interview-language", "interview-history"}
AUTOPILOT_PROMPT = WORK / "autopilot-prompt.md"
_RUN: ContextVar[tuple[EventLog, str] | None] = ContextVar("autopilot_run", default=None)


@contextlib.contextmanager
def recording(log: EventLog, run_id: str):
    """Within this block, agent sessions and autopilot steps are written to `log` under `run_id`."""
    token = _RUN.set((log, run_id))
    try:
        yield
    finally:
        _RUN.reset(token)


def _emit(kind: str, **fields) -> None:
    cur = _RUN.get()
    if cur:
        cur[0].emit(kind, run=cur[1], **fields)


def _autopilot_log(text: str, echo=print) -> None:
    echo(f"[{dt.datetime.now():%H:%M}] {text}")
    WORK.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"- {now()} [autopilot] {text.strip()}\n")


def _short(s, n: int = 110) -> str:
    s = str(s or "").replace(str(WORKSPACE), "").replace("\\\\", "\\").strip().lstrip("\\/")
    s = s.splitlines()[0] if s else ""
    return s if len(s) <= n else s[:n - 1] + "…"


def _render(agent: str, line: str) -> tuple[list[str], str]:
    """One line of the agent's JSON event stream → (progress lines to show, error/result text for limit checks)."""
    return _show(_runner(agent)[0].parse(line))


def _runner(target: str):
    """A routing target (`codex` or `codex:o5`) → (its runner, the model to ask for)."""
    route = routing.parse(target)
    return runners.get(route.runner), route.model


def _agents(log, tier: str = "agentic-heavy", runner: str | None = None, allow_local: bool = False) -> list[str]:
    """Installed targets for a tier in routing order (defaults: claude, then codex), or for the one runner a
    pipeline node asks for."""
    routes = {tier: [runner]} if runner else routing.table(docs.workspace(), load_json(PREFS, {}))
    keep, notes = routing.candidates(tier, routes, allow_local)
    out = []
    for r in keep:
        try:
            runner = runners.get(r.runner)
        except KeyError:
            notes.append(f"{r}: unknown runner")
            continue
        if which(runner.command or runner.id):
            out.append(str(r))
    for n in notes:
        log(f"Routing: {n}")
    return out


def _show(events: list[dict]) -> tuple[list[str], str]:
    shown, err = [], ""
    for ev in events:
        kind, text = ev["type"], ev.get("text")
        if kind == "tool.call":
            shown.append(f"· {ev['name']}" + ("" if ev["arg"] is None else f" {_short(ev['arg'])}"))
        elif kind == "file.changed":
            shown.append(f"· edit {_short(ev['path'])}")
        elif kind == "log" and ev.get("raw"):
            shown += [_short(text, 140)] if text.strip() else []
            err = text
        elif kind == "log":
            shown.append(f"» {_short(text, 130)}")
        elif kind == "error":
            shown.append(f"= error: {_short(text, 130)}")
            err = text
        elif kind == "result":
            err = text
    return shown, err


def _run_agent(agent: str, text: str, lang: str, uid: str, echo=print, *, prompt_file: Path | None = None,
               env: dict | None = None, emit=None, on_start=None) -> subprocess.CompletedProcess:
    """Run one unattended session, streaming a compact view of what the agent does, plus a heartbeat with
    the unit's last checkpoint when it goes quiet. The returned stdout holds the error/result text only.
    The parallel scheduler gives each unit its own prompt file, env (its worktree) and event sink."""
    emit = emit or _emit
    prompt_file = prompt_file or AUTOPILOT_PROMPT
    # multi-line args do not survive Windows .cmd shims: hand over a one-line pointer to the prompt file
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(text, encoding="utf-8")
    brief = _at(prompt_file)
    short = f"Follow the instructions in {brief}" if lang == "en" else f"Sigue las instrucciones de {brief}"
    # pin the project: the agent's own `camarones …` calls must hit this plan, whatever folder it cds into
    runner, model = _runner(agent)
    inv = runner.build(RunRequest(prompt=short, cwd=WORKSPACE,
                                  env={**os.environ, "CAMARONES_ROOT": str(ROOT), **(env or {})}, model=model))
    cmd = inv.argv
    start = last = time.monotonic()
    seen_note = last_note(uid)
    stop = threading.Event()

    def heartbeat() -> None:
        nonlocal seen_note
        while not stop.wait(30):
            if time.monotonic() - last < 60:
                continue
            ckpt = last_note(uid)
            extra = f" — checkpoint: {_short(ckpt, 100)}" if ckpt and ckpt != seen_note else ""
            seen_note = ckpt or seen_note
            echo(f"  … {int((time.monotonic() - start) // 60)} min on {uid}, {agent} still working{extra}")

    tail: list[str] = []
    try:
        p = subprocess.Popen(cmd, cwd=str(inv.cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,
                             env=inv.env)
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, str(e), "")
    if on_start:
        on_start(p)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        for line in p.stdout:
            events = runner.parse(line.rstrip("\n"))
            for ev in events:
                emit(ev["type"], unit=uid, runner=agent, **{k: v for k, v in ev.items() if k != "type"})
            shown, err = _show(events)
            for s in shown:
                echo(f"  {s}")
            if shown:
                last = time.monotonic()
            if err:
                tail = (tail + [err])[-20:]
        rc = p.wait()
    finally:
        stop.set()
        if p.poll() is None:
            p.kill()
    echo(f"  ({int((time.monotonic() - start) // 60)} min)")
    return subprocess.CompletedProcess(cmd, rc, "\n".join(tail), "")


def run_autopilot(lang: str = "es", max_units: int | None = None, poll_seconds: int = 900,
                  include_interviews: bool = False, echo=print) -> int:
    """Run ready units back to back, one fresh unattended session each, switching between Claude Code and
    Codex when one hits its usage limit and waiting while both are limited. Returns units completed.
    Every run is recorded in .camarones/.cache/runs/<run>/events.jsonl."""
    agents = _agents(lambda t: _autopilot_log(t, echo))
    if not agents:
        _autopilot_log("Autopilot: no agent from the agentic-heavy routing is installed (default: `claude`, `codex`) "
                       "— nothing to run.", echo)
        return 0
    from .harness.locks import FileLock, LockBusy
    from .harness.scheduler import RUN_LOCK
    lock = FileLock(RUN_LOCK, wait=0, info={"what": "autopilot"})
    try:
        lock.acquire()
    except LockBusy as e:
        _autopilot_log(f"Autopilot: another documentation run is in progress (pid {e.holder.get('pid')}) — nothing "
                       "started.", echo)
        return 0
    try:
        return _recorded_autopilot(agents, lang, max_units, poll_seconds, include_interviews, echo)
    finally:
        lock.release()


def _recorded_autopilot(agents, lang, max_units, poll_seconds, include_interviews, echo) -> int:
    run_id = f"r-{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    with recording(EventLog(CTX.runs / run_id / "events.jsonl"), run_id):
        _emit("run.started", agents=agents, max_units=max_units)
        try:
            with awake.keep_awake():           # a laptop that sleeps mid-session breaks the agent's connection
                done = _autopilot(agents, lang, max_units, poll_seconds, include_interviews, echo)
        except BaseException:                  # Ctrl+C or a crash: the log must still say the run ended
            _emit("run.finished", interrupted=True)
            kpis.record_run(run_id)
            raise
        _emit("run.finished", done=done)
    kpis.record_run(run_id)
    return done


def _autopilot(agents: list[str], lang: str, max_units: int | None, poll_seconds: int, include_interviews: bool,
               echo) -> int:
    log = lambda t: _autopilot_log(t, echo)                                    # noqa: E731
    # team interviews only consolidate written answers: nothing to ask, so they can run unattended
    skip = set() if include_interviews or docs.interview_mode() == "team" else INTERVIEW_TYPES
    limited: dict[str, dt.datetime] = {}
    noted: set[str] = set()

    def log_once(text: str) -> None:           # routing notes once per run, not once per unit
        if text not in noted:
            noted.add(text)
            log(text)
    done = 0
    for problem in pipeline_problems():
        log(f"pipeline.yaml: {problem} — the plan is used as it was")
    log(f"Autopilot started with {', '.join(agents)}" + (f" (max {max_units} units)" if max_units else ""))
    while max_units is None or done < max_units:
        data = sync()
        ready = available(data)
        queue = [u for u in ready if u["runner"] == "agent" and u["type"] not in skip]
        if not queue:
            wizard = [u["id"] for u in ready if u["runner"] == "wizard"]
            interviews = [u["id"] for u in ready if u["type"] in skip]
            if wizard or interviews:
                why = ([f"wizard step(s) {', '.join(wizard)} (run `{cli_cmd()}`)"] if wizard else []) + \
                      ([f"interview(s) {', '.join(interviews)} (need you, in an interactive session)"] if interviews else [])
                log(f"Autopilot stopped: what is left needs you — {'; '.join(why)}. Then start autopilot again.")
            else:
                d, t = progress(data)
                log(f"Autopilot stopped: nothing ready — {d}/{t} units done "
                    "(finished, or waiting on blocked units / docs/interview/open-questions.md).")
            return done
        u = queue[0]
        s = settings(u["id"])
        targets = _agents(log_once, s["tier"], s.get("runner"), bool(s.get("allow_local")))
        if not targets:
            log(f"Autopilot stopped: no installed agent can run {u['id']} ({s.get('runner') or s['tier']}).")
            return done
        free = [a for a in targets if limited.get(a, dt.datetime.min) <= dt.datetime.now()]
        if not free:
            soonest = min(limited[a] for a in targets)
            wait = max(60, min(poll_seconds, int((soonest - dt.datetime.now()).total_seconds())))
            log(f"All agents are at their usage limit — retrying in {wait // 60} min "
                f"(machine must stay on; Ctrl+C to stop, progress is saved).")
            time.sleep(wait)
            continue
        agent = free[0]
        log(f"{agent} → {u['id']}: {u['title']}")
        _emit("unit.started", unit=u["id"], runner=agent)
        started = time.monotonic()
        r = _run_agent(agent, prompt(u["id"], lang=lang, unattended=True), lang, u["id"], echo)
        output = f"{r.stdout or ''}\n{r.stderr or ''}"
        outcome = _runner(agent)[0].classify(r.returncode, output)
        status = get(load(), u["id"])["status"]
        _emit("unit.finished", unit=u["id"], runner=agent, outcome=outcome, rc=r.returncode, status=status,
              seconds=round(time.monotonic() - started, 1))
        if outcome == "ok":
            log(f"{agent} finished {u['id']} (status: {status})")
            if status in ("todo", "doing"):
                log(f"Autopilot stopped: {u['id']} ended without `plan done`/`plan block` — check its checkpoints "
                    f"in {ws_rel(rel_file(note_file(u['id'])))} before continuing.")
                return done
            done += 1
            continue
        if outcome == "limited":
            limited[agent] = dt.datetime.now() + dt.timedelta(seconds=poll_seconds)
            others = [a for a in targets if limited.get(a, dt.datetime.min) <= dt.datetime.now()]
            log(f"{agent} hit its usage limit" + (f" — switching to {others[0]}" if others else ""))
            continue
        log(f"Autopilot stopped: {agent} failed on {u['id']} (exit {r.returncode}). Last output:\n"
            + output.strip()[-1500:])
        return done
    log(f"Autopilot stopped: reached the limit of {max_units} unit(s).")
    return done
