"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import json, os, re, shutil, subprocess, webbrowser
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from .common import (KIT, ROOT, DOCS, HOME, CACHE, IS_WIN, IS_MAC, VERSIONS, CAM_DIR, CAM_LAYOUT, WORKSPACE, GRAPHS, run, out,
                     which, uv, ensure_path, cli_cmd, sdkman_dir, repo_dir, ws_rel, load_json, save_json)
from . import docs

Log = Callable[[str], None]
TEMPLATES = KIT / "templates"


# ---------- templates ----------
KIT_DOCS = ("PLAYBOOK.md", "CONVENTIONS.md")         # copied into the project so agents (and the team) can read them
KIT_DOCS_STAMP = ROOT / ".camarones" / ".kit-docs.json"


def fill(text: str, name: str) -> str:
    return (text.replace("{{PROJECT_NAME}}", name).replace("{{CLI}}", cli_cmd())
            .replace("{{CAM}}", f"{CAM_DIR}/" if CAM_LAYOUT else ""))


def init_templates(project_name: str | None = None, log: Log = print) -> list[str]:
    """Copy templates that do not exist yet (never overwrites project files), plus the kit's playbook/conventions."""
    created = []
    name = project_name or docs.workspace()["project"]["name"]
    for src in sorted(TEMPLATES.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATES)
        if rel.parts[0] == "skills":            # kit-owned: always refreshed, for Claude Code and Codex alike
            for host in (".claude", ".agents"):
                dst = ROOT / host / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(fill(src.read_text(encoding="utf-8"), name), encoding="utf-8")
            continue
        dst = ROOT / rel
        if dst.exists():
            if rel.as_posix() == "AGENTS.md":
                refresh_block(src, dst, project_name)
            elif rel.as_posix() == "CLAUDE.md":
                ensure_agents_import(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(fill(src.read_text(encoding="utf-8"), name), encoding="utf-8")
        created.append(rel.as_posix())
    created += sync_kit_docs()
    if not (ROOT / ".git").exists():
        subprocess.run(["git", "init", "-q", str(ROOT)])
        created.append(".git (docs repo)")
    docs.write_gitignore()
    for c in created:
        log(f"  + {c}")
    return created


def ensure_agents_import(claude_md: Path) -> None:
    """A pre-existing CLAUDE.md (project notes) must still pull in the kit's AGENTS.md rules."""
    text = claude_md.read_text(encoding="utf-8")
    if "@AGENTS.md" not in text:
        claude_md.write_text("@AGENTS.md\n\n" + text, encoding="utf-8")


def sync_kit_docs() -> list[str]:
    """Copy PLAYBOOK/CONVENTIONS into the project's .camarones/ (versioned with the docs). A copy the team edited
    since the last sync is kept as is — only untouched copies follow kit upgrades."""
    if (ROOT / ".camarones").resolve() == KIT.resolve():
        return []                                   # legacy: the kit itself lives in this project
    import hashlib
    stamp, changed = load_json(KIT_DOCS_STAMP, {}), []
    for n in KIT_DOCS:
        src, dst = KIT / n, ROOT / ".camarones" / n
        cur = hashlib.sha256(dst.read_bytes()).hexdigest() if dst.exists() else None
        new = hashlib.sha256(src.read_bytes()).hexdigest()
        if cur == new or (cur and stamp.get(n) != cur):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        stamp[n] = new
        changed.append(f".camarones/{n}")
    save_json(KIT_DOCS_STAMP, stamp)
    return changed


def refresh_block(src: Path, dst: Path, project_name: str | None = None) -> bool:
    """Kit upgrades: replace only the <!-- camarones:start/end --> block of an existing AGENTS.md (user text is kept)."""
    a, b = "<!-- camarones:start -->", "<!-- camarones:end -->"
    cur, tpl = dst.read_text(encoding="utf-8"), src.read_text(encoding="utf-8")
    if a not in cur or b not in cur or a not in tpl:
        return False
    block = fill(tpl[tpl.index(a):tpl.index(b) + len(b)], project_name or docs.workspace()["project"]["name"])
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
    return [n for n in docs.repo_names() if any((repo_dir(n) / m).exists() for m in JVM_MARKERS)]


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
    rc = [n for n in docs.repo_names() if (repo_dir(n) / ".sdkmanrc").exists()]
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
    "agents": "Claude Code / Codex wiring in cam-docs (skills, MCP, rules), linked from the workspace root",
}
ALL_COMPONENTS = [*KIT_TOOLS, *EXTRAS]


def components() -> list[str]:
    """Components chosen in the wizard (stored in .camarones/workspace.yaml → project.components). Default: all."""
    chosen = docs.workspace()["project"].get("components")
    return list(ALL_COMPONENTS) if chosen is None else [c for c in chosen if c in ALL_COMPONENTS]


def set_profile(name: str) -> None:
    from .install import PROFILES
    if name not in PROFILES:
        raise ValueError(f'Unknown profile: {name}')
    ws = docs.workspace()
    ws['project']['profile'] = name
    ws['project']['components'] = list(PROFILES[name])
    docs.save_workspace(ws)


def set_components(chosen: list[str]) -> None:
    ws = docs.workspace()
    ws["project"]["components"] = [c for c in ALL_COMPONENTS if c in chosen]
    docs.save_workspace(ws)


def tool_ok(name: str) -> bool:
    if name == "openwiki":
        return openwiki_installed()
    return tool_version(name) == VERSIONS[name]


def install_tools(log: Log = print, comps: list[str] | None = None) -> None:
    comps = components() if comps is None else comps
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


# ---------- wiring: everything lives in cam-docs, the service repos stay clean ----------
LINKS = (".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md")   # workspace root → cam-docs
POINTER_START, POINTER_END = "<!-- cam-docs:start -->", "<!-- cam-docs:end -->"


def _append_lines(f: Path, lines: list[str]) -> None:
    have = set(f.read_text(encoding="utf-8").splitlines()) if f.exists() else set()
    new = [l for l in lines if l not in have]
    if new:
        with f.open("a", encoding="utf-8") as fh:
            if have and not f.read_text(encoding="utf-8").endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(new) + "\n")


def git_exclude(repo: Path, pattern: str) -> None:
    """Ignore a path in `repo` locally (.git/info/exclude is never committed, so the repo's history stays clean)."""
    if (repo / ".git").is_dir():
        f = repo / ".git" / "info" / "exclude"
        f.parent.mkdir(parents=True, exist_ok=True)
        _append_lines(f, [pattern])


def link(dst: Path, target: Path, log: Log = print) -> bool:
    """dst → target symlink (relative). An existing real file/dir is never replaced. Windows without symlink
    rights: directories become junctions, files are left alone (the warning says what to do)."""
    if dst.is_symlink():
        if dst.resolve() == target.resolve():
            return True
        dst.unlink()
    elif dst.exists():
        log(f"⚠ {dst.name} already exists in {dst.parent} — not linked (move it into {CAM_DIR}/ or run migrate)")
        return False
    try:
        dst.symlink_to(os.path.relpath(target, dst.parent), target_is_directory=target.is_dir())
        return True
    except OSError:
        if IS_WIN and target.is_dir():
            return run(["cmd", "/c", "mklink", "/J", str(dst), str(target)], check=False, quiet=True).returncode == 0
        log(f"⚠ could not link {dst} → {target} (enable Developer Mode on Windows)")
        return False


def link_workspace(log: Log = print) -> list[str]:
    """Agents open in the workspace folder (so they see every repo): point its config files at cam-docs."""
    if not CAM_LAYOUT:
        return []
    (ROOT / ".claude").mkdir(exist_ok=True)
    return [n for n in LINKS if (ROOT / n).exists() and link(WORKSPACE / n, ROOT / n, log)]


def camarones_mcp() -> dict:
    """MCP entry for the kit's own server — no API keys; it resolves the project by walking up from its cwd."""
    if cli_cmd() == "camarones":
        return {"command": "camarones", "args": ["mcp"]}
    return {"command": "uv", "args": ["run", "--quiet", "--script", str(KIT / "camarones.py"), "mcp"]}


GRAPHIFY_SECTION = re.compile(r"\n*^## graphify\n.*?(?=^## |\Z)", re.S | re.M)


def without_graphify_hooks(data: dict) -> dict:
    """graphify's hooks assume a graphify-out/ in the cwd; the kit keeps graphs in cam-docs/graph/ instead."""
    for event, groups in list((data.get("hooks") or {}).items()):
        groups = [g for g in groups if not any("graphify" in h.get("command", "") for h in g.get("hooks", []))]
        if groups:
            data["hooks"][event] = groups
        else:
            del data["hooks"][event]
    if data.get("hooks") == {}:
        del data["hooks"]
    return data


def install_graphify_skill() -> None:
    """Only the skill: `graphify install --project` would also add hooks and rules pointing at graphify-out/."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run(["graphify", "install", "--project"], cwd=Path(tmp), check=False, quiet=True)
        run(["graphify", "install", "--project", "--platform", "codex"], cwd=Path(tmp), check=False, quiet=True)
        for host in (".claude", ".codex", ".agents"):
            src = Path(tmp) / host / "skills" / "graphify"
            if src.is_dir():
                shutil.copytree(src, ROOT / host / "skills" / "graphify", dirs_exist_ok=True)


def write_agent_config(comps: list[str]) -> None:
    for f in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        if f.is_file() and GRAPHIFY_SECTION.search(text := f.read_text(encoding="utf-8")):
            f.write_text(GRAPHIFY_SECTION.sub("", text).rstrip() + "\n", encoding="utf-8")
    hooks = ROOT / ".codex" / "hooks.json"
    if hooks.is_file():
        data = without_graphify_hooks(load_json(hooks, {}))
        save_json(hooks, data) if data else hooks.unlink()
    mcp_file = ROOT / ".mcp.json"
    cfg = load_json(mcp_file, {})
    servers = cfg.setdefault("mcpServers", {})
    servers["camarones"] = camarones_mcp()
    if "openwiki" not in comps:
        servers.pop("openwiki", None)
    save_json(mcp_file, cfg)
    settings = ROOT / ".claude" / "settings.json"
    st = without_graphify_hooks(load_json(settings, {}))
    st["enabledMcpjsonServers"] = sorted(set(st.get("enabledMcpjsonServers", [])) | set(servers))
    save_json(settings, st)


def wire_repo(name: str, log: Log = print, comps: list[str] | None = None) -> None:
    """Nothing is written into the repo's tracked files: the code graph goes to cam-docs/graph/<repo>, and the
    OpenWiki folder is an untracked symlink into cam-docs/wikis/<repo>."""
    comps = components() if comps is None else comps
    if "openwiki" in comps and CAM_LAYOUT:
        link_repo_wiki(name, log)
    if "graphify" in comps:
        log(f"{name}: building the code graph…")
        if not graph_repo(name):
            log(f"⚠ {name}: graphify build failed")


def link_repo_wiki(name: str, log: Log = print) -> None:
    d, wiki = repo_dir(name), ROOT / "wikis" / name
    if (d / "openwiki").is_dir() and not (d / "openwiki").is_symlink() and not wiki.exists():
        wiki.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d / "openwiki"), str(wiki))
    wiki.mkdir(parents=True, exist_ok=True)
    if link(d / "openwiki", wiki, log):
        git_exclude(d, "/openwiki")


def add_repo_pointer(name: str) -> bool:
    """Optional: a short block in the repo's CLAUDE.md pointing at cam-docs (appended; existing text is kept)."""
    f = repo_dir(name) / "CLAUDE.md"
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    if POINTER_START in text:
        return False
    block = (f"{POINTER_START}\nProject docs, architecture and agent config live in `../{CAM_DIR}/` "
             f"(read `../{CAM_DIR}/docs/llms.txt` first; update the affected docs after changing code).\n{POINTER_END}\n")
    f.write_text((text.rstrip() + "\n\n" if text.strip() else "") + block, encoding="utf-8")
    return True


def wire_one(name: str, log: Log = print, comps: list[str] | None = None) -> None:
    wire_repo(name, log, comps)
    if docs.workspace()["project"].get("repo_pointer"):
        add_repo_pointer(name)


def wire_umbrella(log: Log = print, comps: list[str] | None = None) -> None:
    comps = components() if comps is None else comps
    if "agents" in comps:
        q = dict(cwd=ROOT, check=False, quiet=True)
        if "openwiki" in comps:
            for host in ("claude", "codex"):
                run(["openwiki", "integrations", "install", host, "--project", "."], **q)
        if "graphify" in comps:
            install_graphify_skill()
        init_templates(log=lambda _: None)          # kit skills + AGENTS.md/CLAUDE.md
        write_agent_config(comps)
        linked = link_workspace(log)
        if linked:
            log(f"✔ {WORKSPACE.name}/ → {CAM_DIR}/: {', '.join(linked)}")
    log("✔ project folder ready for Claude Code / Codex")


def setup_steps(comps: list[str] | None = None) -> int:
    """How many ✔ lines setup() will print — drives the progress bar."""
    comps = components() if comps is None else comps
    n = sum(1 for t in KIT_TOOLS if t in comps) + 1          # tools + repos synced
    n += len(docs.repo_names())                              # repos wired
    n += 1                                                   # umbrella
    n += 1 if "graphify" in comps else 0
    n += 1 if "agents" in comps and CAM_LAYOUT else 0
    n += 1 if "likec4" in comps and (DOCS / "architecture" / "likec4.config.json").exists() else 0
    return n


def setup(ci: bool = False, log: Log = print, comps: list[str] | None = None) -> bool:
    comps = components() if comps is None else comps
    missing = [k for k, v in prerequisites().items() if v["need"] and not v["ok"]]
    if missing:
        raise RuntimeError("missing prerequisites: " + ", ".join(missing))
    install_tools(log, comps)
    log("syncing repositories…")
    failed = docs.sync_repos(lambda m: log(m.strip()))
    if failed:
        raise RuntimeError('Repository sync failed: ' + ', '.join(failed))
    log(f"✔ {len(docs.repo_names())} repo(s) in sync")
    if ci:
        return True
    for n in docs.repo_names():
        if (repo_dir(n) / ".git").exists():
            wire_one(n, log, comps)
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
def repo_graph(name: str) -> Path:
    own = GRAPHS / name / "graph.json"
    legacy = repo_dir(name) / "graphify-out" / "graph.json"
    return legacy if not own.exists() and legacy.exists() else own


def graph_repo(name: str) -> bool:
    """AST-only graph of one repo, written to cam-docs/graph/<repo> (GRAPHIFY_OUT) instead of the repo."""
    (GRAPHS / name).mkdir(parents=True, exist_ok=True)
    r = run(["graphify", "update", ".", "--force"], cwd=repo_dir(name), check=False, quiet=True,
            env={"GRAPHIFY_OUT": str(GRAPHS / name)})
    return r.returncode == 0


def graph(rebuild: bool = True, log: Log = print) -> Path | None:
    graphs = []
    for n in docs.repo_names():
        if not repo_dir(n).is_dir():
            continue
        if rebuild or not repo_graph(n).exists():
            graph_repo(n)
        if repo_graph(n).exists():
            graphs.append(str(repo_graph(n)))
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
    run(["graphify", "export", "html", "--graph", str(merged)], quiet=True, check=False, cwd=gdir,
        env={"GRAPHIFY_OUT": str(gdir)})
    log(f"✔ code graph: {len(graphs)} repo(s) → {ws_rel('.camarones/.cache/graph/graph.html')} (cross-repo edges are INFERRED)")
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


# ---------- portal: viewers (C4, code graph, wiki graphs) ----------
VIEWERS = CACHE / "viewers"


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


def build_c4(dest: Path | None = None, log: Log = print) -> bool:
    dest = dest or VIEWERS / "architecture"
    if not (arch_dir() / "likec4.config.json").exists():
        log("⚠ no C4 model yet (docs/architecture/likec4.config.json) — unit arch-system writes it")
        return False
    log("building the interactive C4 explorer (LikeC4)…")
    shutil.rmtree(dest, ignore_errors=True)
    r = run(["likec4", "build", ".", "-o", str(dest), "--base", "/architecture/", "--title", docs.workspace()["project"]["name"]],
            cwd=arch_dir(), check=False, quiet=True)
    ok = r.returncode == 0 and (dest / "index.html").exists()
    log("✔ C4 explorer" if ok else "⚠ C4 explorer skipped: the model has errors (run arch-validate)")
    return ok


def code_graphs() -> dict[str, Path]:
    """Viewer HTML per repo, plus 'all' for the merged graph."""
    found = {n: GRAPHS / n / "graph.html" for n in docs.repo_names() if (GRAPHS / n / "graph.html").is_file()}
    if (CACHE / "graph" / "graph.html").is_file():
        found = {"all": CACHE / "graph" / "graph.html", **found}
    return found


def build_graphs(log: Log = print) -> bool:
    if "graphify" not in components():
        log("⚠ graphify is not installed (setup)")
        return False
    for n in docs.repo_names():
        if repo_dir(n).is_dir():
            log(f"{n}: code graph…")
            if not graph_repo(n):
                log(f"⚠ {n}: graphify failed")
    return graph(rebuild=False, log=log) is not None


def wiki_graph(repo: str, dest: Path | None = None, log: Log = print) -> bool:
    wiki, dest = docs.wiki_dir(repo), dest or VIEWERS / "wiki-graph" / repo
    if not wiki_pages(repo):
        return False
    log(f"exporting the wiki graph of {repo}…")
    shutil.rmtree(dest, ignore_errors=True)
    run(["openwiki", "visualize", wiki.name, "--export", str(dest), "--no-open"], cwd=wiki.parent, check=False, quiet=True)
    ok = (dest / "index.html").exists()
    log(f"✔ wiki graph {repo}" if ok else f"⚠ wiki graph {repo} failed")
    return ok


def newest(paths) -> float:
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def repo_changed_at(repo: str) -> float:
    t = out(["git", "log", "-1", "--format=%ct"], cwd=repo_dir(repo))
    return float(t) if t else 0.0


def viewers() -> dict:
    c4_at = newest([VIEWERS / "architecture" / "index.html"])
    model_at = newest(arch_dir().glob("*.c4")) if arch_dir().is_dir() else 0.0
    graphs = {n: {"at": newest([f]), "stale": n != "all" and repo_changed_at(n) > newest([f])}
              for n, f in code_graphs().items()}
    return {"c4": {"exists": bool(c4_at), "at": c4_at, "stale": bool(c4_at) and model_at > c4_at, "model": bool(model_at)},
            "graphs": graphs, "graphify": "graphify" in components(), "likec4": "likec4" in components()}


# ---------- OpenWiki ----------
PROVIDER_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY",
                 "OPENAI_COMPATIBLE_API_KEY", "OPENAI_CHATGPT_ACCESS_TOKEN")


def openwiki_credentials() -> bool:
    """OpenWiki runs headless only with a provider key in the environment or saved in ~/.openwiki/.env."""
    saved = HOME / ".openwiki" / ".env"
    text = saved.read_text(encoding="utf-8", errors="replace") if saved.exists() else ""
    return any(os.environ.get(k) or re.search(rf"^{k}=\S", text, re.M) for k in PROVIDER_KEYS)


def wiki_engines() -> list[str]:
    """Who can write a wiki without a terminal: OpenWiki itself (provider key), else an agent CLI with the
    OpenWiki MCP tools (uses the agent's own login)."""
    if "openwiki" not in components() or not openwiki_installed():
        return []
    return [e for e, ok in (("openwiki", openwiki_credentials()), ("claude", bool(which("claude"))),
                            ("codex", bool(which("codex")))) if ok]


def wiki_pages(repo: str) -> list[Path]:
    """Generated pages only: INSTRUCTIONS.md is the user-authored brief, not a page."""
    wiki = docs.wiki_dir(repo)
    return [f for f in wiki.rglob("*.md") if not any(p.startswith(".") for p in f.relative_to(wiki).parts)
            and f.relative_to(wiki).as_posix() != "INSTRUCTIONS.md"] if wiki.is_dir() else []


def wikis() -> list[dict]:
    from . import plan
    units = {u["id"]: u["status"] for u in plan.load()["units"]}
    rows = []
    for n in docs.repo_names():
        pages = wiki_pages(n)
        at = newest(pages)
        rows.append({"repo": n, "pages": len(pages), "at": at, "stale": bool(pages) and repo_changed_at(n) > at,
                     "graph": (VIEWERS / "wiki-graph" / n / "index.html").exists(), "unit": units.get(f"repo-wiki:{n}"),
                     "cloned": repo_dir(n).is_dir(),
                     "index": next((f"repos/{n}/{p}" for p in ("quickstart.md", "index.md", "README.md")
                                    if (docs.wiki_dir(n) / p).exists()), None)})
    return rows


def wiki_prompt(repo: str, mode: str) -> str:
    from . import plan
    uid = f"repo-wiki:{repo}"
    head = plan.prompt(uid, unattended=True) if uid in {u["id"] for u in plan.load()["units"]} else ""
    return (head + f"\nTask: {mode} the OpenWiki of `{repo}/` (absolute git root: {repo_dir(repo)}) with the OpenWiki MCP "
            "tools (skill `openwiki`): openwiki_begin → plan → page loop → openwiki_finish, passing that root. Its `openwiki/` "
            f"folder is already a real folder for this run (moved into `{CAM_DIR}/wikis/{repo}/` afterwards). Do not "
            "touch other repo files; what OpenWiki adds itself (AGENTS.md, CLAUDE.md, .github/) is removed afterwards.\n")


OPENWIKI_REPO_FILES = ("AGENTS.md", "CLAUDE.md", ".github/workflows/openwiki-update.yml")


def _is_link(p: Path) -> bool:
    return p.is_symlink() or getattr(p, "is_junction", lambda: False)()


def wiki_open(repo: str, log: Log = print) -> None:
    """OpenWiki refuses a symlinked openwiki/ and adds agent snippets + a GitHub workflow to the repo. So a run gets a
    real openwiki/ seeded from cam-docs/wikis/<repo>, and wiki_close moves the result back and restores the repo."""
    d, wiki, state = repo_dir(repo), ROOT / "wikis" / repo, CACHE / "wiki-open" / f"{repo}.json"
    ow = d / "openwiki"
    if not state.exists():
        saved = {f: (d / f).read_text(encoding="utf-8") if (d / f).is_file() else None for f in OPENWIKI_REPO_FILES}
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(saved), encoding="utf-8")
    if _is_link(ow):
        ow.unlink()
    if not ow.exists():
        shutil.copytree(wiki, ow) if wiki.is_dir() else ow.mkdir()


def wiki_close(repo: str, log: Log = print) -> bool:
    """Only undoes a wiki_open: without its saved state it cannot tell the repo's own AGENTS.md / CLAUDE.md from
    OpenWiki's, so it leaves them alone (a second close, or a close without open, is a no-op)."""
    d, wiki, state = repo_dir(repo), ROOT / "wikis" / repo, CACHE / "wiki-open" / f"{repo}.json"
    if not state.exists():
        log(f"{repo}: no open OpenWiki run — nothing to close")
        link_repo_wiki(repo, log)
        return False
    ow = d / "openwiki"
    if ow.is_dir() and not _is_link(ow):
        if any(ow.iterdir()):
            shutil.rmtree(wiki, ignore_errors=True)
            wiki.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ow), str(wiki))
        else:                                   # nothing written: keep the wiki cam-docs already has
            ow.rmdir()
    saved = json.loads(state.read_text(encoding="utf-8"))
    for f, text in saved.items():
        p = d / f
        if text is not None:
            p.write_text(text, encoding="utf-8")
        elif p.is_file():
            p.unlink()
            for parent in p.relative_to(d).parents:
                if parent != Path(".") and (d / parent).is_dir() and not any((d / parent).iterdir()):
                    (d / parent).rmdir()
    state.unlink(missing_ok=True)
    link_repo_wiki(repo, log)
    return True


@contextmanager
def wiki_workdir(repo: str, log: Log = print):
    wiki_open(repo, log)
    try:
        yield
    finally:
        wiki_close(repo, log)


class WikiAbort(RuntimeError):
    """The engine cannot run at all (quota, login): every other repo of a batch would fail the same way."""


ENGINE_DOWN = re.compile(r"session limit|usage limit|weekly limit|limit reached|rate.?limit|\b429\b|insufficient_quota|"
                         r"credit balance|invalid api key|incorrect api key|\b401\b|unauthori[sz]ed|/login|not logged in|"
                         r"log ?in again|token (?:has )?expired|overloaded", re.I)


def openwiki_generate(repo: str, mode: str = "", log: Log = print, engine: str = "") -> bool:
    """Write or refresh one repo's OpenWiki (same path for the wizard, the portal and the CLI). Raises WikiAbort when
    the engine itself is down, so batches stop instead of failing every remaining repo."""
    from . import plan
    if not repo_dir(repo).is_dir():
        raise RuntimeError(f"{repo} is not cloned (sync first)")
    engines = wiki_engines()
    engine = engine or (engines[0] if engines else "")
    if engine not in engines:
        raise RuntimeError("no way to run OpenWiki headless: save a provider key with `openwiki auth configure <provider>` "
                           "(or set OPENAI_API_KEY / ANTHROPIC_API_KEY), or install Claude Code / Codex")
    link_repo_wiki(repo, log)
    mode = mode or ("update" if wiki_pages(repo) else "init")
    uid = f"repo-wiki:{repo}"
    before = {u["id"]: u["status"] for u in plan.load()["units"]}.get(uid)
    known = before is not None
    tail: deque[str] = deque(maxlen=5)

    def tee(line: str) -> None:
        tail.append(line)
        log(line)

    if known:
        plan.set_status(uid, "doing")
    log(f"OpenWiki {mode} for {repo} via {engine}… (this can take a while)")
    with wiki_workdir(repo, log):
        if engine == "openwiki":
            rc = stream(["openwiki", "code", f"--{mode}", "--print"], repo_dir(repo), tee)
        elif engine == "claude":
            rc = stream(["claude", "-p", wiki_prompt(repo, mode), "--permission-mode", "acceptEdits", "--allowedTools",
                         "mcp__openwiki Skill Read Write Edit Glob Grep Bash(git:*) Bash(ls:*) Bash(camarones:*) Bash(graphify:*)"],
                        WORKSPACE, tee)
        else:
            rc = stream(["codex", "exec", "--full-auto", "-C", str(WORKSPACE), wiki_prompt(repo, mode)], WORKSPACE, tee)
    ok = rc == 0 and bool(wiki_pages(repo))
    if ok:
        if known:
            plan.set_status(uid, "done", f"OpenWiki {mode} via {engine}")
        docs.llms()
        wiki_graph(repo, log=log)
        checkpoint_commit(f"{uid} ({mode})")
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
    from . import serve
    writable(CACHE)
    site, tmp = CACHE / "site", CACHE / "site.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(serve.UI, tmp)
    html = (tmp / "index.html").read_text(encoding="utf-8")
    (tmp / "index.html").write_text(html.replace('content="live"', 'content="static"'), encoding="utf-8")
    docs.llms()
    shutil.copyfile(DOCS / "llms.txt", tmp / "llms.txt")
    api = tmp / "api"

    def dump(rel: str, data) -> None:
        f = api / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    t = serve.tree()
    t["editBase"] = forge_edit_base()
    langs = [""] + t["langs"]
    index = []
    for d in t["docs"]:
        for lang in langs:
            doc = serve.read(d["path"], lang)
            if lang and not doc["exists"]:
                continue
            dump(f"doc/{lang or '_'}/{d['path']}.json", doc)
            index.append({"path": d["path"], "lang": lang, "title": doc["title"], "trust": d["trust"],
                          "text": docs.split_fm(doc["raw"])[1][:20000]})
    log(f"✔ {len(t['docs'])} docs" + (f" + translations ({', '.join(t['langs'])})" if t["langs"] else ""))
    if DOCS.is_dir():
        for f in DOCS.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
                dst = tmp / "raw" / f.relative_to(DOCS)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dst)
    if "likec4" in components() and (not (VIEWERS / "architecture" / "index.html").exists() or viewers()["c4"]["stale"]):
        build_c4(log=log)
    if (VIEWERS / "architecture").is_dir():
        shutil.copytree(VIEWERS / "architecture", tmp / "architecture")
    if "graphify" in components() and not code_graphs():
        graph(rebuild=False, log=log)
    for n, f in code_graphs().items():
        dst = tmp / "code-graph" / ("" if n == "all" else n) / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
    log(f"✔ code graphs ({len(code_graphs())})")
    for w in wikis():
        if w["pages"] and not w["graph"]:
            wiki_graph(w["repo"], log=log)
        if (VIEWERS / "wiki-graph" / w["repo"]).is_dir():
            shutil.copytree(VIEWERS / "wiki-graph" / w["repo"], tmp / "wiki-graph" / w["repo"])
    t["codeGraphs"] = list(code_graphs())
    dump("tree.json", t)
    dump("status.json", serve.status())
    dump("wikis.json", wikis())
    dump("viewers.json", viewers())
    dump("search.json", index)
    for lib in serve.UI_LIBS:
        f = docs.vendor_file(*lib)
        if f:
            dst = tmp / "vendor" / f"{lib[0]}@{lib[1]}" / lib[2]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
    k, failed = docs.vendor(tmp)
    log(f"✔ offline libraries ({k + len(serve.UI_LIBS)})" + (f" — still on CDN: {failed}" if failed else ""))
    shutil.rmtree(site, ignore_errors=True)
    tmp.rename(site)
    image_context()
    log(f"✔ portal exported → {ws_rel('.camarones/.cache/site')}")
    return site


portal = export_site


def portal_steps() -> int:
    wikis_n = sum(1 for n in docs.repo_names() if wiki_pages(n))
    c4 = 1 if (arch_dir() / "likec4.config.json").exists() else 0
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
    """Serve the exported (read-only) portal without Docker — what the deployed one looks like."""
    if not (CACHE / "site" / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — export it first (Portal → Export / `portal`)")
    return serve_editor(port, log, static=True)


def serve_editor(port: int = 8080, log: Log = print, static: bool = False) -> str:
    """The default portal: a local server (no Docker, no npm) that renders docs/ live and lets people edit,
    confirm, comment, commit and rebuild the viewers. Detached, so it outlives the wizard; `down` stops it."""
    stop_local()
    import socket, sys, time
    with socket.socket() as sck:
        if sck.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} is busy — choose another port")
    CACHE.mkdir(parents=True, exist_ok=True)
    kw: dict = {"stdout": subprocess.DEVNULL, "stdin": subprocess.DEVNULL,
                "stderr": (CACHE / "serve.log").open("w", encoding="utf-8"),
                "env": {**os.environ, "CAMARONES_ROOT": str(ROOT)}}
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
    url = f"http://localhost:{port}"
    log(f"✔ portal at {url}" + (" (read-only export, no Docker)" if static else " (live: edit · confirm · rebuild · wikis)"))
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


def open_new_terminal(cmd: list[str], cwd: Path) -> bool:
    """Launch `cmd` in its own terminal window, detached from this process, so an interactive agent session
    does not block the wizard. Returns False when no terminal emulator could be found — caller then falls
    back to running `cmd` in the current terminal."""
    import shlex
    try:
        if IS_WIN:
            subprocess.Popen(cmd, cwd=str(cwd), creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True
        if IS_MAC:
            script = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(cmd)}"
            subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script {json.dumps(script)}'])
            return True
        inner = f"cd {shlex.quote(str(cwd))} && exec {shlex.join(cmd)}"
        for term, args in (("x-terminal-emulator", ["-e", "bash", "-lc", inner]),
                           ("gnome-terminal", ["--", "bash", "-lc", inner]),
                           ("konsole", ["-e", "bash", "-lc", inner]),
                           ("xterm", ["-e", "bash", "-lc", inner])):
            if which(term):
                subprocess.Popen([term, *args], cwd=str(cwd))
                return True
        return False
    except OSError:
        return False


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
    log(f"  ✔ {dst.relative_to(ROOT)} (docs repo pipeline)")
    log(f"  → per-repo snippet: .camarones/ci/{snippet}")
    return dst


# ---------- progress safety: local checkpoint commits in the umbrella repo ----------
CHECKPOINT_PATHS = ["docs", "wikis", ".camarones/workspace.yaml", ".camarones/PLAYBOOK.md", ".camarones/CONVENTIONS.md",
                    ".camarones/.kit-docs.json", ".camarones/ci", ".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md",
                    ".gitignore", ".gitlab-ci.yml", ".github"]


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
