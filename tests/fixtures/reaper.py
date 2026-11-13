"""A run leaves ~70k files behind (git repos, read-only objects) and pytest's own cleanup of them cost the next run a
minute on Windows, so a passing test's tmp_path goes as the test ends. Deleting it right there added a tenth of a second
or more to every test; a child process of the worker deletes it instead while the next test runs. A thread would share
the test's patches: a test that patches os.open or os.rmdir for the whole process would see the deleting's calls, and
the deleting its patch. The worker waits for the child once, at the end of the run."""
from __future__ import annotations

import os, shutil, stat, subprocess, sys, threading
from pathlib import Path


def remove(path: Path) -> None:
    def onerror(fn, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            fn(p)
        except OSError:                         # a file a process still holds: pytest's cleanup gets it later
            pass
    shutil.rmtree(path, **({"onexc": onerror} if sys.version_info >= (3, 12) else {"onerror": onerror}))


class Reaper:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def drop(self, path: Path) -> None:
        with self._lock:
            try:
                if self._proc is None:
                    self._proc = subprocess.Popen([sys.executable, "-I", __file__], stdin=subprocess.PIPE,
                                                  cwd=Path(__file__).parent, encoding="utf-8")
                self._proc.stdin.write(f"{path}\n")
                self._proc.stdin.flush()
            except OSError:                     # the child is gone: this folder is left to pytest's cleanup
                self._proc = None

    def wait(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc:
            try:
                proc.stdin.close()
            except OSError:
                pass
            proc.wait()


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        try:
            remove(Path(line.rstrip("\n")))
        except OSError:
            pass
