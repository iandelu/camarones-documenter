"""The board stays a Backlog.md board (spec §10): Backlog.md reads our files and its edits keep our fields.
Needs npx and network the first time (the package is fetched at the pinned version). Run: uv run pytest -m e2e"""
from __future__ import annotations

import subprocess

import pytest

pytestmark = pytest.mark.e2e


def backlog(common, *args):
    npx = common.which("npx")
    if not npx:
        pytest.skip("npx is not available")
    cmd = [npx, "-y", f"backlog.md@{common.VERSIONS['backlog_md']}", *args]
    r = subprocess.run(cmd, cwd=common.ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300)
    assert r.returncode == 0, f"{args}:\n{r.stdout}\n{r.stderr}"
    return r.stdout


def test_backlogmd_reads_and_edits_our_board(kit):
    from lib import common
    from lib.kanban import TASKS, ops, repair
    from lib.kanban.items import parse_item
    page = common.ROOT / "docs" / "flows" / "checkout.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Checkout\n", encoding="utf-8", newline="\n")
    ops.init(log=lambda _: None)
    ops.add("epic", "Payments", by="ana")
    ops.add("story", "Idempotent handling", epic="WI-1", repos=["api"], docs=["flows/checkout.md"], by="ana")

    listing = backlog(common, "task", "list", "--plain")
    assert "WI-2" in listing and "Idempotent handling" in listing

    def story():
        return next(parse_item(p.read_text(encoding="utf-8"), p) for p in TASKS.glob("wi-2 - *.md"))

    before = dict(story().fm)
    backlog(common, "task", "edit", "WI-2", "-t", "Idempotent handling v2")
    after = story()
    assert after.fm["title"] == "Idempotent handling v2"
    for key in ("x-uid", "x-repos", "documentation", "parent_task_id"):
        assert after.fm[key] == before[key], key

    warnings = repair.repair(log=lambda _: None)["warnings"]
    assert all("wi-2" in w.lower() for w in warnings), warnings


def test_backlogmd_edits_keep_touches_and_dependencies(kit):
    """`x-touches` (a story's footprint) and `dependencies` (a task waiting for another) survive a Backlog.md edit."""
    from lib import common
    from lib.kanban import TASKS, ops, repair
    from lib.kanban.items import parse_item
    ops.init(log=lambda _: None)
    ops.add("story", "Export a page", repos=["api", "web"], touches=["api:src/export.py", "web:src/Export.jsx"],
            by="ana")
    ops.add("task", "Export endpoint", parent="WI-1", repos=["api"], touches=["api:src/export.py"], by="ana")
    ops.add("task", "Export button", parent="WI-1", repos=["web"], touches=["web:src/Export.jsx"],
            dependencies=["WI-2"], by="ana")

    def card(n):
        return next(parse_item(p.read_text(encoding="utf-8"), p) for p in TASKS.glob(f"wi-{n} - *.md"))

    before = {n: dict(card(n).fm) for n in (1, 3)}
    assert before[1]["x-touches"] == ["api:src/export.py", "web:src/Export.jsx"]
    assert before[3]["dependencies"] == ["WI-2"]

    backlog(common, "task", "edit", "WI-1", "-t", "Export a page v2")
    backlog(common, "task", "edit", "WI-3", "-t", "Export button v2")
    story, button = card(1), card(3)
    assert story.fm["title"] == "Export a page v2" and button.fm["title"] == "Export button v2"
    assert story.fm["x-touches"] == before[1]["x-touches"]
    assert button.fm["x-touches"] == before[3]["x-touches"]
    assert button.fm["dependencies"] == before[3]["dependencies"]

    # the footprint files were never created, so repair says so; it finds nothing else wrong after Backlog.md's edits
    warnings = repair.repair(log=lambda _: None)["warnings"]
    assert all("x-touches file not found" in w for w in warnings), warnings
