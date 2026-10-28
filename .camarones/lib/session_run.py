"""Runs an interactive agent session inside the terminal window the kit opened, and keeps its record current
(lib/sessions.py): this process's pid while the agent runs, then when it ended and how. A closed window kills this
process too, so a record with a dead pid is a session nobody has open any more.

Executed as a script by that terminal (`python session_run.py <record> -- <agent argv>`), so stdlib only. A `-` record
is none (the docs update): the agent just runs, with Ctrl+C its own."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def _write(path: Path, rec: dict) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    for _ in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:                 # Windows: the server is reading it right now
            time.sleep(0.05)
    tmp.unlink(missing_ok=True)


def _read(path: Path) -> dict:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) else {}
    except (OSError, ValueError):
        return {}


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("usage: session_run.py <record | -> -- <command…>", file=sys.stderr)
        return 2
    path, cmd = None if argv[0] == "-" else Path(argv[0]), argv[2:]
    if path:
        _write(path, {**_read(path), "pid": os.getpid(), "host": socket.gethostname(), "ts": time.time()})
    # Ctrl+C belongs to the agent; a handler, not SIG_IGN, so it resets. Put back once the record has its end, for a
    # caller in this process
    old = signal.signal(signal.SIGINT, lambda *_: None)
    try:
        try:
            code = subprocess.call(cmd)
        except OSError as e:
            print(e, file=sys.stderr)
            code = 127
        if path:
            _write(path, {**_read(path), "ended": time.time(), "code": code})
    finally:
        signal.signal(signal.SIGINT, old)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
