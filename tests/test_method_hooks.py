"""R36 / X2: hooks that hold the method even when an agent skims the playbook — opt-in per project (`camaron hooks
on`), written by the kit into cam-docs/.claude/settings.json and recognised by trust as the kit's own. SessionStart
brings the plan state in, PostToolUse checks the page just edited, Stop reminds once to update the docs."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest


def settings(kit):
    return json.loads((kit.root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def kit_hooks(kit):
    return {e: [h["command"] for g in groups for h in g.get("hooks", []) if " hook " in h.get("command", "")]
            for e, groups in (settings(kit).get("hooks") or {}).items()}


@pytest.fixture
def hooks(wired):
    import importlib
    wired.trust = importlib.import_module("lib.trust")
    return importlib.import_module("lib.hooks")


def test_off_by_default(wired, hooks):
    assert not any(kit_hooks(wired).values())


def test_on_writes_three_hooks_the_kit_owns(wired, hooks):
    hooks.set_enabled(True)
    found = kit_hooks(wired)
    assert {k for k, v in found.items() if v} == {"SessionStart", "PostToolUse", "Stop"}
    assert wired.trust.pending() == []
    hooks.set_enabled(False)
    assert not any(kit_hooks(wired).values())


def test_the_teams_own_hooks_are_kept(wired, hooks):
    st = settings(wired)
    st.setdefault("hooks", {})["PreToolUse"] = [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo x"}]}]
    (wired.root / ".claude" / "settings.json").write_text(json.dumps(st), encoding="utf-8")
    hooks.set_enabled(True)
    hooks.set_enabled(False)
    assert settings(wired)["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo x"


def test_session_start_brings_the_plan_in(wired, hooks):
    wired.plan.sync()
    text = hooks.session_start()
    assert "plan" in text.lower() and "setup" in text and len(text) <= hooks.CAP


def run_hook(kit, name, payload):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "hook", name], env=env,
                          input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")


def test_post_edit_feeds_a_pages_problems_back(wired, hooks):
    page = wired.root / "docs" / "flows" / "x.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: X\ntype: business-flow\n---\n# X\n\nNo summary here, see above.\n", encoding="utf-8")
    r = run_hook(wired, "post-edit", {"tool_name": "Write", "tool_input": {"file_path": str(page)}})
    assert r.returncode == 2 and "TL;DR" in r.stderr and "flows/x.md" in r.stderr
    other = run_hook(wired, "post-edit", {"tool_name": "Write", "tool_input": {"file_path": str(wired.ws / "api" / "x.java")}})
    assert other.returncode == 0 and not other.stderr


def test_stop_reminds_once_per_session(wired, hooks):
    payload = {"session_id": "s-1", "stop_hook_active": False}
    first = run_hook(wired, "stop", payload)
    assert first.returncode == 0 and json.loads(first.stdout)["decision"] == "block"
    assert "never-documented" in first.stdout or "changed" in first.stdout
    assert run_hook(wired, "stop", payload).stdout.strip() == ""
    assert run_hook(wired, "stop", {"session_id": "s-2", "stop_hook_active": True}).stdout.strip() == ""


def test_the_hooks_command(wired, hooks):
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    out = subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "hooks", "on"], env=env,
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0 and wired.docs.workspace()["hooks"]["method"] is True
    assert kit_hooks(wired)["Stop"]


# ---------- X7: compliance of what a unit writes ----------
GOOD = """---
type: business-flow
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
x-sources:
  - api:README.md
---
# Checkout

> **TL;DR:** The cart calls the payments service.

## Summary
S.

## Sequence
```mermaid
sequenceDiagram
  A->>B: pay
```

## Steps
1. Pay.

## Failure handling
Retry.

## Data touched
Orders.
"""


def test_compliance_score_is_deterministic(wired):
    from lib.harness import comply
    good = wired.root / "docs" / "flows" / "good.md"
    bad = wired.root / "docs" / "flows" / "bad.md"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text(GOOD, encoding="utf-8")
    bad.write_text("---\ntitle: Bad\nx-sources:\n  - api:nope.java\n---\nno heading\n", encoding="utf-8")
    s = comply.score(["flows/good.md", "flows/bad.md"])
    assert s["pages"] == 2 and s["compliant"] == 1 and s["score"] == 0.5
    assert s["by_page"]["flows/bad.md"]["orphan_sources"] == ["api:nope.java"]
    assert s["by_page"]["flows/good.md"]["issues"] == []


def test_comply_runs_one_unit_and_scores_what_it_wrote(wired, tmp_path, monkeypatch):
    import sys as _sys
    from test_scheduler import FAKE
    script = tmp_path / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    monkeypatch.setenv("KIT_DIR", str(wired.kit_dir))
    monkeypatch.setenv("FAKE_SLEEP", "0.1")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [_sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"]}})
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    from lib.harness import comply
    r = comply.run("discovery:api", echo=lambda _: None)
    assert r["status"] == "done" and r["written"] == ["notes/discovery-api.md"]
    assert r["pages"] == 1 and r["score"] == 0.0                      # the fake writes a page without TL;DR or type
    assert list((wired.root / "docs" / ".work" / "evals" / "comply").glob("*.json"))


def test_comply_refuses_a_unit_that_is_not_ready(wired):
    """Found on the sandbox: comply on repo-brief (waiting for the interviews) printed '0 pages' and exit 0."""
    import pytest
    wired.plan.sync()
    from lib.harness import comply
    with pytest.raises(ValueError, match="interview-context"):
        comply.run("repo-brief:api", echo=lambda _: None)
    assert not list((wired.root / "docs" / ".work" / "evals" / "comply").glob("*.json"))


def test_comply_follows_links_to_pages_it_did_not_write(wired):
    """Found on the sandbox: the score checked links against the written pages only, so a brief linking its
    reference.md (written earlier) counted as broken while `check` was clean."""
    docs_dir = wired.root / "docs" / "flows"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "other.md").write_text("---\ntitle: Other\n---\n# Other\n", encoding="utf-8")
    (docs_dir / "good.md").write_text(GOOD.rstrip() + "\n\nSee [the other flow](other.md).\n", encoding="utf-8")
    from lib.harness import comply
    s = comply.score(["flows/good.md"])
    assert s["by_page"]["flows/good.md"]["issues"] == [], s
