"""Keeps VERSIONS, which install and upgrade read from this file as text, and re-exports lib.core for old imports."""
from __future__ import annotations

from .core.ctx import KIT, CAM_DIR, Ctx, docs_root, find_project_marker, find_root
from .core.fsutil import load_json, retry_busy, rmtree, save_json
from .core.paths import (
    CACHE, CAM_LAYOUT, CTX, DOCS, GRAPHS, PREFS, ROOT, WORK, WORKSPACE, WS_FILE, cli_cmd, rel_file, repo_dir, ws_rel,
)
from .core.platform import HOME, IS_MAC, IS_WIN
from .core.process import (
    PARENT_SESSION, ensure_path, extra_bin_dirs, kill_tree, leave_parent_session, out, py, run, sdkman_dir, uv, which,
)

__facade__ = "lib.core"
__all__ = [
    "IS_WIN", "IS_MAC", "HOME", "PREFS", "CTX", "ROOT", "CAM_LAYOUT", "WORKSPACE", "DOCS", "WORK", "WS_FILE", "CACHE",
    "GRAPHS", "KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root", "repo_dir", "ws_rel",
    "rel_file", "cli_cmd", "sdkman_dir", "extra_bin_dirs", "ensure_path", "which", "run", "out", "PARENT_SESSION",
    "leave_parent_session", "kill_tree", "uv", "retry_busy", "load_json", "save_json", "py", "rmtree",
]

VERSIONS = {
    "kit": "4.82.0",
    "backlog_md": "1.55.3",   # Backlog.md, the compatibility check of the board (tests/e2e/test_backlogmd.py)
    "openwiki": "0.5.2",
    "likec4": "1.59.4",
    "graphify": "0.9.65",
    "mmdc": "11.17.0",        # mermaid-cli 11.x = mermaid 11, the major the portal renders with (serve.py VENDOR)
    "gitleaks": "8.30.1",
    "osv-scanner": "2.6.0",
    "node_min_major": 22,
    "electron": "44.7.0",     # the desktop app (`camaron app`), installed into ~/.camarones/desktop
    "uv": "0.12.18",          # the uv image the generated GitLab jobs run in (lib/ci.py)
}
