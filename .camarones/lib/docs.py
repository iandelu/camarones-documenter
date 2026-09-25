"""Docs model: workspace, repo sync, incremental state, trust (draft/confirmed), translations, llms.txt, search."""
from __future__ import annotations

import datetime as dt, hashlib, math, os, re, shutil, subprocess, tarfile, tempfile
from collections import Counter
from pathlib import Path
from typing import Callable

import yaml

from .common import (ROOT, DOCS, WS_FILE, CACHE, WORKSPACE, CAM_DIR, CAM_LAYOUT, repo_dir, rel_file, run, load_json,
                     save_json)

STATE_FILE = DOCS / ".state.json"
STATUS_FILE = DOCS / ".status.json"
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
GI_START, GI_END = "# >>> camarones repos >>>", "# <<< camarones repos <<<"
Log = Callable[[str], None]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------- workspace ----------
def ws_file() -> Path:
    legacy = ROOT / "workspace.yaml"
    if legacy.exists() and not WS_FILE.exists():      # migrate older layout
        WS_FILE.parent.mkdir(parents=True, exist_ok=True)
        legacy.replace(WS_FILE)
    return WS_FILE


def workspace() -> dict:
    ws = (yaml.safe_load(ws_file().read_text(encoding="utf-8")) if ws_file().exists() else None) or {}
    ws.setdefault("project", {})
    ws.setdefault("repos", [])
    ws["project"].setdefault("name", WORKSPACE.name)
    ws["project"].setdefault("translations", ["es"])
    return ws


def save_workspace(ws: dict) -> None:
    header = "# Camarones Documenter workspace: which repos form this project. Edit freely, then run sync.\n"
    f = ws_file()
    f.parent.mkdir(parents=True, exist_ok=True)   # global install: .camarones/ may not exist yet (no code lives here)
    f.write_text(header + yaml.safe_dump(ws, sort_keys=False, allow_unicode=True), encoding="utf-8")


def repo_names() -> list[str]:
    return [r["name"] for r in workspace()["repos"]]


def wiki_repos() -> list[str]:
    """Repos that get an OpenWiki (`wiki: true` in workspace.yaml). None chosen → none: a wiki per repo costs a full
    agent run, and libraries or CI repos rarely need one."""
    return [r["name"] for r in workspace()["repos"] if r.get("wiki")]


def set_wiki_repos(names: list[str]) -> None:
    ws = workspace()
    for r in ws["repos"]:
        r["wiki"] = r["name"] in names
    save_workspace(ws)


def git(repo: Path, *args: str, check=True, env: dict | None = None) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, **(env or {})})
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo.name}: {r.stderr.strip()}")
    return r.stdout.strip()


def detect_repos() -> list[dict]:
    """Repos already sitting in the workspace folder (the 'drop the kit next to your repos' case)."""
    found = []
    for d in sorted(p for p in WORKSPACE.iterdir() if p.is_dir() and (p / ".git").exists()):
        if d.name.startswith(".") or d.name in ("docs", CAM_DIR) or d.name.lower().startswith("camarones-"):
            continue
        url = git(d, "remote", "get-url", "origin", check=False)
        branch = git(d, "rev-parse", "--abbrev-ref", "HEAD", check=False) or "main"
        found.append({"name": d.name, "url": url or "", "branch": branch, "kind": guess_kind(d)})
    return found


def guess_kind(d: Path) -> str:
    if (d / "pubspec.yaml").exists():
        return "mobileApp"
    if (d / "package.json").exists() and not any((d / f).exists() for f in ("pom.xml", "build.gradle", "build.gradle.kts")):
        pkg = (d / "package.json").read_text(encoding="utf-8", errors="ignore")
        if any(k in pkg for k in ('"react"', '"vue"', '"@angular/core"', '"svelte"', '"next"')):
            return "webapp"
    if any((d / f).exists() for f in ("Chart.yaml", "main.tf", "kustomization.yaml")):
        return "infra"
    return "service"


def sync_repos(log: Log = print) -> list[str]:
    """Clone missing repos, fast-forward clean ones. Tokens (🔑) are injected per call, never stored in the repos."""
    from . import creds
    failed = []
    for r in workspace()["repos"]:
        path, branch, url = repo_dir(r["name"]), r.get("branch", "main"), r.get("url", "")
        env = creds.git_env(url)
        if not (path / ".git").exists():
            if not url:
                log(f"⚠ {r['name']}: no url and not present — skipped")
                continue
            log(f"cloning {r['name']} ({branch})…")
            p = subprocess.run(["git", "clone", "--branch", branch, url, str(path)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env={**os.environ, **env})
            if p.returncode != 0:
                failed.append(r["name"])
                hint = " — add a GitLab/GitHub token (🔑)" if re.search(r"auth|denied|403|401|could not read|permission",
                                                                       p.stderr, re.I) else ""
                log(f"⚠ {r['name']}: clone failed{hint}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}")
        elif not url:
            log(f"local  {r['name']} (no remote)")
        elif git(path, "status", "--porcelain", "--untracked-files=no", check=False):
            log(f"skip   {r['name']}: local changes, not pulling")
        else:
            log(f"pulling {r['name']} ({branch})…")
            try:
                git(path, "fetch", "--quiet", "origin", branch, env=env)
                git(path, "checkout", "--quiet", branch)
                git(path, "merge", "--ff-only", "--quiet", f"origin/{branch}")
            except RuntimeError as e:
                # The repo is already cloned locally — a remote that 404s or rejects auth (renamed,
                # made private, deleted, expired token) shouldn't block work on what's already there.
                hint = " — add a GitLab/GitHub token (🔑)" if re.search(r"auth|denied|403|401|could not read", str(e), re.I) else ""
                if re.search(r"not found|repository .* not found", str(e), re.I):
                    hint = " — check the repo still exists at that URL/org, or that you have access"
                log(f"⚠ {r['name']}: remote unreachable, using local copy as-is{hint}: {e}")
    write_gitignore()
    return failed


def write_gitignore() -> None:
    gi = ROOT / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    repos = [] if CAM_LAYOUT else [f"/{n}/" for n in repo_names()]      # cam-docs layout: repos live next to it
    block = "\n".join([GI_START, *repos, "/.camarones/.cache/", "/graph/", "/.claude/settings.local.json",
                       "camarones-documenter*/", "camarones-kit*/", "camarones-documenter*.zip", ".DS_Store", GI_END])
    if GI_START in text:
        text = re.sub(re.escape(GI_START) + r".*?" + re.escape(GI_END), lambda _: block, text, flags=re.S)
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + block + "\n"
    gi.write_text(text, encoding="utf-8")


# ---------- incremental state ----------
def changes() -> dict:
    state, out = load_json(STATE_FILE, {"repos": {}}), {}
    for r in workspace()["repos"]:
        path = repo_dir(r["name"])
        if not (path / ".git").exists():
            out[r["name"]] = {"status": "missing"}
            continue
        head = git(path, "rev-parse", "HEAD", check=False)
        last = state["repos"].get(r["name"], {}).get("sha")
        if not last:
            out[r["name"]] = {"status": "never-documented", "head": head}
        elif last == head:
            out[r["name"]] = {"status": "up-to-date", "head": head}
        else:
            known = subprocess.run(["git", "-C", str(path), "cat-file", "-e", f"{last}^{{commit}}"],
                                   capture_output=True).returncode == 0
            files = git(path, "diff", "--name-status", f"{last}..{head}").splitlines() if known else []
            out[r["name"]] = {"status": "changed" if known else "history-rewritten", "from": last, "head": head, "files": files}
    for name in sorted(set(state["repos"]) - set(repo_names())):
        out[name] = {"status": "removed-from-workspace"}
    return out


def mark_documented(names: list[str] | None = None) -> list[str]:
    state = load_json(STATE_FILE, {"repos": {}})
    names = names or repo_names()
    for n in names:
        state["repos"][n] = {"sha": git(repo_dir(n), "rev-parse", "HEAD"), "at": now()}
    for n in set(state["repos"]) - set(repo_names()):
        del state["repos"][n]
    save_json(STATE_FILE, state)
    return names


# ---------- docs model ----------
def split_fm(text: str) -> tuple[dict, str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), text[m.end():]


def join_fm(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=120) + "---\n" + body


def body_sha(body: str) -> str:
    norm = "\n".join(line.rstrip() for line in body.strip().splitlines())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def iter_docs():
    """(logical_path, file) for every canonical doc: docs/ + each repo's OpenWiki (cam-docs/wikis/<repo>)."""
    if DOCS.is_dir():
        for f in sorted(DOCS.rglob("*.md")):
            rel = f.relative_to(DOCS)
            if rel.parts[0] == "i18n" or any(p.startswith(".") for p in rel.parts):
                continue
            yield rel.as_posix(), f
    for n in repo_names():
        ow = wiki_dir(n)
        if ow.is_dir():
            for f in sorted(ow.rglob("*.md")):
                rel = f.relative_to(ow)
                if any(p.startswith(".") for p in rel.parts) or rel.name in ("INSTRUCTIONS.md", "log.md"):
                    continue
                yield f"repos/{n}/{rel.as_posix()}", f


def wiki_dir(repo: str) -> Path:
    """A repo's OpenWiki lives in cam-docs/wikis/<repo> (the repo gets an untracked openwiki/ symlink to it)."""
    own = ROOT / "wikis" / repo
    return own if own.is_dir() or CAM_LAYOUT else repo_dir(repo) / "openwiki"


def repo_file_exists(ref: str) -> bool:
    ref = ref.split("#", 1)[0]
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    if ":" not in ref:
        return True
    repo, path = ref.split(":", 1)
    base = ROOT if repo in ("umbrella", ".", CAM_DIR) else repo_dir(repo)
    return (base / path).exists()


def first_heading(body: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else None


def trust_of(fm: dict, sha: str) -> str:
    conf = fm.get("x-confirmed") or {}
    return "confirmed" if conf.get("body_sha") == sha else ("needs-reconfirm" if conf else "draft")


def doc_status(logical: str, f: Path, langs: list[str]) -> dict:
    fm, body = split_fm(f.read_text(encoding="utf-8"))
    sha = body_sha(body)
    trust = trust_of(fm, sha)
    missing = [s for s in (fm.get("x-sources") or []) if not repo_file_exists(str(s))]
    i18n = {}
    for lang in ([] if fm.get("type") == "interview" else langs):   # working notes are not translated
        tf = DOCS / "i18n" / lang / logical
        if not tf.exists():
            i18n[lang] = "missing"
        else:
            tfm, _ = split_fm(tf.read_text(encoding="utf-8"))
            i18n[lang] = "current" if (tfm.get("x-translation-of") or {}).get("body_sha") == sha else "outdated"
    return {"path": logical, "file": rel_file(f),
            "title": fm.get("title") or first_heading(body) or f.stem, "description": fm.get("description", ""),
            "type": fm.get("type", ""), "trust": trust, "owner": fm.get("x-owner", "ai"), "orphan_sources": missing,
            "i18n": i18n, "body_sha": sha, "has_frontmatter": bool(fm)}


def collect() -> list[dict]:
    langs = workspace()["project"].get("translations", [])
    rows = [doc_status(l, f, langs) for l, f in iter_docs()]
    save_json(STATUS_FILE, {"generated_at": now(), "docs": rows})
    return rows


def summary(rows: list[dict]) -> dict:
    c = {k: sum(1 for r in rows if r["trust"] == k) for k in ("confirmed", "needs-reconfirm", "draft")}
    c["total"] = len(rows)
    c["orphans"] = sum(1 for r in rows if r["orphan_sources"])
    c["untranslated"] = sum(1 for r in rows if any(v != "current" for v in r["i18n"].values()))
    return c


def resolve(p: str) -> Path:
    f = Path(p)
    if f.is_absolute():
        return f
    return (Path.cwd() / f).resolve() if (Path.cwd() / f).exists() else (ROOT / f).resolve()


def confirm(files: list[str], by: str) -> list[str]:
    done = []
    for p in files:
        f = resolve(p)
        fm, body = split_fm(f.read_text(encoding="utf-8"))
        if not fm:
            raise RuntimeError(f"{p}: no frontmatter, refusing to confirm")
        fm["x-confirmed"] = {"by": by, "at": now(), "body_sha": body_sha(body)}
        f.write_text(join_fm(fm, body), encoding="utf-8")
        done.append(p)
    return done


def translated(files: list[str]) -> list[str]:
    canon = dict(iter_docs())
    done = []
    for p in files:
        f = resolve(p)
        rel = f.relative_to(DOCS / "i18n")
        lang, logical = rel.parts[0], Path(*rel.parts[1:]).as_posix()
        if logical not in canon:
            raise RuntimeError(f"{p}: no canonical doc at {logical}")
        _, cbody = split_fm(canon[logical].read_text(encoding="utf-8"))
        fm, body = split_fm(f.read_text(encoding="utf-8"))
        fm["x-translation-of"] = {"path": logical, "lang": lang, "body_sha": body_sha(cbody)}
        f.write_text(join_fm(fm, body), encoding="utf-8")
        done.append(f"{p} <- {logical}")
    return done


def llms() -> int:
    ws, rows = workspace(), collect()
    order = ["index.md", "overview", "architecture", "domain", "flows", "data", "deployment", "decisions", "quality", "guides", "repos"]
    def key(r):
        head = r["path"].split("/")[0]
        return (order.index(head) if head in order else len(order), r["path"])
    lines = [f"# {ws['project']['name']}", "",
             "> Documentation index for AI agents. Trust: `confirmed` = verified by a human (source of truth); "
             "`draft` = AI-generated, verify against code; `needs-reconfirm` = confirmed, then changed.", ""]
    section = None
    for r in sorted(rows, key=key):
        head = "repos/" + r["path"].split("/")[1] if r["path"].startswith("repos/") else (r["path"].split("/")[0] if "/" in r["path"] else "root")
        if head != section:
            lines += ["", f"## {head}"]
            section = head
        link = os.path.relpath(ROOT / r["file"], DOCS).replace("\\", "/")
        desc = f": {r['description']}" if r["description"] else ""
        lines.append(f"- [{r['title']}]({link}) [{r['trust']}]{desc}")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "llms.txt").write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)) + "\n", encoding="utf-8")
    return len(rows)


def check(strict: bool = False, secrets_only: bool = False) -> tuple[list[str], list[str]]:
    from . import quality
    if secrets_only:
        return quality.check_secrets()
    errors, warns = [], []
    rows = collect()
    for r in rows:
        if not r["has_frontmatter"]:
            errors.append(f"{r['file']}: missing frontmatter")
        if r["orphan_sources"]:
            errors.append(f"{r['file']}: sources no longer exist: {r['orphan_sources']}")
        if r["trust"] == "needs-reconfirm":
            (errors if strict else warns).append(f"{r['file']}: changed after human confirmation")
        for lang, st in r["i18n"].items():
            if st != "current":
                warns.append(f"{r['file']}: translation {lang} {st}")
    for fn in quality.CHECKS:
        e, w = fn(rows, strict)
        errors += e
        warns += w
    return errors, warns


# ---------- search (portal + MCP): BM25 over body tokens, prefix-matched (pedido → pedidos) ----------
def search(query: str, limit: int = 20) -> list[dict]:
    terms = list(dict.fromkeys(t for t in re.findall(r"\w+", query.lower()) if len(t) > 1))
    if not terms:
        return []
    pages = []
    for logical, f in iter_docs():
        fm, body = split_fm(f.read_text(encoding="utf-8", errors="replace"))
        toks = Counter(re.findall(r"\w+", body.lower()))
        tf = {t: sum(c for w, c in toks.items() if w.startswith(t)) for t in terms}
        title = fm.get("title") or first_heading(body) or f.stem
        pages.append((logical, fm, body, sum(toks.values()), tf, str(title)))
    if not pages:
        return []
    n, avg = len(pages), max(1.0, sum(p[3] for p in pages) / len(pages))
    idf = {t: math.log(1 + (n - (df := sum(1 for p in pages if p[4][t])) + 0.5) / (df + 0.5)) for t in terms}
    k1, b, hits = 1.2, 0.75, []
    for logical, fm, body, length, tf, title in pages:
        score = sum(idf[t] * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / avg)) for t in terms)
        score += sum(2 * idf[t] for t in terms if t in title.lower() or t in logical.lower())
        if score:
            hits.append({"path": logical, "title": title, "trust": trust_of(fm, body_sha(body)), "score": round(score, 2),
                         "lines": [l.strip()[:240] for l in body.splitlines() if any(t in l.lower() for t in terms)][:3]})
    hits.sort(key=lambda h: -h["score"])
    return hits[:limit]


CDN_RE = re.compile(r"https://(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)")


def vendor(site: Path) -> tuple[int, list[str]]:
    """Graph viewers load libraries from CDNs: fetch them through npm (works with an internal npm mirror) and
    serve them from /vendor/ so the portal works on-prem without internet."""
    targets = [f for d in ("code-graph", "wiki-graph") if (site / d).exists()
               for f in (site / d).rglob("*") if f.suffix in (".html", ".js")]
    done, failed = set(), set()
    for f in targets:
        text = f.read_text(encoding="utf-8", errors="ignore")
        def sub(m):
            pkg, ver, path = m.groups()
            key = f"{pkg}@{ver}"
            src = None if key in failed else vendor_file(pkg, ver, path)
            if not src:
                failed.add(key)
                return m.group(0)
            done.add(key)
            dst = site / "vendor" / key / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            return f"/vendor/{key}/{path}"
        new = CDN_RE.sub(sub, text)
        if new != text:
            f.write_text(new, encoding="utf-8")
    return len(done), sorted(failed)


def vendor_file(pkg: str, ver: str, path: str) -> Path | None:
    """One file of an npm package, fetched once with `npm pack` into the cache."""
    cache = CACHE / "vendor-cache"
    pkg_dir = cache / f"{pkg}@{ver}".replace("/", "__")
    if not pkg_dir.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            r = run(["npm", "pack", f"{pkg}@{ver}", "--silent", "--pack-destination", tmp], check=False, capture=True)
            tgz = next(Path(tmp).glob("*.tgz"), None)
            if r.returncode != 0 or not tgz:
                return None
            with tarfile.open(tgz) as t:
                try:
                    t.extractall(pkg_dir, filter="data")
                except TypeError:
                    t.extractall(pkg_dir)
    f = (pkg_dir / "package" / path).resolve()
    return f if f.is_file() and pkg_dir.resolve() in f.parents else None


# ---------- human review ----------
FEEDBACK = DOCS / ".work" / "review-feedback.md"
REVIEW_ORDER = ["domain", "glossary", "business-flow", "architecture", "data-model", "deployment", "decision", "quality",
                "overview", "guide"]


def review_queue() -> list[dict]:
    """Pages waiting for a human: re-confirmations first, then by how much the doc type matters to agents."""
    rows = [r for r in collect() if r["trust"] != "confirmed" and r["type"] != "interview" and r["owner"] != "human"
            and r["has_frontmatter"] and r["path"] != "status.md"]
    waiting = {m.group(1) for l in pending_feedback() if (m := re.match(r"- \[ \] `([^`]+)`", l))}
    rows = [r for r in rows if r["file"] not in waiting]      # changes requested: back in the queue once the AI fixed them
    def key(r):
        t = r["type"] if r["type"] in REVIEW_ORDER else "zzz"
        return (0 if r["trust"] == "needs-reconfirm" else 1, REVIEW_ORDER.index(t) if t in REVIEW_ORDER else 99, r["path"])
    return sorted(rows, key=key)


def add_feedback(doc_file: str, text: str, by: str) -> None:
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK.exists():
        FEEDBACK.write_text("# Review feedback\n\nHuman review comments. Agents apply them in the `review-fixes` unit and tick them.\n\n",
                            encoding="utf-8")
    with FEEDBACK.open("a", encoding="utf-8") as fh:
        fh.write(f"- [ ] `{doc_file}` — {text.strip()} _( {by}, {now()[:10]} )_\n")


def pending_feedback() -> list[str]:
    if not FEEDBACK.exists():
        return []
    return [l for l in FEEDBACK.read_text(encoding="utf-8").splitlines() if l.startswith("- [ ]")]
