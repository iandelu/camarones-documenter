"""The board: a Backlog.md-compatible Kanban stored in cam-docs/backlog/ (items are Markdown, board.yaml is the kit's state)."""
from __future__ import annotations

from ..common import CACHE, ROOT

BACKLOG = ROOT / "backlog"
TASKS = BACKLOG / "tasks"
DRAFTS = BACKLOG / "drafts"
ARCHIVE = BACKLOG / "archive" / "tasks"
BOARD = BACKLOG / "board.yaml"
CONFIG = BACKLOG / "config.yml"
LOCK = CACHE / "board.lock"

STATUSES = ("Backlog", "Ready", "In Progress", "In Review", "Done", "Blocked")   # files always hold these English ids
TYPES = ("epic", "story", "bug", "spike", "task")
PRIORITIES = ("P0", "P1", "P2", "P3")
PREFIX = "WI"


def enabled() -> bool:
    return BOARD.exists()
