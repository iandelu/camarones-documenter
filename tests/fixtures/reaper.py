"""A run leaves ~70k files behind (git repos, read-only objects) and pytest's own cleanup of them cost the next run a
minute on Windows, so a passing test's tmp_path goes as the test ends. Deleting it right there added a tenth of a second
or more to every test; a thread of the worker deletes it instead while the next test runs, which spends most of its time
waiting on git and other child processes anyway. The worker waits for that thread once, at the end of the run."""
from __future__ import annotations

import os, queue, shutil, stat, sys, threading
from pathlib import Path


def remove(path: Path) -> None:
    def onerror(fn, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            fn(p)
        except OSError:                         # a file a child process still holds: pytest's cleanup gets it later
            pass
    shutil.rmtree(path, **({"onexc": onerror} if sys.version_info >= (3, 12) else {"onerror": onerror}))


class Reaper:
    def __init__(self, remove=remove):
        self._remove = remove
        self._queue: queue.Queue[Path] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start = threading.Lock()

    def drop(self, path: Path) -> None:
        with self._start:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="tmp-path-reaper", daemon=True)
                self._thread.start()
        self._queue.put(path)

    def wait(self) -> None:
        self._queue.join()

    def _run(self) -> None:
        while True:
            path = self._queue.get()
            try:
                self._remove(path)
            except OSError:
                pass
            finally:
                self._queue.task_done()
