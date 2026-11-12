"""F2 parity oracle: the same command lines through a frozen copy of the entry script as it was before F2
(tests/fixtures/cli_reference.py) and through the real CLI, each on its own fresh copy of one workspace. Exit code,
stdout and stderr must match once each side's folder and timestamps are hidden. Deleted when F2 ends."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import KIT_DIR, TESTS
from fixtures.builder import make_workspace

FIXTURES = TESTS / "fixtures"
REFERENCE = FIXTURES / "cli_reference.py"
REAL = KIT_DIR / "camarones.py"
TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:\d\d)?")

CASES: list[tuple[str, ...]] = [
    # meta (Task 5)
    ("help",), ("-h",), ("nosuch",), ("catalog",), ("catalog", "--json"), ("catalog", "--markdown"),
    ("catalog", "--check"),
    # projects (Task 6)
    ("projects",), ("projects", "--json"), ("projects", "--add", "{ws}", "--json"),
    ("projects", "--inspect", "{ws}", "--json"), ("projects", "--inspect", "{ws}/nope"), ("init",), ("new",), ("join",),
    # machine (Task 7)
    ("version",), ("config",), ("config", "--json"), ("config", "get", "lang"), ("config", "set", "lang"),
    ("config", "get", "nope"), ("detect",), ("profile", "quick"), ("repair",), ("migrate", "--dry-run"),
    ("uninstall", "--dry-run"), ("install", "{ws}/copy", "--dry-run"), ("sync",),
    # analyze (Task 8)
    ("changes",), ("llms",), ("mark-documented",), ("history",), ("fresh",), ("fresh", "--json"), ("fresh", "--ack", "x"),
    ("fresh", "--plan"), ("blocks", "--json"), ("pages", "--json"), ("diagrams", "--json"), ("arch-draft",),
    ("radar", "--json"), ("schemas", "--json"), ("inventory", "--json"), ("bump", "api", "nope", "1.0"), ("stack", "api"),
    ("stack", "api", "Java 21"), ("stack", "api", "--reset"), ("stack", "nope", "x"),
    # check (Task 9)
    ("status",), ("status", "--json"), ("check",), ("check", "--strict"), ("pipeline", "show"),
    ("pipeline", "show", "--json"), ("pipeline", "validate"), ("eval",), ("eval", "list", "--json"), ("eval", "confirm"),
    ("eval", "comply"), ("eval", "draft"), ("ab",), ("ab", "sampling"), ("kpis", "--compare", "a", "b"),
    ("kpis", "--no-check", "--json"), ("stats", "--json"), ("doctor", "--context", "--json"),
    # generate (Task 10)
    ("plan",), ("plan", "--json"), ("plan", "next"), ("plan", "next", "--json"), ("plan", "start"), ("plan", "note"),
    ("plan", "approve"), ("plan", "redo"), ("plan", "add", "x"), ("plan", "add", "flow-x", "Flow X"),
    ("plan", "done", "nope"), ("runs",), ("runs", "--json"), ("runs", "nope"), ("prompt", "update"),
    ("pr", "fresh", "nope"), ("pr", "fresh", "api", "--files", "README.md", "--json"),
    ("docs", "reset", "--redo", "--dry-run"), ("run", "--per-runner", "bad"),
    # team + interviews (Task 11)
    ("remote",), ("share", "--auto", "on"), ("checkpoint",), ("trust", "--json"), ("hooks",), ("hooks", "--json"),
    ("plugins",), ("plugins", "--json"), ("plugins", "enable", "nope"), ("plugins", "add"),
    ("plugins", "outdated", "--json"), ("export", "tour"), ("removed", "add", "old api", "--why", "gone"),
    ("feedback", "docs/overview.md", "too short", "--by", "ana"), ("review", "list"), ("review", "wait"),
    ("review", "wait", "nope", "--timeout", "0"), ("ci", "gitlab"), ("interview", "status", "--json"),
    ("interview", "mode"), ("interview", "import"),
    # board + adr (Task 12)
    ("board", "init"), ("board", "list", "--json"), ("board", "show"), ("board", "add", "story", "First card", "--json"),
    ("board", "merge-driver", "O"), ("adr", "list", "--json"), ("adr", "show"),
]


def normalize(text: str, base: Path) -> str:
    forms = {str(base), base.as_posix(), str(base).replace("\\", "\\\\"), os.path.realpath(base),
             Path(os.path.realpath(base)).as_posix(), os.path.realpath(base).replace("\\", "\\\\")}
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "<BASE>")
    return TIMESTAMP.sub("<TS>", text)


def _env(base: Path, ws: Path) -> dict[str, str]:
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "CAMARONES_ROOT": str(ws / "cam-docs"),
            "COLUMNS": "100"}


def side(script: Path, argv: tuple[str, ...], base: Path) -> tuple[int, str, str]:
    ws = make_workspace(base)
    args = [a.replace("{ws}", str(ws)) for a in argv]
    r = subprocess.run([sys.executable, str(script), *args], env=_env(base, ws), cwd=ws, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    return r.returncode, normalize(r.stdout, base), normalize(r.stderr, base)


def _help(script: Path, base: Path) -> dict:
    ws = make_workspace(base)
    r = subprocess.run([sys.executable, str(FIXTURES / "cli_help.py"), str(script)], env=_env(base, ws), cwd=ws,
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_normalize_hides_the_side_folder_and_timestamps(tmp_path):
    base = tmp_path / "a"
    text = f"{base}/demo at 2026-11-12T10:00:01Z; {base.as_posix()}/x"
    assert normalize(text, base) == "<BASE>/demo at <TS>; <BASE>/x"


@pytest.mark.parametrize("argv", CASES, ids=" ".join)
def test_cli_matches_the_reference(argv, tmp_path, isolated_env):
    assert side(REAL, argv, tmp_path / "b") == side(REFERENCE, argv, tmp_path / "a")


def test_help_and_order_match_the_reference(tmp_path, isolated_env):
    assert _help(REAL, tmp_path / "b") == _help(REFERENCE, tmp_path / "a")


def test_catalog_rows_are_unchanged():
    from lib import catalog
    assert catalog.COMMANDS == json.loads((FIXTURES / "catalog_reference.json").read_text(encoding="utf-8"))


def test_the_oracle_is_not_vacuous(tmp_path, isolated_env):
    code, out, _ = side(REAL, ("help",), tmp_path / "a")
    assert code == 0 and "plan [sync|next|start" in out
    assert side(REAL, ("nosuch",), tmp_path / "b")[0] == 2
