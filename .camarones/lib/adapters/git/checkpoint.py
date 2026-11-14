"""The Vcs port (lib/ports/vcs.py) on git: the paths of the project a checkpoint commit stages."""
from __future__ import annotations

from lib.common import ROOT


CHECKPOINT_PATHS = ["docs", "wikis", "evals", "backlog", ".gitattributes", ".camarones/workspace.yaml", ".camarones/PLAYBOOK.md", ".camarones/CONVENTIONS.md",
                    ".camarones/skeletons", ".camarones/plugins", ".camarones/plugins.lock", ".camarones/.kit-docs.json", ".camarones/ci", ".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md",
                    ".gitignore", ".gitlab-ci.yml", ".github",
                    ".camarones/skills", ".camarones/.kit-skills.json"]   # a team copy, its fork stamp and its rendering travel together


def checkpoint_paths() -> list[str]:
    """What a checkpoint stages. .gitattributes only on a project with a board: it holds the board's merge driver line,
    and a project without one may have a root .gitattributes of its own that the kit never committed."""
    from lib import kanban
    return [p for p in CHECKPOINT_PATHS if (ROOT / p).exists() and (p != ".gitattributes" or kanban.enabled())]
