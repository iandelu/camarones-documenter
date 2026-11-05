"""A test that never returns (tests/fixtures/hang_watchdog.py): reported by name with its stacks, and the run ends."""
from __future__ import annotations

import os, subprocess, sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def test_a_hung_test_is_reported_with_its_stacks_and_the_run_ends(tmp_path):
    (tmp_path / "conftest.py").write_text(
        f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
        "from fixtures.hang_watchdog import pytest_configure, pytest_runtest_protocol, pytest_terminal_summary, "
        "pytest_unconfigure  # noqa: F401\n", encoding="utf-8")
    (tmp_path / "test_inner.py").write_text(
        "import time\n\n\ndef test_hangs():\n    time.sleep(600)\n\n\ndef test_fine():\n    pass\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "pytest", "-n", "2", "--rootdir", str(tmp_path),         # this repo's addopts
                        "-c", str(TESTS.parent / "pyproject.toml"), str(tmp_path)], cwd=tmp_path, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120,
                       env={**os.environ, "CAMARONES_TEST_HANG_LIMIT": "3"})
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert "test_hangs" in out and "crashed" in out, out        # by name, as xdist reports a worker that died
    assert "test_inner.py" in out, out                          # and where it was stuck
