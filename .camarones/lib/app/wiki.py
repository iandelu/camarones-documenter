"""A repo's wiki (GenerateWiki): who can write it here, its pages and their navigation, the scope it was written for,
the starter brief, the run that writes it with OpenWiki or with an agent through OpenWiki's MCP tools, and the wiki
graph the portal shows beside the viewers."""
from __future__ import annotations

import datetime as dt
import json
import os
import posixpath
import re
import shutil
from collections import deque
from pathlib import Path

from lib import docs
from lib.adapters import runners
from lib.app import components, services, setup, share, viewers
from lib.common import CAM_DIR, CTX, ROOT, VERSIONS, WORKSPACE, cli_cmd, rel_file, repo_dir, run, which, ws_rel
from lib.core.paths import WIKI_STAMP
from lib.core.process import stream
from lib.harness.ports import RunRequest
from lib.ports import Log


# ---------- OpenWiki ----------
def wiki_graph(repo: str, dest: Path | None = None, log: Log = print) -> bool:
    wiki, dest = docs.wiki_dir(repo), dest or viewers.VIEWERS / "wiki-graph" / repo
    if not wiki_pages(repo):
        return False
    log(f"exporting the wiki graph of {repo}…")
    shutil.rmtree(dest, ignore_errors=True)
    run(["openwiki", "visualize", wiki.name, "--export", str(dest)], cwd=wiki.parent, check=False, quiet=True)
    ok = (dest / "index.html").exists()
    log(f"✔ wiki graph {repo}" if ok else f"⚠ wiki graph {repo} failed")
    return ok


def wiki_engines() -> list[str]:
    """Who can write a wiki without a terminal: OpenWiki itself (provider key), else an agent CLI with the
    OpenWiki MCP tools (uses the agent's own login)."""
    if "openwiki" not in components.components() or not services.current().toolchain.openwiki_installed():
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
    from lib import install_state
    cmd = next(c for c in services.current().wiki_engine.OPENWIKI_INSTALL if c[3] == host)
    log(f"Connecting OpenWiki to {host} in this project…")
    install_state.learn([cmd])
    if run(cmd, cwd=ROOT, check=False, quiet=True).returncode != 0 or not services.current().wiki_engine.openwiki_wired(host):
        raise RuntimeError(f"OpenWiki could not be connected to {host} in this project: run `camaron setup`")
    setup.write_agent_config(components.components())


def wiki_engine_help() -> str | None:
    """Why no engine can write a wiki here (a key of ENGINE_HELP), or None when one can."""
    if wiki_engines():
        return None
    if "openwiki" not in components.components():
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
    from lib import quickarch, radar
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
    from lib import plan
    units = {u["id"]: u["status"] for u in plan.load()["units"]}
    chosen = docs.wiki_repos()
    can_run = bool(wiki_engines())
    rows = []
    for n in docs.repo_names():
        pages, nav = wiki_pages(n), wiki_nav(n)
        at, graph_at = viewers.newest(pages), viewers.newest([viewers.VIEWERS / "wiki-graph" / n / "index.html"])
        rows.append({"repo": n, "pages": len(nav["pages"]), "nav": nav, "at": at, "stale": bool(pages) and viewers.repo_changed_at(n) > at,
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
    from lib import plan
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
        from lib.harness import runs
        from lib.harness.events import EventLog
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
        from lib import plan

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
        from lib.harness import kpis
        seconds = round((dt.datetime.now() - self.started).total_seconds(), 1)
        self._emit("unit.finished", unit=self.uid, runner=self.engine, outcome="ok" if ok else "failed",
                   status="done" if ok else "todo", seconds=seconds)
        self._emit("run.finished", done=1 if ok else 0)
        kpis.record_run(self.run_id)


def openwiki_generate(repo: str, mode: str = "", log: Log = print, engine: str = "", force: bool = False) -> bool:
    """Write or refresh one repo's OpenWiki (same path for the wizard, the portal and the CLI). Raises WikiAbort when
    the engine itself is down, so batches stop instead of failing every remaining repo."""
    from lib import plan
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
        share.checkpoint_commit(f"{uid} ({mode})")
        log(f"✔ wiki {repo}: {len(wiki_pages(repo))} pages")
        return True
    if known:
        plan.set_status(uid, before, record=False)
    reason = (tail[-1] if tail else "no output")[:300] if rc else "finished without writing any page"
    log(f"⚠ OpenWiki {mode} for {repo} failed (exit {rc}): {reason}")
    if rc and any(ENGINE_DOWN.search(l) for l in tail):
        raise WikiAbort(f"{engine} cannot run right now — {reason}. Nothing else was started; retry when it is back.")
    return False
