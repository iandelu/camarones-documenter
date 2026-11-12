"""Moved to lib/core/ctx.py; this path keeps old imports working."""
from ..core.ctx import CAM_DIR, KIT, Ctx, docs_root, find_project_marker, find_root

__facade__ = "lib.core.ctx"
__all__ = ["KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root"]
