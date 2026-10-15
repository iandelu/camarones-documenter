"""Plugins (R10): a folder with a plugin.yaml manifest. The kit's own pieces live in lib/plugins/; a project's in
cam-docs/.camarones/plugins/. Whether a plugin runs code is computed from what it provides and the files it ships,
never trusted from the manifest. A project plugin that runs code is not loaded until it is approved."""
from __future__ import annotations

import functools
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
NEEDS_APPROVAL = "not loaded: runs code and needs approval"


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

    @property
    def active(self) -> bool:
        return not self.errors and (self.source == "kit" or not self.runs_code)

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


def discover() -> list[Plugin]:
    taken = {p.name for p in kit()}
    return [*kit(), *(_load(folder, "project", taken) for folder in _folders(PROJECT_DIR))]


def provided(kind: str) -> list[dict]:
    """Everything active plugins provide of one kind (e.g. runners), in discovery order."""
    return [item for p in discover() if p.active for item in p.provides.get(kind) or []]


def rows() -> list[dict]:
    return [{"name": p.name, "version": str(p.manifest.get("version", "")), "source": p.source,
             "provides": sorted(p.provides), "runs_code": p.runs_code, "status": p.status, "errors": p.errors}
            for p in discover()]
