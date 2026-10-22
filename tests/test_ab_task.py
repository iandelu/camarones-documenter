"""R33: `camaron ab --task "<task>"` — the same coding task twice, each in throwaway git worktrees of the service repos:
with cam-docs (its own worktree, the agent links) and without (only the code). The real checkouts are never touched.
An opt-in sampling hook (off by default, per project and per machine) keeps real prompts on this machine for replay."""
from __future__ import annotations

import io, json, sys

import pytest

from fixtures.builder import snapshot

AGENT = r'''
import json, os, sys
cwd = os.getcwd()
seen = sorted(os.listdir(cwd))
with open(os.path.join(cwd, "api", "src", "main", "java", "demo", "Api.java"), "a", encoding="utf-8") as fh:
    fh.write("// touched\n")
open(os.environ["FAKE_LOG"], "a", encoding="utf-8").write(json.dumps({"cwd": cwd, "seen": seen,
    "root": os.environ.get("CAMARONES_ROOT", "")}) + "\n")
print(json.dumps({"summary": "done", "files": ["api/src/main/java/demo/Api.java"]}))
'''


@pytest.fixture
def ab(wired, tmp_path, monkeypatch):
    import importlib
    script = tmp_path / "agent.py"
    script.write_text(AGENT, encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "agent.log"))
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script)]}}, "routing": {"agentic-heavy": ["fake"]}})
    wired.log = tmp_path / "agent.log"
    return importlib.import_module("lib.harness.ab")


def runs(wired):
    return [json.loads(l) for l in wired.log.read_text(encoding="utf-8").splitlines()]


def test_both_variants_work_in_throwaway_worktrees_and_the_real_repos_stay_untouched(wired, ab):
    before = {r: snapshot(wired.ws / r) for r in ("api", "web", "worker")}
    r = ab.run_task("Make Api implement Runnable", "fake", echo=lambda _: None)
    assert {r: snapshot(wired.ws / r) for r in ("api", "web", "worker")} == before
    with_docs, without = runs(wired)
    assert "cam-docs" in with_docs["seen"] and "AGENTS.md" in with_docs["seen"]
    assert with_docs["root"].endswith("cam-docs")
    assert not {"cam-docs", "AGENTS.md", "CLAUDE.md", ".mcp.json", ".claude", ".codex", ".agents"} & set(without["seen"])
    assert set(without["seen"]) >= {"api", "web", "worker"}
    for side in ("with", "without"):
        assert r[side]["files_changed"] == 1 and "touched" in r[side]["diff"]
    assert r["task"] == "Make Api implement Runnable"
    assert list((wired.root / "docs" / ".work" / "evals" / "ab").glob("*-task.json"))


def test_the_worktrees_are_gone_afterwards(wired, ab):
    ab.run_task("x", "fake", echo=lambda _: None)
    for repo in ("api", "web", "worker"):
        out = __import__("subprocess").run(["git", "-C", str(wired.ws / repo), "worktree", "list"],
                                           capture_output=True, text=True).stdout
        assert out.count("\n") == 1


def test_a_check_command_scores_each_variant(wired, ab):
    r = ab.run_task("x", "fake", check=[sys.executable, "-c", "import sys; sys.exit(0)"], echo=lambda _: None)
    assert r["with"]["check"] == r["without"]["check"] == "passed"


def test_tasks_respect_the_projects_switch(wired, ab):
    ws = wired.docs.workspace()
    ws["ab"] = {"enabled": False}
    wired.docs.save_workspace(ws)
    with pytest.raises(RuntimeError, match="turned off"):
        ab.run_task("x", "fake", echo=lambda _: None)


# ---------- sampling: off unless the project and this machine both opt in ----------
HOOK = {"session_id": "s1", "prompt": "Add a refund endpoint to the orders service", "cwd": "/w"}


def sample(ab, monkeypatch, rate_hit=True):
    monkeypatch.setattr(ab.random, "random", lambda: 0.0 if rate_hit else 0.99)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(HOOK)))
    return ab.sample_from_hook()


def test_sampling_is_off_by_default(wired, ab, monkeypatch):
    assert sample(ab, monkeypatch) is False and ab.samples() == []


def test_sampling_needs_the_machine_to_opt_in_too(wired, ab, monkeypatch):
    ws = wired.docs.workspace()
    ws["ab"] = {"sampling": {"enabled": True, "rate": 0.1}}
    wired.docs.save_workspace(ws)
    assert sample(ab, monkeypatch) is False
    ab.set_machine_sampling(True)
    assert sample(ab, monkeypatch) is True and ab.samples()[0]["prompt"] == HOOK["prompt"]
    assert sample(ab, monkeypatch, rate_hit=False) is False and len(ab.samples()) == 1
    assert not list(wired.root.rglob("ab-samples*"))                                   # never in the repo


def test_the_hook_is_installed_locally_and_approved(wired, ab):
    import importlib
    trust = importlib.import_module("lib.trust")
    ab.install_hook()
    st = json.loads((wired.root / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    cmd = st["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "ab sample" in cmd
    assert trust.pending() == []
    ab.remove_hook()
    st = json.loads((wired.root / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in (st.get("hooks") or {})


def test_the_task_command(wired, ab):
    import os, subprocess
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    out = subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "ab", "--task", "Make it Runnable",
                          "--json"], env=env, capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["with"]["files_changed"] == 1 and r["without"]["files_changed"] == 1
    hook = subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "ab", "sample"], env=env,
                          input="{not json", capture_output=True, text=True, encoding="utf-8")
    assert hook.returncode == 0                                                           # a hook never fails
