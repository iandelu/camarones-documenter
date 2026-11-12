"""The CLI surface as data: every command, flag, default, choice and alias. A refactor that moves commands around must
leave this file untouched."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from conftest import TESTS
from fixtures.cli_shape import shape


def test_the_cli_surface_is_unchanged(kit):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(TESTS / "fixtures" / "cli_shape.py")], env=env, cwd=kit.root,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    now = json.loads(r.stdout)
    snap = TESTS / "snapshots" / "cli.json"
    if os.environ.get("CAMARONES_UPDATE_SNAPSHOTS") == "1":
        snap.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    assert now == json.loads(snap.read_text(encoding="utf-8")), (
        "the CLI changed; if on purpose, rerun with CAMARONES_UPDATE_SNAPSHOTS=1 and review the diff")


def test_aliases_fold_into_one_entry():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("camaron", aliases=["camarones"])
    assert shape(p)["subparsers"] == {
        "dest": "cmd", "required": False,
        "subcommands": {"camaron": {"aliases": ["camarones"], "args": [], "exclusive_groups": [], "subparsers": None}}}


def test_exclusive_groups_and_types_are_recorded():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--b", type=int)
    g.add_argument("--a")
    p.add_argument("pos", nargs="*")
    s = shape(p)
    assert s["exclusive_groups"] == [{"dests": ["a", "b"], "required": True}]
    rows = {r["dest"]: r for r in s["args"]}
    assert rows["b"]["type"] == "int" and rows["a"]["type"] is None
    assert rows["pos"]["required"] is None
