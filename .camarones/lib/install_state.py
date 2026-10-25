"""Install state (X4): what this kit wrote into the project on this machine, so `doctor` tells drift (a kit file edited
or gone, a link missing) and `repair` puts it back. Kept per machine in ~/.camarones/install/, outside the repo like the
trust approvals: the agent-tool skills recorded here (graphify, OpenWiki) are what the pinned tools wrote on this
machine, so trust counts them as the kit's own instead of asking about every file. A project without a record (made
before 4.20) is checked against what the kit renders now; its next setup or repair records the rest."""
from __future__ import annotations

import hashlib, os, shutil
from pathlib import Path

from .common import CAM_LAYOUT, HOME, ROOT, WORKSPACE, VERSIONS, repo_dir, load_json, save_json

STORE_DIR = HOME / ".camarones" / "install"
AGENT_DIRS = (".claude", ".codex", ".agents")


def store_path(root: Path | None = None) -> Path:
    key = os.path.normcase(str((root or ROOT).resolve()))
    return STORE_DIR / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}.json"


def load(root: Path | None = None) -> dict:
    return load_json(store_path(root), {}) or {}


def _digest(p: Path) -> str:
    from .trust import _digest as digest
    return digest(p.read_bytes())


def _record(owned: dict[str, str]) -> None:
    """trust item id → digest of what the kit (or a pinned tool it ran) wrote for this project on this machine."""
    if not owned:
        return
    state = load()
    state.setdefault("owned", {}).update(owned)
    save_json(store_path(), {**state, "root": str(ROOT.resolve()), "kit": VERSIONS["kit"],
                             "owned": dict(sorted(state["owned"].items()))})


def record_from(src: Path, dst_rel: str) -> None:
    """A tool's own output (built in a scratch folder) that the kit copies to `dst_rel`: only what the tool made."""
    _record({f"file {dst_rel}/{f.relative_to(src).as_posix()}": _digest(f)
             for f in sorted(src.rglob("*")) if f.is_file()})


def _learnable(item) -> bool:
    return (item.id.startswith("file ") and "/skills/" in item.id) or item.id.startswith("mcp ") \
        or item.id == "codex config"


def learn(cmds: list[list[str]], restore: bool = False) -> None:
    """Run a tool's installer in a scratch git repo first and record exactly what it writes there (skills, its MCP
    entries): the same files in the project are then the tool's, whoever committed them; anything else is asked.
    `restore` copies its skill files back where the project's copy is gone or differs (the installer itself skips a
    tool it believes installed)."""
    import tempfile
    from . import env, trust
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        env.run(["git", "init", "-q"], cwd=scratch, check=False, quiet=True)
        for cmd in cmds:
            env.run(cmd, cwd=scratch, check=False, quiet=True)
        made = {i.id: i.digest for i in trust.items(scratch).values() if _learnable(i)}
        _record(made)
        for key in made if restore else ():
            rel = key.removeprefix("file ")
            if key.startswith("file ") and (not (ROOT / rel).is_file() or _digest(ROOT / rel) != made[key]):
                (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(scratch / rel, ROOT / rel)


def owned() -> dict[str, set[str]]:
    return {k: {d} for k, d in (load().get("owned") or {}).items()}


def drift() -> list[dict]:
    """Kit files edited or gone, and links that should point into cam-docs but do not."""
    if not CAM_LAYOUT:
        return []
    from . import docs, env
    out = []
    expected = {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in env.kit_skill_files().items()}
    for rel, want in expected.items():
        f = ROOT / rel
        if not f.is_file():
            out.append({"path": rel, "state": "missing", "what": "kit skill"})
        elif hashlib.sha256(f.read_text(encoding="utf-8").encode("utf-8")).hexdigest() != want:
            out.append({"path": rel, "state": "edited", "what": "kit skill"})
    for key, want in (load().get("owned") or {}).items():
        if not key.startswith("file "):
            continue
        rel = key.removeprefix("file ")
        f = ROOT / rel
        if not f.is_file():
            out.append({"path": rel, "state": "missing", "what": "tool skill"})
        elif _digest(f) != want:
            out.append({"path": rel, "state": "edited", "what": "tool skill"})
    for n in env.LINKS:
        if (ROOT / n).exists() and os.path.realpath(WORKSPACE / n) != os.path.realpath(ROOT / n):
            out.append({"path": f"{WORKSPACE.name}/{n}", "state": "not linked", "what": "workspace link"})
    if "openwiki" in env.components():
        for r in docs.repo_names():
            d = repo_dir(r)
            if d.is_dir() and os.path.realpath(d / "openwiki") != os.path.realpath(ROOT / "wikis" / r):
                out.append({"path": f"{r}/openwiki", "state": "not linked", "what": "repo wiki link"})
    if "agents" in env.components() and env.which("claude"):
        out += [{"path": r, "state": "not registered", "what": "repo MCP (Claude Code)"} for r in docs.repo_names()
                if repo_dir(r).is_dir() and not env.repo_mcp_registered(r)]
    return out


def repair(log=print) -> list[dict]:
    """Put back what the kit owns: its skills and agent config, the agent tools' skills, the links. Never touches the
    team's pages or files the kit did not write. Returns what is still off (links held back by trust, say)."""
    from . import docs, env
    comps = env.components()
    env.wire_umbrella(log, comps)
    if "openwiki" in comps and "agents" in comps:
        learn(env.OPENWIKI_INSTALL, restore=True)
    if "openwiki" in comps:
        for r in docs.repo_names():
            if repo_dir(r).is_dir():
                env.link_repo_wiki(r, log)
    if "agents" in comps:
        for r in docs.repo_names():
            env.wire_repo_mcp(r, log)
    from . import kanban
    if kanban.enabled():                                  # a joined clone gets the board's merge driver here
        from .kanban import ops
        ops.ensure_driver()
    return drift()


def forget(root: Path | None = None) -> None:
    p = store_path(root)
    p.unlink(missing_ok=True)
    if p.parent.is_dir() and not any(p.parent.iterdir()):
        p.parent.rmdir()
