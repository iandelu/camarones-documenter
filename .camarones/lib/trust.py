"""Agent config trust: which hooks, MCP servers, settings and skills this machine lets its agents load.

cam-docs is the team's repo (join/share) and its .claude/.codex/.agents/.mcp.json are linked into the workspace root,
so anyone who can push to it could add a hook or an MCP server that runs on every teammate's machine. This module
lists those surfaces, recognises what this kit writes itself (env.refresh_agent_config re-renders it for this machine)
and keeps approvals per machine in ~/.camarones/trust/ — outside the repo, so nothing committed can approve itself."""
from __future__ import annotations

import hashlib, itertools, json, os
from dataclasses import dataclass, field
from pathlib import Path

from .common import CAM_LAYOUT, HOME, ROOT, WORKSPACE, load_json, save_json

AGENT_DIRS = (".claude", ".codex", ".agents")
AGENT_LINKS = (*AGENT_DIRS, ".mcp.json")         # workspace-root links that make agents load this config
CLAUDE_SETTINGS = {"settings.json": "", "settings.local.json": " (local)"}
RISKY_SETTINGS = ("statusLine", "apiKeyHelper", "awsAuthRefresh", "awsCredentialExport", "otelHeadersHelper", "env",
                  "permissions", "enableAllProjectMcpServers", "enabledPlugins", "extraKnownMarketplaces")
STRUCTURED = {".claude/settings.json", ".claude/settings.local.json", ".codex/config.toml", ".codex/hooks.json"}
JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}
STORE_DIR = HOME / ".camarones" / "trust"


@dataclass(frozen=True)
class Item:
    id: str                      # stable key: "mcp <name>", "claude hook <event> <matcher>", "file <path>"…
    kind: str                    # mcp · hook · setting · codex · skill · file
    detail: str                  # what it runs or where it points, as shown to the user
    digest: str = field(repr=False)
    group: str = ""              # display unit: a skill folder groups its files

    @property
    def label(self) -> str:
        return self.group or self.id


def _digest(value) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _short(value, n: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _cmdline(server: dict) -> str:
    if not isinstance(server, dict):
        return _short(server)
    parts = [server.get("command") or server.get("url") or ""] + [str(a) for a in server.get("args") or []]
    extra = f"  env: {', '.join(server['env'])}" if isinstance(server.get("env"), dict) and server["env"] else ""
    return _short(" ".join(p for p in parts if p) or server) + extra


def _read_json(p: Path):
    """(data, ok). A file agents may still parse some other way is never skipped: unreadable → not ok."""
    try:
        return json.loads(p.read_text(encoding="utf-8")), True
    except FileNotFoundError:
        return {}, True
    except (OSError, ValueError):
        return None, False


def _rel(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def _group(rel: str) -> str:
    parts = rel.split("/")
    return "/".join(parts[:3]) if len(parts) > 3 and parts[1] == "skills" else ""


def items(root: Path | None = None) -> dict[str, Item]:
    """Everything in the agent config that can run code, widen access or steer an agent."""
    root = root or ROOT
    found: dict[str, Item] = {}

    def add(id_: str, kind: str, value, detail: str, group: str = "") -> None:
        found[id_] = Item(id_, kind, detail, _digest(value), group)

    def whole(rel: str) -> None:                 # a config file we cannot parse is shown (and approved) as a whole
        p = root / rel
        add(f"file {rel}", "file", p.read_bytes(), f"{rel} (unreadable as JSON)")

    data, ok = _read_json(root / ".mcp.json")
    if not ok:
        whole(".mcp.json")
    for name, server in ((data or {}).get("mcpServers") or {}).items():
        add(f"mcp {name}", "mcp", server, _cmdline(server))

    for fname, tag in CLAUDE_SETTINGS.items():
        rel = f".claude/{fname}"
        st, ok = _read_json(root / rel)
        if not ok:
            whole(rel)
            continue
        hooks: dict[str, list[str]] = {}
        for event, groups in ((st or {}).get("hooks") or {}).items():
            for g in groups if isinstance(groups, list) else [groups]:
                g = g if isinstance(g, dict) else {"hooks": [g]}
                key = f"claude hook {event} {g.get('matcher', '')}".rstrip() + tag
                for h in g.get("hooks") or []:
                    hooks.setdefault(key, []).append(
                        (h.get("command") or h.get("url") or h.get("prompt") or json.dumps(h)) if isinstance(h, dict)
                        else str(h))
        for key, cmds in hooks.items():
            add(key, "hook", cmds, _short(" ; ".join(cmds)))
        for k in RISKY_SETTINGS:
            if k in (st or {}):
                add(f"claude {k}{tag}", "setting", st[k], f"{k}: {_short(st[k])}")

    codex = root / ".codex" / "config.toml"
    if codex.is_file():
        from .env import CODEX_MCP_RE
        text = codex.read_text(encoding="utf-8")
        block = CODEX_MCP_RE.search(text)
        if block:
            add("codex mcp block", "codex", block.group(0).strip(), "MCP servers in the kit's block of .codex/config.toml")
        rest = [ln.strip() for ln in CODEX_MCP_RE.sub("", text).splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        if rest:
            add("codex config", "codex", "\n".join(rest), _short(" · ".join(rest)))
    hooks_json = root / ".codex" / "hooks.json"
    if hooks_json.is_file():
        data, ok = _read_json(hooks_json)
        add("codex hooks", "hook", data if ok else hooks_json.read_bytes(), _short(data if ok else "(unreadable)"))

    for d in AGENT_DIRS:
        for cur, dirs, files in os.walk(root / d, followlinks=False):
            for name in [*files, *[x for x in dirs if Path(cur, x).is_symlink()]]:
                p = Path(cur) / name
                rel = _rel(p, root)
                if rel in STRUCTURED or name in JUNK or "__pycache__" in p.parts:
                    continue
                kind = "skill" if "/skills/" in f"/{rel}" else "file"
                if p.is_symlink():                   # never followed: where it points is what gets approved
                    target = os.readlink(p)
                    add(f"file {rel}", kind, f"link:{target}", f"{rel} → {target}", _group(rel))
                else:
                    add(f"file {rel}", kind, p.read_bytes(), rel, _group(rel))
    return found


def owned() -> dict[str, set[str]]:
    """id → digests of what this kit writes for this machine right now: its skills and its MCP entries (the Codex block
    holds whichever of them the kit wrote there)."""
    from . import env
    out = {f"file {rel}": {_digest(text.encode("utf-8"))} for rel, text in env.kit_skill_files().items()}
    servers = {"camarones": env.camarones_mcp(), "likec4": env.likec4_mcp()}
    out.update({f"mcp {k}": {_digest(v)} for k, v in servers.items()})
    out["codex mcp block"] = {_digest(env.codex_block(dict(sub)).strip())
                              for n in (1, 2) for sub in itertools.combinations(servers.items(), n)}
    return out


# ---------- per-machine approvals ----------
def store_path(root: Path | None = None) -> Path:
    key = os.path.normcase(str((root or ROOT).resolve()))
    return STORE_DIR / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}.json"


def _store(root: Path | None = None) -> dict | None:
    return load_json(store_path(root), None)


def _save(approved: dict[str, str], root: Path | None = None) -> None:
    save_json(store_path(root), {"root": str((root or ROOT).resolve()), "approved": dict(sorted(approved.items()))})


def _linked_here() -> bool:
    """This machine already loads the config: a workspace link into cam-docs (it lives outside the repo, so a clone
    cannot fake it; a real folder with the same name resolves to itself, not into cam-docs)."""
    return any((WORKSPACE / n).exists() and os.path.realpath(WORKSPACE / n) == os.path.realpath(ROOT / n)
               for n in AGENT_LINKS)


def pending(root: Path | None = None) -> list[tuple[Item, str]]:
    """Items neither written by the kit nor approved on this machine, with "new" or "changed".
    First look: a project this machine already links (created before this check) is trusted as it is; any other
    starts with no approvals — that is what a fresh clone of the team's repo gets."""
    if not CAM_LAYOUT:
        return []
    root = root or ROOT
    store = _store(root)
    if store is None:
        if _linked_here():
            _save({i.id: i.digest for i in items(root).values()}, root)
            return []
        _save({}, root)
        store = {"approved": {}}
    approved = store.get("approved") or {}
    own = owned()
    out = []
    for it in items(root).values():
        if it.digest in own.get(it.id, ()) or approved.get(it.id) == it.digest:
            continue
        out.append((it, "changed" if it.id in approved else "new"))
    return sorted(out, key=lambda x: (x[0].kind, x[0].id))


def approve(ids: list[str] | None = None, root: Path | None = None) -> int:
    """Approve what is pending now (or only `ids`). Returns how many items were approved."""
    root = root or ROOT
    todo = [it for it, _ in pending(root) if ids is None or it.id in ids]
    approved = (_store(root) or {}).get("approved") or {}
    approved.update({it.id: it.digest for it in todo})
    _save(approved, root)
    return len(todo)


def decline(root: Path | None = None) -> list[str]:
    """Keep the agents of this machine away from the config: drop the workspace links (never a real file or folder).
    The approvals stay as they are, so the same items are asked again. Returns the links removed."""
    from . import env
    pending(root)                                    # makes sure the store exists: no later "first look" trust
    return env.unlink_agent_config()


def forget(root: Path | None = None) -> None:
    """Uninstall: this project's approvals go, and the folder too once it is empty."""
    p = store_path(root)
    p.unlink(missing_ok=True)
    if p.parent.is_dir() and not any(p.parent.iterdir()):
        p.parent.rmdir()


def grouped(rows: list[tuple[Item, str]]) -> list[tuple[str, str, str, str]]:
    """(kind, label, detail, status) per display unit: a skill folder is one row with its file count."""
    out: dict[str, list] = {}
    for it, status in rows:
        r = out.setdefault(it.label, [it.kind, it.label, [], set()])
        r[2].append(it.detail)
        r[3].add(status)
    return [(k, label, d[0] if len(d) == 1 else f"{label} ({len(d)} files)", "changed" if "changed" in s else "new")
            for k, label, d, s in out.values()]
