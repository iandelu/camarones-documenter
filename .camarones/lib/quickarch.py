"""First-look architecture: a fast, deterministic scan of every repo (no AI) that drafts a C4 model.

It detects stack, datastores, brokers (with exchanges/topics), HTTP calls between repos and identity providers,
renders LikeC4 files + a terminal tree, and lets the user accept it as the AI-draft starting point of docs/architecture.
"""
from __future__ import annotations

import json, re, shutil
from pathlib import Path

from .common import DOCS, CACHE, run, which, repo_dir
from . import docs

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".gradle", ".idea", ".venv", "venv", "__pycache__",
             "graphify-out", "openwiki", ".dart_tool", ".next", "coverage", ".claude", ".codex", ".agents", "vendor"}
EXTS = {".java", ".kt", ".kts", ".ts", ".tsx", ".js", ".mjs", ".py", ".go", ".dart", ".cs", ".rb", ".php",
        ".yml", ".yaml", ".properties", ".json", ".env", ".xml", ".gradle", ".toml", ".conf", ".tf"}
MAX_FILES, MAX_BYTES = 4000, 300_000

DB_PATTERNS = [
    (r"jdbc:postgresql://([\w.\-]+)(?::\d+)?/([\w\-]+)|postgres(?:ql)?://[^@\s]*@?([\w.\-]+)(?::\d+)?/([\w\-]+)", "PostgreSQL"),
    (r"jdbc:(?:mysql|mariadb)://([\w.\-]+)(?::\d+)?/([\w\-]+)|mysql://[^@\s]*@?([\w.\-]+)(?::\d+)?/([\w\-]+)", "MySQL"),
    (r"jdbc:oracle:[^\s\"']*@([\w.\-]+)(?::\d+)?[:/]([\w\-]+)", "Oracle"),
    (r"jdbc:sqlserver://([\w.\-]+)[^\s;]*;(?:database|databaseName)=([\w\-]+)", "SQL Server"),
    (r"mongodb(?:\+srv)?://[^@\s]*@?([\w.\-]+)(?::\d+)?/([\w\-]+)", "MongoDB"),
]
DEP_DB = {"postgresql": "PostgreSQL", "mysql-connector": "MySQL", "mariadb": "MySQL", "ojdbc": "Oracle",
          "mssql-jdbc": "SQL Server", "spring-boot-starter-data-mongodb": "MongoDB", "mongoose": "MongoDB",
          "psycopg": "PostgreSQL", "pg\"": "PostgreSQL", "sqflite": "SQLite (device)", "hibernate-reactive": None}
# Firebase: one Firestore and one Storage per Firebase project (.firebaserc), shared by every repo that uses them
FIREBASE = {"Firestore": ("cloud_firestore", "firebase/firestore", "@google-cloud/firestore", "getfirestore(",
                          "firebasefirestore.instance", ".firestore()", "firestore.client(", "firebase_admin.firestore"),
            "Firebase Storage": ("firebase_storage", "firebase/storage", "getstorage(", "firebasestorage.instance",
                                 ".storage().bucket")}
FUNCTION_CALLS = ("httpscallable", "cloud_functions", "firebase/functions", "firebasefunctions.instance")
CACHE_DEPS = ("spring-boot-starter-data-redis", "redisson", "ioredis", "\"redis\"", "jedis", "lettuce", "quarkus-redis")
RABBIT_DEPS = ("spring-boot-starter-amqp", "spring-rabbit", "amqplib", "pika", "rabbitmq", "smallrye-reactive-messaging-rabbitmq")
KAFKA_DEPS = ("spring-kafka", "kafka-clients", "kafkajs", "confluent-kafka", "smallrye-reactive-messaging-kafka", "sarama")
IDP_HINTS = (("keycloak", "Keycloak"), ("auth0", "Auth0"), ("cognito", "AWS Cognito"), ("firebase_auth", "Firebase Auth"),
             ("firebase/auth", "Firebase Auth"), ("firebaseauth.instance", "Firebase Auth"), ("okta", "Okta"))
PUBLISH = [r"convertAndSend\(\s*\"([\w.\-]+)\"", r"kafkaTemplate\.send\(\s*\"([\w.\-]+)\"", r"@Outgoing\(\s*\"([\w.\-]+)\"",
           r"\.publish\(\s*['\"]([\w.\-]+)['\"]", r"producer\.send\(\s*\{?\s*topic:\s*['\"]([\w.\-]+)['\"]"]
CONSUME = [r"@RabbitListener\([^)]*queues\s*=\s*\{?\s*\"([\w.\-]+)\"", r"@KafkaListener\([^)]*topics\s*=\s*\{?\s*\"([\w.\-]+)\"",
           r"@Incoming\(\s*\"([\w.\-]+)\"", r"consumer\.subscribe\(\s*\{?\s*topics?:\s*\[?['\"]([\w.\-]+)['\"]"]


def ident(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", name)
    s = parts[0].lower() + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)
    return ("x" + s) if not s or s[0].isdigit() else s


def q(text: str) -> str:
    return text.replace("'", "’")


def files(repo: Path):
    n = 0
    for p in repo.rglob("*"):
        if n >= MAX_FILES:
            return
        if any(part in SKIP_DIRS for part in p.relative_to(repo).parts):
            continue
        if p.is_file() and (p.suffix in EXTS or p.name.startswith(".env") or p.name in ("Dockerfile", "pubspec.yaml")):
            try:
                if p.stat().st_size <= MAX_BYTES:
                    n += 1
                    yield p
            except OSError:
                continue


def stack(repo: Path, blob: str) -> str:
    t = []
    if (repo / "pom.xml").exists() or (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
        lang = "Kotlin" if (repo / "build.gradle.kts").exists() or ".kt\n" in blob else "Java"
        m = re.search(r"<java\.version>(\d+)|jvmToolchain\((\d+)\)|sourceCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(\d+)", blob)
        t.append(f"{lang} {next(g for g in m.groups() if g)}" if m else lang)
        if "spring-boot" in blob:
            t.append("Spring Boot")
        if "io.quarkus" in blob:
            t.append("Quarkus")
        if "micronaut" in blob:
            t.append("Micronaut")
    if (repo / "pubspec.yaml").exists():
        t.append("Flutter/Dart")
    if (repo / "package.json").exists():
        try:        # the manifest only: vendored or built JS is full of "next"/"vue" keys
            pkg = (repo / "package.json").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pkg = ""
        for key, label in (("\"next\"", "Next.js"), ("\"react\"", "React"), ("\"@angular/core\"", "Angular"),
                           ("\"vue\"", "Vue"), ("\"@nestjs/core\"", "NestJS"), ("\"express\"", "Express")):
            if key in pkg:
                t.append(label)
        t.insert(0, "TypeScript" if (repo / "tsconfig.json").exists() else "Node.js")
    if (repo / "pyproject.toml").exists() or (repo / "requirements.txt").exists():
        t.append("Python")
        for key, label in (("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask")):
            if key in blob.lower():
                t.append(label)
    if (repo / "go.mod").exists():
        t.append("Go")
    return " · ".join(dict.fromkeys(t)) or "?"


def repo_blob(repo: Path) -> str:
    """Every scanned file of a repo, each behind a `### <path>` header (what the detectors search)."""
    texts = []
    for f in files(repo):
        try:
            texts.append(f"\n### {f.relative_to(repo).as_posix()}\n" + f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return "".join(texts)


MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json", "pyproject.toml", "requirements.txt",
             "go.mod", "pubspec.yaml")


def _source(blob: str, at: int) -> str | None:
    """The file a match comes from: the nearest `### <path>` header before it (see repo_blob)."""
    i = blob.rfind("\n### ", 0, max(at, 0) + 1)
    return blob[i + 5:blob.index("\n", i + 1)] if i >= 0 else None


def _functions_dir(repo: Path) -> str | None:
    """The repo's Cloud Functions folder: firebase.json's `functions.source` (default `functions`) with firebase-functions."""
    try:
        cfg = json.loads((repo / "firebase.json").read_text(encoding="utf-8")) if (repo / "firebase.json").is_file() else {}
    except (OSError, ValueError):
        cfg = {}
    fn = cfg.get("functions") if isinstance(cfg, dict) else None
    src = (fn[0] if isinstance(fn, list) and fn else fn or {}).get("source", "functions") if isinstance(fn, (dict, list)) else "functions"
    pkg = repo / src / "package.json"
    try:
        return src if pkg.is_file() and "firebase-functions" in pkg.read_text(encoding="utf-8", errors="ignore") else None
    except OSError:
        return None


def _firebase_project(repo: Path, blob: str) -> str | None:
    try:
        rc = json.loads((repo / ".firebaserc").read_text(encoding="utf-8")) if (repo / ".firebaserc").is_file() else {}
        if (rc.get("projects") or {}).get("default"):
            return rc["projects"]["default"]
    except (OSError, ValueError, AttributeError):
        pass
    m = re.search(r"projectId\s*[:=]\s*['\"]([\w-]+)['\"]|\"project_id\"\s*:\s*\"([\w-]+)\"", blob)
    return (m.group(1) or m.group(2)) if m else None


def _split(blob: str, prefix: str) -> tuple[str, str]:
    """(the blob without the files under `prefix`, those files) — repo_blob's `### <path>` sections."""
    keep, moved = [], []
    for part in re.split(r"(?=\n### )", blob):
        (moved if part.startswith(f"\n### {prefix}/") else keep).append(part)
    return "".join(keep), "".join(moved)


def scan() -> dict:
    """Returns {repos: {name: {...}}, dbs: {key: {...}}, brokers: set, idps: set, edges: [...], sources: set}; sources
    are the `repo:path` files the stack and the relations were read from, for the first-look page's x-sources."""
    ws = docs.workspace()
    names = [r["name"] for r in ws["repos"] if repo_dir(r["name"]).is_dir()]
    kinds = {r["name"]: r.get("kind", "service") for r in ws["repos"]}
    fixed = {r["name"]: r["stack"] for r in ws["repos"] if r.get("stack")}    # stack confirmed by a human or an agent
    model = {"repos": {}, "dbs": {}, "brokers": set(), "idps": set(), "edges": [], "caches": set(), "sources": set()}
    blobs = {}
    for n in names:
        repo = repo_dir(n)
        blob = repo_blob(repo)
        blobs[n] = blob
        model["sources"] |= {f"{n}:{m}" for m in MANIFESTS if (repo / m).is_file()}
        model["repos"][n] = {"kind": kinds.get(n, "service"), "tech": fixed.get(n) or stack(repo, blob)}
        if src := _functions_dir(repo):                    # Cloud Functions: a container of their own
            fn = f"{n} Cloud Functions"
            blobs[n], blobs[fn] = _split(blob, src)
            lang = "TypeScript" if (repo / src / "tsconfig.json").is_file() else "Node.js"
            model["repos"][fn] = {"kind": "service", "tech": f"Cloud Functions · {lang}", "repo": n}
    owner = {n: r.get("repo", n) for n, r in model["repos"].items()}
    projects = {n: _firebase_project(repo_dir(n), blobs[n]) for n in names}
    found_projects = {p for p in projects.values() if p}
    default_project = next(iter(found_projects)) if len(found_projects) == 1 else ws["project"]["name"]
    for n, blob in blobs.items():
        low = blob.lower()

        def cite(at: int, n=n, blob=blob) -> None:
            if at >= 0 and (path := _source(blob, at)):
                model["sources"].add(f"{owner[n]}:{path}")
        for label, hints in FIREBASE.items():
            hit = next((low.find(h) for h in hints if h in low), -1)
            if hit >= 0:
                proj = projects.get(owner[n]) or default_project
                model["dbs"].setdefault(f"{label}:{proj}", {"label": label, "name": proj, "users": set()})["users"].add(n)
                cite(hit)
        # datastores (explicit URLs first → shared DB detection by host/name)
        found_db = False
        for pat, label in DB_PATTERNS:
            for m in re.finditer(pat, blob, re.I):
                g = [x for x in m.groups() if x]
                if len(g) >= 2:
                    host, db = g[0], g[1]
                    key = f"{label}:{db}" if host in ("localhost", "127.0.0.1", "db", "postgres", "mysql", "mongo") else f"{label}:{host}/{db}"
                    model["dbs"].setdefault(key, {"label": label, "name": db, "users": set()})["users"].add(n)
                    cite(m.start())
                    found_db = True
        if not found_db:
            for dep, label in DEP_DB.items():
                if label and dep in low:
                    key = f"{label}:{n}"
                    model["dbs"].setdefault(key, {"label": label, "name": f"{n} db", "users": set()})["users"].add(n)
                    cite(low.find(dep))
                    break
        if any(d in low for d in CACHE_DEPS):
            model["caches"].add(n)
        for label, deps in (("RabbitMQ", RABBIT_DEPS), ("Kafka", KAFKA_DEPS)):
            if any(d in low for d in deps):
                model["brokers"].add(label)
                cite(min(low.find(d) for d in deps if d in low))
                pubs = {m for p in PUBLISH for m in re.findall(p, blob)}
                subs = {m for p in CONSUME for m in re.findall(p, blob)}
                if pubs:
                    model["edges"].append((n, label, "async", "publishes " + ", ".join(sorted(pubs)[:3])))
                if subs:
                    model["edges"].append((label, n, "async", "delivers " + ", ".join(sorted(subs)[:3])))
                if not pubs and not subs:
                    model["edges"].append((n, label, "async", "uses"))
        for key, label in IDP_HINTS:
            if key in low:
                model["idps"].add(label)
                cite(low.find(key))
                model["edges"].append((n, label, "sync", "authenticates with"))
        # HTTP calls to sibling repos: their name used as a host / service reference
        for other in names:
            if other == n:
                continue
            hit = re.search(rf"(https?://|//|\b){re.escape(other)}(?=[:/.\"'\s]|$)", blob) or \
                re.search(rf"{re.escape(other)}[.-]?(url|host|base-?url|endpoint|uri)", low)
            if hit:
                model["edges"].append((n, other, "sync", "calls (HTTP)"))
                cite(hit.start())
    functions = [n for n, r in model["repos"].items() if r.get("repo")]
    for n in names:                                       # apps calling Cloud Functions (httpsCallable, cloud_functions)
        low = blobs[n].lower()
        if functions and any(h in low for h in FUNCTION_CALLS):
            for fn in [f for f in functions if owner[f] == n] or functions:
                model["edges"].append((n, fn, "sync", "calls"))
    for key, d in model["dbs"].items():
        for u in sorted(d["users"]):
            model["edges"].append((u, key, "sync", "reads/writes"))
    return model


def render_c4(model: dict, project: str) -> dict[str, str]:
    """LikeC4 sources (spec reused from the kit template)."""
    sys_id = ident(project) or "system"
    ids = {n: ident(n) for n in model["repos"]}
    kind_map = {"service": "service", "webapp": "webapp", "mobileApp": "mobileApp", "library": "component", "infra": "component"}
    lines = ["// Camarones first-look draft — generated by a static scan (no AI). Review it; everything is #ai-draft.",
             "model {", "  user = actor 'User' 'Uses the system' { #ai-draft }", "", f"  {sys_id} = system '{q(project)}' {{"]
    for n, r in model["repos"].items():
        lines += [f"    {ids[n]} = {kind_map.get(r['kind'], 'service')} '{q(n)}' {{", "      #ai-draft",
                  f"      technology '{q(r['tech'])}'", f"      metadata {{ repo '{q(r.get('repo', n))}' }}", "    }"]
    ext_ids = {}
    for key, d in model["dbs"].items():
        i = ident(f"db {d['label']} {d['name']}")
        ext_ids[key] = f"{sys_id}.{i}"
        shared = " #shared-db" if len(d["users"]) > 1 else ""
        lines += [f"    {i} = database '{q(d['label'])}: {q(d['name'])}' {{", f"      #ai-draft{shared}",
                  f"      technology '{q(d['label'])}'", "    }"]
    for b in sorted(model["brokers"]):
        i = ident(b)
        ext_ids[b] = f"{sys_id}.{i}"
        lines += [f"    {i} = queue '{q(b)}' {{", "      #ai-draft", f"      technology '{q(b)}'", "    }"]
    if model["caches"]:
        lines += ["    cache = database 'Redis cache' {", "      #ai-draft", "      technology 'Redis'", "    }"]
    lines.append("  }")
    for idp in sorted(model["idps"]):
        i = ident(idp)
        ext_ids[idp] = i
        lines += [f"  {i} = externalSystem '{q(idp)}' {{ #ai-draft }}"]
    lines.append("")
    front = [n for n, r in model["repos"].items() if r["kind"] in ("webapp", "mobileApp")] or list(model["repos"])[:1]
    for n in front:
        lines.append(f"  user -> {sys_id}.{ids[n]} 'uses'")
    ref = lambda x: f"{sys_id}.{ids[x]}" if x in ids else ext_ids.get(x, ident(x))
    seen = set()
    for a, b, kind, label in model["edges"]:
        k = (a, b, label)
        if k in seen:
            continue
        seen.add(k)
        lines.append(f"  {ref(a)} -[{kind}]-> {ref(b)} '{q(label)}'")
    for n in model["caches"]:
        lines.append(f"  {ref(n)} -[sync]-> {sys_id}.cache 'caches'")
    lines.append("}")
    # top-level `include *` = actors, the system and every external system, so elements added later (the AI
    # refinement, by hand) show up in the context view without anyone having to remember to edit it
    views = ["views {", "  view index {", "    title 'System context'", "    include *", "  }",
             f"  view containers of {sys_id} {{", "    title 'Containers'", "    include *", "  }", "}"]
    spec = (Path(__file__).resolve().parent.parent / "templates" / "docs" / "architecture" / "spec.c4").read_text(encoding="utf-8")
    cfg = '{ "name": "%s", "title": "%s" }\n' % (ident(project) or "project", project.replace('"', "'"))
    return {"likec4.config.json": cfg, "spec.c4": spec, "model.c4": "\n".join(lines) + "\n", "views.c4": "\n".join(views) + "\n"}


def draft(log=print) -> dict:
    """Scan, write the draft to .camarones/.cache/firstlook, validate and (if LikeC4 is installed) build a one-file viewer."""
    project = docs.workspace()["project"]["name"]
    log("scanning repos (stack, databases, brokers, HTTP calls)…")
    model = scan()
    log(f"✔ {len(model['repos'])} repos, {len(model['dbs'])} datastores, {len(model['brokers'])} brokers, "
        f"{len(model['edges'])} relations")
    out = CACHE / "firstlook"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for name, text in render_c4(model, project).items():
        (out / name).write_text(text, encoding="utf-8")
    log("✔ C4 draft written")
    html = None
    if which("likec4"):
        log("validating and rendering with LikeC4…")
        r = run(["likec4", "validate", "."], cwd=out, check=False, capture=True)
        model["valid"] = r.returncode == 0
        b = run(["likec4", "build", ".", "-o", str(out / "_site"), "--output-single-file", "--title", project],
                cwd=out, check=False, capture=True)
        cand = out / "_site" / "index.html"
        html = cand if b.returncode == 0 and cand.exists() else None
        log("✔ interactive view ready" if html else "⚠ could not build the interactive view")
    else:
        model["valid"] = None
        log("✔ LikeC4 not installed: terminal view only")
    model["dir"], model["html"] = out, html
    return model


def first_look_page(model: dict) -> str:
    """The `architecture/first-look.md` text for a draft: its repos, the relations it saw and the code it read."""
    rows = "\n".join(f"| {n} | {r['kind']} | {r['tech']} |" for n, r in model["repos"].items())
    rels = "\n".join(f"- {a} → {b}: {label}" for a, b, _, label in model["edges"]) or "- (none detected)"
    sources = sorted(model.get("sources") or ())                 # facts read from code: agents may use the page
    cited = "\nx-sources:" + "".join(f"\n  - {s}" for s in sources) if sources else ""
    return f"""---
type: architecture
title: Architecture — first look
description: Automatic first draft of the system architecture (static scan, no AI). Starting point for the C4 model.{cited}
---
# Architecture — first look

> **TL;DR:** Generated by a static scan of the repositories (no AI): one container per repo and the relations the scan
> could see. Open the interactive C4 explorer in the portal's **Architecture (C4)** tab (`camaron up`).

| Repo | Kind | Stack |
|---|---|---|
{rows}

## Detected relations
{rels}
"""


def save(model: dict, overwrite: bool = False, page: bool = True) -> list[str]:
    """Copy the draft into docs/architecture (the C4 source of truth) and, with `page` (the old layout), write
    `first-look.md` from it; `page=False` writes the C4 files only. Returns the written files."""
    dst = DOCS / "architecture"
    dst.mkdir(parents=True, exist_ok=True)
    written = []
    for name in ("likec4.config.json", "spec.c4", "model.c4", "views.c4"):
        target = dst / name
        if target.exists() and not overwrite and name != "spec.c4":
            continue
        shutil.copyfile(model["dir"] / name, target)
        written.append(f"docs/architecture/{name}")
    first = dst / "first-look.md"
    if not page or ("docs/architecture/model.c4" not in written and first.exists()):
        return written                      # the kept model has its own (maybe AI-verified) page: don't contradict it
    first.write_text(first_look_page(model), encoding="utf-8")
    written.append("docs/architecture/first-look.md")
    return written
