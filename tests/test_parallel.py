"""Several agents on one plan at once: a cross-process lock on plan.yaml, atomic saves and per-unit claims."""
from __future__ import annotations

import datetime as dt
import os, subprocess, sys, textwrap

import pytest
import yaml

from conftest import KIT_DIR


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def finish(plan, *uids):
    for uid in uids:
        plan.set_status(uid, "done", record=False)


def cli(kit, *args, session: str | None = None):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    env.pop("CAMARONES_SESSION", None)
    if session:
        env["CAMARONES_SESSION"] = session
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "plan", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


# ---------- lock + atomic save ----------
def test_file_lock_serialises_and_takes_over_a_dead_holder(kit, monkeypatch):
    common = kit.common
    lock = kit.root / ".camarones" / ".cache" / "t.lock"
    with common.file_lock(lock):
        assert lock.exists()
        with pytest.raises(RuntimeError):
            with common.file_lock(lock, timeout=0.2, reentrant=False):
                pass
    assert not lock.exists()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("999999", encoding="utf-8")                  # left behind by a crashed process
    monkeypatch.setattr(common, "pid_alive", lambda pid: False)
    with common.file_lock(lock, timeout=1):
        assert lock.read_text(encoding="utf-8") == str(os.getpid())


def test_concurrent_writers_lose_no_update(kit):
    """Two processes adding 30 units each, interleaved with status changes: every unit and status survives."""
    kit.plan.sync()
    code = textwrap.dedent("""
        import sys
        sys.path.insert(0, sys.argv[1])
        from lib import plan
        tag = sys.argv[2]
        for i in range(30):
            plan.add(f"flow:{tag}-{i}", f"flow {tag} {i}")
            plan.set_status(f"flow:{tag}-{i}", "blocked", record=False)
    """)
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    procs = [subprocess.Popen([sys.executable, "-c", code, str(KIT_DIR), tag], env=env, cwd=kit.ws,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for tag in ("a", "b")]
    for p in procs:
        out, _ = p.communicate(timeout=240)
        assert p.returncode == 0, out
    data = kit.plan.load()
    flows = [u for u in data["units"] if u["type"] == "flow"]
    assert len(flows) == 60
    assert all(u["status"] == "blocked" for u in flows)


def test_save_is_atomic_and_leaves_no_temp_file(kit):
    kit.plan.sync()
    assert yaml.safe_load(kit.plan.PLAN.read_text(encoding="utf-8"))["units"]
    assert [p.name for p in kit.plan.PLAN.parent.iterdir() if p.suffix == ".tmp"] == []


# ---------- claims ----------
@pytest.fixture
def ready(kit):
    plan = kit.plan
    plan.sync()
    finish(plan, "setup", "discovery:api", "discovery:web", "discovery:worker")
    return kit


def test_claim_refuses_a_unit_another_live_session_holds(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A", agent="claude")
    u = unit(plan.load(), "discovery-cross")
    assert u["status"] == "doing" and u["owner"]["session"] == "A" and u["owner"]["agent"] == "claude"
    with pytest.raises(plan.Taken):
        plan.claim("discovery-cross", "B")
    plan.claim("discovery-cross", "A")                                       # the same session resumes
    plan.claim("discovery-cross", "B", force=True)                           # an explicit takeover
    assert unit(plan.load(), "discovery-cross")["owner"]["session"] == "B"


def test_a_stale_claim_can_be_taken(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A")
    old = (dt.datetime.now() - plan.CLAIM_TTL - dt.timedelta(minutes=1)).replace(microsecond=0).isoformat()

    def age(data):
        unit(data, "discovery-cross")["owner"]["seen"] = old
    plan.mutate(age)
    plan.claim("discovery-cross", "B")
    assert unit(plan.load(), "discovery-cross")["owner"]["session"] == "B"


def test_a_doing_unit_without_owner_is_free(ready):
    """3.x plans have no owners: a unit left `doing` by an old session is resumed as before."""
    plan = ready.plan
    plan.set_status("discovery-cross", "doing")
    plan.claim("discovery-cross", "B")
    assert unit(plan.load(), "discovery-cross")["owner"]["session"] == "B"


def test_closing_a_unit_releases_its_claim_and_notes_refresh_it(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A")
    before = unit(plan.load(), "discovery-cross")["owner"]["seen"]
    plan.mutate(lambda d: unit(d, "discovery-cross")["owner"].update(seen="2000-01-01T00:00:00"))
    plan.note("discovery-cross", "half way")
    assert unit(plan.load(), "discovery-cross")["owner"]["seen"] >= before
    plan.set_status("discovery-cross", "done")
    assert "owner" not in unit(plan.load(), "discovery-cross")


def test_sync_keeps_the_claim(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A")
    plan.sync()
    assert unit(plan.load(), "discovery-cross")["owner"]["session"] == "A"


def test_available_can_hide_units_taken_by_others(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A")
    assert "discovery-cross" in [u["id"] for u in plan.available()]
    assert "discovery-cross" not in [u["id"] for u in plan.available(session="B")]
    assert "discovery-cross" in [u["id"] for u in plan.available(session="A")]


def test_claim_next_picks_a_free_unit_atomically(ready):
    plan = ready.plan
    plan.claim("discovery-cross", "A")
    plan.add("flow:x", "x", deps=[])
    got = plan.claim_next("B", pick=lambda ready: next((u for u in ready if u["runner"] == "agent"), None))
    assert got and got["id"] == "flow:x"
    assert plan.claim_next("C", pick=lambda ready: next((u for u in ready if u["runner"] == "agent"), None)) is None


# ---------- shared files: open questions, handoff, prompts, checkpoints ----------
def test_plan_ask_appends_tagged_questions_without_losing_any(ready):
    plan = ready.plan
    plan.sync()
    code = textwrap.dedent("""
        import sys
        sys.path.insert(0, sys.argv[1])
        from lib import plan
        for i in range(15):
            plan.ask(sys.argv[2], f"question {sys.argv[2]} {i}?")
    """)
    env = {**os.environ, "CAMARONES_ROOT": str(ready.root), "PYTHONUTF8": "1"}
    procs = [subprocess.Popen([sys.executable, "-c", code, str(KIT_DIR), uid], env=env, cwd=ready.ws,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for uid in ("repo-brief:api", "domain")]
    for p in procs:
        out, _ = p.communicate(timeout=240)
        assert p.returncode == 0, out
    text = plan.OPEN_QUESTIONS.read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if l.startswith("- [ ] ")]
    assert len(lines) == 30
    assert any("context · repo-brief:api) question repo-brief:api 0?" in l for l in lines)   # topic from the soft dep
    assert any("language · domain) question domain 3?" in l for l in lines)
    plan.ask("data", "who owns orders?", topic="history")
    assert "history · data) who owns orders?" in plan.OPEN_QUESTIONS.read_text(encoding="utf-8")


def test_handoff_keeps_recent_sessions_newest_first(ready):
    plan = ready.plan
    plan.HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    plan.HANDOFF.write_text("# Session handoff 🦐\n\nEach agent session rewrites \"Last session\" when it finishes a plan "
                            "unit. Read this first in every new session.\n\n## Last session — setup\n- Done: installed.\n",
                            encoding="utf-8", newline="\n")
    plan.handoff("discovery:api", "- Done: api mapped.\n### a heading the agent wrote")
    text = plan.HANDOFF.read_text(encoding="utf-8")
    assert "## Recent sessions" in text and "## Last session" not in text
    assert text.index("### discovery:api") < text.index("### setup")         # the old section became an entry
    assert "#### a heading the agent wrote" in text                            # cannot split the entries
    for i in range(12):
        plan.handoff(f"flow:{i}", f"- Done: flow {i}")
    text = plan.HANDOFF.read_text(encoding="utf-8")
    assert text.count("\n### ") == plan.HANDOFF_KEEP
    assert text.index("### flow:11") < text.index("### flow:10")
    assert "### setup" not in text
    plan.handoff("flow:12", "- Done")                                          # idempotent shape
    assert plan.HANDOFF.read_text(encoding="utf-8").count("## Recent sessions") == 1


def test_prompt_files_are_per_unit(ready):
    plan = ready.plan
    a, b = plan.prompt_file("repo-brief:api"), plan.prompt_file("repo-brief:web")
    assert a != b and a.parent == b.parent and ":" not in a.name


def test_prompt_tells_the_session_to_use_the_shared_file_commands(ready):
    text = ready.plan.prompt("discovery-cross", unattended=True)
    assert "plan handoff discovery-cross" in text
    assert "plan start discovery-cross --session" in text


def test_interview_prompt_starts_from_the_drafts_questions(ready):
    text = ready.plan.prompt("interview-context")
    assert "open-questions.md" in text and "context ·" in text


def test_checkpoint_commits_are_serialised(ready, monkeypatch):
    env, common = ready.env, ready.common
    seen = []
    real_run = env.run

    def spy(cmd, *a, **kw):
        if cmd[:2] == ["git", "add"]:
            seen.append(env.CHECKPOINT_LOCK.exists())
        return real_run(cmd, *a, **kw)
    monkeypatch.setattr(env, "run", spy)
    (ready.root / "docs").mkdir(exist_ok=True)
    (ready.root / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=ready.root, check=True)
    env.checkpoint_commit("x")
    assert seen == [True] and not env.CHECKPOINT_LOCK.exists()


# ---------- CLI ----------
def test_cli_start_refuses_a_taken_unit(ready):
    r = cli(ready, "start", "discovery-cross", "--session", "A")
    assert r.returncode == 0, r.stdout + r.stderr
    r = cli(ready, "start", "discovery-cross", session="B")
    assert r.returncode == 3 and "A" in (r.stdout + r.stderr)
    r = cli(ready, "start", "discovery-cross", "--session", "B", "--force")
    assert r.returncode == 0, r.stdout + r.stderr
    assert unit(ready.plan.load(), "discovery-cross")["owner"]["session"] == "B"


def test_cli_next_claim_prints_the_claimed_unit(ready):
    ready.plan.claim("discovery-cross", "A")
    r = cli(ready, "next", "--claim", "--session", "B")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "discovery-cross" not in r.stdout                                  # taken by A
    r = cli(ready, "next")
    assert "taken: A" in r.stdout


def test_cli_ask_and_handoff(ready):
    r = cli(ready, "ask", "domain", "which context owns pets?")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "which context owns pets?" in ready.plan.OPEN_QUESTIONS.read_text(encoding="utf-8")
    r = cli(ready, "handoff", "domain", "- Done: glossary draft")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "### domain" in ready.plan.HANDOFF.read_text(encoding="utf-8")
