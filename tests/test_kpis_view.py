"""The KPIs tab (S14): one call gathers what the CLI's `kpis` and `stats` print — coverage per repo, freshness, the C4
model's confirmed share, runs by month, usage — plus the questions nobody found an answer to. Those are kept on this
machine only (never in the committed stats), without e-mails or long numbers, and one click turns one into an open
question for the next interview."""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from test_kpis import make_run
from test_mcp_resources import write

NOW = datetime(2026, 10, 20, 11, 0)


def test_a_question_with_no_answer_is_kept_locally_without_personal_data(kit):
    u = kit.usage
    u.record("portal:ask", channel="human", hit=False, query="  Qué base de DATOS usa??  ", now=NOW)
    u.record("portal:ask", channel="human", hit=False, query="qué base de datos usa??", now=NOW)
    u.record("mcp:search", channel="agent", hit=False, query="who owns ana.lopez@acme.com account 4111111111111111",
             now=NOW)
    u.record("portal:ask", channel="human", hit=True, query="checkout flow", now=NOW)
    misses = {m["q"]: m for m in u.misses()}
    assert misses["qué base de datos usa??"]["n"] == 2 and misses["qué base de datos usa??"]["last"] == "2026-10-20"
    assert "who owns … account …" in misses and "checkout flow" not in misses
    committed = "".join(f.read_text(encoding="utf-8") for f in u.DIR.glob("*.json"))
    assert "base de datos" not in committed and "acme" not in committed                # stats stay counters only
    u.set_enabled(False)
    u.record("portal:ask", channel="human", hit=False, query="something else", now=NOW)
    assert "something else" not in {m["q"] for m in u.misses()}


def test_the_list_is_bounded(kit, monkeypatch):
    u = kit.usage
    monkeypatch.setattr(u, "MAX_MISSES", 3)
    for i in range(5):
        u.record("portal:ask", channel="human", hit=False, query=f"question {i}", now=NOW)
    assert [m["q"] for m in u.misses()] == ["question 4", "question 3", "question 2"]


def test_ask_remembers_what_it_could_not_answer(kit):
    from lib import serve
    serve.api_ask("zzqx frobnicate")
    assert "zzqx frobnicate" in {m["q"] for m in kit.usage.misses()}


@pytest.fixture
def project(kit):
    write(kit, "repos/api/brief.md", "---\ntitle: api brief\n---\n# api\n\nThe REST backend.\n")
    write(kit, "repos/web/brief.md", "---\ntitle: web brief\n---\n# web\n\nThe frontend.\n", confirm=False)
    write(kit, "overview.md", "---\ntitle: Overview\n---\n# Overview\n\nThe shop.\n", confirm=False)
    arch = kit.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text("model {\n  a = service 'A' {\n    #confirmed\n  }\n  b = service 'B' {\n"
                                   "    #ai-draft\n  }\n}\n", encoding="utf-8")
    make_run(kit, "r-20261015-100000-1", [("discovery:api", "claude", 60, "ok", 1000, 100, 0.40)], wall=60)
    kit.usage.record("portal:ask", channel="human", hit=False, query="how are refunds made", now=NOW)
    return kit


def test_the_dashboard_has_coverage_per_repo_c4_runs_and_misses(project):
    from lib.harness import kpis
    d = kpis.dashboard(today=date(2026, 10, 20))
    by = {r["repo"]: r for r in d["coverage"]["byRepo"]}
    assert (by["api"]["confirmed"], by["api"]["draft"]) == (1, 0) and (by["web"]["confirmed"], by["web"]["draft"]) == (0, 1)
    assert by["worker"]["pages"] == 0 and by["(project)"]["draft"] >= 1
    assert d["c4"] == {"elements": 2, "confirmed": 1, "draft": 1}
    assert d["runs"][0]["month"] == "2026-10" and d["runs"][0]["done"] == 1
    assert set(d["freshness"]) >= {"fresh", "suspect", "stale", "unverified", "outOfDate"}
    assert d["misses"][0]["q"] == "how are refunds made"
    assert {"pages", "confirmed_pct"} <= set(d["trust"]) and "searches" in d["usefulness"]


def test_a_missed_question_becomes_an_open_question(project):
    from lib import serve
    r = serve.kpis_miss({"q": "how are refunds made", "action": "question"})
    text = (project.root / "docs" / "interview" / "open-questions.md").read_text(encoding="utf-8")
    assert "how are refunds made" in text and "docs-gap" in text and r["misses"] == []
    project.usage.record("portal:ask", channel="human", hit=False, query="what is a pet", now=NOW)
    assert serve.kpis_miss({"q": "what is a pet", "action": "dismiss"})["misses"] == []
    with pytest.raises(KeyError):
        serve.kpis_miss({"q": "never asked", "action": "question"})


def test_the_portal_serves_it(project):
    import threading, urllib.request
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), project.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/kpis", timeout=30) as r:
            d = json.loads(r.read())
        assert d["c4"]["elements"] == 2 and d["misses"]
    finally:
        srv.shutdown()
