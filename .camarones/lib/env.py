"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import datetime as dt, json, os, posixpath, re, shutil, subprocess, sys
from collections import deque
from pathlib import Path

from .common import (CTX, KIT, ROOT, DOCS, CACHE, IS_WIN, VERSIONS, CAM_DIR, WORKSPACE, run, out,
                     which, cli_cmd, repo_dir, ws_rel, rel_file)
from . import docs
from .app import services
from .adapters import runners
from .harness.ports import RunRequest
from .harness.locks import pid_alive  # noqa: F401  (pid_alive re-exported)
from .core.paths import WIKI_STAMP
from .ports import Log
from .projects import git_failure  # noqa: F401  (git_failure re-exported)



# ---------- portal: viewers (C4, code graph, wiki graphs) ----------
def stream(cmd: list[str], cwd: Path, log: Log, env: dict | None = None) -> int:
    """Run a long command and hand each output line to `log` (the portal shows it live)."""
    try:
        pr = subprocess.Popen([which(cmd[0]) or cmd[0], *cmd[1:]], cwd=str(cwd), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", env={**os.environ, **(env or {})})
    except OSError as e:
        log(f"⚠ {cmd[0]}: {e}")
        return 127
    for line in pr.stdout:
        line = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", line).rstrip()
        if line.strip():
            log(line)
    return pr.wait()


def wiki_graph(repo: str, dest: Path | None = None, log: Log = print) -> bool:
    wiki, dest = docs.wiki_dir(repo), dest or services.current().viewers.VIEWERS / "wiki-graph" / repo
    if not wiki_pages(repo):
        return False
    log(f"exporting the wiki graph of {repo}…")
    shutil.rmtree(dest, ignore_errors=True)
    run(["openwiki", "visualize", wiki.name, "--export", str(dest)], cwd=wiki.parent, check=False, quiet=True)
    ok = (dest / "index.html").exists()
    log(f"✔ wiki graph {repo}" if ok else f"⚠ wiki graph {repo} failed")
    return ok



# ---------- OpenWiki ----------
def wiki_engines() -> list[str]:
    """Who can write a wiki without a terminal: OpenWiki itself (provider key), else an agent CLI with the
    OpenWiki MCP tools (uses the agent's own login)."""
    if "openwiki" not in services.current().components.components() or not services.current().toolchain.openwiki_installed():
        return []
    return [e for e, ok in (("openwiki", services.current().wiki_engine.openwiki_credentials()), ("claude", bool(which("claude"))),
                            ("codex", bool(which("codex")))) if ok]


ENGINE_HELP = {
    "off": "OpenWiki is not one of this project's components: add it with the wizard (⚙️ Settings → components) "
           "or `camaron setup` after adding `openwiki` to project.components in workspace.yaml",
    "missing": "OpenWiki is not installed on this machine: run `camaron setup`",
    "key": "no way to run OpenWiki headless: save a provider key with `openwiki auth configure <provider>` "
           "(or set OPENAI_API_KEY / ANTHROPIC_API_KEY), or install Claude Code / Codex",
}


def wire_openwiki(host: str, log: Log = print) -> None:
    """An agent writes the wiki through OpenWiki's MCP server: connect it the way setup does when it is missing
    (a project set up without the agents step, or a config someone removed), and let headless runs load it."""
    if services.current().wiki_engine.openwiki_wired(host):
        return
    from . import install_state
    cmd = next(c for c in services.current().wiki_engine.OPENWIKI_INSTALL if c[3] == host)
    log(f"Connecting OpenWiki to {host} in this project…")
    install_state.learn([cmd])
    if run(cmd, cwd=ROOT, check=False, quiet=True).returncode != 0 or not services.current().wiki_engine.openwiki_wired(host):
        raise RuntimeError(f"OpenWiki could not be connected to {host} in this project: run `camaron setup`")
    services.current().setup.write_agent_config(services.current().components.components())


def wiki_engine_help() -> str | None:
    """Why no engine can write a wiki here (a key of ENGINE_HELP), or None when one can."""
    if wiki_engines():
        return None
    if "openwiki" not in services.current().components.components():
        return "off"
    return "key" if services.current().toolchain.openwiki_installed() else "missing"


def wiki_pages(repo: str) -> list[Path]:
    """Generated pages only: INSTRUCTIONS.md is the user-authored brief, not a page."""
    wiki = docs.wiki_dir(repo)
    return [f for f in wiki.rglob("*.md") if not any(p.startswith(".") for p in f.relative_to(wiki).parts)
            and f.relative_to(wiki).as_posix() != "INSTRUCTIONS.md"] if wiki.is_dir() else []


WIKI_LINK_RE = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)")


def wiki_nav(repo: str) -> dict:
    """A wiki's own navigation: pages in the order of its index.md, then the rest, plus backlinks between pages."""
    wiki = docs.wiki_dir(repo)
    files = {f.relative_to(wiki).as_posix(): f for f in wiki_pages(repo) if f.name != "log.md"}
    if not files:
        return {"home": None, "pages": [], "backlinks": {}}

    def links(rel: str) -> list[str]:
        base = posixpath.dirname(rel)
        text = files[rel].read_text(encoding="utf-8", errors="replace")
        return [t for t in (posixpath.normpath(posixpath.join(base, h)) for h in WIKI_LINK_RE.findall(text)
                            if not re.match(r"^[a-z]+:", h, re.I)) if t in files]

    order = (["index.md"] + links("index.md")) if "index.md" in files else []
    order = list(dict.fromkeys(order + sorted(files)))
    pages = []
    for rel in order:
        fm, body = docs.split_fm(files[rel].read_text(encoding="utf-8", errors="replace"))
        pages.append({"path": docs.wiki_path(repo, rel), "title": fm.get("title") or docs.first_heading(body) or Path(rel).stem})
    backlinks: dict[str, set] = {}
    for rel in files:
        for target in links(rel):
            if target != rel:
                backlinks.setdefault(docs.wiki_path(repo, target), set()).add(docs.wiki_path(repo, rel))
    home = next((docs.wiki_path(repo, p) for p in ("quickstart.md", "index.md", "README.md") if p in files), pages[0]["path"])
    return {"home": home, "pages": pages, "backlinks": {k: sorted(v) for k, v in sorted(backlinks.items())}}


WIKI_SCOPE = 2                 # 1: repo internals only (kit <= 3.9) · 2: a complete wiki, the repo's side of flows and C4


def wiki_scope(repo: str) -> int:
    """Scope a wiki was written for; wikis from before the stamp existed are scope 1."""
    try:
        return int(json.loads((docs.wiki_dir(repo) / WIKI_STAMP).read_text(encoding="utf-8")).get("scope", 1))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1


def stamp_wiki(repo: str, **extra) -> None:
    f = docs.wiki_dir(repo) / WIKI_STAMP
    f.write_text(json.dumps({"scope": WIKI_SCOPE, **extra}, indent=2) + "\n", encoding="utf-8")


def wiki_old(repo: str) -> bool:
    return bool(wiki_pages(repo)) and wiki_scope(repo) < WIKI_SCOPE


def old_wikis() -> list[str]:
    return [n for n in docs.repo_names() if wiki_old(n)]


STARTER_MARK = "<!-- camarones:starter-brief -->"
COVERAGE = ("Overview: what the repo does for the project and how to run it locally", "Modules and layers",
            "Configuration and environment variables", "Testing: how to run the tests and what they cover",
            "Build, CI and deployment", "Known issues and technical debt")


def starter_brief(repo: str) -> bool:
    """A brief written without AI from the static scan (stack, tools, detected relations), so a first wiki does not
    wait for repo-brief; repo-brief replaces it (it starts with STARTER_MARK). Never written over an existing brief."""
    f = docs.wiki_dir(repo) / "INSTRUCTIONS.md"
    if f.exists():
        return False
    from . import quickarch, radar
    path = repo_dir(repo)
    cfg = next((r for r in docs.workspace()["repos"] if r["name"] == repo), {})
    stack = cfg.get("stack") or quickarch.stack(path, quickarch.repo_blob(path)) or "an undetected stack"
    tools = radar.scan_repo(repo, path)
    cats = {t["category"] for t in tools}
    edges = [e for e in quickarch.scan()["edges"] if repo in (e[0], e[1])]
    talks = [f"- {'→ ' + e[1] if e[0] == repo else '← ' + e[0]}: {e[3]}" for e in edges]
    tooling = [f"- {radar.CATEGORIES.get(c, c)}: {', '.join(t['label'] for t in tools if t['category'] == c)}"
               for c in sorted(cats)]
    coverage = list(COVERAGE[:2])
    if "contracts" in cats or any("HTTP" in e[3] for e in edges) or cfg.get("kind", "service") == "service":
        coverage.append("API surface: one page per group of endpoints, events or jobs")
    if "data" in cats or any(e[3] == "reads/writes" for e in edges):
        coverage.append("Data: what it stores, schema and migrations")
    if "ui" in cats:
        coverage.append("Screens and navigation")
    coverage += COVERAGE[2:]
    project = docs.workspace()["project"]["name"]
    text = "\n".join([
        STARTER_MARK,
        f"# {repo} — wiki brief",
        "",
        f"Starter brief written without AI from a static scan of the repo. The repo-brief unit replaces it with the "
        f"repo's role, bounded context and glossary; until then, read the code for what this page does not say.",
        "",
        "## Role",
        f"`{repo}` is a {cfg.get('kind', 'service')} of {project}, built with {stack}.",
        "",
        "## Talks to",
        *(talks or ["- Nothing detected by the static scan."]),
        "",
        "## Tooling",
        *(tooling or ["- Nothing detected by the static scan."]),
        "",
        "## What to emphasize",
        "What the code does for the project and why, in the project's own terms; link the pages under `docs/` for "
        "the cross-repo domain, flows and C4 instead of repeating them.",
        "",
        "## Coverage",
        *[f"- {c}" for c in coverage],
        "",
    ])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")
    return True


def wiki_brief_kind(repo: str) -> str | None:
    """`ai` (written by repo-brief or a person), `starter` (STARTER_MARK) or None (no brief yet)."""
    f = docs.wiki_dir(repo) / "INSTRUCTIONS.md"
    if not f.is_file():
        return None
    return "starter" if f.read_text(encoding="utf-8", errors="replace").startswith(STARTER_MARK) else "ai"


def wiki_brief_ready(repo: str) -> bool:
    """A first wiki needs the brief that repo-brief writes (role, bounded context, glossary), or OpenWiki writes a
    generic wiki that ignores the project's language and repeats what docs/ already covers."""
    return (docs.wiki_dir(repo) / "INSTRUCTIONS.md").is_file()


def wikis() -> list[dict]:
    from . import plan
    units = {u["id"]: u["status"] for u in plan.load()["units"]}
    chosen = docs.wiki_repos()
    can_run = bool(wiki_engines())
    rows = []
    for n in docs.repo_names():
        pages, nav = wiki_pages(n), wiki_nav(n)
        at, graph_at = services.current().viewers.newest(pages), services.current().viewers.newest([services.current().viewers.VIEWERS / "wiki-graph" / n / "index.html"])
        rows.append({"repo": n, "pages": len(nav["pages"]), "nav": nav, "at": at, "stale": bool(pages) and services.current().viewers.repo_changed_at(n) > at,
                     "graph": bool(graph_at), "graphStale": bool(graph_at) and at > graph_at, "old": wiki_old(n),
                     "unit": units.get(f"repo-wiki:{n}"),
                     "cloned": repo_dir(n).is_dir(), "chosen": n in chosen, "ready": bool(pages) or wiki_brief_ready(n),
                     "brief": wiki_brief_kind(n), "canGenerate": can_run and repo_dir(n).is_dir(),
                     "index": next((docs.wiki_path(n, p) for p in ("quickstart.md", "index.md", "README.md")
                                    if (docs.wiki_dir(n) / p).exists()), None)})
    return rows


def wiki_prompt(repo: str, mode: str) -> str:
    """Self-contained on purpose: the caller owns the plan status, the move back to cam-docs and the commit, so the
    agent must not run the unit protocol (plan start/done, checkpoint) nor `wiki` itself."""
    from . import plan
    uid, cli = f"repo-wiki:{repo}", cli_cmd()
    notes = plan.note_file(uid)
    resume = (f"A previous run left checkpoints in `{ws_rel(rel_file(notes))}`: read them first. " if notes.exists() else "")
    return (f"Camarón — unattended OpenWiki run for `{repo}` (plan unit `{uid}`).\n"
            f"Task: {mode} the OpenWiki of `{repo}/` (absolute git root: {repo_dir(repo)}) with the OpenWiki MCP tools "
            "(skill `openwiki`): openwiki_begin → plan → page loop → openwiki_finish, passing that root. OpenWiki resumes an "
            f"interrupted run by itself. {resume}\n"
            f"Scope: `{ws_rel(f'wikis/{repo}/INSTRUCTIONS.md')}` is this repo's brief (role, bounded context, glossary, "
            "what to emphasize) — follow its terms.\n"
            "Coverage: write a complete wiki, enough for a new developer to work on this repo with it alone: overview and "
            "quickstart (build, test, run locally); the repo's architecture (modules or layers, main components, how a "
            "request or message travels through them); one page per API surface (endpoints, events consumed and produced, "
            "scheduled jobs) and per important domain or logic area; data and integrations (what it owns and stores, what "
            "it calls, who calls it); configuration and environments; testing; operations (deploy, observability, "
            "troubleshooting); known issues and tech debt. Give a topic its own page rather than compressing it: a service "
            "with real logic usually needs 10 pages or more, a small library fewer. Every claim anchored to code. Draw "
            "what prose explains badly, with Mermaid: a sequenceDiagram for each main request or message path, a "
            "stateDiagram-v2 for every entity or job with a status lifecycle, a flowchart for branching rules.\n"
            f"Cross-repo context: the shared domain, business flows and C4 model live in `{ws_rel('docs/')}`. Explain this "
            "repo's part in them from its own side, and link those pages as the files sit on disk (from a page at the "
            "wiki's top: `../../docs/<page>`; one more `../` per subfolder) instead of copying them.\n"
            + ("Expand: this wiki was written under an older, narrower scope (internals only). Keep the pages that are "
               "still correct, add the pages Coverage asks for that are missing, and deepen the thin ones.\n"
               if mode == "update" and wiki_old(repo) else "") +
            f"Boundaries: `{repo}/openwiki/` is a real folder for this run. When you finish, the caller moves it into "
            f"`{CAM_DIR}/wikis/{repo}/`, removes what OpenWiki adds to the repo (AGENTS.md, CLAUDE.md, .github/) and marks "
            f"the plan unit — do none of that yourself, never run `{cli} wiki`, and do not touch other repo files.\n"
            f"Progress: after each page run `{cli} plan note {uid} \"<page done / next>\"`. This run is unattended: never "
            f"ask; append questions to `{ws_rel('docs/interview/open-questions.md')}`. At the end rewrite the \"Last "
            f"session\" section of `{ws_rel('docs/.work/handoff.md')}`.\n")


class WikiAbort(RuntimeError):
    """The engine cannot run at all (quota, login): every other repo of a batch would fail the same way."""


ENGINE_DOWN = re.compile(r"session limit|usage limit|weekly limit|limit reached|rate.?limit|\b429\b|insufficient_quota|"
                         r"credit balance|invalid api key|incorrect api key|\b401\b|unauthori[sz]ed|/login|not logged in|"
                         r"log ?in again|token (?:has )?expired|overloaded", re.I)


class _WikiRun:
    """A wiki written by an agent runner is a run of its own (`r-…-wiki-<repo>`): `runs`, the KPIs and the plan bill
    see its tokens and cost. The user reads the agent's progress, not its JSON stream."""

    def __init__(self, repo: str, uid: str, engine: str):
        from .harness import runs
        from .harness.events import EventLog
        self.uid, self.engine, self.started = uid, engine, dt.datetime.now()
        self.run_id = f"r-{self.started:%Y%m%d-%H%M%S}-{os.getpid()}{runs.WIKI}{repo}"
        self.log = EventLog(CTX.runs / self.run_id / "events.jsonl")
        self.runner = runners.get(engine)
        self._emit("run.started", what="wiki")
        self._emit("unit.started", unit=uid, runner=engine, isolation="none")

    def _emit(self, type: str, **fields) -> None:
        try:
            self.log.emit(type, run=self.run_id, **fields)
        except Exception:  # noqa: BLE001 — a run log that cannot be written must never break the wiki
            pass

    def line(self, show: Log, tail: deque) -> Log:
        from . import plan

        def each(line: str) -> None:
            events = self.runner.parse(line)
            for ev in events:
                if ev["type"] == "usage":
                    self._emit("usage", unit=self.uid, runner=self.engine, **{k: v for k, v in ev.items() if k != "type"})
            shown, err = plan._show(events)
            for s in shown:
                show(s)
            if err:
                tail.append(err)
        return each

    def finish(self, ok: bool) -> None:
        from .harness import kpis
        seconds = round((dt.datetime.now() - self.started).total_seconds(), 1)
        self._emit("unit.finished", unit=self.uid, runner=self.engine, outcome="ok" if ok else "failed",
                   status="done" if ok else "todo", seconds=seconds)
        self._emit("run.finished", done=1 if ok else 0)
        kpis.record_run(self.run_id)


def openwiki_generate(repo: str, mode: str = "", log: Log = print, engine: str = "", force: bool = False) -> bool:
    """Write or refresh one repo's OpenWiki (same path for the wizard, the portal and the CLI). Raises WikiAbort when
    the engine itself is down, so batches stop instead of failing every remaining repo."""
    from . import plan
    if not repo_dir(repo).is_dir():
        raise RuntimeError(f"{repo} is not cloned (sync first)")
    engines = wiki_engines()
    engine = engine or (engines[0] if engines else "")
    if engine not in engines:
        raise RuntimeError(ENGINE_HELP[wiki_engine_help() or "key"])
    services.current().links.link_repo_wiki(repo, log)
    mode = mode or ("update" if wiki_pages(repo) else "init")
    if mode == "init" and not force and not wiki_brief_ready(repo):
        raise RuntimeError(f"{repo}: no {ws_rel(f'wikis/{repo}/INSTRUCTIONS.md')} yet — run its repo-brief unit first "
                           "(it gives OpenWiki the repo's role and glossary), or force it with `wiki --force`")
    uid = f"repo-wiki:{repo}"
    before = {u["id"]: u["status"] for u in plan.load()["units"]}.get(uid)
    known = before is not None
    tail: deque[str] = deque(maxlen=5)

    def tee(line: str) -> None:
        tail.append(line)
        log(line)

    if engine != "openwiki":
        wire_openwiki(engine, log)
    record = None
    with services.current().wiki_engine.wiki_lock(repo):
        if known:
            plan.set_status(uid, "doing")
        log(f"OpenWiki {mode} for {repo} via {engine}… (this can take a while)")
        with services.current().wiki_engine.wiki_workdir(repo, log):
            if engine == "openwiki":
                rc = stream(["openwiki", "code", f"--{mode}", "--print"], repo_dir(repo), tee)
            else:
                tools = ("mcp__openwiki", "Skill", "Read", "Write", "Edit", "Glob", "Grep", "Bash(git:*)", "Bash(ls:*)",
                         "Bash(graphify:*)", f"Bash({cli_cmd()} plan note:*)")
                req = RunRequest(prompt=wiki_prompt(repo, mode), cwd=WORKSPACE, allow_tools=tools, stream=True)
                record = _WikiRun(repo, uid, engine)
                try:
                    rc = stream(runners.get(engine).build(req).argv, WORKSPACE, record.line(tee, tail))
                except BaseException:          # a crash or Ctrl+C: the run log still says the run ended
                    record.finish(False)
                    raise
    ok = rc == 0 and bool(wiki_pages(repo))
    if record:
        record.finish(ok)
    if ok:
        brief = docs.wiki_dir(repo) / "INSTRUCTIONS.md"
        if engine != "openwiki" or (brief.is_file() and "## Coverage" in brief.read_text(encoding="utf-8")):
            stamp_wiki(repo, mode=mode, engine=engine, kit=VERSIONS["kit"])
        if known:
            plan.set_status(uid, "done", f"OpenWiki {mode} via {engine}")
        docs.llms()
        wiki_graph(repo, log=log)
        services.current().share.checkpoint_commit(f"{uid} ({mode})")
        log(f"✔ wiki {repo}: {len(wiki_pages(repo))} pages")
        return True
    if known:
        plan.set_status(uid, before, record=False)
    reason = (tail[-1] if tail else "no output")[:300] if rc else "finished without writing any page"
    log(f"⚠ OpenWiki {mode} for {repo} failed (exit {rc}): {reason}")
    if rc and any(ENGINE_DOWN.search(l) for l in tail):
        raise WikiAbort(f"{engine} cannot run right now — {reason}. Nothing else was started; retry when it is back.")
    return False


# ---------- portal: static export (what CI deploys) ----------
def forge_edit_base() -> str:
    """https://…/-/edit/<branch>/ (GitLab) or …/edit/<branch>/ (GitHub) for the cam-docs repo, '' without a remote."""
    url = out(["git", "remote", "get-url", "origin"], cwd=ROOT)
    if not url:
        return ""
    url = re.sub(r"^git@([^:]+):", r"https://\1/", url).removesuffix(".git")
    url = re.sub(r"^https://[^@/]+@", "https://", url)
    branch = out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT) or "main"
    return f"{url}/edit/{branch}/" if "github" in url else f"{url}/-/edit/{branch}/"


def export_site(log: Log = print) -> Path:
    """The same portal app, read-only: HTML + JSON snapshots of the API, the viewers and the libraries they need.
    No npm build — any static host (nginx image, GitLab/GitHub Pages) serves it."""
    from . import quality
    from .app import portal_views
    quality.assert_no_secrets()
    writable(CACHE)
    site, tmp = CACHE / "site", CACHE / "site.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(portal_views.UI, tmp)
    html = (tmp / "index.html").read_text(encoding="utf-8")
    (tmp / "index.html").write_text(html.replace('content="live"', 'content="static"'), encoding="utf-8")
    docs.llms()
    shutil.copyfile(DOCS / "llms.txt", tmp / "llms.txt")
    shutil.copyfile(DOCS / "llms-full.txt", tmp / "llms-full.txt")
    api = tmp / "api"

    def dump(rel: str, data) -> None:
        f = api / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    t = portal_views.tree()
    t["editBase"] = forge_edit_base()
    langs = [""] + t["langs"]
    index = []
    for d in t["docs"]:
        decisions = portal_views.covering(d["path"])
        for lang in langs:
            doc = portal_views.read(d["path"], lang)
            if lang and not doc["exists"]:
                continue
            doc["decisions"] = decisions
            dump(f"doc/{lang or '_'}/{d['path']}.json", doc)
            index.append({"path": d["path"], "lang": lang, "title": doc["title"], "trust": d["trust"],
                          "text": docs.split_fm(doc["raw"])[1][:20000]})
    log(f"✔ {len(t['docs'])} docs" + (f" + translations ({', '.join(t['langs'])})" if t["langs"] else ""))
    images = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
    folders = [(DOCS, tmp / "raw")] + [(docs.wiki_dir(n), tmp / "raw" / "wikis" / n) for n in docs.repo_names()]
    for src, out_dir in folders:                    # a wiki page's images: raw/wikis/<repo>/… as the server serves them
        for f in (src.rglob("*") if src.is_dir() else ()):
            if f.is_file() and f.suffix.lower() in images:
                dst = out_dir / f.relative_to(src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dst)
    if "likec4" in services.current().components.components() and (not (services.current().viewers.VIEWERS / "architecture" / "index.html").exists() or services.current().viewers.viewers()["c4"]["stale"]):
        services.current().viewers.build_c4(log=log)
    if (services.current().viewers.VIEWERS / "architecture").is_dir():
        shutil.copytree(services.current().viewers.VIEWERS / "architecture", tmp / "architecture")
    if "graphify" in services.current().components.components() and not services.current().viewers.code_graphs():
        services.current().viewers.graph(rebuild=False, log=log)
    for n, f in services.current().viewers.code_graphs().items():
        dst = tmp / "code-graph" / ("" if n == "all" else n) / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
    log(f"✔ code graphs ({len(services.current().viewers.code_graphs())})")
    for w in wikis():
        if w["pages"] and (not w["graph"] or w["graphStale"]):
            wiki_graph(w["repo"], log=log)
        if (services.current().viewers.VIEWERS / "wiki-graph" / w["repo"]).is_dir():
            shutil.copytree(services.current().viewers.VIEWERS / "wiki-graph" / w["repo"], tmp / "wiki-graph" / w["repo"])
    t["codeGraphs"] = list(services.current().viewers.code_graphs())
    dump("tree.json", t)
    dump("status.json", portal_views.status())
    dump("wikis.json", wikis())
    dump("viewers.json", services.current().viewers.viewers())
    from . import codemap
    for n in codemap.available():
        dump(f"codemap/{n}.json", codemap.load(n))
    dump("search.json", index)
    for lib in portal_views.UI_LIBS:
        f = docs.vendor_file(*lib)
        if f:
            dst = tmp / "vendor" / f"{lib[0]}@{lib[1]}" / lib[2]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
    k, failed = docs.vendor(tmp)
    log(f"✔ offline libraries ({k + len(portal_views.UI_LIBS)})" + (f" — still on CDN: {failed}" if failed else ""))
    shutil.rmtree(site, ignore_errors=True)
    tmp.rename(site)
    services.current().containers.image_context()
    log(f"✔ portal exported → {ws_rel('.camarones/.cache/site')}")
    return site


portal = export_site


def portal_steps() -> int:
    wikis_n = sum(1 for n in docs.repo_names() if wiki_pages(n))
    c4 = 1 if (services.current().diagrams.arch_dir() / "likec4.config.json").exists() else 0
    return 4 + 2 * c4 + 2 * wikis_n


def writable(d: Path) -> None:
    """A cache left behind by a `sudo` run would make every later build fail half-way with a bare PermissionError."""
    if IS_WIN or not d.exists():
        return
    uid = os.getuid()
    bad = [p for p in (d, *d.iterdir()) if p.stat().st_uid != uid]
    if bad:
        raise RuntimeError(f"{bad[0]} belongs to another user (an earlier run with sudo?). Fix it with:\n"
                           f"  sudo chown -R $(whoami) \"{d}\"")


def project_id() -> str:
    return docs.workspace()["project"].get("id") or re.sub(r"[^a-z0-9]+", "-", ROOT.name.lower()).strip("-") or "project"


def compose_cmd() -> list[str]:
    """For servers/CI: `docker compose -f .camarones/portal/compose.yml` (always with an explicit file)."""
    return ["docker", "compose", "-f", str(KIT / "portal" / "compose.yml"), "-p", f"{project_id()}-docs"]


def docker_up(port: int = 8080, log: Log = print) -> str:
    """Plain `docker build` + `docker run`: no compose file or compose plugin needed (works with any Docker)."""
    ok, why = services.current().containers.docker_ready()
    if not ok:
        raise RuntimeError(why)
    stop_local()
    ctx = services.current().containers.image_context()
    pid = project_id()
    image, name = f"camarones-docs-{pid}:local", f"{pid}-docs"
    log("building the nginx image…")
    run(["docker", "build", "-t", image, str(ctx)], quiet=True)
    log("✔ image " + image)
    run(["docker", "rm", "-f", name], check=False, quiet=True)
    log(f"starting container {name} on port {port}…")
    r = run(["docker", "run", "-d", "--name", name, "--restart", "unless-stopped", "-p", f"{port}:80", image],
            check=False, quiet=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        if "port is already allocated" in err or "address already in use" in err:
            raise RuntimeError(f"port {port} is busy — choose another port")
        raise RuntimeError(f"docker run failed: {err[-1500:]}")
    url = f"http://localhost:{port}"
    log(f"✔ portal at {url}")
    return url


SERVE_PID = CACHE / "serve.pid"


def serve_local(port: int = 8080, log: Log = print) -> str:
    """Serve the exported (read-only) portal without Docker — what the deployed one looks like."""
    if not (CACHE / "site" / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — export it first (Portal → Export / `portal`)")
    return serve_editor(port, log, static=True)


def serve_editor(port: int = 8080, log: Log = print, static: bool = False) -> str:
    """The default portal: a local server (no Docker, no npm) that renders docs/ live and lets people edit,
    confirm, comment, commit and rebuild the viewers. Detached, so it outlives the wizard; `down` stops it."""
    stop_local()
    import secrets, socket, sys, time
    with socket.socket() as sck:
        if sck.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} is busy — choose another port")
    CACHE.mkdir(parents=True, exist_ok=True)
    token = "" if static else secrets.token_urlsafe(24)       # the machine token: lets this browser write the board
    penv = {k: v for k, v in os.environ.items() if k != "CAMARONES_PORTAL_TOKEN"}
    kw: dict = {"stdout": subprocess.DEVNULL, "stdin": subprocess.DEVNULL,
                "stderr": (CACHE / "serve.log").open("w", encoding="utf-8"),
                "env": {**penv, "CAMARONES_ROOT": str(ROOT), **({"CAMARONES_PORTAL_TOKEN": token} if token else {})}}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    cmd = [sys.executable, str(KIT / "camarones.py"), "up", "--foreground", "--port", str(port)] + (["--static"] if static else [])
    pr = subprocess.Popen(cmd, **kw)
    SERVE_PID.write_text(str(pr.pid), encoding="utf-8")
    for _ in range(20):
        time.sleep(0.25)
        if pr.poll() is not None:
            raise RuntimeError("the portal server did not start — see " + str(CACHE / "serve.log"))
        with socket.socket() as sck:
            if sck.connect_ex(("127.0.0.1", port)) == 0:
                break
    url = portal_url(port, token or None)       # the static export takes no writes (POST is 405): no token
    log(f"✔ portal at {url}" + (" (read-only export, no Docker)" if static else " (live: read · edit · confirm · review)"))
    return url


def portal_url(port: int, token: str | None = None, route: str = "") -> str:
    """The portal address with ONE fragment: `#<route>&cam-token=<token>` (route like `#/c4`, optional), or
    `#cam-token=<token>` without a route. The frontend takes `cam-token` out of the fragment and keeps the route."""
    parts = [p for p in (route.lstrip("#"), f"cam-token={token}" if token else "") if p]
    return f"http://localhost:{port}/" + (("#" + "&".join(parts)) if parts else "")


def portal_token(url: str) -> str | None:
    m = re.search(r"[#&]cam-token=([\w-]+)", url)
    return m.group(1) if m else None


def stop_local() -> bool:
    if not SERVE_PID.exists():
        return False
    try:
        pid = int(SERVE_PID.read_text().strip())
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except (ValueError, OSError):
        pass
    SERVE_PID.unlink(missing_ok=True)
    return True


def docker_down() -> None:
    stop_local()
    if which("docker"):
        run(["docker", "rm", "-f", f"{project_id()}-docs"], check=False, quiet=True)
        run([*compose_cmd(), "down"], cwd=ROOT, check=False, quiet=True)   # installs from older kits


# ---------- CI ----------
def detect_forge() -> str:
    urls = " ".join(r.get("url", "") for r in docs.workspace()["repos"])
    urls += " " + out(["git", "-C", str(ROOT), "remote", "get-url", "origin"])
    if "github" in urls:
        return "github"
    return "gitlab"


def install_ci(forge: str | None = None, log: Log = print) -> Path:
    forge = forge or detect_forge()
    if forge == "github":
        dst = ROOT / ".github" / "workflows" / "docs.yml"
        src = KIT / "ci" / "umbrella.github.yml"
    else:
        dst = ROOT / ".gitlab-ci.yml"
        src = KIT / "ci" / "umbrella.gitlab-ci.yml"
        if dst.exists() and "camarones" not in dst.read_text(encoding="utf-8"):
            dst = ROOT / ".gitlab-ci.camarones.yml"
            log("  existing .gitlab-ci.yml kept: add `include: local: .gitlab-ci.camarones.yml` to it")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    snippet = f"repo.{'github.yml' if forge == 'github' else 'gitlab-ci.yml'}"
    (ROOT / ".camarones" / "ci").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KIT / "ci" / snippet, ROOT / ".camarones" / "ci" / snippet)   # service repos include it from here
    from . import ci
    fresh = ROOT / ".camarones" / "ci" / ci.FILES[forge]
    fresh.write_text(ci.render(forge), encoding="utf-8", newline="\n")      # generated from lib/ci.py, ci: in workspace.yaml
    log(f"  ✔ {dst.relative_to(ROOT)} (docs repo pipeline)")
    log(f"  → per-repo snippet: .camarones/ci/{snippet}")
    log(f"  → per-repo pull request check (no AI): .camarones/ci/{ci.FILES[forge]}")
    proposal = ci.render_propose(forge)
    if proposal:                                    # ci.target: self-hosted — the AI job runs on the team's runner
        (ROOT / ".camarones" / "ci" / ci.FILES_PROPOSE[forge]).write_text(proposal, encoding="utf-8", newline="\n")
        log(f"  → per-repo docs proposal (AI, self-hosted runner): .camarones/ci/{ci.FILES_PROPOSE[forge]}")
    return dst
