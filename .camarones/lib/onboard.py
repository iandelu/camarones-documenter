"""Onboarding: what a folder picked in the desktop app is, before any project exists, and the first-run state the CLI
wizard and the app share (step lists, position in `firstrun.json`, the name step, `start`). `inspect` reads the disk
(and `git remote`/`rev-parse` through docs.detect_repos) and never writes; it must work on any folder, so it takes
everything from its argument and none from this process's project globals. Never imports `wizard` at module level."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

import yaml

from .common import (CAM_DIR, CAM_LAYOUT, IS_WIN, cli_cmd, ensure_path, find_project_marker, load_json, repo_dir, run,
                     save_json, ws_rel)
from .harness.ctx import Ctx
from . import docs, env, plan, projects

STEPS = ("name", "repos", "tools", "setup", "stack", "arch", "intro")   # first-run steps, saved by id
LEGACY_STEPS = ("name", "repos", "tools", "setup", "arch", "intro")     # firstrun.json before 3.3 kept only the index
JOIN_STEPS = ("tools", "setup", "intro")   # joining a team's cam-docs: the rest is shared and already decided
GREENFIELD_STEPS = ("name", "repos", "tools", "setup", "intro")   # nothing to read yet: no stack scan, no C4 draft
WS_HEADER = "# Camarón workspace: which repos form this project. Edit freely, then run sync.\n"

# a file that says "there is code here"; *.csproj is matched by suffix (its name is the project's)
MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json", "pyproject.toml", "go.mod", "Cargo.toml",
             "pubspec.yaml", "composer.json", "Gemfile")


# Windows reserves these names (with or without an extension): a folder called `con` cannot be created or opened
DEVICE_NAMES = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))})


class Refused(ValueError):
    """`start` will not make this folder a project; `code` is the stable word the app words itself: `home` (the user's
    home or a filesystem root) or `no-git` (code that is not in a git repository yet)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


def kind_of(ws: dict) -> str:
    """`legacy` (document existing code) or `greenfield` (a project that starts from an idea). Absent = `legacy`, so
    every 3.x/4.x project reads as before."""
    return ws["project"].get("kind") or "legacy"


def _read_ws(docs_root: Path) -> dict:
    try:
        ws = yaml.safe_load((docs_root / ".camarones" / "workspace.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        ws = None
    ws = ws if isinstance(ws, dict) else {}
    if not isinstance(ws.get("project"), dict):
        ws["project"] = {}
    return ws


def is_home_or_root(path: Path) -> bool:
    """`path` is the user's home or a filesystem root (it equals its own anchor): never a workspace, since the docs
    folder and every repo scan would land there. Compared as the same file when both exist (a case-insensitive volume
    spells one folder many ways), else resolved, case-insensitive on Windows."""
    def key(p: Path) -> str:
        s = str(p.resolve())
        return s.casefold() if IS_WIN else s

    def same(a: Path, b: Path) -> bool:
        try:
            return os.path.samefile(a, b)
        except OSError:
            return key(a) == key(b)

    p = Path(path).resolve()
    return same(p, Path.home()) or same(p, Path(p.anchor))


def _enclosing_repo(f: Path) -> Path | None:
    """The nearest folder above `f` with a `.git` (a directory, or the file of a worktree/submodule). The search never
    goes up into home or a filesystem root: a dotfiles repo in `~` does not own what is below it."""
    for a in f.parents:
        if is_home_or_root(a):
            return None
        if (a / ".git").exists():
            return a
    return None


def _project_root(f: Path) -> Path | None:
    """The docs root `f` belongs to: `f` itself, its cam-docs/, a folder above it (f is inside the docs tree or, in the
    3.x layout, a repo in it) or, for a repo, the cam-docs/ next to it. A project further away is not this folder's."""
    m = find_project_marker(f)
    if m is None:
        return None
    if m in (f, f / CAM_DIR) or m in f.parents or ((f / ".git").exists() and m == f.parent / CAM_DIR):
        return m
    return None


def _has_manifest(d: Path) -> bool:
    try:
        return any((d / m).exists() for m in MANIFESTS) or any(d.glob("*.csproj"))
    except OSError:
        return False


def _has_code(f: Path) -> bool:
    """A manifest at the top or one folder down (a monorepo's `src/`, `app/`); deeper is not looked at."""
    try:
        return _has_manifest(f) or any(_has_manifest(d) for d in f.iterdir() if d.is_dir())
    except OSError:
        return False


def _has_repos(f: Path) -> bool:
    try:
        return projects.has_repos(f)
    except OSError:
        return False


def inspect(folder: Path) -> dict:
    """What `folder` is, first match wins: project · repo · umbrella · code · empty. Returns `case`, `kind`,
    `workspace` (the folder that holds the repos), `docs_root`, `name` (the workspace folder's), `repos` (docs.detect_repos
    rows), `siblings` (repo case: the other repos next to it) and `warning`: `home` when the workspace is the user's home or a
    filesystem root and no project is there yet (wins over the rest), else `no-git` for code without a repository. A picked `cam-docs` folder
    is read as the workspace it belongs to, and a folder inside a git repository as that repository."""
    f, warning, siblings = Path(folder).resolve(), "", []
    if f.name.lower() == CAM_DIR and f.parent != f:
        f = f.parent
    root = _project_root(f)
    if not root and (enclosing := _enclosing_repo(f)):      # a folder inside a repo is that repo, never a place for git init
        f = enclosing
        root = _project_root(f)
    if root:
        case, kind = "project", kind_of(_read_ws(root))
        workspace = root.parent if root.name == CAM_DIR else root     # 3.x layout: the docs root is the workspace
    elif (f / ".git").exists():
        case, kind, workspace = "repo", "legacy", f.parent
    elif _has_repos(f):
        case, kind, workspace = "umbrella", "legacy", f
    elif _has_code(f):
        case, kind, workspace, warning = "code", "legacy", f, "no-git"
    else:
        case, kind, workspace = "empty", "greenfield", f
    if case != "project" and is_home_or_root(workspace):     # a project already there keeps opening (AGENTS 2.3)
        warning = "home"
    try:
        repos = docs.detect_repos(workspace) if workspace.is_dir() else []
    except OSError:                         # unreadable folder: no repos to show, not a crash
        repos = []
    if case == "repo":
        siblings = [r for r in repos if r["name"] != f.name]
        repos = [r for r in repos if r["name"] == f.name]
    return {"case": case, "kind": kind, "workspace": str(workspace), "docs_root": str(root or workspace / CAM_DIR),
            "name": workspace.name, "repos": repos, "siblings": siblings, "warning": warning}


# ---------- first-run state: one implementation for the CLI wizard and the app ----------
def write_workspace(ws_file: Path, ws: dict) -> None:
    ws_file.parent.mkdir(parents=True, exist_ok=True)   # global install: .camarones/ may not exist yet
    ws_file.write_text(WS_HEADER + yaml.safe_dump(ws, sort_keys=False, allow_unicode=True), encoding="utf-8",
                       newline="\n")


def name_project(ws: dict, name: str, fallback: str) -> dict:
    """The name step's whole effect on `ws`: name, id (a slug of it), canonical language and translations defaults."""
    p = ws.setdefault("project", {})
    p["name"] = (name or "").strip() or fallback
    p["id"] = "".join(c if c.isalnum() else "-" for c in p["name"].lower()).strip("-")
    p.setdefault("canonical_language", "en")
    p["translations"] = p.get("translations") or ["es"]
    return ws


def firstrun_file(root: Path) -> Path:
    return Ctx.for_root(root).cache / "firstrun.json"


def steps(mode: str, kind: str) -> tuple[str, ...]:
    """The first-run steps for a mode (`new` | `join`) and a project kind; an unknown kind reads as `legacy`."""
    if mode == "join":
        return JOIN_STEPS
    return GREENFIELD_STEPS if kind == "greenfield" else STEPS


def first_run_mode(state: dict, shared_ready: bool, local_ready: bool) -> str:
    """"done" (straight to the menu), "new" (full first run, or resume one) or "join": plan + workspace.yaml came with
    the team's cam-docs but this machine has no first-run state, so only its tools and repos still need setting up.
    A project that already has both on this machine is an install from before v2.4: nothing to redo."""
    if state.get("done"):
        return "done"
    if state.get("mode") == "join":
        return "join"
    if state or not shared_ready:
        return "new"
    return "done" if local_ready else "join"


def resume_id(state: dict) -> str:
    """The step the first run continues at: by id, or by index for firstrun.json files written before 3.3."""
    if state.get("name") in STEPS:
        return state["name"]
    i = int(state.get("step", 0))
    return LEGACY_STEPS[i] if 0 <= i < len(LEGACY_STEPS) else STEPS[min(max(i, 0), len(STEPS) - 1)]


def local_ready() -> bool:
    """This machine already has what setup gives: every repo with a URL cloned and the chosen kit tools."""
    if missing_repos():
        return False
    return all(env.tool_ok(k) for k in env.KIT_TOOLS if k in env.components())


def mode(saved: dict) -> str:
    """The first-run mode for the `saved` position (firstrun.json), the one rule the CLI wizard and the app share."""
    from .common import WS_FILE
    shared = plan.PLAN.exists() and WS_FILE.exists()          # team work that came with the repo (or pre-2.4)
    return first_run_mode(saved, shared, local_ready=bool(shared and not saved) and local_ready())


def state() -> dict:
    """Where this project's first run stands, for the app: `name` (the project's, from workspace.yaml), `mode` (new |
    join | done, computed as the CLI wizard does), `kind`, `steps` (this mode's, without `name`: the start screen did
    it), `step` (the saved one; the first listed when it was `name`), `done`, the workspace's `repos` and the repos
    `found` sitting in the folder."""
    from .common import ROOT
    saved = load_json(firstrun_file(ROOT), {})
    m = mode(saved)
    ws = docs.workspace()
    kind = kind_of(ws)
    ids = [s for s in steps("new" if m == "done" else m, kind) if s != "name"]
    step = resume_id(saved)
    try:
        found = docs.detect_repos()
    except OSError:
        found = []
    return {"name": ws["project"].get("name") or "", "mode": m, "kind": kind, "steps": ids,
            "step": step if step in ids else ids[0], "done": m == "done", "repos": ws["repos"], "found": found}


def save_position(root: Path, step: str, mode: str) -> None:
    """Where the first run stands, so closing the window or switching between the CLI and the app never loses it."""
    save_json(firstrun_file(root), {"step": STEPS.index(step), "name": step, "done": False,
                                    **({"mode": mode} if mode == "join" else {})})


def finish(root: Path, steps_count: int) -> None:
    save_json(firstrun_file(root), {"step": steps_count, "done": True})


def start(folder: Path, name: str | None = None) -> Path:
    """Make the picked folder a project, ready for the wizard's `repos` step; returns its docs root. Idempotent: on a
    folder that already is a project it only registers it and writes nothing else. `Refused` (a ValueError with a
    `code`) when the workspace is home or a root, or the folder is code without git; both before anything is written."""
    f = Path(folder)
    if not f.is_dir():
        raise ValueError(f"not a folder: {f}")
    info = inspect(f)
    if info["warning"] == "home":
        raise Refused("home", f"{info['workspace']} is your home folder or a drive root: pick the folder of one project")
    if info["case"] == "code":
        raise Refused("no-git", f"{f} has code but no git repository: run git init in it first")
    root = Path(info["docs_root"])
    if info["case"] == "project":
        projects.register(root, name=(name or "").strip() or _read_ws(root)["project"].get("name") or info["name"])
        return root
    label = (name or "").strip() or info["name"]
    root = projects.adopt(Path(info["workspace"]), label)        # registers it too
    ws = name_project({"project": {}, "repos": info["repos"]}, label, info["name"])
    ws["project"]["kind"] = info["kind"]
    write_workspace(Ctx.for_root(root).ws_file, ws)             # this process's module globals point at another project
    save_position(root, "repos", "new")
    return root


def git_init(folder: Path) -> list[Path]:
    """`git init` for a code folder that has no repository: in `folder` itself when it holds a manifest at its top,
    else in each first-level subfolder that does. Returns the folders initialised. ValueError when `folder` already is
    a repository or there is nothing to initialise."""
    f = Path(folder).resolve()
    if not f.is_dir():
        raise ValueError(f"not a folder: {f}")
    if is_home_or_root(f):
        raise ValueError(f"{f} is your home folder or a drive root: pick the folder of one project")
    if (f / ".git").exists():
        raise ValueError(f"{f} is already a git repository")
    if enclosing := _enclosing_repo(f):                      # the subfolders are inside it too
        raise ValueError(f"{f} is inside the git repository {enclosing}")
    try:
        targets = [f] if _has_manifest(f) else sorted(d for d in f.iterdir()
                                                       if d.is_dir() and not (d / ".git").exists() and _has_manifest(d))
    except OSError as e:
        raise ValueError(f"cannot read {f}: {e}") from None
    if not targets:
        raise ValueError(f"no code to put under git in {f}")
    done: list[Path] = []
    for t in targets:
        try:
            run(["git", "init", "-q"], cwd=t, quiet=True)
        except RuntimeError as e:
            if done:
                raise RuntimeError(f"{e}\nalready initialised: {', '.join(str(d) for d in done)}") from None
            raise
        done.append(t)
    return done


# ---------- tools: one table, install all (recommended) or pick ----------
def tool_rows() -> list[dict]:
    """Every prerequisite and kit tool as a row: `id, label, ok, kind` (t_required | t_optional | t_kit), `rec`
    (recommended), `sys` (a system tool, not a kit component), `found` (version) and `note`."""
    pre = env.prerequisites()
    have_agent = any(pre[a]["ok"] for a in ("claude", "codex"))
    rows = []
    for k, v in pre.items():
        kind = "t_required" if v["need"] else "t_optional"
        rec = v["need"] or k in ("docker", "java") or (k == "claude" and not have_agent)
        rows.append({"id": k, "label": v["hint"], "ok": v["ok"], "kind": kind, "rec": rec, "sys": True,
                     "found": v.get("found", ""), "note": v.get("note", "")})
    chosen = env.components()
    for k, label in {**env.KIT_TOOLS, **env.EXTRAS}.items():
        installed = env.tool_ok(k) if k in env.KIT_TOOLS else (k in chosen)
        rows.append({"id": k, "label": label, "ok": installed, "kind": "t_kit", "rec": True, "sys": False,
                     "found": env.VERSIONS.get(k, "") if installed and k in env.KIT_TOOLS else "", "note": ""})
    return rows


def install_choice(rows: list[dict], choice: str, picked: list[str] | None = None) -> tuple[list[str], list[str]]:
    """`(system tools to install, kit components to keep)` for `all` (what is recommended and missing, the kit's
    whole set; one agent CLI is enough), `pick` (the ids in `picked`, split by kind) or `none` (install nothing)."""
    have_agent = any(r["ok"] for r in rows if r["id"] in ("claude", "codex"))
    if choice == "all":
        return ([r["id"] for r in rows if r["sys"] and not r["ok"] and r["rec"]
                 and not (r["id"] in ("claude", "codex") and have_agent)], list(env.ALL_COMPONENTS))
    if choice == "pick":
        picked = picked or []
        return [p for p in picked if p in env.prerequisites()], [p for p in picked if p in env.ALL_COMPONENTS]
    return [], env.components()


def install_tools(system: list[str], components: list[str], log, cancelled: Callable[[], bool] | None = None) -> list[str]:
    """Save the chosen components, install the system tools in order and refresh PATH; returns the ones that failed.
    `cancelled` is asked before each install: once it says yes, the rest are left alone."""
    env.set_components(components)
    failed = []
    for k in system:
        if cancelled and cancelled():
            break
        if env.install_prereq(k, log=log):
            log(f"✔ {k}")                  # one finished step each, so the app's progress counts the system tools too
        else:
            failed.append(k)
    ensure_path()
    return failed


# ---------- setup ----------
def run_setup(log, cancelled: Callable[[], bool] | None = None) -> bool:
    """The setup step's work: templates, `env.setup`, the plan for this workspace (also when setup failed, so the
    portal has one) and the `setup` unit marked done when it worked. True when setup succeeded. `cancelled` (the app's
    cancel button) is asked between steps: before setup starts and once it ends; a cancelled setup is not marked done."""
    if cancelled and cancelled():
        return False
    env.init_templates(docs.workspace()["project"]["name"], log=lambda _: None)   # `log` counts setup's own steps
    try:
        ok = env.setup(log=log)
    finally:
        plan.sync()                        # a setup that raised still leaves the plan in place
    if ok and not (cancelled and cancelled()):
        plan.set_status("setup", "done", "first run")
        return True
    return False


def missing_repos() -> list[str]:
    """Repos the workspace lists with a URL and no clone on this machine yet."""
    return [r["name"] for r in docs.workspace()["repos"] if r.get("url") and not (repo_dir(r["name"]) / ".git").exists()]


# ---------- architecture (C4) ----------
def arch_prompt(lang: str) -> str:
    """The agent prompt that refines the static C4 draft; `lang` (es | en) is the language it talks to the user in."""
    cli = cli_cmd()
    talk = "Spanish" if lang == "es" else "English"
    arch = ws_rel("docs/architecture")
    # the agent runs in WORKSPACE: in the cam-docs layout a bare `docs/…` path would make it write a second,
    # unused model next to the repos while the portal keeps showing the unrefined draft
    layout = (f"\nLayout: you run in the workspace folder. Docs live in `{CAM_DIR}/` (its own git repo); the service repos "
              f"are its siblings. Edit only the files under `{arch}/` — never create a `docs/` folder anywhere else.\n"
              if CAM_LAYOUT else "")
    code = ("`graphify query` in the repos, " if "graphify" in env.components() else "")
    first_look = (f" Update `{arch}/first-look.md` to match."            # an old-layout project's page
                  if (docs.DOCS / "architecture" / "first-look.md").exists() else "")
    return f"""Camarones session — improve the first-look architecture draft.
{layout}
`{arch}/model.c4` + `views.c4` hold the architecture draft; it started from a static scan (no AI) that guessed repos,
datastores, brokers and HTTP calls from manifests, config and code. Read `{ws_rel('.camarones/CONVENTIONS.md')}` §4
(C4 rules) and the kinds/tags in `{arch}/spec.c4` first (do not edit spec.c4).
1. Verify every element and relation against the code ({code}OpenAPI/AsyncAPI files, config, client code).
   Fix technologies, names, directions and labels (endpoint / exchange / topic); remove false positives; add what is missing
   (external systems, identity provider, shared databases, frontends/apps). A relation is a runtime call or message —
   hosting/CI/deployment targets belong to the deployment unit, not here.
2. Keep `views.c4` in step with the model: `index` must show the actors, the system and every external system;
   `containers` everything inside the system. Remove view references to elements you deleted.
3. Keep everything `#ai-draft`. Run `{cli} arch-validate` after every edit until it prints ✓ Valid (it validates
   `{arch}/`, so a model written anywhere else is not checked).{first_look}
4. Show the user the result as a short tree (containers → relations) and ask whether it is right; apply their corrections.
   Tell them the portal's Architecture (C4) tab rebuilds from `{arch}/` (`{cli} up`).
Talk to the user in {talk}. Do not modify application code.
"""


# ---------- what the app's endpoints do (serve.py only parses and answers) ----------
LAST_DRAFT: dict = {}        # the newest C4 draft (quickarch.draft's model): /firstlook serves its html, `save` copies it
DRAFT_LOCK = threading.Lock()   # a new draft replaces LAST_DRAFT whole, never edits it: readers see one draft or the other


def last_draft() -> dict:
    with DRAFT_LOCK:
        return LAST_DRAFT


def go_to(step: str) -> dict:
    """Save `step` as the position (a join stays a join) and return the state. ValueError: `done` when the first run
    is over (the app must not reopen it by a stray call), `step` for an id that is not one of this mode's steps."""
    from .common import ROOT
    st = state()
    if st["mode"] == "done":
        raise ValueError("done")
    if step not in st["steps"]:
        raise ValueError("step")
    save_position(ROOT, step, "join" if st["mode"] == "join" else "new")
    return state()


def set_repos(rows: list) -> dict:
    """The repos step: validate the rows (`name` required and unique, `url` optional, `branch` defaults to main, `kind`
    to service), keep the extra keys an existing repo already has (stack, wiki…) and save. A legacy project needs at
    least one. Raises ValueError with a code: `repos` · `name` · `url` · `duplicate`."""
    if not isinstance(rows, list):
        raise ValueError("repos")
    ws = docs.workspace()
    old = {r["name"]: r for r in ws["repos"]}
    out, seen = [], set()
    for r in rows:
        name = str(r.get("name") or "").strip() if isinstance(r, dict) else ""
        if (not name or "/" in name or "\\" in name or ":" in name or ".." in name or name[0] in ".-"
                or name.lower() == CAM_DIR.lower() or name.split(".")[0].lower() in DEVICE_NAMES):
            raise ValueError("name")             # it becomes a folder next to the others: no paths, drives, options or devices
        if name in seen:
            raise ValueError("duplicate")
        seen.add(name)
        url = str(r.get("url") or "").strip()
        if url.startswith("-"):                  # git would read it as an option
            raise ValueError("url")
        out.append({**old.get(name, {}), "name": name, "url": url,
                    "branch": str(r.get("branch") or "").strip() or "main",
                    "kind": str(r.get("kind") or "").strip() or "service"})
    if not out and kind_of(ws) == "legacy":
        raise ValueError("repos")
    ws["repos"] = out
    docs.save_workspace(ws)
    return state()


def setup_job(system: list[str], components: list[str], log, cancelled: Callable[[], bool] | None = None) -> dict:
    """The setup step as a job body: install, then `run_setup`. Every finished (✔) line is logged as `[n/total] …`,
    `total` being setup's own steps plus one per system tool. `cancelled` stops it between steps. Returns {rc, result:
    {failed, missing, ok, cancelled}}."""
    total, n = env.setup_steps(components) + len(system), 0

    def counted(msg) -> None:
        nonlocal n
        m = str(msg).strip()
        if m.startswith("✔"):
            n += 1
            m = f"[{min(n, total)}/{total}] {m}"
        if m:
            log(m)

    failed, ok = [], False
    try:
        failed = install_tools(system, components, counted, cancelled)
        ok = run_setup(counted, cancelled)
    except Exception as e:  # noqa: BLE001 — the step shows what went wrong and offers to retry
        log(f"⚠ {e}")
    stopped = bool(cancelled and cancelled())
    if stopped:
        ok = False
        log("cancelled")
    return {"rc": 0 if ok else 1, "result": {"failed": failed, "missing": missing_repos(), "ok": ok, "cancelled": stopped}}


def stack_rows() -> dict:
    """radar.scan() reduced to what the stack step edits: {repo: {stack, detected_stack}}."""
    from . import radar
    return {n: {"stack": r["stack"], "detected_stack": r["detected_stack"]} for n, r in radar.scan().items()}


def scan_job(log) -> dict:
    from .wizard import scan_repos     # lazy: the wizard imports this module
    scan_repos(log=log)
    return {"rc": 0}


def arch_draft(log) -> dict:
    """The arch step's static draft (no AI), kept in LAST_DRAFT; the result is what the step shows: repos, datastores,
    brokers and relations (R4: not external systems), whether the model validated and whether /firstlook has a page."""
    from . import quickarch
    m = quickarch.draft(log=log)
    global LAST_DRAFT
    with DRAFT_LOCK:
        LAST_DRAFT = dict(m)
    res = {"repos": [{"name": n, **{k: v for k, v in r.items() if k in ("kind", "tech")}} for n, r in m["repos"].items()],
           "datastores": [{"key": k, "label": d["label"], "name": d["name"], "users": sorted(d["users"])}
                          for k, d in m["dbs"].items()],
           "brokers": sorted(m["brokers"]),
           "relations": [{"from": a, "to": b, "kind": kind, "label": label} for a, b, kind, label in m["edges"]],
           "valid": m.get("valid"), "html": bool(m.get("html"))}
    return {"rc": 0, "result": res}


def arch_save(overwrite: bool = False) -> dict:
    """Copy the last draft into docs/architecture. An existing model.c4 is never replaced unless `overwrite`. The new
    page layout has no first-look.md: only an old-layout project gets one (as the wizard's arch step does)."""
    from . import pages, quickarch
    draft = last_draft()
    if not draft:
        raise ValueError("draft")
    if (docs.DOCS / "architecture" / "model.c4").exists() and not overwrite:
        return {"exists": True}
    return {"written": quickarch.save(draft, overwrite=overwrite, page=pages.layout() == "old"), "exists": False}


def done() -> dict:
    """Close the first run and checkpoint what it wrote."""
    from .common import ROOT
    m = mode(load_json(firstrun_file(ROOT), {}))
    finish(ROOT, len(steps("new" if m == "done" else m, kind_of(docs.workspace()))))
    return {"committed": bool(env.checkpoint_commit("first setup"))}
