"""Work plan: the documentation job split into session-sized units, persisted in docs/.work/plan.yaml.

Each unit is small enough for one agent session (fresh context). Agents and the wizard use:
  plan sync   (re)build units from workspace.yaml, keeping statuses
  plan next   units whose dependencies are done
  plan start/done/block/drop/add
and docs/.work/handoff.md carries the baton between sessions.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from .common import WORK, CAM_LAYOUT, CAM_DIR, cli_cmd, ws_rel, rel_file, IS_WIN
from . import docs

PLAN = WORK / "plan.yaml"
HANDOFF = WORK / "handoff.md"
LOG = WORK / "log.md"
DONE = ("done", "dropped")

# unit type → (phase, runner, title template, playbook section)
TYPES = {
    "quick-overview":   (2, "agent", "First overview: purpose, run instructions, one flow and sources", "quick-overview"),
    "setup":            (0, "wizard", "Environment ready (tools, repos, agent wiring)", "setup"),
    "discovery":        (1, "agent",  "Discovery of {repo}", "discovery"),
    "discovery-cross":  (1, "agent",  "Cross-repo correlation (integrations, shared DBs, candidate flows)", "discovery-cross"),
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
    PLAN.write_text("# Camarones Documenter work plan — one unit per agent session. Managed by the camarones CLI.\n"
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
    u += [unit("interview-context", "interview-context", ["discovery-cross"]),
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
            bu.update({k: cur[k] for k in ("status", "notes", "updated") if k in cur})
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
    if comps is not None and "openwiki" not in comps:      # OpenWiki not installed → no repo-wiki units
        for u in merged:
            if u["type"] == "repo-wiki" and u["status"] == "todo":
                u["status"], u["notes"] = "dropped", "OpenWiki not selected"
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
    ready = [u for u in data["units"] if u["status"] in ("todo", "doing", "blocked")
             and all(st.get(d, "done") in DONE for d in u["deps"])]
    order = {"doing": 0, "todo": 1, "blocked": 2}
    return sorted(ready, key=lambda u: (order[u["status"]], u["phase"]))


def set_status(uid: str, status: str, note: str | None = None) -> dict:
    data = load()
    u = get(data, uid)
    u["status"] = status
    u["updated"] = now()
    if note:
        u["notes"] = note
    save(data)
    if status in ("done", "blocked", "dropped"):
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


UNITS_DIR = WORK / "units"


def note_file(uid: str) -> Path:
    return UNITS_DIR / (uid.replace(":", "__").replace("/", "_") + ".md")


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
        mark = " ← ready" if u["id"] in ready and u["status"] == "todo" else ""
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
           f"Camarones Documenter wizard: `{cli}`).")
    resume = ""
    notes = note_file(u["id"])
    if u.get("status") == "doing" or notes.exists():
        rel = ws_rel(rel_file(notes))
        resume = (f"\nRESUME — a previous session already worked on this unit and was closed before finishing. Do NOT start over:\n"
                  f"read its checkpoints in `{rel}`" + (f" (last: {last_note(u['id'])})" if last_note(u["id"]) else "") +
                  f", look at `git status` / `git diff` in `{ws_rel('.')}` for work that was written but not committed, "
                  "check which of the unit's output files already exist, and continue from there.\n")
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
              "Never write kit files into the service repos.\n") if CAM_LAYOUT else ""
    return f"""Camarones Documenter session — unit `{u['id']}`: {u['title']}
{resume}{extra}{layout}
You are documenting this project with the Camarones Documenter kit (works the same in Claude Code and Codex).
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
