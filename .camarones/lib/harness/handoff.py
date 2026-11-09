"""A unit passing between a run and the person, whichever process runs it: a file per request, as a run's cancel file is
(`runs/<run>/handoff/<unit>.json`). The project server writes it, the run watches for it: `{"to": "you"}` ends the
unit's agent so that a terminal can open on its conversation, `{"to": "stop"}` ends it and the run skips the unit, and
`{"to": "pilot", "session": …, "agent": …}` gives the unit back for the run to resume."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from .. import sessions
from ..common import CTX, retry_busy


def file(run_id: str, uid: str) -> Path:
    return CTX.runs / run_id / "handoff" / f"{sessions.slug(uid)}.json"


def request(run_id: str, uid: str, to: str, **fields) -> None:
    """Whole or not at all: the run reads this file while it is being written."""
    f = file(run_id, uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f"{f.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps({"to": to, "unit": uid, "at": time.time(), **fields}), encoding="utf-8")
    retry_busy(lambda: os.replace(tmp, f))


def _load(f: Path) -> dict | None:
    try:
        req = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):               # none; or, on Windows, being replaced right now: seen at the next look
        return None
    return req if isinstance(req, dict) else None


def read(run_id: str, uid: str) -> dict | None:
    return _load(file(run_id, uid))


def clear(run_id: str, uid: str) -> None:
    try:
        retry_busy(lambda: file(run_id, uid).unlink(missing_ok=True))
    except OSError:                             # held open that long on Windows: a run must not end over it
        pass


def pending(run_id: str) -> dict[str, dict]:
    """The run's requests by unit."""
    d = CTX.runs / run_id / "handoff"
    found = (_load(f) for f in sorted(d.glob("*.json"))) if d.is_dir() else ()
    return {req["unit"]: req for req in found if req and req.get("unit")}
