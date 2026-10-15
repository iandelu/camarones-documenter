"""A/B with vs without cam-docs (R19): the same question, once through the docs and once with only the code, in a
throwaway folder that links the repos and nothing else (no cam-docs, no AGENTS.md, no MCP). Tokens, time, tool calls
and how many exact identifiers each answer names are compared and kept for the team."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest

from fixtures.builder import snapshot


@pytest.fixture
def ab(kit):
    from lib.harness import ab
    return ab


@pytest.fixture
def fake_ask(kit, monkeypatch):
    """Answers as if the docs saved tokens: the docs variant is cheaper and names the identifier."""
    from lib.harness import evals
    seen = []

    def ask(target, req):
        docs = any("camarones" in t for t in req.allow_tools or ())
        seen.append({"docs": docs, "cwd": req.cwd, "stream": req.stream, "tools": req.allow_tools, "prompt": req.prompt})
        answer = {"answer": "POST /refunds" if docs else "some endpoint", "cited": ["flows/refund.md"] if docs else []}
        return {"lines": [json.dumps(answer)], "seconds": 10.0 if docs else 40.0, "rc": 0,
                "tokens_in": 1000 if docs else 9000, "tokens_out": 100 if docs else 300,
                "cost_usd": 0.1 if docs else 0.5, "tool_calls": 2 if docs else 14}
    monkeypatch.setattr(evals, "_ask", ask)
    return seen


QUESTION = {"id": "refund", "q": "How is a refund processed?", "expect": ["flows/refund.md"], "mention": ["POST /refunds"]}


def test_both_variants_are_asked_and_compared(kit, ab, fake_ask):
    r = ab.run([QUESTION], "claude", echo=lambda _: None)
    row = r["questions"][0]
    assert row["with"]["tokens_in"] == 1000 and row["without"]["tokens_in"] == 9000
    assert row["with"]["mentions"] == 1.0 and row["without"]["mentions"] == 0.0
    assert r["delta"]["tokens_in"] == -8000 and r["delta"]["seconds"] == -30.0 and r["delta"]["tool_calls"] == -12
    assert r["tokens_saved_pct"] == pytest.approx(88.9, abs=0.1)
    saved = list((kit.root / "docs" / ".work" / "evals" / "ab").glob("*.json"))
    assert len(saved) == 1 and ab.latest()["tokens_saved_pct"] == r["tokens_saved_pct"]


def test_the_control_sees_the_repos_and_nothing_of_cam_docs(kit, ab, fake_ask):
    ab.run([QUESTION], "claude", echo=lambda _: None)
    with_docs, control = (next(s for s in fake_ask if s["docs"] == d) for d in (True, False))
    assert with_docs["cwd"] == kit.common.WORKSPACE and control["cwd"] != kit.common.WORKSPACE
    assert control["tools"] and not any("mcp" in t for t in control["tools"]) and "Edit" not in control["tools"]
    assert "source code" in control["prompt"] and "camarones" not in control["prompt"]
    assert with_docs["stream"] and control["stream"]                     # usage is only reported when streaming


def test_the_control_folder_links_only_the_repos_and_is_removed(kit, ab):
    before = {r: snapshot(kit.ws / r) for r in ("api", "web", "worker")}
    with ab.control_workspace() as tmp:
        assert kit.root.resolve() not in tmp.resolve().parents and kit.ws.resolve() not in tmp.resolve().parents
        assert sorted(p.name for p in tmp.iterdir()) == ["api", "web", "worker"]
        assert (tmp / "api" / "pom.xml").read_text(encoding="utf-8").startswith("<project>")
        assert not any((tmp / n).exists() for n in ("cam-docs", "AGENTS.md", "CLAUDE.md", ".mcp.json", ".claude"))
    assert not tmp.exists()
    assert {r: snapshot(kit.ws / r) for r in ("api", "web", "worker")} == before        # repos untouched


def test_a_free_question_has_no_answer_key(kit, ab, fake_ask):
    r = ab.run([{"id": "qa", "q": "How is a refund processed?"}], "claude", echo=lambda _: None)
    assert r["questions"][0]["with"]["mentions"] is None and r["delta"]["tokens_in"] == -8000


def test_the_team_can_turn_ab_off(kit, ab, fake_ask):
    ws = kit.docs.workspace()
    ws["ab"] = {"enabled": False}
    kit.docs.save_workspace(ws)
    assert not ab.enabled()
    with pytest.raises(RuntimeError, match="ab.enabled"):
        ab.run([QUESTION], "claude", echo=lambda _: None)
    assert fake_ask == []


def test_streaming_read_only_runs_report_usage(kit, monkeypatch):
    from lib.adapters import runners
    from lib.adapters.runners import base
    from lib.harness.ports import RunRequest
    monkeypatch.setattr(base, "which", lambda name: f"/bin/{name}")
    req = RunRequest(prompt="p", cwd=kit.ws, allow_tools=("Read",), stream=True)
    assert runners.get("claude").build(req).argv[-3:] == ["--output-format", "stream-json", "--verbose"]
    assert "--json" in runners.get("codex").build(req).argv
    plain = RunRequest(prompt="p", cwd=kit.ws, allow_tools=("Read",))
    assert "--output-format" not in runners.get("claude").build(plain).argv            # OpenWiki's command unchanged


def test_kpis_show_the_last_comparison(kit, ab, fake_ask):
    ab.run([QUESTION], "claude", echo=lambda _: None)
    from lib.harness import kpis
    last = kpis.report(run_check=False)["usefulness"]["ab"]
    assert last["tokens_saved_pct"] == pytest.approx(88.9, abs=0.1) and last["questions"] == 1


def test_the_ab_command_needs_a_question(kit):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "ab"], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 2 and "--qa" in r.stderr
