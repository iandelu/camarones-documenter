"""Integration (R12): a parallel unit's worktree comes back into the main cam-docs deterministically. Main is merged
into the unit's branch first, inside the worktree, and the gates run there; main only receives a merge that cannot
conflict. Conflicts, new gate errors or local changes in main block the unit and leave main untouched."""
from __future__ import annotations

import subprocess

import pytest


def git(path, *args):
    return subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=True).stdout.strip()


def no_gates():
    return []


def main_changes(root):
    """Uncommitted changes in the main cam-docs, apart from the live plan (committed by checkpoints, not here)."""
    return [l for l in git(root, "status", "--porcelain").splitlines() if "docs/.work/" not in l]


@pytest.fixture
def setup(wired):
    from lib.harness import integrate
    from lib.harness.worktrees import Worktrees
    wired.plan.sync()
    wt = Worktrees(wired.common.CTX)
    events = []

    def unit(uid, files):
        w = wt.add(uid)
        for rel, text in files.items():
            f = w.path / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8", newline="\n")
        wired.plan.set_status(uid, "done")
        return w

    def run(uid, gates=None, policy="on-conflict"):
        return integrate.integrate(uid, wired.common.CTX, gates=no_gates() if gates is None else gates, policy=policy,
                                   emit=lambda kind, **f: events.append((kind, f)))
    return {"wt": wt, "unit": unit, "run": run, "events": events, "integrate": integrate}


def status(wired, uid):
    return next(u for u in wired.plan.load()["units"] if u["id"] == uid)


def test_disjoint_units_both_land_and_their_worktrees_go(wired, setup):
    a = setup["unit"]("discovery:api", {"docs/repos/api/brief.md": "# api\n"})
    b = setup["unit"]("discovery:web", {"docs/repos/web/brief.md": "# web\n"})
    assert setup["run"]("discovery:api").outcome == "merged"
    assert setup["run"]("discovery:web").outcome == "merged"
    assert (wired.root / "docs/repos/api/brief.md").exists() and (wired.root / "docs/repos/web/brief.md").exists()
    assert not a.path.exists() and not b.path.exists() and setup["wt"].list() == []
    assert main_changes(wired.root) == []
    assert [k for k, _ in setup["events"]] == ["merge.ok", "merge.ok"]


def test_the_real_gates_run_on_a_clean_unit(wired, setup):
    setup["unit"]("discovery:api", {"docs/repos/api/brief.md": "---\ntitle: api\n---\n# api\n"})
    assert setup["run"]("discovery:api", gates=setup["integrate"].GATES).outcome == "merged"


def test_derived_files_never_conflict(wired, setup):
    setup["unit"]("discovery:api", {"docs/a.md": "a\n", "docs/llms.txt": "from api\n", "docs/.status.json": "{}\n"})
    setup["unit"]("discovery:web", {"docs/b.md": "b\n", "docs/llms.txt": "from web\n", "docs/.status.json": "[]\n"})
    assert setup["run"]("discovery:api").outcome == "merged"
    assert setup["run"]("discovery:web").outcome == "merged"
    assert "from web" not in (wired.root / "docs/llms.txt").read_text(encoding="utf-8")       # regenerated, not copied


def test_overlapping_edits_block_the_unit_and_leave_main_alone(wired, setup):
    setup["unit"]("discovery:api", {"docs/overview.md": "# Overview\n\napi says this\n"})
    b = setup["unit"]("discovery:web", {"docs/overview.md": "# Overview\n\nweb says that\n"})
    setup["run"]("discovery:api")
    head = git(wired.root, "rev-parse", "HEAD")
    r = setup["run"]("discovery:web")
    assert r.outcome == "conflict" and "docs/overview.md" in r.detail
    assert git(wired.root, "rev-parse", "HEAD") == head and main_changes(wired.root) == []
    assert status(wired, "discovery:web")["status"] == "blocked" and "integrate" in status(wired, "discovery:web")["notes"]
    fix = status(wired, "integrate:discovery:web")
    assert fix["status"] == "todo" and ".cw/" in fix["notes"] and "docs/overview.md" in fix["notes"]
    assert b.path.exists() and git(b.path, "status", "--porcelain") == ""       # the unit's work is kept, committed
    assert ("merge.conflict", {"unit": "discovery:web", "files": ["docs/overview.md"]}) in setup["events"]


def test_policy_never_only_blocks(wired, setup):
    setup["unit"]("discovery:api", {"docs/overview.md": "x\n"})
    setup["unit"]("discovery:web", {"docs/overview.md": "y\n"})
    setup["run"]("discovery:api", policy="never")
    setup["run"]("discovery:web", policy="never")
    assert status(wired, "discovery:web")["status"] == "blocked"
    assert not any(u["id"].startswith("integrate:") for u in wired.plan.load()["units"])


def test_new_gate_errors_block_but_old_ones_do_not(wired, setup):
    calls = []

    def gate(ctx):
        calls.append(ctx.root)
        old = {"docs/legacy.md: broken link"}
        return old | ({"docs/new.md: missing frontmatter"} if (ctx.root / "docs/new.md").exists() else set())
    setup["unit"]("discovery:api", {"docs/fine.md": "ok\n"})
    assert setup["run"]("discovery:api", gates=[("check", gate)]).outcome == "merged"
    setup["unit"]("discovery:web", {"docs/new.md": "no frontmatter\n"})
    head = git(wired.root, "rev-parse", "HEAD")
    r = setup["run"]("discovery:web", gates=[("check", gate)])
    assert r.outcome == "gate-failed" and "docs/new.md: missing frontmatter" in r.detail and "legacy" not in r.detail
    assert git(wired.root, "rev-parse", "HEAD") == head
    assert status(wired, "integrate:discovery:web")["status"] == "todo"


def test_local_changes_in_main_are_never_overwritten(wired, setup):
    setup["unit"]("discovery:api", {"docs/overview.md": "# Overview\n\nfrom the unit\n"})
    (wired.root / "docs/overview.md").write_text("# Overview\n\nsomeone is editing\n", encoding="utf-8")
    r = setup["run"]("discovery:api")
    assert r.outcome == "main-dirty" and "docs/overview.md" in r.detail
    assert (wired.root / "docs/overview.md").read_text(encoding="utf-8") == "# Overview\n\nsomeone is editing\n"
    assert status(wired, "discovery:api")["status"] == "blocked"
    assert not any(u["id"].startswith("integrate:") for u in wired.plan.load()["units"])


def test_a_unit_with_no_changes_just_closes(wired, setup):
    w = setup["unit"]("discovery:api", {})
    assert setup["run"]("discovery:api").outcome == "nothing" and not w.path.exists()


def test_the_units_handoff_is_folded_into_handoff_md(wired, setup):
    setup["unit"]("discovery:api", {"docs/a.md": "a\n"})
    per_unit = setup["integrate"].handoff_file("discovery:api")
    per_unit.parent.mkdir(parents=True, exist_ok=True)
    per_unit.write_text("- Done: api discovered.\n- Pending: nothing.\n", encoding="utf-8")
    setup["run"]("discovery:api")
    text = wired.plan.HANDOFF.read_text(encoding="utf-8")
    assert "## Last session — discovery:api" in text and "api discovered" in text
    assert not per_unit.exists()


def test_integration_never_touches_the_live_plan_in_main(wired, setup):
    setup["unit"]("discovery:api", {"docs/a.md": "a\n", "docs/.work/plan.yaml": "stray copy\n"})
    note = wired.plan.WORK / "units" / "keep.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("uncommitted checkpoint", encoding="utf-8")
    before = wired.plan.PLAN.read_text(encoding="utf-8")
    setup["run"]("discovery:api")
    assert wired.plan.PLAN.read_text(encoding="utf-8") == before and note.read_text(encoding="utf-8") == "uncommitted checkpoint"


def test_plan_state_committed_on_the_branch_never_reaches_main(wired, setup):
    """An older kit can checkpoint the worktree's copy of the plan into the unit's branch: integration drops it."""
    wired.env.checkpoint_commit("plan")
    w = setup["unit"]("discovery:api", {"docs/a.md": "a\n"})
    work = w.path / "docs" / ".work"
    (work / "plan.yaml").write_text("units: []\n", encoding="utf-8")
    (work / "units").mkdir(parents=True, exist_ok=True)
    (work / "units" / "stray.md").write_text("stray", encoding="utf-8")
    git(w.path, "add", "-A")
    git(w.path, "commit", "-qm", "old kit checkpoint")
    live = wired.plan.PLAN.read_text(encoding="utf-8")
    assert setup["run"]("discovery:api").outcome == "merged"
    assert wired.plan.PLAN.read_text(encoding="utf-8") == live and (wired.root / "docs" / "a.md").exists()
    assert not (wired.root / "docs" / ".work" / "units" / "stray.md").exists()
    assert "docs/.work" not in git(wired.root, "diff", "--name-only", "HEAD~1", "HEAD")
