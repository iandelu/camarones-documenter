"""AI drafts vs what people confirm (R18): when a unit is done the kit keeps a copy of the AI-written pages; when a
person confirms one, the share of words they changed is recorded. 0 = confirmed as written, 1 = rewritten. A cheap,
honest signal of draft quality, shared through docs/.work/ai-drafts.json."""
from __future__ import annotations

import json

import pytest

WORDS = " ".join(f"word{i}" for i in range(20))


def page(kit, rel, body, owner=None):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\ntitle: {rel}\n" + (f"x-owner: {owner}\n" if owner else "") + "---\n"
    f.write_text(fm + body + "\n", encoding="utf-8")
    return f


@pytest.fixture
def drafts(kit):
    from lib.harness import drafts
    kit.plan.sync()
    return drafts


def test_done_snapshots_ai_drafts_but_not_human_pages(kit, drafts):
    page(kit, "flows/checkout.md", WORDS)
    page(kit, "overview/notes.md", "written by a person", owner="human")
    kit.plan.set_status("discovery:api", "done")
    snap = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]
    assert set(snap) == {"flows/checkout.md"} and snap["flows/checkout.md"]["unit"] == "discovery:api"


def test_confirming_after_a_ten_percent_edit_records_about_point_one(kit, drafts):
    f = page(kit, "flows/checkout.md", WORDS)
    kit.plan.set_status("discovery:api", "done")
    f.write_text(f.read_text(encoding="utf-8").replace("word3 word4", "changed3 changed4"), encoding="utf-8")
    kit.docs.confirm([str(f)], by="ana")
    c = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]["flows/checkout.md"]["confirmations"][-1]
    assert c["by"] == "ana" and c["edit"] == pytest.approx(0.1, abs=0.01)
    entry = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]["flows/checkout.md"]
    assert entry["body"] == ""                                   # no page copies kept once confirmed
    kit.docs.confirm([str(f)], by="ana")                          # confirming again measures nothing new
    assert len(json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]["flows/checkout.md"]["confirmations"]) == 1


def test_confirming_untouched_draft_records_zero_and_unknown_pages_nothing(kit, drafts):
    f = page(kit, "flows/checkout.md", WORDS)
    kit.plan.set_status("discovery:api", "done")
    g = page(kit, "flows/manual.md", "never seen by the kit")
    kit.docs.confirm([str(f), str(g)], by="ana")
    pages = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]
    assert pages["flows/checkout.md"]["confirmations"][-1]["edit"] == 0.0 and "flows/manual.md" not in pages


def test_a_redrafted_page_replaces_its_snapshot(kit, drafts):
    f = page(kit, "flows/checkout.md", WORDS)
    kit.plan.set_status("discovery:api", "done")
    page(kit, "flows/checkout.md", WORDS + " more")
    kit.plan.set_status("discovery:web", "done")
    snap = json.loads(drafts.FILE.read_text(encoding="utf-8"))["pages"]["flows/checkout.md"]
    assert snap["unit"] == "discovery:web" and snap["body"].rstrip().endswith("more")


def test_kpis_report_the_average_edit(kit, drafts):
    f = page(kit, "flows/checkout.md", WORDS)
    g = page(kit, "flows/refund.md", WORDS)
    kit.plan.set_status("discovery:api", "done")
    f.write_text(f.read_text(encoding="utf-8").replace("word3 word4", "changed3 changed4"), encoding="utf-8")
    kit.docs.confirm([str(f), str(g)], by="ana")
    from lib.harness import kpis
    t = kpis.report(run_check=False)["trust"]
    assert t["ai_pages_confirmed"] == 2 and t["ai_edit_avg"] == pytest.approx(0.05, abs=0.01)
