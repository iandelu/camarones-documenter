"""Generated blocks (X3): facts read straight from the repos, no AI — env vars, commands, HTTP endpoints, topics.

A block lives in any page as `<!-- generated:<kind> repo=<repo> sha=<hash> -->…<!-- /generated:<kind> -->`, with an
optional `id=<id>` (which diagram of a kind) after `repo`. The hash is the block's body as the kit wrote it: a body that
no longer matches was edited by hand (kept, and `check` says so), one that matches but differs from a fresh scan is out
of date (refreshed). A person can confirm a block (`confirmed=<hash of the generated body it started from> by=<name>`):
refresh never touches it, and `check` only says when the code moved past it. Each repo gets `docs/repos/<repo>/reference.md`
built from these blocks."""
from __future__ import annotations

import hashlib, re
from pathlib import Path

import yaml

from .common import DOCS, ROOT, cli_cmd, repo_dir, rel_file
from . import diagrams, docs, quickarch

KINDS = ("commands", "env", "endpoints", "topics", "schema")
DIAGRAM_KINDS = diagrams.KINDS                                              # not in KINDS: they never join a reference page
BLOCK_RE = re.compile(r"<!-- generated:(?P<kind>[\w-]+) repo=(?P<repo>[\w.\-]+)(?: id=(?P<id>[\w.\-]+))?"
                      r"(?: confirmed=(?P<confirmed>[0-9a-f]+))?(?: by=(?P<by>[^\s>]+))?(?: sha=(?P<sha>[0-9a-f]+))? -->\n"
                      r"(?P<body>.*?)<!-- /generated:(?P=kind) -->", re.S)
SYSTEM = "_system"                                                          # reserved repo name: the whole system, no folder
PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::([^}]*))?\}")
SECRETISH = re.compile(r"PASS|SECRET|TOKEN|KEY|CREDENTIAL|PRIVATE", re.I)
CONFIG_FILES = re.compile(r"^(application|bootstrap)[\w-]*\.(ya?ml|properties)$")
ENV_EXAMPLES = (".env.example", ".env.sample", ".env.template", ".env.dist")
FRONTEND_ENV = re.compile(r"^environment[\w.-]*\.ts$")                  # Angular src/environments/environment*.ts
FRONTEND_KEY = re.compile(r"^\s*(\w+)\s*:\s*(?:(['\"`])(.*?)\2|([\w.\-]+))\s*,?\s*$")
OPENAPI_FILES = re.compile(r"^(openapi|swagger)[\w.-]*\.(ya?ml|json)$|\.openapi\.ya?ml$")
TEST_DIRS = {"test", "tests", "__tests__", "e2e", "testFixtures"}
HTTP = ("get", "post", "put", "patch", "delete", "head", "options")
MAPPING = re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping\b(?:\s*\(([^)]*)\))?|@RequestMapping\s*\(([^)]*)\)")
STRING = re.compile(r"\"([^\"]*)\"")
NOTHING = "_Nothing found by the static scan._"
PAGE = "repos/{repo}/reference.md"


def _scan_files(repo: Path) -> list[Path]:
    return sorted((f for f in quickarch.files(repo) if not TEST_DIRS & set(f.relative_to(repo).parts[:-1])),
                  key=lambda f: f.relative_to(repo).as_posix())


def _read(f: Path) -> str:
    try:
        return f.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _ref(name: str, repo: Path, f: Path, line: int | None = None) -> str:
    return f"{name}:{f.relative_to(repo).as_posix()}" + (f"#L{line}" if line else "")


# ---------- the scanners: (repo name, repo folder) -> rows ----------
def env_rows(name: str, repo: Path) -> list[dict]:
    rows: dict[str, dict] = {}

    def add(var, default, f, line):
        hidden = default and SECRETISH.search(var)
        rows.setdefault(var, {"name": var, "default": "(hidden)" if hidden else default,
                              "source": _ref(name, repo, f, line)})
    base_first = sorted(_scan_files(repo), key=lambda f: (f.relative_to(repo).parent.as_posix(),
                                                          f.stem not in ("application", "bootstrap", "environment"), f.name))
    for f in base_first:
        if CONFIG_FILES.match(f.name):
            for i, line in enumerate(_read(f).splitlines(), 1):
                for m in PLACEHOLDER.finditer(line):
                    add(m.group(1), (m.group(2) or "").strip(), f, i)
        elif FRONTEND_ENV.match(f.name) and f.parent.name == "environments":
            for i, line in enumerate(_read(f).splitlines(), 1):
                m = FRONTEND_KEY.match(line)
                if m:
                    add(m.group(1), m.group(3) if m.group(2) else m.group(4), f, i)
        elif f.name in ENV_EXAMPLES:
            for i, line in enumerate(_read(f).splitlines(), 1):
                m = re.match(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)", line)
                if m:
                    add(m.group(1), m.group(2).strip().strip("\"'"), f, i)
    return list(rows.values())


def command_rows(name: str, repo: Path) -> list[dict]:
    rows = []

    def add(cmd, what, src):
        rows.append({"command": cmd, "what": what, "source": f"{name}:{src}"})
    pom, gradle = repo / "pom.xml", next((repo / g for g in ("build.gradle.kts", "build.gradle") if (repo / g).exists()), None)
    if pom.exists():
        mvn = "./mvnw" if (repo / "mvnw").exists() else "mvn"
        if "spring-boot" in _read(pom):
            add(f"{mvn} spring-boot:run", "Run the app locally", "pom.xml")
        add(f"{mvn} test", "Run the tests", "pom.xml")
        add(f"{mvn} package", "Build the artifact", "pom.xml")
    if gradle:
        gw = "./gradlew" if (repo / "gradlew").exists() else "gradle"
        if "spring-boot" in _read(gradle) or "org.springframework.boot" in _read(gradle):
            add(f"{gw} bootRun", "Run the app locally", gradle.name)
        add(f"{gw} test", "Run the tests", gradle.name)
        add(f"{gw} build", "Build the artifact", gradle.name)
    pkg = repo / "package.json"
    if pkg.exists():
        import json
        try:
            scripts = (json.loads(_read(pkg)) or {}).get("scripts") or {}
        except ValueError:
            scripts = {}
        npm = "pnpm" if (repo / "pnpm-lock.yaml").exists() else "yarn" if (repo / "yarn.lock").exists() else "npm"
        for s, cmd in scripts.items():
            add(f"{npm} run {s}", f"`{_cell(cmd)}`", "package.json")
    make = repo / "Makefile"
    if make.exists():
        for t in re.findall(r"^([A-Za-z][\w-]*)\s*:(?!=)", _read(make), re.M):
            add(f"make {t}", "Makefile target", "Makefile")
    compose = next((repo / c for c in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")
                    if (repo / c).exists()), None)
    if compose:
        add("docker compose up", "Start the local stack", compose.name)
    return rows


def endpoint_rows(name: str, repo: Path) -> list[dict]:
    rows = []
    for f in _scan_files(repo):
        if not OPENAPI_FILES.search(f.name):
            continue
        try:
            spec = yaml.safe_load(_read(f)) or {}
        except yaml.YAMLError:
            continue
        for path, ops in ((spec.get("paths") or {}) if isinstance(spec, dict) else {}).items():
            for method, op in (ops or {}).items() if isinstance(ops, dict) else ():
                if method in HTTP:
                    op = op if isinstance(op, dict) else {}
                    rows.append({"method": method.upper(), "path": path,
                                 "what": op.get("summary") or op.get("operationId") or "", "source": _ref(name, repo, f)})
    return rows or _spring_endpoints(name, repo)


def _join(base: str, sub: str) -> str:
    return "/" + "/".join(p for p in f"{base}/{sub}".split("/") if p)


def _spring_endpoints(name: str, repo: Path) -> list[dict]:
    rows = []
    for f in _scan_files(repo):
        if f.suffix not in (".java", ".kt"):
            continue
        text = _read(f)
        if "@RestController" not in text and "@Controller" not in text:
            continue
        cls = re.search(r"\bclass\s+\w+", text)
        head = text[:cls.start()] if cls else ""
        base_m = re.search(r"@RequestMapping\s*\(([^)]*)\)", head)
        base = (STRING.search(base_m.group(1)) or [None, ""])[1] if base_m else ""
        for m in MAPPING.finditer(text, cls.end() if cls else 0):
            if m.group(1):
                method, args = m.group(1).upper(), m.group(2) or ""
            else:
                verb = re.search(r"RequestMethod\.(\w+)", m.group(3))
                method, args = (verb.group(1) if verb else "ANY"), m.group(3)
            sub = STRING.search(args)
            rows.append({"method": method, "path": _join(base, sub.group(1) if sub else ""), "what": "",
                         "source": _ref(name, repo, f, text.count("\n", 0, m.start()) + 1)})
    return rows


def topic_rows(name: str, repo: Path) -> list[dict]:
    rows: dict[tuple, dict] = {}
    for f in _scan_files(repo):
        if f.suffix not in (".java", ".kt", ".ts", ".js", ".mjs", ".py", ".go", ".cs"):
            continue
        text = _read(f)
        for direction, patterns in (("publishes", quickarch.PUBLISH), ("consumes", quickarch.CONSUME)):
            for p in patterns:
                for m in re.finditer(p, text):
                    rows.setdefault((m.group(1), direction), {
                        "topic": m.group(1), "direction": direction,
                        "source": _ref(name, repo, f, text.count("\n", 0, m.start()) + 1)})
    return [rows[k] for k in sorted(rows)]


# ---------- rendering ----------
def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _default(value: str) -> str:
    return "—" if not value else value if value == "(hidden)" else f"`{_cell(value)}`"


def _where(source: str) -> str:
    return f"`{source.split(':', 1)[1]}`"


def render(kind: str, name: str, repo: Path | None, id: str | None = None) -> tuple[str, list[str]] | None:
    """(block body, sources it was read from); None when the kind has nothing to say without a repo folder."""
    if kind in DIAGRAM_KINDS:
        return diagrams.render(kind, name, id)
    if repo is None:
        return None
    if kind == "schema":
        from . import schemas
        return schemas.render_block(name, repo)
    if kind == "env":
        rows = env_rows(name, repo)
        lines = ["| Variable | Default | Where |", "|---|---|---|"] + [
            f"| `{r['name']}` | {_default(r['default'])} | {_where(r['source'])} |"
            for r in rows]
    elif kind == "commands":
        rows = command_rows(name, repo)
        lines = [f"Run in `{name}/`.", "", "| Command | What it does | Source |", "|---|---|---|"] + [
            f"| `{_cell(r['command'])}` | {r['what']} | {_where(r['source'])} |" for r in rows]
    elif kind == "endpoints":
        rows = endpoint_rows(name, repo)
        lines = ["| Method | Path | What | Source |", "|---|---|---|---|"] + [
            f"| {r['method']} | `{_cell(r['path'])}` | {_cell(r['what']) or '—'} | {_where(r['source'])} |" for r in rows]
    else:
        rows = topic_rows(name, repo)
        lines = ["| Topic | Direction | Evidence |", "|---|---|---|"] + [
            f"| `{_cell(r['topic'])}` | {r['direction']} | {_where(r['source'])} |" for r in rows]
    sources = list(dict.fromkeys(r["source"].split("#", 1)[0] for r in rows))
    return ("\n".join(lines) if rows else NOTHING), sources


def sha(body: str) -> str:
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:12]


def block(kind: str, repo: str, body: str, id: str | None = None, confirmed: str | None = None,
          by: str | None = None) -> str:
    attrs = "".join(f" {k}={v}" for k, v in (("id", id), ("confirmed", confirmed), ("by", by)) if v)
    return f"<!-- generated:{kind} repo={repo}{attrs} sha={sha(body)} -->\n{body.strip()}\n<!-- /generated:{kind} -->"


class Scanner:
    """One scan per (kind, repo, id) for a whole refresh or check."""

    def __init__(self):
        self.repos = set(docs.repo_names())
        self.cache: dict[tuple, tuple[str, list[str]]] = {}

    def get(self, kind: str, repo: str, id: str | None = None) -> tuple[str, list[str]] | None:
        if kind not in KINDS + DIAGRAM_KINDS or (repo != SYSTEM and (repo not in self.repos or not repo_dir(repo).is_dir())):
            return None
        if (kind, repo, id) not in self.cache:
            self.cache[(kind, repo, id)] = render(kind, repo, None if repo == SYSTEM else repo_dir(repo), id)
        return self.cache[(kind, repo, id)]


def states(text: str, scan: Scanner):
    """(match, state, fresh body or None) per block; state: new | current | stale | edited | unknown | confirmed |
    confirmed-stale (a person confirmed it; the last two are never rewritten)."""
    for m in BLOCK_RE.finditer(text):
        got = scan.get(m["kind"], m["repo"], m["id"])
        body = m["body"].strip()
        if m["confirmed"]:
            yield m, "confirmed" if got and sha(got[0]) == m["confirmed"] else "confirmed-stale", got and got[0]
        elif got is None:
            yield m, "unknown", None
        elif m["sha"] and m["sha"] != sha(body):
            yield m, "edited", got[0]
        elif not m["sha"]:
            yield m, "new", got[0]
        else:
            yield m, "current" if body == got[0].strip() else "stale", got[0]


def _pages():
    return [(r, ROOT / r["file"]) for r in docs.collect() if r.get("space", "docs") == "docs"]


def refresh(force: bool = False) -> dict:
    """Fill or update every block in the docs. Hand-edited blocks are kept unless `force`; pages a person owns are
    never touched."""
    scan, out = Scanner(), {"updated": [], "edited": [], "human": []}
    for row, f in _pages():
        text = f.read_text(encoding="utf-8")
        if not BLOCK_RE.search(text):
            continue
        if row.get("owner") == "human":
            out["human"].append(rel_file(f))
            continue
        parts, last, sources = [], 0, []
        for m, state, body in states(text, scan):
            if body is None or state in ("confirmed", "confirmed-stale"):
                continue
            sources += scan.get(m["kind"], m["repo"], m["id"])[1]
            if state == "edited" and not force:
                out["edited"].append(f"{rel_file(f)} ({m['kind']}, {m['repo']})")
                continue
            parts += [text[last:m.start()], block(m["kind"], m["repo"], body, id=m["id"])]
            last = m.end()
        new = "".join(parts) + text[last:]
        fm, body_text = docs.split_fm(new)
        if fm.get("x-generated") and sources:
            new = docs.join_fm({**fm, "x-sources": list(dict.fromkeys(sources))}, body_text)
        if new != text:
            f.write_text(new, encoding="utf-8", newline="\n")
            out["updated"].append(rel_file(f))
    return out


def reference_page(repo: str, scan: Scanner) -> str:
    blocks, sources = {}, []
    for k in KINDS:
        body, src = scan.get(k, repo)
        blocks[k] = block(k, repo, body)
        sources += src
    fm = {"type": "overview", "title": f"{repo} reference",
          "description": f"Commands, environment variables, HTTP endpoints and message topics of {repo}, read from its "
                         "build files, configuration and contracts by a static scan (no AI).",
          "tags": [repo], **({"x-sources": list(dict.fromkeys(sources))} if sources else {}), "x-owner": "ai",
          "x-generated": True}
    body = f"""# {repo} reference

> **TL;DR:** What `{repo}` needs to build, run and talk to other services, read straight from its files by a static
> scan (no AI). `camaron blocks` refreshes the tables: fix the source files, not the tables.

## Commands

{blocks['commands']}

## Environment variables

{blocks['env']}

## HTTP endpoints

{blocks['endpoints']}

## Message topics

{blocks['topics']}
"""
    return docs.join_fm(fm, body)


def write_reference(log=lambda _: None) -> list[str]:
    """Create `docs/repos/<repo>/reference.md` for every repo that has none. Existing pages are left to `refresh`."""
    scan, created = Scanner(), []
    for repo in sorted(scan.repos):
        page = DOCS / PAGE.format(repo=repo)
        if page.exists() or not repo_dir(repo).is_dir():
            continue
        text = reference_page(repo, scan)
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8", newline="\n")
        created.append(rel_file(page))
        log(f"✔ {rel_file(page)}")
    return created


def check(rows: list[dict], strict: bool = False) -> tuple[list[str], list[str]]:
    scan, issues = Scanner(), []
    for r in rows:
        if r.get("space", "docs") != "docs" or r.get("owner") == "human":
            continue
        f = ROOT / r["file"]
        text = f.read_text(encoding="utf-8", errors="replace")
        if "<!-- generated:" not in text:
            continue
        for m, state, _ in states(text, scan):
            what = f"{rel_file(f)}: generated block `{m['kind']}` ({m['repo']})"
            if state == "edited":
                issues.append(f"{what} was edited by hand: fix its source in the repo and run "
                              f"`{cli_cmd()} blocks` (`blocks --force` takes the code's version)")
            elif state in ("stale", "new"):
                issues.append(f"{what} is out of date with the code: run `{cli_cmd()} blocks`")
            elif state == "confirmed-stale":
                issues.append(f"{what}: the code changed since this diagram was confirmed — ask for a proposal or "
                              "confirm it again")
    return (issues, []) if strict else ([], issues)
