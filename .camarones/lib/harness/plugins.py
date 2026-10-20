"""Plugins (R10): a folder with a plugin.yaml manifest. The kit's own pieces live in lib/plugins/; a project's in
cam-docs/.camarones/plugins/. Whether a plugin runs code is computed from what it provides and the files it ships,
never trusted from the manifest. A project plugin that runs code is not loaded until this machine approves it
(lib/trust.py, R28); any change to its files asks again."""
from __future__ import annotations

import functools, hashlib, os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..common import CTX, VERSIONS

KIT_DIR = Path(__file__).resolve().parent.parent / "plugins"
PROJECT_DIR = CTX.root / ".camarones" / "plugins"
KINDS = ("checks", "hooks", "mcp", "pipelines", "prompts", "runners", "skills", "types")
CODE_KINDS = ("runners", "hooks", "mcp")              # a command template is code execution too
STEERING_KINDS = ("prompts", "skills", "types")       # text that reaches an agent
CODE_FILES = {".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".cmd", ".bat", ".ps1", ".exe", ".command"}
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
NEEDS_APPROVAL = "not loaded: needs approval on this machine"


@dataclass
class Plugin:
    name: str
    path: Path
    source: str                                       # kit | project
    manifest: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def provides(self) -> dict:
        p = self.manifest.get("provides")
        return p if isinstance(p, dict) else {}

    @property
    def runs_code(self) -> bool:
        if any(self.provides.get(k) for k in CODE_KINDS):
            return True
        if any(isinstance(c, dict) and c.get("entry") for c in self.provides.get("checks") or []):
            return True
        return any(f.suffix.lower() in CODE_FILES for f in self.path.rglob("*") if f.is_file())

    @property
    def steers_agents(self) -> bool:
        return any(self.provides.get(k) for k in STEERING_KINDS)

    def fingerprint(self) -> str:
        """Every file of the folder (links by target, never followed): what an approval covers."""
        h = hashlib.sha256()
        for f in sorted(p for p in self.path.rglob("*") if p.is_file() or p.is_symlink()):
            rel = f.relative_to(self.path).as_posix()
            if "__pycache__" in rel:
                continue
            data = f"link:{os.readlink(f)}".encode() if f.is_symlink() else f.read_bytes().replace(b"\r\n", b"\n")
            h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
        return h.hexdigest()

    def summary(self) -> str:
        """What it would run, as shown when asking for approval."""
        parts = []
        for r in self.provides.get("runners") or []:
            argv = " ".join(map(str, r.get("argv") or [])) if isinstance(r, dict) else ""
            parts.append(f"runners: {r.get('id')} ({argv})" if isinstance(r, dict) else f"runners: {r}")
        for h in self.provides.get("hooks") or []:
            parts.append(f"hooks: {h.get('event')} ({h.get('command')})" if isinstance(h, dict) else f"hooks: {h}")
        for m in self.provides.get("mcp") or []:
            parts.append(f"mcp: {m.get('name')} ({m.get('command')})" if isinstance(m, dict) else f"mcp: {m}")
        for c in self.provides.get("checks") or []:
            if isinstance(c, dict) and c.get("entry"):
                parts.append(f"checks: {c.get('id')} ({c['entry']})")
        code = [f.relative_to(self.path).as_posix() for f in sorted(self.path.rglob("*"))
                if f.is_file() and f.suffix.lower() in CODE_FILES]
        if code:
            parts.append("code files: " + ", ".join(code[:6]) + (" …" if len(code) > 6 else ""))
        steer = [f"{k}: {', '.join(map(str, self.provides[k]))}" for k in STEERING_KINDS if self.provides.get(k)]
        if steer and not self.runs_code:
            parts.append("steers agents — " + " · ".join(steer))
        return f"{self.path.name}/ — " + " · ".join(parts)

    @property
    def needs_trust(self) -> bool:
        """Runs code or steers an agent, and arrived with the team's repo: approved per machine (R28, RFC §2.4)."""
        return self.source == "project" and (self.runs_code or self.steers_agents)

    @property
    def active(self) -> bool:
        if self.errors:
            return False
        if not self.needs_trust:
            return True
        from .. import trust
        return trust.plugin_approved(self)

    @property
    def status(self) -> str:
        if self.errors:
            return "invalid"
        return "active" if self.active else NEEDS_APPROVAL


def _version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:3])


def satisfies(version: str, spec: str) -> bool:
    """`>=3.16,<4` style ranges; an empty spec accepts any kit."""
    have = _version(version)
    for part in filter(None, (s.strip() for s in (spec or "").split(","))):
        op, ref = re.match(r"(>=|<=|==|>|<)?\s*(.+)", part).groups()
        want = _version(ref)
        want, cmp = want + (0,) * (3 - len(want)), have + (0,) * (3 - len(have))
        ok = {">=": cmp >= want, "<=": cmp <= want, ">": cmp > want, "<": cmp < want}.get(op or "==", cmp == want)
        if not ok:
            return False
    return True


def _check(p: Plugin, taken: set[str]) -> None:
    m = p.manifest
    if not NAME.fullmatch(str(m.get("name", ""))):
        p.errors.append(f"name: use lowercase letters, digits and dashes (got '{m.get('name')}')")
    elif p.source == "project" and m["name"] in taken:
        p.errors.append(f"name: the kit already has a plugin called '{m['name']}'")
    if not SEMVER.fullmatch(str(m.get("version", ""))):
        p.errors.append(f"version: not a semantic version (got '{m.get('version')}')")
    if m.get("kit") and not satisfies(VERSIONS["kit"], str(m["kit"])):
        p.errors.append(f"kit: needs kit {m['kit']}, this is {VERSIONS['kit']}")
    if "provides" in m and not isinstance(m["provides"], dict):
        p.errors.append("provides: expected a mapping of kinds")
    for kind in p.provides:
        if kind not in KINDS:
            p.errors.append(f"provides.{kind}: unknown kind (use {', '.join(KINDS)})")


def _load(folder: Path, source: str, taken: set[str]) -> Plugin:
    p = Plugin(folder.name, folder, source)
    try:
        m = yaml.safe_load((folder / "plugin.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        p.errors.append(f"plugin.yaml: cannot be read ({str(e).splitlines()[0]})")
        return p
    if not isinstance(m, dict):
        p.errors.append("plugin.yaml: expected a mapping (name, version, provides)")
        return p
    p.manifest = m
    _check(p, taken)
    if NAME.fullmatch(str(m.get("name", ""))):
        p.name = m["name"]                    # an invalid name is reported; the folder name identifies the plugin
    return p


def _folders(base: Path) -> list[Path]:
    return sorted(d for d in base.glob("*") if (d / "plugin.yaml").is_file()) if base.is_dir() else []


@functools.lru_cache(maxsize=1)
def kit() -> tuple[Plugin, ...]:
    """The kit's own plugins: they ship with this code, so they are read once per process."""
    return tuple(_load(folder, "kit", set()) for folder in _folders(KIT_DIR))


def discover(project_dir: Path | None = None) -> list[Plugin]:
    taken = {p.name for p in kit()}
    return [*kit(), *(_load(folder, "project", taken) for folder in _folders(project_dir or PROJECT_DIR))]


def provided(kind: str) -> list[dict]:
    """Everything active plugins provide of one kind (e.g. runners), in discovery order."""
    return [item for p in discover() if p.active for item in p.provides.get(kind) or []]


def rows() -> list[dict]:
    return [{"name": p.name, "version": str(p.manifest.get("version", "")), "source": p.source,
             "provides": sorted(p.provides), "runs_code": p.runs_code, "status": p.status, "errors": p.errors}
            for p in discover()]
