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
                       capture_output=True, text=True, encoding="utf-8", check=True)
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
    assert shape(p)["subcommands"] == {"camaron": {"aliases": ["camarones"], "args": [], "subcommands": {}}}
