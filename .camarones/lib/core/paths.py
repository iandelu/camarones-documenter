"""Where a project lives: the machine prefs file, the Ctx-derived roots and the helpers that resolve paths in them."""
from __future__ import annotations

import os
from pathlib import Path

from .ctx import Ctx
from .platform import HOME, IS_WIN
from .process import which

PREFS = HOME / ".camarones.json"              # per-machine choices: language, models, runners, routing


CTX = Ctx.from_env()
ROOT = CTX.root
CAM_LAYOUT = CTX.cam_layout                        # cam-docs layout: repos are ROOT's siblings, not its children
WORKSPACE = CTX.workspace                          # folder holding the repos; agents are launched here
DOCS = CTX.docs
WORK = CTX.work                # plan, handoff, session log (committed, hidden from portal); CAMARONES_STATE_ROOT moves it
WS_FILE = CTX.ws_file                              # project config: per-project, never shared across projects
CACHE = CTX.cache                                  # generated, git-ignored: portal build, site, code graph, vendor cache
GRAPHS = CTX.graphs                                # per-repo graphify output (git-ignored), kept out of the repos


def repo_dir(name: str) -> Path:
    return WORKSPACE / name


def ws_rel(path: str) -> str:
    """A ROOT-relative path as seen from WORKSPACE, where agents run: cam-docs/docs/…, docs/… in the legacy layout,
    .cw/<n>/docs/… in a unit's worktree."""
    return Path(os.path.relpath(ROOT / path, WORKSPACE)).as_posix()


def rel_file(f: Path) -> str:
    """ROOT-relative posix path; files outside ROOT (a repo's wiki) get a ../ path that still joins with ROOT."""
    return Path(os.path.relpath(f, ROOT)).as_posix()


def cli_cmd() -> str:
    """How humans/agents invoke Camarón on this OS; legacy launchers remain a compatibility fallback."""
    if os.environ.get("CAMARONES_GLOBAL") or not (ROOT / "camaron.command").exists() and which("camaron"):
        return "camaron"
    if (ROOT / ("camaron.cmd" if IS_WIN else "camaron.command")).exists():
        return r".\camaron.cmd" if IS_WIN else "./camaron.command"
    return r".\camarones.cmd" if IS_WIN else "./camarones.command"
