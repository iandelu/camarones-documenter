"""Library inventory (S7): the direct dependencies of every repo, from its manifests and lockfiles, without AI or
network. Each row: repo, ecosystem, name, version (exact or locked; None when only a range or a parent manages it),
declared (what the manifest says), scope (runtime, test, dev, build), category (dep_categories.yaml), language and
the manifest it came from. The same library at two versions across repos is flagged (`drift`). The result goes to
docs/.work/inventory.json (with the CVEs of lib/osv.py when a scan ran) and docs/overview/libraries.md, an AI draft
whose x-sources are the manifests."""
from __future__ import annotations

import json, re
import xml.etree.ElementTree as ET
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from .common import DOCS, WORK, repo_dir, load_json, save_json
from . import docs, radar

PAGE = DOCS / "overview" / "libraries.md"
DATA = WORK / "inventory.json"
CATEGORIES_FILE = Path(__file__).with_name("dep_categories.yaml")
LANGUAGE = {"Maven": "Java", "npm": "JavaScript", "PyPI": "Python", "Go": "Go", "NuGet": ".NET", "Packagist": "PHP",
            "crates.io": "Rust", "Pub": "Dart"}
LOCK_BYTES = 50_000_000
EXACT = re.compile(r"^v?\d+(\.\d+)*([.+-][\w.+-]+)?$")
MANIFEST_NAMES = ("pom.xml", "build.gradle", "build.gradle.kts", "libs.versions.toml", "package.json", "pyproject.toml",
                  "requirements*.txt", "go.mod", "*.csproj", "composer.json", "Cargo.toml", "pubspec.yaml")


def categories() -> list[tuple[str, list[str]]]:
    return [(k, [str(p).lower() for p in v]) for k, v in (yaml.safe_load(CATEGORIES_FILE.read_text(encoding="utf-8")) or {}).items()]


def category(name: str, cats: list[tuple[str, list[str]]]) -> str:
    low = name.lower()
    names = [low, low.split(":", 1)[1]] if ":" in low else [low]
    for cat, pats in cats:
        if any(fnmatchcase(n, p) for n in names for p in pats):
            return cat
    return "other"


def _row(ecosystem: str, name: str, declared: str | None, scope: str, version: str | None = None, **extra) -> dict:
    declared = (declared or "").strip()
    exact = declared.removeprefix("==").removeprefix("=")
    if version is None and EXACT.match(exact) and ecosystem not in ("crates.io",) and not declared.startswith(("^", "~")):
        version = exact
    return {"ecosystem": ecosystem, "name": name, "version": version, "declared": declared, "scope": scope, **extra}


# ---------- one parser per manifest ----------
def pom(text: str) -> dict:
    """One pom's own facts, before any inheritance: its coordinates, parent, properties, managed and direct deps."""
    root = ET.fromstring(text)
    ns = {"m": root.tag.split("}")[0][1:]} if root.tag.startswith("{") else {}
    q = (lambda path: "/".join(f"m:{p}" for p in path.split("/"))) if ns else (lambda path: path)  # noqa: E731
    find = lambda el, path: (el.findtext(q(path), namespaces=ns) or "").strip()  # noqa: E731
    deps = lambda path: [{k: find(d, k) for k in ("groupId", "artifactId", "version", "scope", "type")}  # noqa: E731
                         for d in root.findall(q(path), ns)]
    props = {}
    for p in root.findall(q("properties"), ns):
        for child in p:
            props[child.tag.split("}")[-1]] = (child.text or "").strip()
    parent = tuple(find(root, f"parent/{k}") for k in ("groupId", "artifactId", "version"))
    group, version = find(root, "groupId") or parent[0], find(root, "version") or parent[2]
    props.update({"project.groupId": group, "project.version": version, "project.parent.version": parent[2]})
    return {"key": f"{group}:{find(root, 'artifactId')}", "version": version, "parent": parent if parent[1] else None,
            "props": props, "managed": deps("dependencyManagement/dependencies/dependency"),
            "deps": deps("dependencies/dependency")}


def _interpolate(value: str, props: dict) -> str:
    for _ in range(5):                                          # ${a} → ${b} → 1.0
        new = re.sub(r"\$\{([^}]+)\}", lambda m: props.get(m.group(1), m.group(0)), value)
        if new == value:
            break
        value = new
    return value


def _lineage(p: dict, index: dict) -> list[dict]:
    """The pom and the ancestors found in the same repo, nearest first (a loop or an outside parent ends it)."""
    out = [p]
    while (parent := out[-1]["parent"]) and (up := index.get(f"{parent[0]}:{parent[1]}")) and up not in out:
        out.append(up)
    return out


def _management(p: dict, index: dict, depth: int = 0) -> tuple[dict, list[str]]:
    """groupId:artifactId → (version, scope, where, raw version, managing pom) from the lineage's dependencyManagement,
    the repo's own imported BOMs included; and the BOMs imported from outside the repo, named but never fetched."""
    chain = _lineage(p, index)
    props = {k: v for x in reversed(chain) for k, v in x["props"].items()}
    managed, outside = {}, []
    for x in reversed(chain):
        where = _interpolate(f"{x['key']}:{x['version']}", props)
        for d in x["managed"]:
            name = _interpolate(f"{d['groupId']}:{d['artifactId']}", props)
            if d["type"] == "pom" and d["scope"] == "import":
                bom = index.get(name)
                if bom is not None and bom is not p and depth < 5:
                    managed.update(_management(bom, index, depth + 1)[0])
                else:
                    outside.append(f"{name}:{_interpolate(d['version'], props)}")
            else:
                managed[name] = (_interpolate(d["version"], props), d["scope"], where, d["version"], x)
    return managed, outside


def maven(text: str) -> list[dict]:
    return maven_deps(pom(text), {})


def maven_deps(p: dict, index: dict) -> list[dict]:
    """A pom's direct dependencies. `index` (groupId:artifactId → pom()) holds the repo's other poms: a module takes
    its versions and properties from a parent or a BOM there, as Maven would, without fetching anything."""
    chain = _lineage(p, index)
    props = {k: v for x in reversed(chain) for k, v in x["props"].items()}
    managed, outside = _management(p, index)
    parent = _interpolate(":".join(x for x in p["parent"] if x), props) if p["parent"] else None
    out = []
    for d in p["deps"]:
        name = _interpolate(f"{d['groupId']}:{d['artifactId']}", props)
        raw = d["version"]
        version, scope, where = (_interpolate(raw, props), d["scope"], None) if raw else managed.get(name, (None, d["scope"], None))[:3]
        if not raw and not where:
            where = ", ".join(dict.fromkeys(outside)) or parent
        scope = {"test": "test", "provided": "build", "runtime": "runtime"}.get(d["scope"] or scope, "runtime")
        out.append(_row("Maven", name, raw, scope, version if version and "${" not in version else None,
                        managedBy=None if raw else where))
    return out


PROPERTY = re.compile(r"\s*\$\{([\w.-]+)\}\s*")


def version_site(repo: Path, rel: str, name: str) -> dict | None:
    """Where this repo writes the version `name` gets in the pom at `rel`, which `camaron bump` rewrites: {"file",
    "property"} or {"file", "version"} (the text of a <version> there). A module's version may sit in its parent or in
    a BOM of the same repo. None when it is set outside the repo (a parent or a BOM never fetched)."""
    poms = _poms(repo)
    if rel not in poms:
        return None
    index = {p["key"]: p for p in poms.values()}
    p = poms[rel]
    chain = _lineage(p, index)
    props = {k: v for x in reversed(chain) for k, v in x["props"].items()}
    own = [d["version"] for d in p["deps"] if d["version"] and _interpolate(f"{d['groupId']}:{d['artifactId']}", props) == name]
    raw, owner = (own[0], p) if own else (_management(p, index)[0].get(name) or (None,) * 5)[3:]
    for _ in range(5):                                          # ${a} → ${b} → 1.0: the literal is what changes
        if not raw:
            return None
        if not (m := PROPERTY.fullmatch(raw)):
            return {"file": owner["rel"], "version": raw.strip()} if "${" not in raw else None
        prop = m.group(1)
        holder = next((x for x in chain + _lineage(owner, index) if prop in x["props"] and not prop.startswith("project.")), None)
        if holder is None:
            return None
        if not PROPERTY.fullmatch(holder["props"][prop]):
            return {"file": holder["rel"], "property": prop}
        raw, owner = holder["props"][prop], holder
    return None


GRADLE_DEP = re.compile(r"\b(implementation|api|compileOnly|runtimeOnly|annotationProcessor|kapt|ksp|testImplementation|"
                        r"testRuntimeOnly|testCompileOnly|androidTestImplementation|developmentOnly)\s*\(?\s*['\"]"
                        r"([\w.-]+):([\w.-]+):([^'\"@]+)['\"]")


def gradle(text: str) -> list[dict]:
    out = []
    for conf, group, artifact, version in GRADLE_DEP.findall(text):
        scope = "test" if conf.startswith(("test", "androidTest")) else "build" if conf in (
            "compileOnly", "annotationProcessor", "kapt", "ksp") else "runtime"
        out.append(_row("Maven", f"{group}:{artifact}", version, scope))
    return out


def version_catalog(text: str) -> list[dict]:
    versions = dict(re.findall(r'^\s*([\w.-]+)\s*=\s*"([^"]+)"', text.split("[libraries]")[0].split("[versions]")[-1], re.M))
    body = text.split("[libraries]", 1)[1].split("\n[", 1)[0] if "[libraries]" in text else ""
    out = []
    for line in body.splitlines():
        if m := re.search(r'module\s*=\s*"([^"]+)"', line):
            ref = re.search(r'version\.ref\s*=\s*"([^"]+)"', line)
            ver = re.search(r'version\s*=\s*"([^"]+)"', line)
            out.append(_row("Maven", m.group(1), versions.get(ref.group(1)) if ref else ver.group(1) if ver else "", "runtime"))
        elif m := re.search(r'=\s*"([\w.-]+:[\w.-]+):([^"]+)"', line):
            out.append(_row("Maven", m.group(1), m.group(2), "runtime"))
    return out


def npm(text: str, lock: dict | None) -> list[dict]:
    pkg = json.loads(text)
    locked = {k.removeprefix("node_modules/"): v.get("version") for k, v in ((lock or {}).get("packages") or {}).items()
              if k.startswith("node_modules/") and "/node_modules/" not in k}
    if not locked:
        locked = {k: v.get("version") for k, v in ((lock or {}).get("dependencies") or {}).items()}   # lockfile v1
    out = []
    for key, scope in (("dependencies", "runtime"), ("devDependencies", "dev"), ("optionalDependencies", "runtime")):
        for name, spec in (pkg.get(key) or {}).items():
            out.append(_row("npm", name, str(spec), scope, locked.get(name)))
    return out


PEP508 = re.compile(r"^\s*([A-Za-z0-9][\w.-]*)(\[[^\]]*\])?\s*([^;#]*)")


def _pep508(spec: str, scope: str, locked: dict) -> dict | None:
    m = PEP508.match(spec)
    if not m:
        return None
    name = m.group(1)
    return _row("PyPI", name, m.group(3).strip(), scope, locked.get(name.lower().replace("_", "-")))


def _toml_arrays(text: str, header: str) -> dict[str, list[str]]:
    """`key = [ "a", "b" ]` arrays inside one TOML table (no TOML parser on Python 3.10)."""
    m = re.search(rf"^\[{re.escape(header)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if not m:
        return {}
    return {k: [a or b for a, b in re.findall(r'"([^"]+)"|\'([^\']+)\'', body)]
            for k, body in re.findall(r"^\s*([\w-]+)\s*=\s*\[(.*?)\]", m.group(1), re.M | re.S)}


def python_lock(text: str) -> dict[str, str]:
    return {n.lower().replace("_", "-"): v for n, v in re.findall(r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"', text)}


def pyproject(text: str, locked: dict) -> list[dict]:
    out = []
    project = _toml_arrays(text, "project")
    for spec in project.get("dependencies") or []:
        out.append(_pep508(spec, "runtime", locked))
    for table in ("project.optional-dependencies", "dependency-groups", "tool.uv"):
        for group, specs in _toml_arrays(text, table).items():
            scope = "dev" if group in ("dev", "test", "tests", "lint", "dev-dependencies") else "runtime"
            out += [_pep508(s, scope, locked) for s in specs]
    m = re.search(r"^\[tool\.poetry\.(dependencies|group\.dev\.dependencies|dev-dependencies)\]\s*$(.*?)(?=^\[|\Z)",
                  text, re.M | re.S)
    if m:
        for name, spec in re.findall(r'^\s*([\w.-]+)\s*=\s*"([^"]*)"', m.group(2), re.M):
            if name != "python":
                out.append(_row("PyPI", name, spec, "runtime" if m.group(1) == "dependencies" else "dev",
                                locked.get(name.lower())))
    return [r for r in out if r]


def requirements(text: str, locked: dict) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith(("-", "git+", "http")) and (r := _pep508(line, "runtime", locked)):
            out.append(r)
    return out


def gomod(text: str) -> list[dict]:
    out = []
    block = re.findall(r"require\s*\((.*?)\)", text, re.S)
    lines = [l for b in block for l in b.splitlines()] + re.findall(r"^require\s+(\S+\s+\S+.*)$", text, re.M)
    for line in lines:
        if "// indirect" in line:
            continue
        if m := re.match(r"\s*(\S+)\s+(v\S+)", line):
            out.append(_row("Go", m.group(1), m.group(2), "runtime"))
    return out


def csproj(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"<PackageReference\b([^>]*)>", text):
        name = re.search(r'Include="([^"]+)"', m.group(1))
        attr = re.search(r'Version="([^"]+)"', m.group(1))
        child = re.match(r"\s*<Version>([^<]+)</Version>", text[m.end():])
        if name:
            out.append(_row("NuGet", name.group(1), attr.group(1) if attr else child.group(1) if child else "", "runtime"))
    return out


def composer(text: str) -> list[dict]:
    data = json.loads(text)
    return [_row("Packagist", n, v, scope) for key, scope in (("require", "runtime"), ("require-dev", "dev"))
            for n, v in (data.get(key) or {}).items() if "/" in n]


def cargo(text: str) -> list[dict]:
    out = []
    for table, scope in (("dependencies", "runtime"), ("dev-dependencies", "dev"), ("build-dependencies", "build")):
        m = re.search(rf"^\[{table}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
        for name, rest in re.findall(r"^\s*([\w-]+)\s*=\s*(.+)$", m.group(1), re.M) if m else []:
            v = re.search(r'version\s*=\s*"([^"]+)"', rest) if rest.startswith("{") else re.match(r'"([^"]+)"', rest)
            out.append(_row("crates.io", name, v.group(1) if v else "", scope))
    return out


def pubspec(text: str) -> list[dict]:
    data = yaml.safe_load(text) or {}
    out = []
    for key, scope in (("dependencies", "runtime"), ("dev_dependencies", "dev")):
        for name, spec in (data.get(key) or {}).items():
            declared = "sdk" if isinstance(spec, dict) and "sdk" in spec else (
                str(spec.get("version", "")) if isinstance(spec, dict) else str(spec or ""))
            out.append(_row("Pub", name, declared, scope))
    return out


# ---------- the scan ----------
def _read(f: Path) -> str:
    return radar.read_small(f)


def _poms(repo: Path, paths: list[str] | None = None) -> dict[str, dict]:
    """Every readable pom of the repo by its path in it: what a module inherits from is looked up here."""
    out = {}
    for rel in radar.entries(repo) if paths is None else paths:
        if Path(rel).name == "pom.xml" and (repo / rel).is_file():
            try:
                out[rel] = {**pom(_read(repo / rel)), "rel": rel}
            except ET.ParseError:
                continue
    return out


def scan_repo(name: str, repo: Path) -> list[dict]:
    rows: list[dict] = []
    paths = [p for p in radar.entries(repo) if any(radar.matches(p, m) for m in MANIFEST_NAMES)]
    poms = _poms(repo, paths)
    index = {p["key"]: p for p in poms.values()}
    for rel in paths:
        f = repo / rel
        if not f.is_file():
            continue
        text, base = _read(f), f.name
        try:
            if base == "pom.xml":
                found = maven_deps(poms[rel], index) if rel in poms else []
            elif base in ("build.gradle", "build.gradle.kts"):
                found = gradle(text)
            elif base == "libs.versions.toml":
                found = version_catalog(text)
            elif base == "package.json":
                found = npm(text, _json_lock(f.with_name("package-lock.json")))
            elif base == "pyproject.toml":
                found = pyproject(text, _python_locks(f.parent))
            elif radar.matches(rel, "requirements*.txt"):
                found = requirements(text, _python_locks(f.parent))
            elif base == "go.mod":
                found = gomod(text)
            elif base.endswith(".csproj"):
                found = csproj(text)
            elif base == "composer.json":
                found = composer(text)
            elif base == "Cargo.toml":
                found = cargo(text)
            elif base == "pubspec.yaml":
                found = pubspec(text)
            else:
                found = []
        except (ValueError, ET.ParseError, yaml.YAMLError):
            continue                                          # a manifest the scan cannot read is skipped, not fatal
        rows += [{**r, "repo": name, "source": f"{name}:{rel}"} for r in found]
    return rows


def _json_lock(f: Path) -> dict | None:
    """A lockfile is optional and often large: read it up to LOCK_BYTES, and without it the declared ranges stay."""
    try:
        return json.loads(f.read_text(encoding="utf-8", errors="ignore")) if f.is_file() and f.stat().st_size <= LOCK_BYTES else None
    except (OSError, ValueError):
        return None


def _python_locks(folder: Path) -> dict[str, str]:
    for lock in ("uv.lock", "poetry.lock"):
        f = folder / lock
        if f.is_file() and f.stat().st_size <= LOCK_BYTES:
            return python_lock(f.read_text(encoding="utf-8", errors="ignore"))
    return {}


def scan() -> dict:
    cats = categories()
    rows = []
    for r in docs.workspace()["repos"]:
        repo = repo_dir(r["name"])
        if repo.is_dir():
            rows += scan_repo(r["name"], repo)
    seen: dict[tuple, set] = {}
    for row in rows:
        row["category"] = category(row["name"], cats)
        row["language"] = LANGUAGE.get(row["ecosystem"], row["ecosystem"])
        seen.setdefault((row["ecosystem"], row["name"]), set()).add(row["version"] or row["declared"])
    for row in rows:
        row["drift"] = len(seen[(row["ecosystem"], row["name"])]) > 1
        row.setdefault("managedBy", None)
    rows.sort(key=lambda r: (r["repo"], r["category"], r["name"]))
    return {"libraries": rows, "vulns": None}


def cell(text: str) -> str:
    return str(text).replace("|", "\\|")


def render(result: dict) -> str:
    rows = result["libraries"]
    fm = {"type": "overview", "title": "Libraries",
          "description": "Every repository's direct dependencies by category (framework, data, cache, security, messaging, "
                         "testing…), with versions and known vulnerabilities. Static scan of the manifests, no AI.",
          "tags": ["stack", "dependencies"], "x-sources": sorted({r["source"] for r in rows}), "x-owner": "ai"}
    from . import pages
    vulns = result.get("vulns") is not None
    repos = {*docs.repo_names(), *(r["repo"] for r in rows)}                  # the workspace's, manifests or not
    drift = {r["name"] for r in rows if r["drift"]}
    vulnerable = {r["name"] for r in rows if r.get("vulns")}
    tldr = (f"{pages.count(len(rows), 'direct dependency', 'direct dependencies')} across {pages.count(len(repos), 'repo')}" +
            (f"; {pages.count(len(drift), 'library', 'libraries')} with different versions in different repos" if drift else "") +
            (f"; {pages.count(len(vulnerable), 'library', 'libraries')} with known vulnerabilities" if vulnerable else "") + ".")
    lines = ["# Libraries", "", f"> **TL;DR:** {tldr}", ""]
    for repo in dict.fromkeys(r["repo"] for r in rows):
        lines += [f"## {repo}", "", "| Category | Library | Version | Scope |" + (" Vulnerabilities |" if vulns else ""),
                  "|---|---|---|---|" + ("---|" if vulns else "")]
        for r in (x for x in rows if x["repo"] == repo):
            version = r["version"] or (f"managed ({r['managedBy'].rsplit(':', 1)[-1]})" if r["managedBy"] else r["declared"]) or "—"
            row = f"| {r['category']} | `{cell(r['name'])}` | {cell(version)}{' ⚠️ drift' if r['drift'] else ''} | {r['scope']} |"
            if vulns:
                row += " " + (", ".join(f"{v['cve'] or v['id']} ({v['severity']}" + (f", fixed in {v['fixed']})" if v["fixed"] else ")")
                                        for v in r.get("vulns") or []) or "—") + " |"
            lines.append(row)
        lines.append("")
    if not rows:
        lines += ["No manifests found.", ""]
    lines += [pages.HOW, "Read from each repo's manifests and lockfiles with no AI. `camaron inventory --cves` adds the known "
              "vulnerabilities (OSV); the portal's Libraries tab filters this list.", ":::", ""]
    return docs.join_fm(fm, "\n".join(lines))


def run(log=print, cves: bool = False) -> Path:
    """Scan, keep the result in docs/.work/inventory.json and write docs/overview/libraries.md (never over a human's).
    `cves`: add the known vulnerabilities (lib/osv.py); otherwise the last scan's findings are kept for unchanged rows."""
    result = scan()
    if cves:
        from . import osv
        result["vulns"] = osv.attach(result["libraries"], log=log)
    else:
        last = load()
        old = {(r["repo"], r["ecosystem"], r["name"], r["version"]): r.get("vulns") for r in last.get("libraries") or []}
        for r in result["libraries"]:
            if (key := (r["repo"], r["ecosystem"], r["name"], r["version"])) in old and old[key] is not None:
                r["vulns"] = old[key]
        result["vulns"] = last.get("vulns") if any("vulns" in r for r in result["libraries"]) else None
    save_json(DATA, result)
    old = docs.split_fm(PAGE.read_text(encoding="utf-8"))[0] if PAGE.exists() else {}
    if old.get("x-owner") == "human":
        log(f"· {PAGE.name} is owned by a human: not rewritten")
        return PAGE
    text = render(result)
    if old.get("x-confirmed"):
        fm, body = docs.split_fm(text)
        text = docs.join_fm({**fm, "x-confirmed": old["x-confirmed"]}, body)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    log(f"✔ {len(result['libraries'])} libraries in {len({r['repo'] for r in result['libraries']})} repos")
    return PAGE


def exit_code(data: dict, fail_on: str | None) -> int:
    """0 unless CI asked to fail (`--fail-on high` counts critical too) and a known vulnerability is that serious:
    a scan that finds vulnerabilities did its job, and the desktop app shows a non-zero exit as a failed job."""
    worst = {"high": ("high", "critical"), "critical": ("critical",)}.get(fail_on or "", ())
    return 1 if any(v.get("severity") in worst for r in data.get("libraries") or [] for v in r.get("vulns") or []) else 0


def load() -> dict:
    return load_json(DATA, {}) if DATA.exists() else {}
