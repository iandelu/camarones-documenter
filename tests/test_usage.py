"""Team usage stats: counters per person and machine in docs/.work/usage (travel with `share`), recorded by the MCP
server, the live portal, the CLI and the wizard, and summed up by `stats` into adoption, usage and health KPIs."""
from __future__ import annotations

import importlib, json
from datetime import date, datetime

import pytest

from test_team_repo import bare, cli, git, remote_files


def page(kit, rel: str, title: str, body: str = "") -> None:
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {title}\n---\n# {title}\n\n{body}\n", encoding="utf-8", newline="\n")


def files(kit) -> list:
    return sorted(kit.usage.DIR.glob("*.json"))


def month(kit, key: str = "2026-10") -> dict:
    (f,) = files(kit)
    return json.loads(f.read_text(encoding="utf-8"))["months"][key]


NOW = datetime(2026, 10, 2, 11, 0)


# ---------- recording ----------
def test_recording_is_on_until_someone_declines(kit):
    assert not kit.usage.decided() and kit.usage.enabled()
    kit.usage.record("cli:check", now=NOW)
    assert month(kit)["events"] == {"cli:check": 1}


def test_counts_events_days_searches_and_pages_per_channel(kit):
    rec = kit.usage.record
    rec("mcp:search_docs", channel="agent", hit=True, now=NOW)
    rec("mcp:search_docs", channel="agent", hit=False, now=NOW)
    rec("portal:doc", channel="human", page="docs/flows/checkout.md", now=datetime(2026, 10, 3, 9))
    rec("portal:doc", channel="human", page="flows/checkout.md", now=datetime(2026, 10, 3, 10))
    rec("cli:check", now=datetime(2026, 11, 1))
    m = month(kit)
    assert m["events"] == {"mcp:search_docs": 2, "portal:doc": 2}
    assert m["days"] == {"2026-10-02": 2, "2026-10-03": 2}
    assert m["searches"] == {"agent": {"hit": 1, "miss": 1}}
    assert m["pages"] == {"human": {"flows/checkout.md": 2}}
    assert month(kit, "2026-11")["events"] == {"cli:check": 1}


def test_declined_records_nothing_and_the_choice_is_per_machine(kit):
    kit.usage.set_enabled(False)
    kit.usage.record("cli:check", now=NOW)
    assert kit.usage.decided() and not files(kit)
    assert kit.usage.SETTING.is_relative_to(kit.common.CACHE)


def test_the_file_is_pseudonymous_and_per_machine(kit, monkeypatch):
    kit.usage.record("cli:check", now=NOW)
    kit.usage.me.cache_clear()
    monkeypatch.setattr(kit.usage.platform, "node", lambda: "other-laptop")
    kit.usage.record("cli:check", now=NOW)
    names = [f.name for f in files(kit)]
    assert len(names) == 2 and len({n.split("-")[0] for n in names}) == 1
    assert all("test@example.com" not in f.read_text(encoding="utf-8") and "example" not in f.name for f in files(kit))


def test_recording_never_breaks_the_tool(kit):
    kit.usage.DIR.mkdir(parents=True)
    (kit.usage.DIR / f"{kit.usage.me()}.json").write_text("[not, json", encoding="utf-8")
    kit.usage.record("cli:check", now=NOW)                               # corrupt file: starts again
    assert month(kit)["events"] == {"cli:check": 1}
    kit.common.WS_FILE.unlink()
    kit.usage.record("cli:check", now=NOW)                               # not a project (uninstalled): no-op
    assert month(kit)["events"] == {"cli:check": 1}


def test_stats_travel_with_share(kit, tmp_path):
    kit.env.init_templates("demo", log=lambda _: None)
    remote = bare(tmp_path)
    kit.env.set_remote(str(remote))
    kit.usage.record("cli:check", now=NOW)
    assert kit.env.share(log=lambda _: None)["status"] == "pushed"
    assert f"docs/.work/usage/{kit.usage.me()}.json" in remote_files(remote)


# ---------- where it is recorded ----------
def test_mcp_records_agent_searches_and_reads(kit):
    page(kit, "flows/checkout.md", "Checkout", "Pay with the card gateway.")
    mcp = importlib.import_module("lib.mcp")
    for name, args in (("search_docs", {"query": "gateway"}), ("search_docs", {"query": "kafka"}),
                       ("read_doc", {"path": "docs/flows/checkout.md"}), ("read_doc", {"path": "nope.md"}),
                       ("list_docs", {})):
        mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    (f,) = files(kit)
    m = next(iter(json.loads(f.read_text(encoding="utf-8"))["months"].values()))
    assert m["events"] == {"mcp:search_docs": 2, "mcp:read_doc": 2, "mcp:list_docs": 1}
    assert m["searches"] == {"agent": {"hit": 1, "miss": 1}}
    assert m["pages"] == {"agent": {"flows/checkout.md": 1}}


def test_portal_records_only_what_the_reader_asked_for(kit):
    page(kit, "flows/checkout.md", "Checkout", "Pay with the card gateway.")
    serve = importlib.import_module("lib.serve")
    serve.api_search({"q": "gate"})                                      # palette, as you type: not counted
    serve.api_doc({"path": "flows/checkout.md"})
    assert not files(kit)
    assert serve.api_search({"q": "gateway", "track": "1"})
    serve.api_search({"q": "kafka", "track": "1"})
    serve.api_doc({"path": "flows/checkout.md", "track": "1"})
    (f,) = files(kit)
    m = next(iter(json.loads(f.read_text(encoding="utf-8"))["months"].values()))
    assert m["searches"] == {"human": {"hit": 1, "miss": 1}}
    assert m["pages"] == {"human": {"flows/checkout.md": 1}}


def test_cli_records_the_command_and_toggles_recording(kit):
    kit.env.init_templates("demo", log=lambda _: None)
    assert cli(kit.root, kit.ws, "status").returncode == 0
    assert "cli:status" in month(kit, datetime.now().strftime("%Y-%m"))["events"]
    r = cli(kit.root, kit.ws, "stats", "--record", "off")
    assert r.returncode == 0 and "usage stats: off" in r.stdout, r.stdout + r.stderr
    assert not kit.usage.enabled()


# ---------- the report ----------
def seed_team(kit) -> None:
    """Three people, two months: one agent-heavy, one portal reader, one who only ran the CLI last month."""
    kit.usage.DIR.mkdir(parents=True)
    people = {
        "aaaaaaaaaa-111111": {"2026-10": {"days": {"2026-10-01": 5, "2026-10-02": 3}, "events": {"mcp:search_docs": 6, "mcp:read_doc": 2},
                                          "searches": {"agent": {"hit": 5, "miss": 1}}, "pages": {"agent": {"flows/checkout.md": 2}}}},
        "aaaaaaaaaa-222222": {"2026-10": {"days": {"2026-10-02": 1}, "events": {"cli:check": 1}}},     # same person, laptop 2
        "bbbbbbbbbb-333333": {"2026-10": {"days": {"2026-10-02": 4}, "events": {"portal:search": 2, "portal:doc": 2},
                                          "searches": {"human": {"hit": 1, "miss": 1}},
                                          "pages": {"human": {"flows/checkout.md": 1, "overview.md": 1}}}},
        "cccccccccc-444444": {"2026-09": {"days": {"2026-09-20": 1}, "events": {"wizard:next": 1}}},
    }
    for stem, months in people.items():
        kit.common.save_json(kit.usage.DIR / f"{stem}.json", {"v": 1, "months": months})


def test_report_sums_the_team(kit):
    page(kit, "flows/checkout.md", "Checkout")
    page(kit, "overview.md", "Overview")
    page(kit, "domain/glossary.md", "Glossary")
    seed_team(kit)
    r = kit.usage.report(months=2, today=date(2026, 10, 15))
    oct_, sep = r["months"]
    assert (oct_["month"], sep["month"]) == ("2026-10", "2026-09")
    assert oct_["people"] == 2 and sep["people"] == 1 and r["people"] == 3
    assert oct_["active_days"] == 3                                      # (a, 1st) (a, 2nd) (b, 2nd)
    assert (oct_["agent_queries"], oct_["human_queries"]) == (8, 4)
    assert oct_["searches"] == 8 and oct_["no_results_pct"] == 25
    assert r["top_pages"][0] == {"path": "flows/checkout.md", "reads": 3, "agent": 2, "human": 1}
    assert r["unread_pages"] == ["domain/glossary.md"]
    assert r["top_features"][0] == {"event": "mcp:search_docs", "count": 6}
    assert r["health"]["pages"] == 3 and r["health"]["confirmed_pct"] == 0


def test_report_on_a_project_without_stats(kit):
    r = kit.usage.report(today=date(2026, 10, 15))
    assert r["people"] == 0 and r["top_pages"] == [] and len(r["months"]) == 3


def test_cli_stats_json_and_markdown(kit):
    kit.env.init_templates("demo", log=lambda _: None)
    page(kit, "flows/checkout.md", "Checkout")
    seed_team(kit)
    r = cli(kit.root, kit.ws, "stats", "--json", "--months", "12")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["people"] == 4                         # the three seeded + whoever ran it
    r = cli(kit.root, kit.ws, "stats")
    assert r.returncode == 0 and "| Month |" in r.stdout and "flows/checkout.md" in r.stdout, r.stdout + r.stderr


def test_doc_changes_count_people_writing_but_not_the_stats_themselves(kit):
    kit.env.init_templates("demo", log=lambda _: None)
    page(kit, "overview.md", "Overview")
    kit.env.checkpoint_commit("overview")
    base = kit.usage.report(months=1)["months"][0]["doc_commits"]
    kit.usage.record("cli:check")
    kit.env.checkpoint_commit("stats only")
    r = kit.usage.report(months=1)["months"][0]
    assert base >= 1 and r["doc_commits"] == base and r["writers"] == 1


# ---------- wizard ----------
def test_setup_asks_once(kit, fake_wizard):
    w = fake_wizard([False])
    w.ask_usage()
    assert kit.usage.decided() and not kit.usage.enabled()
    fake_wizard([]).ask_usage()                                          # decided: not asked again
    assert "us_ask" in kit.wizard.T["es"] and "us_ask" in kit.wizard.T["en"]


def test_an_upgraded_project_is_told_once_and_records(kit, fake_wizard):
    w = fake_wizard([])
    said = []
    w.say = lambda msg, *_a: said.append(str(msg))
    w.usage_notice()
    w.usage_notice()
    assert kit.usage.enabled() and kit.usage.decided() and len(said) == 1


def test_wizard_stats_view_and_toggle(kit, fake_wizard):
    seed_team(kit)
    w = fake_wizard(["toggle", None])
    w.paged = lambda *_a: None
    w.do_stats()
    assert not kit.usage.enabled()
