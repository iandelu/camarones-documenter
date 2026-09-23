"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import json, os, re, shutil, subprocess, webbrowser
from pathlib import Path
from typing import Callable

from .common import (KIT, ROOT, DOCS, HOME, CACHE, IS_WIN, IS_MAC, VERSIONS, run, out, which, uv, ensure_path, cli_cmd,
                     sdkman_dir)
from . import docs

Log = Callable[[str], None]
TEMPLATES = KIT / "templates"


# ---------- templates ----------
def init_templates(project_name: str | None = None, log: Log = print) -> list[str]:
    """Copy umbrella templates that do not exist yet (never overwrites project files)."""
    created = []
    for src in sorted(TEMPLATES.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATES)
        dst = ROOT / rel
        if dst.exists():
            if rel.as_posix() == "AGENTS.md":
                refresh_block(src, dst, project_name)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        name = project_name or docs.workspace()["project"]["name"]
        dst.write_text(text.replace("{{PROJECT_NAME}}", name).replace("{{CLI}}", cli_cmd()), encoding="utf-8")
        created.append(rel.as_posix())
    if not (ROOT / ".git").exists():
        subprocess.run(["git", "init", "-q", str(ROOT)])
        created.append(".git (umbrella repo)")
    docs.write_gitignore()
    for c in created:
        log(f"  + {c}")
    return created


def refresh_block(src: Path, dst: Path, project_name: str | None = None) -> bool:
    """Kit upgrades: replace only the <!-- camarones:start/end --> block of an existing AGENTS.md (user text is kept)."""
    a, b = "<!-- camarones:start -->", "<!-- camarones:end -->"
    cur, tpl = dst.read_text(encoding="utf-8"), src.read_text(encoding="utf-8")
    if a not in cur or b not in cur or a not in tpl:
        return False
    name = project_name or docs.workspace()["project"]["name"]
    block = tpl[tpl.index(a):tpl.index(b) + len(b)].replace("{{PROJECT_NAME}}", name).replace("{{CLI}}", cli_cmd())
    new = cur[:cur.index(a)] + block + cur[cur.index(b) + len(b):]
    if new != cur:
        dst.write_text(new, encoding="utf-8")
        return True
    return False


# ---------- prerequisites ----------
def node_major() -> int:
    v = out(["node", "-v"])
    m = re.match(r"v(\d+)", v)
    return int(m.group(1)) if m else 0


JVM_MARKERS = ("pom.xml", "build.gradle", "build.gradle.kts", "mvnw", "gradlew", ".sdkmanrc", ".java-version")


def jvm_repos() -> list[str]:
    return [n for n in docs.repo_names() if any((ROOT / n / m).exists() for m in JVM_MARKERS)]


def java_info() -> dict:
    """Java is optional for Camarones itself, but agents need it to build/test JVM repos. Detects PATH, JAVA_HOME and SDKMAN."""
    sdk = (sdkman_dir() / "bin" / "sdkman-init.sh").exists()
    r = run(["java", "-version"], check=False, capture=True) if which("java") else None
    ver = ""
    if r and r.returncode == 0:
        m = re.search(r'version "([^"]+)"', (r.stderr or "") + (r.stdout or ""))
        ver = m.group(1) if m else "?"
    tools = [t for t in ("mvn", "gradle") if which(t)]
    note = []
    if sdk:
        note.append("SDKMAN ✔ (" + ", ".join(sorted(p.name for p in (sdkman_dir() / "candidates").iterdir()
                                                    if (p / "current").exists())) + ")" if (sdkman_dir() / "candidates").is_dir() else "SDKMAN ✔")
    if tools:
        note.append("build: " + ", ".join(tools))
    rc = [n for n in docs.repo_names() if (ROOT / n / ".sdkmanrc").exists()]
    if rc:
        note.append(".sdkmanrc in: " + ", ".join(rc) + " → `sdk env` inside those repos")
    return {"ok": bool(ver), "need": False, "found": f"java {ver}" if ver else "—", "sdkman": sdk,
            "hint": "Java (JDK) — `sdk install java`" if sdk else "Java (JDK) — SDKMAN (https://sdkman.io), brew or winget",
            "note": " · ".join(note)}


def prerequisites() -> dict[str, dict]:
    extra = {"java": java_info()} if jvm_repos() else {}
    return extra | {
        "git": {"ok": bool(which("git")), "need": True, "hint": "git"},
        "node": {"ok": node_major() >= VERSIONS["node_min_major"], "need": True,
                 "hint": f"Node.js >= {VERSIONS['node_min_major']}", "found": out(["node", "-v"]) or "—"},
        "docker": {"ok": bool(which("docker")), "need": False, "hint": "Docker Desktop (only to serve the portal)"},
        "claude": {"ok": bool(which("claude")), "need": False, "hint": "Claude Code CLI"},
        "codex": {"ok": bool(which("codex")), "need": False, "hint": "Codex CLI"},
    }


def install_prereq(name: str, log: Log = print) -> bool:
    """Best-effort install with the OS package manager. Returns True if a command ran successfully."""
    cmds: dict[str, list[list[str]]] = {}
    if IS_WIN and which("winget"):
        base = ["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements", "--id"]
        cmds = {"git": [base + ["Git.Git"]], "node": [base + ["OpenJS.NodeJS.LTS"]],
                "docker": [base + ["Docker.DockerDesktop"]]}
    elif IS_MAC and which("brew"):
        cmds = {"git": [["brew", "install", "git"]], "node": [["brew", "install", "node@22"], ["brew", "link", "--overwrite", "node@22"]],
                "docker": [["brew", "install", "--cask", "docker"]]}
    if name == "java":
        if (sdkman_dir() / "bin" / "sdkman-init.sh").exists() and not IS_WIN:
            cmds["java"] = [["bash", "-c", f'source "{sdkman_dir()}/bin/sdkman-init.sh" && yes | sdk install java']]
        elif IS_MAC and which("brew"):
            cmds["java"] = [["brew", "install", "openjdk@21"]]
        elif IS_WIN and which("winget"):
            cmds["java"] = [["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements",
                             "--id", "EclipseAdoptium.Temurin.21.JDK"]]
    npm_cli = {"claude": [["npm", "install", "-g", "@anthropic-ai/claude-code"]],
               "codex": [["npm", "install", "-g", "@openai/codex"]]}
    cmds.update(npm_cli)
    if name not in cmds:
        return False
    for c in cmds[name]:
        log("$ " + " ".join(c))
        if run(c, check=False).returncode != 0:
            return False
    ensure_path()
    return True


# ---------- pinned tools ----------
def tool_version(name: str) -> str:
    m = re.search(r"\d+\.\d+\.\d+", out([name, "--version"]))
    return m.group(0) if m else ""


def npm_global(pkg: str, log: Log) -> None:
    if run(["npm", "install", "-g", pkg], check=False, quiet=True).returncode != 0:
        if IS_WIN:
            raise RuntimeError(f"npm install -g {pkg} failed")
        log(f"  npm -g needs permissions: installing {pkg} into ~/.local")
        run(["npm", "install", "-g", "--prefix", str(HOME / ".local"), pkg], quiet=True)
        ensure_path()


def openwiki_installed() -> bool:
    r = run(["npm", "ls", "-g", "--depth=0", f"openwiki@{VERSIONS['openwiki']}"], check=False, quiet=True)
    if r.returncode == 0:
        return True
    r = run(["npm", "ls", "-g", "--prefix", str(HOME / ".local"), "--depth=0", f"openwiki@{VERSIONS['openwiki']}"],
            check=False, quiet=True)
    return r.returncode == 0


# ---------- components the user can choose ----------
KIT_TOOLS = {
    "graphify": "graphify — code knowledge graph (Claude/Codex query it instead of grepping)",
    "likec4": "LikeC4 — C4 architecture diagrams + interactive explorer",
    "openwiki": "OpenWiki — one wiki per repo with grounded claims",
}
EXTRAS = {
    "agents": "Claude Code / Codex wiring in every repo (skills, MCP, rules)",
    "hooks": "git hooks: code graph rebuilds itself on commit / checkout",
}
ALL_COMPONENTS = [*KIT_TOOLS, *EXTRAS]


def components() -> list[str]:
    """Components chosen in the wizard (stored in .camarones/workspace.yaml → project.components). Default: all."""
    return docs.workspace()["project"].get("components") or list(ALL_COMPONENTS)


def set_components(chosen: list[str]) -> None:
    ws = docs.workspace()
    ws["project"]["components"] = [c for c in ALL_COMPONENTS if c in chosen]
    docs.save_workspace(ws)


def tool_ok(name: str) -> bool:
    if name == "openwiki":
        return openwiki_installed()
    return tool_version(name) == VERSIONS[name]


def install_tools(log: Log = print, comps: list[str] | None = None) -> None:
    comps = comps or components()
    if "graphify" in comps:
        if not tool_ok("graphify"):
            log(f"installing graphify {VERSIONS['graphify']} (uv)…")
            run([uv(), "tool", "install", "--force", f"graphifyy=={VERSIONS['graphify']}"], quiet=True)
            ensure_path()
        log(f"✔ graphify {tool_version('graphify')}")
    if "likec4" in comps:
        if not tool_ok("likec4"):
            log(f"installing likec4 {VERSIONS['likec4']} (npm)…")
            npm_global(f"likec4@{VERSIONS['likec4']}", log)
        log(f"✔ likec4 {tool_version('likec4')}")
    if "openwiki" in comps:
        if not tool_ok("openwiki"):
            log(f"installing openwiki {VERSIONS['openwiki']} (npm)…")
            npm_global(f"openwiki@{VERSIONS['openwiki']}", log)
        log(f"✔ openwiki {VERSIONS['openwiki']}")
        envf = HOME / ".openwiki" / ".env"
        envf.parent.mkdir(exist_ok=True)
        if "OPENWIKI_TELEMETRY_DISABLED=1" not in (envf.read_text(encoding="utf-8") if envf.exists() else ""):
            with envf.open("a", encoding="utf-8") as fh:
                fh.write("OPENWIKI_TELEMETRY_DISABLED=1\n")


# ---------- repo wiring ----------
def _append_lines(f: Path, lines: list[str]) -> None:
    have = set(f.read_text(encoding="utf-8").splitlines()) if f.exists() else set()
    new = [l for l in lines if l not in have]
    if new:
        with f.open("a", encoding="utf-8") as fh:
            if have and not f.read_text(encoding="utf-8").endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(new) + "\n")


def wire_repo(name: str, log: Log = print, comps: list[str] | None = None) -> None:
    comps = comps or components()
    d = ROOT / name
    q = dict(check=False, quiet=True, cwd=d)
    agents = "agents" in comps
    if agents and "openwiki" in comps:
        log(f"{name}: OpenWiki skill + MCP for Claude/Codex…")
        for host in ("claude", "codex"):
            if run(["openwiki", "integrations", "install", host, "--project", "."], **q).returncode != 0:
                log(f"⚠ {name}: openwiki {host} integration failed")
    if "graphify" in comps:
        if agents:
            log(f"{name}: graphify skill + 'query the graph first' rules…")
            run(["graphify", "install", "--project"], **q)
            run(["graphify", "install", "--project", "--platform", "codex"], **q)
            run(["graphify", "claude", "install"], **q)
            run(["graphify", "codex", "install"], **q)
        if "hooks" in comps and run(["graphify", "hook", "install"], **q).returncode != 0:
            log(f"⚠ {name}: graphify git hooks not installed")
        _append_lines(d / ".gitignore", ["graphify-out/", "*.graphify-bak"])
        _append_lines(d / ".graphifyignore", [".claude/", ".codex/", ".agents/", "openwiki/", "graphify-out/"])
        _append_lines(d / ".claudeignore", ["graphify-out/"])
        log(f"{name}: building the code graph…")
        if run(["graphify", "update", ".", "--force"], **q).returncode != 0:
            log(f"⚠ {name}: graphify build failed")


def wire_umbrella(log: Log = print, comps: list[str] | None = None) -> None:
    comps = comps or components()
    if "agents" in comps and "openwiki" in comps:
        for host in ("claude", "codex"):
            run(["openwiki", "integrations", "install", host, "--project", "."], cwd=ROOT, check=False, quiet=True)
    log("✔ project folder ready for Claude Code / Codex")


def setup_steps(comps: list[str] | None = None) -> int:
    """How many ✔ lines setup() will print — drives the progress bar."""
    comps = comps or components()
    n = sum(1 for t in KIT_TOOLS if t in comps) + 1          # tools + repos synced
    n += len(docs.repo_names())                              # repos wired
    n += 1                                                   # umbrella
    n += 1 if "graphify" in comps else 0
    n += 1 if "likec4" in comps and (DOCS / "architecture" / "likec4.config.json").exists() else 0
    return n


def setup(ci: bool = False, log: Log = print, comps: list[str] | None = None) -> bool:
    comps = comps or components()
    missing = [k for k, v in prerequisites().items() if v["need"] and not v["ok"]]
    if missing:
        raise RuntimeError("missing prerequisites: " + ", ".join(missing))
    install_tools(log, comps)
    log("syncing repositories…")
    docs.sync_repos(lambda m: log(m.strip()))
    log(f"✔ {len(docs.repo_names())} repo(s) in sync")
    if ci:
        return True
    for n in docs.repo_names():
        if (ROOT / n / ".git").exists():
            wire_repo(n, log, comps)
            log(f"✔ {n}")
    wire_umbrella(log, comps)
    if "graphify" in comps:
        log("merging the cross-repo code graph…")
        graph(rebuild=False, log=log)
    if "likec4" in comps and (DOCS / "architecture" / "likec4.config.json").exists():
        ok, _ = arch_validate()
        log("✔ C4 model valid" if ok else "⚠ C4 model has errors: run arch-validate")
    return True


# ---------- code graph ----------
def graph(rebuild: bool = True, log: Log = print) -> Path | None:
    graphs = []
    for n in docs.repo_names():
        d = ROOT / n
        if not d.is_dir():
            continue
        if rebuild or not (d / "graphify-out" / "graph.json").exists():
            run(["graphify", "update", ".", "--force"], cwd=d, check=False, quiet=True)
        g = d / "graphify-out" / "graph.json"
        if g.exists():
            graphs.append(str(g))
    if not graphs:
        log("✔ no code graphs yet")
        return None
    gdir = CACHE / "graph"
    gdir.mkdir(parents=True, exist_ok=True)
    merged = gdir / "graph.json"
    if len(graphs) > 1:
        run(["graphify", "merge-graphs", *graphs, "--out", str(merged)], quiet=True)
    else:
        shutil.copyfile(graphs[0], merged)
    run(["graphify", "export", "html", "--graph", str(merged)], quiet=True, check=False)
    log(f"✔ code graph: {len(graphs)} repo(s) → .camarones/.cache/graph/graph.html (cross-repo edges are INFERRED)")
    return gdir / "graph.html"


# ---------- C4 ----------
def arch_dir() -> Path:
    return DOCS / "architecture"


def arch_validate() -> tuple[bool, str]:
    if not (arch_dir() / "likec4.config.json").exists():
        return False, "no docs/architecture/likec4.config.json yet"
    r = run(["likec4", "validate", "."], cwd=arch_dir(), check=False, capture=True)
    text = re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + (r.stderr or ""))
    keep = [l for l in text.splitlines() if re.search(r"ERROR|Line \d+|Invalid|Valid|WARN .*layout", l)]
    return r.returncode == 0, "\n".join(keep[-40:])


def arch_start() -> None:
    run(["likec4", "start", "."], cwd=arch_dir(), check=False)


# ---------- portal ----------
def portal(log: Log = print) -> Path:
    b, site = CACHE / "portal", CACHE / "site"
    b.mkdir(parents=True, exist_ok=True)
    log("preparing the portal (Starlight)… first time downloads ~150 MB with npm")
    shutil.copytree(KIT / "portal", b, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules", "dist", ".astro", "Dockerfile", "compose.yml"))
    stamp = b / "node_modules" / ".camarones-stamp"
    if not stamp.exists() or (KIT / "portal" / "package.json").stat().st_mtime > stamp.stat().st_mtime:
        run(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=b, quiet=True)
        stamp.touch()
    log("✔ portal shell")
    log("collecting docs, translations and trust badges…")
    content = b / "src" / "content" / "docs"
    shutil.rmtree(content, ignore_errors=True)
    content.mkdir(parents=True)
    public = b / "public"
    public.mkdir(exist_ok=True)
    docs.llms()
    n = docs.portal_content(content, b / "portal.config.json")
    shutil.copyfile(DOCS / "llms.txt", public / "llms.txt")
    log(f"✔ {n} docs")
    cfg = json.loads((b / "portal.config.json").read_text(encoding="utf-8"))
    for sub in ("architecture", "code-graph", "wiki-graph"):
        shutil.rmtree(public / sub, ignore_errors=True)
    if (arch_dir() / "likec4.config.json").exists():
        log("building the interactive C4 explorer (LikeC4)…")
        run(["likec4", "build", ".", "-o", str(public / "architecture"), "--base", "/architecture/", "--title", cfg["name"]],
            cwd=arch_dir(), quiet=True)
        log("✔ C4 explorer")
    log("adding the code graph…")
    g = CACHE / "graph" / "graph.html"
    if not g.exists():
        graph(rebuild=False, log=log)
    if g.exists():
        (public / "code-graph").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(g, public / "code-graph" / "index.html")
    log("✔ code graph")
    for r in cfg["repos"]:
        if r["wikiGraph"]:
            log(f"exporting the wiki graph of {r['name']}…")
            run(["openwiki", "visualize", "openwiki", "--export", str(public / "wiki-graph" / r["name"])],
                cwd=ROOT / r["name"], check=False, quiet=True)
            log(f"✔ wiki graph {r['name']}")
    log("building the static site (Astro)…")
    run(["npm", "run", "build", "--silent"], cwd=b, quiet=True)
    log("✔ static site")
    shutil.rmtree(site, ignore_errors=True)
    shutil.move(str(b / "dist"), str(site))
    k, failed = docs.vendor(site)
    log(f"✔ offline viewers ({k} libraries)" + (f" — still on CDN: {failed}" if failed else ""))
    image_context()
    pages = sum(1 for _ in site.rglob("index.html"))
    log(f"✔ site ready: {pages} pages")
    return site


def portal_steps() -> int:
    wikis = sum(1 for n in docs.repo_names() if (ROOT / n / "openwiki").is_dir())
    c4 = 1 if (arch_dir() / "likec4.config.json").exists() else 0
    return 7 + c4 + wikis


def image_context() -> Path:
    """Self-contained docker build context: Dockerfile + nginx.conf + site/ (used locally and by CI)."""
    site, ctx = CACHE / "site", CACHE / "portal-image"
    if not (site / "index.html").exists():
        raise RuntimeError("the portal is not built yet — build it first (Portal → Build / `portal`)")
    shutil.rmtree(ctx, ignore_errors=True)
    shutil.copytree(site, ctx / "site")
    shutil.copyfile(KIT / "portal" / "Dockerfile", ctx / "Dockerfile")
    shutil.copyfile(KIT / "nginx.conf", ctx / "nginx.conf")
    return ctx


def project_id() -> str:
    return docs.workspace()["project"].get("id") or re.sub(r"[^a-z0-9]+", "-", ROOT.name.lower()).strip("-") or "project"


def compose_cmd() -> list[str]:
    """For servers/CI: `docker compose -f .camarones/portal/compose.yml` (always with an explicit file)."""
    return ["docker", "compose", "-f", str(KIT / "portal" / "compose.yml"), "-p", f"{project_id()}-docs"]


def docker_ready() -> tuple[bool, str]:
    if not which("docker"):
        return False, "docker not found — install Docker Desktop (or use 'Serve without Docker')"
    if run(["docker", "info"], check=False, quiet=True).returncode != 0:
        return False, "Docker is installed but not running — open Docker Desktop and try again (or use 'Serve without Docker')"
    return True, ""


def docker_up(port: int = 8080, log: Log = print) -> str:
    """Plain `docker build` + `docker run`: no compose file or compose plugin needed (works with any Docker)."""
    ok, why = docker_ready()
    if not ok:
        raise RuntimeError(why)
    stop_local()
    ctx = image_context()
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
    """Serve the built portal without Docker (Python's static server, keeps running after the wizard closes)."""
    site = CACHE / "site"
    if not (site / "index.html").exists():
        raise RuntimeError("the portal is not built yet — build it first")
    stop_local()
    import socket, sys, time
    with socket.socket() as sck:
        if sck.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} is busy — choose another port")
    kw: dict = {"cwd": str(site), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    pr = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], **kw)
    SERVE_PID.write_text(str(pr.pid), encoding="utf-8")
    time.sleep(0.8)
    if pr.poll() is not None:
        raise RuntimeError("the local server did not start")
    url = f"http://localhost:{port}"
    log(f"✔ portal at {url} (no Docker)")
    return url


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


def open_url(url: str) -> None:
    webbrowser.open(url)


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
    log(f"  ✔ {dst.relative_to(ROOT)} (umbrella pipeline)")
    log(f"  → per-repo snippet: .camarones/ci/repo.{'github.yml' if forge == 'github' else 'gitlab-ci.yml'}")
    return dst


# ---------- progress safety: local checkpoint commits in the umbrella repo ----------
CHECKPOINT_PATHS = ["docs", ".camarones/workspace.yaml", "AGENTS.md", "CLAUDE.md", ".gitignore"]


def checkpoint_commit(message: str) -> bool:
    """Commit docs progress locally (never pushes). Keeps work safe if a session or the computer closes."""
    if not (ROOT / ".git").exists():
        return False
    paths = [p for p in CHECKPOINT_PATHS if (ROOT / p).exists()]
    run(["git", "add", "--", *paths], cwd=ROOT, check=False, quiet=True)
    if run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False, quiet=True).returncode == 0:
        return False
    ident = [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarones Documenter",
                                                                       "-c", "user.email=camarones@localhost"]
    r = run(["git", *ident, "commit", "-q", "-m", f"docs(camarones): {message}", "--no-verify"], cwd=ROOT, check=False, quiet=True)
    return r.returncode == 0
