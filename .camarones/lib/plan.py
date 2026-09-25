"""Work plan: the documentation job split into session-sized units, persisted in docs/.work/plan.yaml.

Each unit is small enough for one agent session (fresh context). Agents and the wizard use:
  plan sync   (re)build units from workspace.yaml, keeping statuses
  plan next   units whose dependencies are done
  plan start/done/block/drop/add
and docs/.work/handoff.md carries the baton between sessions.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import yaml

from .common import ROOT, WORK, CAM_LAYOUT, CAM_DIR, WORKSPACE, cli_cmd, ws_rel, rel_file, IS_WIN, which
from . import docs

PLAN = WORK / "plan.yaml"
HANDOFF = WORK / "handoff.md"
LOG = WORK / "log.md"
DONE = ("done", "dropped")
NO_WIKI = "No wiki for this repo (wizard → Wikis → choose repos)"
LIVE_INTERVIEWS = "Interviews are done live, not by team questionnaire"

# unit type → (phase, runner, title template, playbook section)
TYPES = {
    "quick-overview":   (2, "agent", "First overview: purpose, run instructions, one flow and sources", "quick-overview"),
    "setup":            (0, "wizard", "Environment ready (tools, repos, agent wiring)", "setup"),
    "discovery":        (1, "agent",  "Discovery of {repo}", "discovery"),
    "discovery-cross":  (1, "agent",  "Cross-repo correlation (integrations, shared DBs, candidate flows)", "discovery-cross"),
    "questionnaire":    (2, "agent",  "Team questionnaire: inferred answers and options to share with the team", "questionnaire"),
    "answers":          (2, "wizard", "Team answers: share the questionnaire and import the answers", "answers"),
    "interview-context":  (2, "agent", "Interview 1: bounded contexts, external actors, environments", "interview"),
    "interview-language": (2, "agent", "Interview 2: DDD glossary, SLAs / NFRs", "interview"),
    "interview-history":  (2, "agent", "Interview 3: historical decisions, known debt, validate integrations/flows/data", "interview"),
    "repo-brief":       (3, "agent",  "{repo}: README + AGENTS.md/CLAUDE.md (stack) + C4 components + OpenWiki brief", "repo-brief"),
    "repo-wiki":        (3, "agent",  "{repo}: OpenWiki repository wiki", "repo-wiki"),
    "arch-system":      (4, "agent",  "C4 system: context + containers views", "arch-system"),
    "domain":           (4, "agent",  "Domain: bounded contexts, context map, glossary, actors", "domain"),
    "data":             (4, "agent",  "Data models: ERDs, ownership, shared DBs", "data"),
    "deployment":       (4, "agent",  "Deployment: environments + C4 deployment views", "deployment"),
    "decisions-quality": (4, "agent", "ADRs, SLAs, tech debt", "decisions-quality"),
    "security-review":  (5, "agent",  "[beta] Security review: threats and vulnerabilities", "security-review"),
    "architecture-review": (5, "agent", "[beta] Architecture review: coupling, duplication, tech debt", "architecture-review"),
    "flows-catalog":    (5, "agent",  "Business flows catalog (propose, validate, create flow units)", "flows-catalog"),
    "flow":             (5, "agent",  "Flow: {slug}", "flow"),
    "i18n":             (6, "agent",  "Spanish translations + index", "i18n"),
    "portal":           (7, "wizard", "Build and run the portal", "portal"),
    "ci":               (7, "wizard", "CI pipelines (umbrella + per-repo snippets)", "ci"),
    "confirm":          (7, "wizard", "Human review: confirm pages", "confirm"),
    "handover":         (7, "agent",  "Handover: summary, commits on branches, next steps", "handover"),
    "review-fixes":     (7, "agent",  "Apply human review feedback", "review-fixes"),
    "doc-fixes":        (7, "agent",  "Fix documentation problems (check errors, orphans, re-confirmations, translations)", "doc-fixes"),
}


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


def save(data: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    PLAN.write_text("# Camarón work plan — one unit per agent session. Managed by the camarones CLI.\n"
                    + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


def unit(uid: str, type_: str, deps: list[str], repo: str | None = None, slug: str | None = None, title: str | None = None) -> dict:
    phase, runner, tpl, section = TYPES[type_]
    return {"id": uid, "type": type_, "phase": phase, "runner": runner,
            "title": title or tpl.format(repo=repo or "", slug=slug or ""), "status": "todo",
            "deps": deps, "repo": repo, "notes": "", "updated": None}


def blueprint(repos: list[str]) -> list[dict]:
    disc = [f"discovery:{r}" for r in repos]
    briefs = [f"repo-brief:{r}" for r in repos]
    wikis = [f"repo-wiki:{r}" for r in repos]
    if docs.workspace()['project'].get('profile') == 'quick':
        return [unit('setup', 'setup', []),
                *[unit(f'discovery:{r}', 'discovery', ['setup'], repo=r) for r in repos],
                unit('quick-overview', 'quick-overview', disc),
                unit('portal', 'portal', ['quick-overview']),
                unit('confirm', 'confirm', ['quick-overview']),
                unit('handover', 'handover', ['portal', 'confirm'])]
    u = [unit("setup", "setup", [])]
    u += [unit(f"discovery:{r}", "discovery", ["setup"], repo=r) for r in repos]
    u += [unit("discovery-cross", "discovery-cross", disc)]
    first_interview = ["discovery-cross"]
    if docs.interview_mode() == "team":      # the team answers a questionnaire; the interview units consolidate it
        u += [unit("questionnaire", "questionnaire", ["discovery-cross"]),
              unit("answers", "answers", ["questionnaire"])]
        first_interview = ["answers"]
    u += [unit("interview-context", "interview-context", first_interview),
          unit("interview-language", "interview-language", ["interview-context"]),
          unit("interview-history", "interview-history", ["interview-context"])]
    for r in repos:
        u += [unit(f"repo-brief:{r}", "repo-brief", ["interview-context"], repo=r),
              unit(f"repo-wiki:{r}", "repo-wiki", [f"repo-brief:{r}"], repo=r)]
    u += [unit("arch-system", "arch-system", briefs),
          unit("domain", "domain", ["interview-language"]),
          unit("data", "data", ["discovery-cross", "interview-history"]),
          unit("deployment", "deployment", ["arch-system"]),
          unit("decisions-quality", "decisions-quality", ["interview-history"]),
          unit("flows-catalog", "flows-catalog", ["arch-system", "interview-history"]),
          unit("i18n", "i18n", ["domain", "flows-catalog"]),
          unit("portal", "portal", ["arch-system"]),
          unit("ci", "ci", ["setup"]),
          unit("confirm", "confirm", ["domain", "decisions-quality", "flows-catalog"]),
          unit("handover", "handover", ["i18n", "portal", "confirm", *wikis])]
    return u


def sync() -> dict:
    """Merge the blueprint into the stored plan: keep statuses/notes, add units for new repos, drop removed repos."""
    data = load()
    old_profile = data.get('profile', 'full')
    profile = docs.workspace()['project'].get('profile', 'full')
    repos = docs.repo_names()
    existing = {u["id"]: u for u in data["units"]}
    merged = []
    for bu in blueprint(repos):
        cur = existing.pop(bu["id"], None)
        if cur:
            bu.update({k: cur[k] for k in ("status", "notes", "updated", "redo") if k in cur})
            if cur.get("status") == "dropped" and bu.get("repo") in repos:
                bu["status"] = "todo"
            if cur.get('notes') == 'Not part of the selected profile':
                bu['status'], bu['notes'] = 'todo', ''
            if old_profile != profile and bu['id'] in ('setup', 'portal', 'confirm', 'handover'):
                bu['status'] = 'todo'
        merged.append(bu)
    for leftover in existing.values():     # dynamic units (flows, splits) or units of removed repos
        if profile == 'quick' and leftover['type'] not in ('flow', 'doc-fixes', 'review-fixes') and leftover['status'] == 'todo':
            leftover['status'], leftover['notes'] = 'dropped', 'Not part of the selected profile'
        if leftover.get("repo") and leftover["repo"] not in repos:
            leftover["status"] = "dropped"
        merged.append(leftover)
    # flows must finish before i18n/confirm consider flows complete
    flow_ids = [u["id"] for u in merged if u["type"] == "flow" and u["status"] != "dropped"]
    for u in merged:
        if u["id"] in ("i18n", "confirm"):
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


def get(data: dict, uid: str) -> dict:
    for u in data["units"]:
        if u["id"] == uid:
            return u
    raise KeyError(f"unknown unit '{uid}' — see `{cli_cmd()} plan`")


def available(data: dict | None = None) -> list[dict]:
    data = data or load()
    st = {u["id"]: u["status"] for u in data["units"]}
    deps = {u["id"]: u["deps"] for u in data["units"]}

    def waits_on(u: dict) -> list[str]:
        if not u.get("redo"):
            return u["deps"]
        up, frontier = set(), set(u["deps"])     # a reopened unit also waits for a redo further up its chain
        while frontier:
            up |= frontier
            frontier = {d for f in frontier for d in deps.get(f, [])} - up
        return list(up)
    ready = [u for u in data["units"] if u["status"] in ("todo", "doing", "blocked")
             and all(st.get(d, "done") in DONE for d in waits_on(u))]
    order = {"doing": 0, "todo": 1, "blocked": 2}
    return sorted(ready, key=lambda u: (order[u["status"]], u["phase"]))


def set_status(uid: str, status: str, note: str | None = None, record: bool = True) -> dict:
    """record=False puts a unit back where it was (a failed run) without logging it as a new transition."""
    data = load()
    u = get(data, uid)
    u["status"] = status
    if status in DONE:
        u.pop("redo", None)
    if record:
        u["updated"] = now()
    if note:
        u["notes"] = note
    save(data)
    if record and status in ("done", "blocked", "dropped"):
        WORK.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"- {u['updated']} **{uid}** → {status}" + (f": {note}" if note else "") + "\n")
    return u


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
        frontier = {u["id"] for u in data["units"] if u["id"] not in found and frontier & set(u["deps"])}
        found |= frontier
    return [u for u in data["units"] if u["id"] in found and u["status"] == "done"]


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
        f = note_file(u["id"])
        if f.exists():
            f.rename(f.with_name(f"{f.stem}.before-redo-{stamp.replace(':', '')}.md"))
    save(data)
    WORK.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        for u in targets:
            fh.write(f"- {stamp} **{u['id']}** → redo (was done {u['redo']})\n")
    return targets


UNITS_DIR = WORK / "units"


def note_file(uid: str) -> Path:
    return UNITS_DIR / (uid.replace(":", "__").replace("/", "_") + ".md")


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


def render(data: dict | None = None) -> str:
    data = data or load()
    icon = {"todo": "·", "doing": "▶", "done": "✔", "blocked": "✖", "dropped": "—"}
    ready = {u["id"] for u in available(data)}
    lines, phase = [], None
    for u in sorted(data["units"], key=lambda u: u["phase"]):   # stable: blueprint order within a phase
        if u["phase"] != phase:
            phase = u["phase"]
            lines.append(f"\nPhase {phase}")
        mark = (" ← ready" if u["id"] in ready and u["status"] == "todo" else "") + (" ↻ redo" if u.get("redo") else "")
        note = f"  ({u['notes']})" if u.get("notes") else ""
        lines.append(f"  {icon[u['status']]} {u['id']:<28} {u['title']}{mark}{note}")
    d, t = progress(data)
    return f"Progress: {d}/{t} units done" + "\n".join(lines)


# ---------- session prompts ----------
def prompt(uid: str, lang: str = "es", unattended: bool = False) -> str:
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
    redo_txt = ""
    if u.get("redo"):
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
                 f"and outdated/missing translations (then `{cli} translated <files>`). Finish with `{cli} llms` and a clean `check`.\n")
    layout = (f"\nLayout: you run in the workspace folder. Docs and agent config live in `{CAM_DIR}/` (its own git repo; every "
              f"`docs/…` or `.camarones/…` path in the playbook is relative to it); the service repos are its siblings (`<repo>/`). "
              "Never write kit files into the service repos.\n") if CAM_LAYOUT else (
              "\nLayout: this project uses the older single-folder layout — its docs are `docs/` and `.camarones/` of "
              f"this folder ({ROOT}). Ignore the playbook's `{CAM_DIR}/` prefix and any other `{CAM_DIR}/` folder you see.\n")
    return f"""Camarón session — unit `{u['id']}`: {u['title']}
{redo_txt}{resume}{extra}{layout}
You are documenting this project with the Camarón kit (works the same in Claude Code and Codex).
1. Read `{ws_rel('.camarones/PLAYBOOK.md')}` → sections "Session protocol" and "{section}", and `{ws_rel('.camarones/CONVENTIONS.md')}` (binding).
2. Read `{ws_rel('docs/.work/handoff.md')}` (what previous sessions did and left pending). Do not redo finished work.
3. Run `{cli} plan start {u['id']}`, then do ONLY this unit, as deep as the playbook asks. The CLI is `{cli}`
   (`{cli} help` lists commands). Write docs in English; talk to the user in {talk}.
   Save progress as you go (the user may close the session at any time): after each significant step run
   `{cli} plan note {u['id']} "<what is done / what is next>"` and write findings to their files immediately.
4. Finish: `{cli} plan done {u['id']} --note "<one line>"` (or `plan block … --note "why"`), rewrite the
   "Last session" section of `{ws_rel('docs/.work/handoff.md')}` (done, decisions, pending, files to read first next time),
   run `{cli} check` and `{cli} checkpoint "{u['id']}"` (local commit of the docs so nothing is lost).
5. {ask}
"""


# ---------- autopilot ----------
AGENTS = ("claude", "codex")
INTERVIEW_TYPES = {"interview-context", "interview-language", "interview-history"}
# best guess at the CLIs' wording, matched only against the end of the output (where the CLI prints its
# error) so a unit documenting a rate-limited API isn't misread; anything else stops the loop instead
LIMIT_HINTS = ("usage limit", "rate limit", "rate_limit", "limit reached", "try again later",
               "too many requests", "resets at", "limit will reset", "quota exceeded")
AUTOPILOT_PROMPT = WORK / "autopilot-prompt.md"


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
    try:
        ev = json.loads(line)
    except ValueError:
        return ([_short(line, 140)] if line.strip() else []), line
    kind = ev.get("type")
    if agent == "claude":
        if kind == "assistant":
            shown = []
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    arg = next((inp[k] for k in ("file_path", "path", "command", "pattern", "url", "description") if inp.get(k)), "")
                    shown.append(f"· {c.get('name')} {_short(arg)}")
                elif c.get("type") == "text" and c.get("text", "").strip():
                    shown.append(f"» {_short(c['text'], 130)}")
            return shown, ""
        if kind == "result":
            res = str(ev.get("result") or ev.get("subtype") or "")
            return ([f"= {'error: ' if ev.get('is_error') else ''}{_short(res, 130)}"] if ev.get("is_error") else []), res
        return [], ""
    item = ev.get("item") or {}
    if kind == "item.started" and item.get("type") == "command_execution":
        cmd = str(item.get("command", ""))
        return [f"· $ {_short(cmd.split('-Command', 1)[-1].strip(chr(39) + ' '))}"], ""
    if kind == "item.completed":
        if item.get("type") == "agent_message":
            return [f"» {_short(item.get('text'), 130)}"], ""
        if item.get("type") == "file_change":
            return [f"· edit {_short(c.get('path'))}" for c in item.get("changes", [])], ""
        if item.get("type") == "mcp_tool_call":
            return [f"· {item.get('server')}.{item.get('tool')}"], ""
    if kind in ("turn.failed", "error"):
        msg = str((ev.get("error") or {}).get("message") or ev.get("message") or "")
        return [f"= error: {_short(msg, 130)}"], msg
    return [], ""


def _run_agent(agent: str, text: str, lang: str, uid: str, echo=print) -> subprocess.CompletedProcess:
    """Run one unattended session, streaming a compact view of what the agent does, plus a heartbeat with
    the unit's last checkpoint when it goes quiet. The returned stdout holds the error/result text only."""
    # multi-line args do not survive Windows .cmd shims: hand over a one-line pointer to the prompt file
    WORK.mkdir(parents=True, exist_ok=True)
    AUTOPILOT_PROMPT.write_text(text, encoding="utf-8")
    brief = ws_rel(rel_file(AUTOPILOT_PROMPT))
    short = f"Follow the instructions in {brief}" if lang == "en" else f"Sigue las instrucciones de {brief}"
    cmd = ([which(agent), "-p", short, "--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]
           if agent == "claude" else
           [which(agent), "exec", "--approve-for-me", "--skip-git-repo-check", "--json", short])
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
        # pin the project: the agent's own `camarones …` calls must hit this plan, whatever folder it cds into
        p = subprocess.Popen(cmd, cwd=str(WORKSPACE), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,
                             env={**os.environ, "CAMARONES_ROOT": str(ROOT)})
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, str(e), "")
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        for line in p.stdout:
            shown, err = _render(agent, line.rstrip("\n"))
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
    Codex when one hits its usage limit and waiting while both are limited. Returns units completed."""
    log = lambda t: _autopilot_log(t, echo)                                    # noqa: E731
    agents = [a for a in AGENTS if which(a)]
    if not agents:
        log("Autopilot: neither `claude` nor `codex` is installed — nothing to run.")
        return 0
    # team interviews only consolidate written answers: nothing to ask, so they can run unattended
    skip = set() if include_interviews or docs.interview_mode() == "team" else INTERVIEW_TYPES
    limited: dict[str, dt.datetime] = {}
    done = 0
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
        free = [a for a in agents if limited.get(a, dt.datetime.min) <= dt.datetime.now()]
        if not free:
            soonest = min(limited.values())
            wait = max(60, min(poll_seconds, int((soonest - dt.datetime.now()).total_seconds())))
            log(f"All agents are at their usage limit — retrying in {wait // 60} min "
                f"(machine must stay on; Ctrl+C to stop, progress is saved).")
            time.sleep(wait)
            continue
        agent = free[0]
        log(f"{agent} → {u['id']}: {u['title']}")
        r = _run_agent(agent, prompt(u["id"], lang=lang, unattended=True), lang, u["id"], echo)
        output = f"{r.stdout or ''}\n{r.stderr or ''}"
        if r.returncode == 0:
            status = get(load(), u["id"])["status"]
            log(f"{agent} finished {u['id']} (status: {status})")
            if status in ("todo", "doing"):
                log(f"Autopilot stopped: {u['id']} ended without `plan done`/`plan block` — check its checkpoints "
                    f"in {ws_rel(rel_file(note_file(u['id'])))} before continuing.")
                return done
            done += 1
            continue
        if any(h in output[-2000:].lower() for h in LIMIT_HINTS):
            limited[agent] = dt.datetime.now() + dt.timedelta(seconds=poll_seconds)
            others = [a for a in agents if limited.get(a, dt.datetime.min) <= dt.datetime.now()]
            log(f"{agent} hit its usage limit" + (f" — switching to {others[0]}" if others else ""))
            continue
        log(f"Autopilot stopped: {agent} failed on {u['id']} (exit {r.returncode}). Last output:\n"
            + output.strip()[-1500:])
        return done
    log(f"Autopilot stopped: reached the limit of {max_units} unit(s).")
    return done
