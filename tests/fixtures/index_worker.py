"""Worker of the two-process index test. Module-level so the `spawn` start method (Windows, macOS) can import it."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parents[2] / ".camarones"


def run(root: str, home: str, rounds: int, bump: str, want: str) -> None:
    """Call connect()+nodes() `rounds` times on the project at `root`, bumping `bump`'s mtime each round so that both
    processes keep finding the index stale. Every answer must list `want` among the touches of some node."""
    os.environ["CAMARONES_ROOT"] = root
    os.environ["HOME"] = os.environ["USERPROFILE"] = home
    for k in ("CAMARONES_GLOBAL", "CAMARONES_STATE_ROOT"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(KIT_DIR))
    from lib.kanban import index

    for _ in range(rounds):
        now = time.time_ns()
        os.utime(bump, ns=(now, now))
        conn = index.connect()
        try:
            touches = {t for n in index.nodes(conn) for t in n["touches"]}
        finally:
            conn.close()
        assert want in touches, touches
