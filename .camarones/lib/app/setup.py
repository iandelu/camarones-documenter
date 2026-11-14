"""Setting a project up on this machine: the prerequisites and the kit's pinned tools, and the wiring that points the
workspace, its repos and the agents' config at cam-docs."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from lib import binaries, docs
from lib.app import components, services, templates, viewers
from lib.common import (CAM_DIR, CAM_LAYOUT, DOCS, HOME, ROOT, VERSIONS, WORKSPACE, WS_FILE, cli_cmd, ensure_path,
                        load_json, out, repo_dir, run, save_json, sdkman_dir, uv, which)
from lib.ports import Log


# ---------- prerequisites ----------
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
        "node": {"ok": services.current().toolchain.node_major() >= VERSIONS["node_min_major"], "need": True,
                 "hint": f"Node.js >= {VERSIONS['node_min_major']}", "found": out(["node", "-v"]) or "—"},
        "docker": {"ok": bool(which("docker")), "need": False, "hint": "Docker Desktop (only to serve the portal)"},
        "claude": {"ok": bool(which("claude")), "need": False, "hint": "Claude Code CLI"},
        "codex": {"ok": bool(which("codex")), "need": False, "hint": "Codex CLI"},
    }


def install_tools(log: Log = print, comps: list[str] | None = None) -> None:
    comps = components.components() if comps is None else comps
    if "graphify" in comps:
        if not services.current().toolchain.tool_ok("graphify"):
            log(f"installing graphify {VERSIONS['graphify']} (uv)…")
            run([uv(), "tool", "install", "--force", f"graphifyy=={VERSIONS['graphify']}"], quiet=True)
            ensure_path()
        log(f"✔ graphify {services.current().toolchain.tool_version('graphify')}")
    if "likec4" in comps:
        if not services.current().toolchain.tool_ok("likec4"):
            log(f"installing likec4 {VERSIONS['likec4']} (npm)…")
            services.current().toolchain.npm_global(f"likec4@{VERSIONS['likec4']}", log)
        log(f"✔ likec4 {services.current().toolchain.tool_version('likec4')}")
    if "openwiki" in comps:
        if not services.current().toolchain.tool_ok("openwiki"):
            log(f"installing openwiki {VERSIONS['openwiki']} (npm)…")
            services.current().toolchain.npm_global(f"openwiki@{VERSIONS['openwiki']}", log)
        log(f"✔ openwiki {VERSIONS['openwiki']}")
        envf = HOME / ".openwiki" / ".env"
        envf.parent.mkdir(exist_ok=True)
        if "OPENWIKI_TELEMETRY_DISABLED=1" not in (envf.read_text(encoding="utf-8") if envf.exists() else ""):
            with envf.open("a", encoding="utf-8") as fh:
                fh.write("OPENWIKI_TELEMETRY_DISABLED=1\n")
    if "quality" in comps:                  # optional: a failure only means CLI check skips that check (one WARN)
        if not services.current().toolchain.tool_ok("mmdc"):
            log(f"installing mermaid-cli {VERSIONS['mmdc']} (npm, downloads a headless Chromium)…")
            try:
                services.current().toolchain.npm_global(f"@mermaid-js/mermaid-cli@{VERSIONS['mmdc']}", log)
            except RuntimeError as e:
                log(f"⚠ mermaid-cli not installed ({e}) — diagrams will not be validated")
        if not services.current().toolchain.tool_ok("gitleaks"):
            log(f"installing gitleaks {VERSIONS['gitleaks']}…")
            binaries.ensure("gitleaks", log)
        gl = binaries.bin_path("gitleaks")
        log(f"✔ quality gate: mermaid-cli {services.current().toolchain.tool_version('mmdc') or 'missing'} · gitleaks {'ok' if gl else 'missing'}")


# ---------- wiring: everything lives in cam-docs, the service repos stay clean ----------
POINTER_START, POINTER_END = "<!-- cam-docs:start -->", "<!-- cam-docs:end -->"


def link_workspace(log: Log = print) -> list[str]:
    """Agents open in the workspace folder (so they see every repo): point its config files at cam-docs. Agent config
    this machine has not approved (lib/trust.py) is not linked; links that already exist are left for the user to
    decide in the wizard or with `trust`. A folder or CLAUDE.md of the person's own already there is merged into."""
    if not CAM_LAYOUT:
        return []
    from lib import trust
    (ROOT / ".claude").mkdir(exist_ok=True)
    held = trust.pending()
    if held:
        log(f"⚠ agent config not linked: {len(held)} item(s) not approved on this machine — review them with "
            f"`{cli_cmd()} trust`")
    out = []
    for n in services.current().links.LINKS:
        if not (ROOT / n).exists() or (held and n in trust.AGENT_LINKS):
            continue
        dst = WORKSPACE / n
        mine = dst.exists() and not services.current().links._linked(dst) and ((dst.is_dir() and (ROOT / n).is_dir()) or n == "CLAUDE.md")
        if services.current().links._merge(n, log) if mine else services.current().links.link(dst, ROOT / n, log):
            out.append(n)
    return out


def unlink_agent_config() -> list[str]:
    """Drop the workspace links that make agents load cam-docs' agent config, also those inside a folder of the
    person's own. A real file or folder is the user's."""
    from lib import trust
    gone = []
    for n in trust.AGENT_LINKS:
        p = WORKSPACE / n
        if services.current().links._linked(p) and os.path.realpath(p) == os.path.realpath(ROOT / n):
            services.current().links._unlink(p)
            gone.append(n)
    for p in services.current().links.merged_links(trust.AGENT_DIRS):
        services.current().links._unlink(p)
        gone.append(f"{p.parent.name}/{p.name}")
    return gone


def write_codex_mcp(servers: dict) -> None:
    """Same servers for Codex, in a managed block of .codex/config.toml (other content is kept; a server the user
    already defined outside the block is left to them)."""
    f = ROOT / ".codex" / "config.toml"
    if not templates._own_file(f):
        return
    text = services.current().agent_config.CODEX_MCP_RE.sub("", f.read_text(encoding="utf-8") if f.is_file() else "")
    block = services.current().agent_config.codex_block({k: v for k, v in servers.items() if f"[mcp_servers.{k}]" not in text})
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text((text.rstrip() + "\n\n" if text.strip() else "") + block, encoding="utf-8")


def install_graphify_skill() -> None:
    """Only the skill: `graphify install --project` would also add hooks and rules pointing at graphify-out/."""
    import tempfile
    from lib import install_state
    with tempfile.TemporaryDirectory() as tmp:
        run(["graphify", "install", "--project"], cwd=Path(tmp), check=False, quiet=True)
        run(["graphify", "install", "--project", "--platform", "codex"], cwd=Path(tmp), check=False, quiet=True)
        for host in (".claude", ".codex", ".agents"):
            src = Path(tmp) / host / "skills" / "graphify"
            if src.is_dir():
                shutil.copytree(src, ROOT / host / "skills" / "graphify", dirs_exist_ok=True)
                install_state.record_from(src, f"{host}/skills/graphify")


def write_agent_config(comps: list[str]) -> None:
    """Runs before trust is asked: a file reached through a linked folder is left alone, and a link where the kit
    writes .mcp.json, .codex/config.toml or .claude/settings.json is replaced by the file, never read or written."""
    for f in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        if templates._real(f) and f.is_file() and services.current().agent_config.GRAPHIFY_SECTION.search(text := f.read_text(encoding="utf-8")):
            f.write_text(services.current().agent_config.GRAPHIFY_SECTION.sub("", text).rstrip() + "\n", encoding="utf-8")
    hooks = ROOT / ".codex" / "hooks.json"
    if templates._real(hooks) and hooks.is_file():
        data = services.current().agent_config.without_graphify_hooks(load_json(hooks, {}))
        save_json(hooks, data) if data else hooks.unlink()
    mcp_file = ROOT / ".mcp.json"
    own_mcp = templates._own_file(mcp_file)
    cfg = load_json(mcp_file, {}) if own_mcp else {}
    servers = cfg.setdefault("mcpServers", {})
    servers["camarones"] = services.current().agent_config.camarones_mcp()
    if "openwiki" not in comps:
        servers.pop("openwiki", None)
    if "likec4" in comps:
        servers["likec4"] = services.current().agent_config.likec4_mcp()
    else:
        servers.pop("likec4", None)
    if own_mcp:
        save_json(mcp_file, cfg)
    write_codex_mcp({k: servers[k] for k in ("camarones", "likec4") if k in servers})
    settings = ROOT / ".claude" / "settings.json"
    if not templates._own_file(settings):
        return
    from lib import hooks
    st = hooks.apply(services.current().agent_config.without_graphify_hooks(load_json(settings, {})))  # method hooks, when the project opts in
    st["enabledMcpjsonServers"] = sorted(set(st.get("enabledMcpjsonServers", [])) | set(servers))
    save_json(settings, st)


def refresh_agent_config() -> None:
    """Re-render what the kit owns in the agent config (its skills and MCP entries) for this machine, so a copy edited
    in .claude/skills — or rendered on a teammate's machine — goes back to the effective text (the team's copy of a
    skill, else the kit's) before trust.pending()."""
    if CAM_LAYOUT and WS_FILE.exists() and "agents" in components.components():
        templates.write_kit_skills()
        write_agent_config(components.components())


def wire_repo(name: str, log: Log = print, comps: list[str] | None = None) -> None:
    """Nothing is written into the repo's tracked files: the code graph goes to cam-docs/graph/<repo>, and the
    OpenWiki folder is an untracked symlink into cam-docs/wikis/<repo>."""
    comps = components.components() if comps is None else comps
    if "openwiki" in comps and CAM_LAYOUT:
        services.current().links.link_repo_wiki(name, log)
    if "agents" in comps and CAM_LAYOUT:
        services.current().agent_config.wire_repo_mcp(name, log)
    if "graphify" in comps:
        log(f"{name}: building the code graph…")
        if not services.current().code.graph_repo(name):
            log(f"⚠ {name}: graphify build failed")


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
    comps = components.components() if comps is None else comps
    if "agents" in comps:
        q = dict(cwd=ROOT, check=False, quiet=True)
        if "openwiki" in comps:
            from lib import install_state
            install_state.learn(services.current().wiki_engine.OPENWIKI_INSTALL)
            for cmd in services.current().wiki_engine.OPENWIKI_INSTALL:
                run(cmd, **q)
        if "graphify" in comps:
            install_graphify_skill()
        templates.init_templates(log=lambda _: None)          # kit skills + AGENTS.md/CLAUDE.md
        write_agent_config(comps)
        linked = link_workspace(log)
        if linked:
            log(f"✔ {WORKSPACE.name}/ → {CAM_DIR}/: {', '.join(linked)}")
    log("✔ project folder ready for Claude Code / Codex")


def setup_steps(comps: list[str] | None = None) -> int:
    """How many ✔ lines setup() will print — drives the progress bar."""
    comps = components.components() if comps is None else comps
    n = sum(1 for t in components.KIT_TOOLS if t in comps) + 1          # tools + repos synced
    n += len(docs.repo_names())                              # repos wired
    n += 1                                                   # umbrella
    n += 1 if "graphify" in comps else 0
    n += 1 if "agents" in comps and CAM_LAYOUT else 0
    n += 1 if "likec4" in comps and (DOCS / "architecture" / "likec4.config.json").exists() else 0
    return n


def setup(ci: bool = False, log: Log = print, comps: list[str] | None = None) -> bool:
    comps = components.components() if comps is None else comps
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
        viewers.graph(rebuild=False, log=log)
    if "likec4" in comps and (DOCS / "architecture" / "likec4.config.json").exists():
        ok, _ = services.current().diagrams.arch_validate()
        log("✔ C4 model valid" if ok else "⚠ C4 model has errors: run arch-validate")
    return True
