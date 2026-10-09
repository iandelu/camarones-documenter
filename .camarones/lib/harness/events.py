"""Run event log: JSON Lines that feed the live portal, KPIs and cost. The scheduler is the only writer; readers
(portal SSE, `kpis`) resume from a byte offset and never see a half-written line."""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

VERSION = 1


class EventLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def emit(self, type: str, **fields) -> dict:
        ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        ev = {"v": VERSION, "ts": ts, "type": type, **fields}
        data = (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as fh:          # one write per event: lines never interleave
                fh.write(data)
        return ev

    def read(self, offset: int = 0) -> tuple[list[dict], int]:
        """Complete events after `offset` and the offset to resume from; a trailing partial line is left for later."""
        try:
            with self.path.open("rb") as fh:
                fh.seek(offset)
                chunk = fh.read()
        except FileNotFoundError:
            return [], offset
        complete = chunk[:chunk.rfind(b"\n") + 1]
        events = []
        for line in complete.decode("utf-8", errors="replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue                                # a damaged line must not stop the portal or the KPIs
        return events, offset + len(complete)
