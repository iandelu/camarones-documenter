"""Project health snapshot: coverage read from the reports a repo already holds (JaCoCo, lcov, Cobertura)."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

JACOCO = ('<?xml version="1.0" encoding="UTF-8"?><report name="app">'
          '<package name="a"><counter type="LINE" missed="5" covered="5"/></package>'
          '<counter type="LINE" missed="20" covered="80"/></report>\n')


def put(repo: Path, rel: str, text: str, mtime: float | None = None) -> Path:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(f, (mtime, mtime))
    return f


def test_jacoco_report_level_line_counter(tmp_path):
    from lib import health
    put(tmp_path, "target/site/jacoco/jacoco.xml", JACOCO)
    [r] = health.coverage_reports(tmp_path)
    assert (r["type"], r["percent"], r["path"]) == ("jacoco", 80.0, "target/site/jacoco/jacoco.xml")
    assert r["at"]


def test_lcov_sums_every_file(tmp_path):
    from lib import health
    put(tmp_path, "coverage/app/lcov.info", "SF:a.js\nLF:10\nLH:5\nend_of_record\nSF:b.js\nLF:30\nLH:25\nend_of_record\n")
    [r] = health.coverage_reports(tmp_path)
    assert (r["type"], r["percent"], r["path"]) == ("lcov", 75.0, "coverage/app/lcov.info")


def test_cobertura_line_rate(tmp_path):
    from lib import health
    put(tmp_path, "coverage/cobertura-coverage.xml", '<coverage line-rate="0.6234" branch-rate="0"></coverage>\n')
    [r] = health.coverage_reports(tmp_path)
    assert (r["type"], r["percent"]) == ("cobertura", 62.3)


def test_reports_outside_the_known_paths_are_ignored(tmp_path):
    from lib import health
    put(tmp_path, "src/jacoco.xml", JACOCO)
    assert health.coverage_reports(tmp_path) == []


def test_hostile_or_huge_reports_are_skipped(tmp_path):
    from lib import health
    body = JACOCO.split("?>", 1)[1]
    put(tmp_path, "target/site/jacoco/jacoco.xml", '<?xml version="1.0"?><!DOCTYPE report [<!ENTITY x "y">]>' + body)
    put(tmp_path, "build/reports/jacoco/test/huge.xml", JACOCO + "<!--" + " " * health.MAX_REPORT_BYTES + "-->")
    put(tmp_path, "build/reports/jacoco/test/cut.xml", "<report><counter type=")
    put(tmp_path, "coverage/lcov.info", "LF:4\nLH:1\n")
    reports = {r["path"]: r for r in health.coverage_reports(tmp_path)}
    assert len(reports) == 4
    assert reports["target/site/jacoco/jacoco.xml"]["error"] == "DTD or entity declarations are not accepted"
    assert reports["build/reports/jacoco/test/huge.xml"]["error"] == f"larger than {health.MAX_REPORT_BYTES} bytes"
    assert reports["build/reports/jacoco/test/cut.xml"]["error"] and "percent" not in reports["build/reports/jacoco/test/cut.xml"]
    assert reports["coverage/lcov.info"]["percent"] == 25.0


REAL_DOCTYPE = '<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">'


def test_a_real_jacoco_report_with_its_public_doctype_parses(tmp_path):
    from lib import health
    put(tmp_path, "target/site/jacoco/jacoco.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + REAL_DOCTYPE + JACOCO.split("?>", 1)[1])
    [r] = health.coverage_reports(tmp_path)
    assert r["percent"] == 80.0


def test_the_external_dtd_a_report_names_is_never_read(tmp_path):
    from lib import health
    put(tmp_path, "target/site/jacoco/report.dtd", '<!ENTITY x "20">')
    body = JACOCO.split("?>", 1)[1].replace('missed="20"', 'missed="&x;"')
    put(tmp_path, "target/site/jacoco/jacoco.xml", '<?xml version="1.0"?>' + REAL_DOCTYPE + body)
    [r] = health.coverage_reports(tmp_path)
    assert "percent" not in r and r["error"]


def test_a_utf16_document_cannot_hide_its_doctype(tmp_path):
    from lib import health
    text = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE report [<!ENTITY x "y">]>' + JACOCO.split("?>", 1)[1]
    (tmp_path / "target/site/jacoco").mkdir(parents=True)
    (tmp_path / "target/site/jacoco/jacoco.xml").write_bytes(text.encode("utf-16"))
    (tmp_path / "build/reports/jacoco").mkdir(parents=True)
    (tmp_path / "build/reports/jacoco/le.xml").write_bytes(text.encode("utf-16-le"))
    reports = health.coverage_reports(tmp_path)
    assert [r.get("error") for r in reports] == ["not UTF-8 text"] * 2


def test_impossible_percentages_are_errors(tmp_path):
    from lib import health
    put(tmp_path, "coverage/a/cobertura-nan.xml", '<coverage line-rate="nan"></coverage>')
    put(tmp_path, "coverage/b/cobertura-inf.xml", '<coverage line-rate="inf"></coverage>')
    put(tmp_path, "coverage/c/cobertura-high.xml", '<coverage line-rate="1.5"></coverage>')
    put(tmp_path, "coverage/d/lcov.info", "LF:10\nLH:12\n")
    put(tmp_path, "coverage/e/lcov.info", "LF:10\nLH:-2\n")
    reports = health.coverage_reports(tmp_path)
    assert len(reports) == 5
    assert all("error" in r and "percent" not in r for r in reports)
    assert health.repo_coverage(reports) is None


def test_repo_coverage_takes_the_newest_good_report(tmp_path):
    from lib import health
    put(tmp_path, "target/site/jacoco/jacoco.xml", JACOCO, mtime=1_700_000_000)
    put(tmp_path, "coverage/lcov.info", "LF:oops", mtime=1_700_100_000)
    reports = health.coverage_reports(tmp_path)
    assert reports[0]["path"] == "coverage/lcov.info" and "error" in reports[0]
    cov = health.repo_coverage(reports)
    assert cov["percent"] == 80.0 and cov["source"] == "report" and cov["path"] == "target/site/jacoco/jacoco.xml"
    assert cov["at"] == reports[1]["at"]
    assert health.repo_coverage([]) is None
    assert health.repo_coverage([reports[0]]) is None


# ---- technical debt from the quality pages ----

def quality_page(kit, name, body):
    f = kit.root / "docs" / "quality" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {name}\n---\n{body}", encoding="utf-8")
    return f


def test_debt_rows_go_to_the_repos_their_evidence_names(kit):
    from lib import health
    quality_page(kit, "tech-debt.md", "# Technical debt\n\n## Items\n\n"
                 "| Item | Impact | Evidence | Owner |\n|---|---|---|---|\n"
                 "| Legacy DAO | High: slow queries | `api:src/A.java` | Ana |\n"
                 "| Shared client | media | `api:x`, `web:y` | Luis |\n")
    got = health.debt_items(["api", "web", "worker"])
    assert set(got) == {"api", "web", "worker", "_project"}
    assert [i["item"] for i in got["api"]] == ["Legacy DAO", "Shared client"]
    assert [i["item"] for i in got["web"]] == ["Shared client"]
    assert got["worker"] == [] and got["_project"] == []
    first, second = got["api"]
    assert (first["impact"], second["impact"]) == ("high", "medium")
    assert first == {"source": "quality/tech-debt.md", "trust": "draft", "item": "Legacy DAO", "impact": "high",
                     "effort": "", "evidence": ["api:src/A.java"], "owner": "Ana", "recommendation": ""}
    assert second["evidence"] == ["api:x", "web:y"] and second["owner"] == "Luis"


def test_architecture_review_columns(kit):
    from lib import health
    quality_page(kit, "architecture-review.md", "# Architecture review\n\n"
                 "| Area | Impact | Estimated effort | Evidence | Recommendation |\n|---|---|---|---|---|\n"
                 "| Messaging | Low | 2 weeks | `worker:worker/main.py` | Split the queue |\n")
    [item] = health.debt_items(["api", "web", "worker"])["worker"]
    assert item["source"] == "quality/architecture-review.md" and item["trust"] == "draft"
    assert (item["item"], item["impact"], item["effort"]) == ("Messaging", "low", "2 weeks")
    assert item["evidence"] == ["worker:worker/main.py"] and item["recommendation"] == "Split the queue"
    assert item["owner"] == ""


def test_spanish_headers_extra_columns_and_the_skeleton(kit):
    from lib import health
    quality_page(kit, "tech-debt.md", "# Deuda técnica\n\n> **TL;DR:** x\n\n## Items\n\n"
                 "| Elemento | Impacto | Evidencia | Responsable | Notas |\n|---|---|---|---|---|\n"
                 "| <what> | <high/medium/low and why> | `<repo>:<path>` | <team or person> | – |\n"
                 "| Cola lenta | Alto, bloquea | `api:q` | Eva | no tocar \\| ver wiki |\n"
                 "| Sin dueño | Baja | `web:z` | | |\n")
    got = health.debt_items(["api", "web"])
    [a] = got["api"]
    assert (a["item"], a["impact"], a["owner"], a["evidence"]) == ("Cola lenta", "high", "Eva", ["api:q"])
    assert "Notas" not in a and "no tocar" not in str(a)
    [w] = got["web"]
    assert (w["item"], w["impact"], w["owner"]) == ("Sin dueño", "low", "")
    assert got["_project"] == []                 # the skeleton row is no item


def test_rows_naming_no_known_repo_are_project_level(kit):
    from lib import health
    quality_page(kit, "tech-debt.md", "# Debt\n\n## Items\n\n| Item | Impact | Evidence | Owner |\n|---|---|---|---|\n"
                 "| No CI | high | none | Ana |\n| Old repo | low | `gone:src/a` | Ana |\n| Odd impact | tbd | | |\n")
    got = health.debt_items(["api", "web"])
    assert got["api"] == [] and got["web"] == []
    assert [(i["item"], i["impact"]) for i in got["_project"]] == [("No CI", "high"), ("Old repo", "low"), ("Odd impact", "unknown")]


def test_no_quality_pages_means_no_debt(kit):
    from lib import health
    assert health.debt_items(["api", "web"]) == {"api": [], "web": [], "_project": []}


def test_debt_trust_follows_the_page(kit):
    from lib import health
    f = quality_page(kit, "tech-debt.md", "# Debt\n\n## Items\n\n| Item | Impact | Evidence |\n|---|---|---|\n| A | high | `api:x` |\n")
    kit.docs.confirm([str(f)], by="ana")
    assert health.debt_items(["api"])["api"][0]["trust"] == "confirmed"


# ---- the snapshot: state rules, build, load ----

import copy
import json
from datetime import date

TODAY = date(2026, 10, 26)
API = "src/main/java/demo/Api.java"          # 5 lines in the fixture repo


def repo_block(**over):
    return {"cloned": True, "libraries": 3, "vulns": {}, "vulnerable": [],
            "sonar": {"used": False, "project": "", "organization": "", "host": "", "link": ""},
            "coverage": None, "reports": [], "debt": [], **over}


def clean_snapshot():
    return {"v": 1, "at": "2026-10-26T08:00:00Z",
            "machine": {"at": "2026-10-26T08:00:00Z", "missing": [], "drift": 0, "tools": 6},
            "docs": {"at": "2026-10-26T08:00:00Z", "stale": [], "suspect": [], "evals": {"total": 3, "confirmed": 2},
                     "context": {"total": 100, "budget": 500, "over": False}, "review": 0},
            "inventory": {"at": "2026-10-20T00:00:00Z", "scanned": True},
            "repos": {"api": repo_block(), "web": repo_block()}, "debt_project": []}


def vuln(sev):
    return {"name": "lib", "version": "1.0", "severity": sev, "id": "GHSA-1", "cve": "CVE-1", "fixed": "1.1"}


def mutated(fn):
    s = clean_snapshot()
    fn(s)
    return s


def set_(path, value):
    def apply(s):
        node = s
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
    return apply


def debt(impact):
    return {"source": "quality/tech-debt.md", "trust": "draft", "item": "x", "impact": impact, "effort": "",
            "evidence": [], "owner": "", "recommendation": ""}


COV = {"at": "x", "source": "report", "path": "p"}
CASES = [
    # (name, change, area, state, first reason)
    ("tool missing", set_(["machine", "missing"], ["git"]), "machine", "bad", "machine.missing"),
    ("drift only", set_(["machine", "drift"], 2), "machine", "warn", "machine.drift"),
    ("never checked", set_(["machine"], {"error": "boom"}), "machine", "warn", "machine.unchecked"),
    ("stale page", set_(["docs", "stale"], [{"path": "a.md", "repos": ["api"]}]), "docs", "bad", "docs.stale"),
    ("suspect page", set_(["docs", "suspect"], [{"path": "a.md", "repos": []}]), "docs", "warn", "docs.suspect"),
    ("over budget", set_(["docs", "context"], {"total": 900, "budget": 500, "over": True}), "docs", "warn", "docs.context"),
    ("no confirmed question", set_(["docs", "evals"], {"total": 3, "confirmed": 0}), "docs", "warn", "docs.noEvals"),
    ("waiting for review", set_(["docs", "review"], 4), "docs", "warn", "docs.review"),
    ("high vulnerability", set_(["repos", "api", "vulnerable"], [vuln("high")]), "code", "bad", "code.vulnHigh"),
    ("critical vulnerability", set_(["repos", "api", "vulnerable"], [vuln("critical")]), "code", "bad", "code.vulnHigh"),
    ("medium vulnerability", set_(["repos", "api", "vulnerable"], [vuln("medium")]), "code", "warn", "code.vulnMedium"),
    ("never scanned", set_(["inventory"], {"at": None, "scanned": False}), "code", "warn", "code.noScan"),
    ("scan 31 days old", set_(["inventory", "at"], "2026-09-25T10:00:00Z"), "code", "warn", "code.oldScan"),
    ("coverage 49.9", set_(["repos", "api", "coverage"], {"percent": 49.9, **COV}), "code", "warn", "code.lowCoverage"),
    ("high debt", set_(["repos", "web", "debt"], [debt("high")]), "code", "warn", "code.highDebt"),
    ("high project debt", set_(["debt_project"], [debt("high")]), "code", "warn", "code.highDebt"),
]
OKS = [
    ("scan 30 days old", set_(["inventory", "at"], "2026-09-26T10:00:00Z")),
    ("coverage 50.0", set_(["repos", "api", "coverage"], {"percent": 50.0, **COV})),
    ("low debt", set_(["repos", "web", "debt"], [debt("low"), debt("unknown")])),
    ("repo not cloned", set_(["repos", "api"], repo_block(cloned=False, libraries=0))),
]


@pytest.mark.parametrize("name,change,area,state,key", CASES, ids=[c[0] for c in CASES])
def test_areas_follow_the_rules(name, change, area, state, key):
    from lib import health
    got = health.areas(mutated(change), today=TODAY)
    assert got["areas"][area]["state"] == state
    assert got["areas"][area]["next"]["key"] == key
    assert all(v["state"] == "ok" for k, v in got["areas"].items() if k != area)
    assert got["verdict"][0]["key"] == key


@pytest.mark.parametrize("name,change", OKS, ids=[c[0] for c in OKS])
def test_areas_stay_ok_at_the_limit(name, change):
    from lib import health
    got = health.areas(mutated(change), today=TODAY)
    assert {v["state"] for v in got["areas"].values()} == {"ok"} and got["verdict"] == []


def test_all_clean_is_three_ok_and_no_verdict():
    from lib import health
    got = health.areas(clean_snapshot(), today=TODAY)
    assert {k: v["state"] for k, v in got["areas"].items()} == {"machine": "ok", "docs": "ok", "code": "ok"}
    assert got["verdict"] == [] and got["repo_state"] == {"api": "ok", "web": "ok"}
    assert all(v["next"] is None for v in got["areas"].values())


def test_figures_are_the_areas_two_key_numbers():
    from lib import health
    s = clean_snapshot()
    s["machine"].update(missing=["git", "node"])
    s["docs"].update(stale=[{"path": "a.md", "repos": []}], review=3)
    s["repos"]["api"].update(libraries=10, vulns={"critical": 1, "high": 2, "medium": 1},
                             vulnerable=[vuln("critical"), vuln("high"), vuln("high"), vuln("medium")])
    s["repos"]["web"]["libraries"] = 5
    a = health.areas(s, today=TODAY)["areas"]
    assert a["machine"]["figures"] == [{"key": "machine.tools", "n": 6}, {"key": "machine.missing", "n": 2}]
    assert a["docs"]["figures"] == [{"key": "docs.stale", "n": 1}, {"key": "docs.review", "n": 3}]
    assert a["code"]["figures"] == [{"key": "code.libraries", "n": 15}, {"key": "code.vulnHigh", "n": 3}]


def test_next_action_is_the_first_reason():
    from lib import health
    s = clean_snapshot()
    s["docs"].update(stale=[{"path": "a.md", "repos": ["api"]}], review=2)
    assert health.areas(s, today=TODAY)["areas"]["docs"]["next"] == {"key": "docs.stale", "row": "fresh"}
    s["docs"]["stale"] = []
    assert health.areas(s, today=TODAY)["areas"]["docs"]["next"] == {"key": "docs.review", "row": "review"}


def test_every_reason_points_at_its_row():
    from lib import health
    assert health.ROWS == {
        "machine.missing": "doctor", "machine.unchecked": "doctor", "machine.drift": "drift", "docs.stale": "fresh",
        "docs.suspect": "fresh", "docs.context": "context", "docs.noEvals": "evals", "docs.review": "review",
        "code.vulnHigh": "libs", "code.gateFailed": "repos", "code.vulnMedium": "libs", "code.noScan": "libs",
        "code.oldScan": "libs", "code.lowCoverage": "repos", "code.highDebt": "repos"}


def test_verdict_lists_the_reasons_of_every_area_that_is_not_ok_in_area_order():
    from lib import health
    s = clean_snapshot()
    s["machine"]["drift"] = 2
    s["docs"]["stale"] = [{"path": "a.md", "repos": []}] * 3
    s["repos"]["api"]["vulnerable"] = [vuln("high"), vuln("high")]
    got = health.areas(s, today=TODAY)
    assert [(v["key"], v["n"]) for v in got["verdict"]] == [("machine.drift", 2), ("docs.stale", 3), ("code.vulnHigh", 2)]


def test_repo_state_is_the_worst_of_its_vulns_coverage_and_debt():
    from lib import health
    s = clean_snapshot()
    s["repos"]["api"]["vulnerable"] = [vuln("medium"), vuln("critical")]
    s["repos"]["web"]["coverage"] = {"percent": 10.0, **COV}
    s["repos"]["worker"] = repo_block(debt=[debt("high")])
    s["repos"]["old"] = repo_block(cloned=False, libraries=0)
    assert health.areas(s, today=TODAY)["repo_state"] == {"api": "bad", "web": "warn", "worker": "warn", "old": None}


BOOM = {"error": "boom"}
UNREAD = [
    # (name, change, area, row the next action opens)
    ("freshness", lambda s: s["docs"].update(stale=BOOM, suspect=BOOM), "docs", "fresh"),
    ("evals", set_(["docs", "evals"], BOOM), "docs", "evals"),
    ("budget", set_(["docs", "context"], BOOM), "docs", "context"),
    ("review queue", set_(["docs", "review"], BOOM), "docs", "review"),
    ("whole docs block", set_(["docs"], BOOM), "docs", "fresh"),
    ("inventory", set_(["inventory"], BOOM), "code", "libs"),
    ("sonar of a repo", set_(["repos", "api", "sonar"], BOOM), "code", "repos"),
    ("coverage of a repo", set_(["repos", "api", "reports"], BOOM), "code", "repos"),
    ("debt of a repo", set_(["repos", "web", "debt"], BOOM), "code", "repos"),
    ("project debt", set_(["debt_project"], BOOM), "code", "repos"),
    ("whole repos block", set_(["repos"], BOOM), "code", "repos"),
    ("a repo that failed to build", set_(["repos", "api"], BOOM), "code", "repos"),
]


@pytest.mark.parametrize("name,change,area,row", UNREAD, ids=[c[0] for c in UNREAD])
def test_a_source_that_failed_makes_its_area_warn(name, change, area, row):
    from lib import health
    got = health.areas(mutated(change), today=TODAY)
    assert got["areas"][area]["state"] == "warn"
    assert got["areas"][area]["next"] == {"key": f"{area}.unread", "row": row}
    assert all(v["state"] == "ok" for k, v in got["areas"].items() if k != area)
    assert [v["key"] for v in got["verdict"]] == [f"{area}.unread"]


def test_unread_comes_after_the_other_reasons():
    from lib import health
    s = mutated(set_(["docs", "evals"], BOOM))
    s["docs"]["review"] = 2
    docs = health.areas(s, today=TODAY)["areas"]["docs"]
    assert docs["next"] == {"key": "docs.review", "row": "review"}
    s["docs"]["stale"] = [{"path": "a.md", "repos": []}]
    got = health.areas(s, today=TODAY)
    assert got["areas"]["docs"]["state"] == "bad"
    assert [v["key"] for v in got["verdict"]] == ["docs.stale", "docs.review", "docs.unread"]


def test_a_repo_not_cloned_does_not_count_in_the_code_area():
    from lib import health
    s = clean_snapshot()
    s["repos"]["gone"] = repo_block(cloned=False, libraries=0, vulnerable=[vuln("critical")], debt=[debt("high")],
                                    sonar=BOOM, reports=BOOM)
    got = health.areas(s, today=TODAY)
    assert got["areas"]["code"]["state"] == "ok" and got["repo_state"]["gone"] is None


# ---- build and load ----

NO_PROBES = {"prerequisites": [{"name": "git", "need": True, "ok": True}, {"name": "uv", "need": True, "ok": False},
                               {"name": "docker", "need": False, "ok": False}],
             "tools": [{"name": "likec4", "ok": True}, {"name": "gitleaks", "ok": False}], "drift": [{"file": "x"}]}


@pytest.fixture
def probed(wired, monkeypatch):
    """A wired project whose doctor reads a fixed result instead of probing the machine's tools."""
    from lib import doctor
    monkeypatch.setattr(doctor, "report", lambda: copy.deepcopy(NO_PROBES))
    return wired


def quiet(_):
    pass


def test_build_writes_a_snapshot_the_api_can_load(probed):
    from lib import health
    snap = health.build(log=quiet)
    assert snap["v"] == 1 and snap["at"] and health.load() == snap
    assert json.loads(health.SNAPSHOT.read_text(encoding="utf-8")) == snap
    assert health.SNAPSHOT.name == "health.json"
    assert set(snap["repos"]) == set(probed.docs.repo_names())
    assert snap["machine"]["missing"] == ["uv", "gitleaks"] and snap["machine"]["drift"] == 1
    assert snap["inventory"] == {"at": None, "scanned": False}
    assert snap["areas"]["code"]["figures"][1] == {"key": "code.vulnHigh", "n": None}          # never scanned: "—", not 0
    assert set(snap) >= {"machine", "docs", "inventory", "repos", "debt_project", "areas", "repo_state", "verdict"}
    assert snap["areas"]["machine"]["state"] == "bad" and snap["areas"]["code"]["next"]["key"] == "code.noScan"
    api = snap["repos"]["api"]
    assert api["cloned"] is True and api["coverage"] is None and api["reports"] == [] and api["debt"] == []
    assert api["sonar"] == {"used": False, "project": "", "organization": "", "host": "", "link": ""}
    assert isinstance(snap["docs"]["evals"]["total"], int) and isinstance(snap["docs"]["review"], int)


def test_build_reads_the_saved_inventory_per_repo(probed):
    from lib import health, inventory
    probed.common.save_json(inventory.DATA, {
        "libraries": [
            {"repo": "api", "name": "a", "ecosystem": "maven", "version": "1", "vulns": [
                {"id": "G1", "cve": "CVE-1", "severity": "high", "fixed": "2"},
                {"id": "G2", "cve": None, "severity": "medium", "fixed": None}]},
            {"repo": "api", "name": "b", "ecosystem": "maven", "version": "3", "vulns": []},
            {"repo": "web", "name": "c", "ecosystem": "npm", "version": "1", "vulns": []}],
        "vulns": {"at": "2026-10-01T00:00:00Z", "online": True}})
    snap = health.build(log=quiet)
    assert snap["inventory"] == {"at": "2026-10-01T00:00:00Z", "scanned": True}
    api = snap["repos"]["api"]
    assert api["libraries"] == 2 and api["vulns"] == {"high": 1, "medium": 1}
    assert api["vulnerable"][0] == {"name": "a", "version": "1", "severity": "high", "id": "G1", "cve": "CVE-1", "fixed": "2"}
    assert snap["repos"]["web"]["libraries"] == 1 and snap["repos"]["web"]["vulnerable"] == []
    assert snap["areas"]["code"]["next"]["key"] == "code.vulnHigh"


def test_an_inventory_never_scanned_for_vulnerabilities_is_not_scanned(probed):
    from lib import health, inventory
    probed.common.save_json(inventory.DATA, {"libraries": [{"repo": "api", "name": "a", "ecosystem": "maven", "version": "1"}],
                                             "vulns": None})
    snap = health.build(log=quiet)
    assert snap["inventory"] == {"at": None, "scanned": False} and snap["repos"]["api"]["libraries"] == 1


@pytest.mark.parametrize("saved", [None, [], {"vulns": True}, {"libraries": "x"}, {"libraries": ["api"]},
                                   {"libraries": [{"repo": "api", "vulns": "x"}]},
                                   {"libraries": [{"repo": "api", "vulns": ["x"]}]}],
                         ids=["null", "list", "vulns true", "libraries string", "library row a string",
                              "library vulns a string", "vuln a string"])
def test_an_inventory_of_the_wrong_shape_does_not_stop_the_build(probed, saved):
    from lib import health, inventory
    probed.common.save_json(inventory.DATA, saved)
    snap = health.build(log=quiet)
    assert snap["inventory"]["error"] and set(snap["repos"]) == set(probed.docs.repo_names())
    code = snap["areas"]["code"]
    assert code["state"] == "warn" and code["next"] == {"key": "code.unread", "row": "libs"}
    assert code["figures"] == [{"key": "code.libraries", "n": None}, {"key": "code.vulnHigh", "n": None}]
    assert health.load() == snap


def test_a_repo_that_fails_to_build_is_unread_not_a_crash(probed, monkeypatch):
    from lib import health, inventory
    probed.common.save_json(inventory.DATA, {"libraries": [{"repo": "api", "name": "a", "ecosystem": "m", "version": "1"}],
                                             "vulns": {"at": "2026-10-20T00:00:00Z"}})
    real = health._vulns_of
    monkeypatch.setattr(health, "_vulns_of", lambda libs: (_ for _ in ()).throw(RuntimeError("bad rows")) if libs else real(libs))
    snap = health.build(log=quiet)
    assert snap["repos"]["api"] == {"error": "bad rows"} and snap["repos"]["web"]["cloned"] is True
    assert snap["repo_state"]["api"] is None and snap["areas"]["code"]["next"] == {"key": "code.unread", "row": "repos"}


def test_build_reads_coverage_sonar_and_debt(probed):
    from lib import health
    api = probed.common.repo_dir("api")
    put(api, "target/site/jacoco/jacoco.xml", JACOCO)
    put(api, "sonar-project.properties", "sonar.projectKey=acme_api\nsonar.organization=acme\n")
    quality_page(probed, "tech-debt.md", "# Debt\n\n## Items\n\n| Item | Impact | Evidence | Owner |\n|---|---|---|---|\n"
                 "| Slow | high | `api:x` | Ana |\n| No CI | low | none | Ana |\n")
    snap = health.build(log=quiet)
    r = snap["repos"]["api"]
    assert r["coverage"]["percent"] == 80.0 and r["reports"][0]["path"] == "target/site/jacoco/jacoco.xml"
    assert r["sonar"]["used"] is True and r["sonar"]["project"] == "acme_api" and r["sonar"]["organization"] == "acme"
    assert r["sonar"]["host"] == "" and r["sonar"]["link"]
    assert [i["item"] for i in r["debt"]] == ["Slow"] and [i["item"] for i in snap["debt_project"]] == ["No CI"]
    assert snap["repo_state"]["api"] == "warn"


def test_stale_and_suspect_pages_name_the_repos_of_their_code(probed):
    from lib import health
    probed.plan.sync()
    for rel, srcs in (("flows/a.md", [f"api:{API}#L3-L5"]), ("flows/b.md", ["worker:worker/main.py"])):
        f = probed.root / "docs" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("---\ntitle: t\nx-sources:\n" + "".join(f"  - {s}\n" for s in srcs) + "---\n# T\n", encoding="utf-8")
    from lib.harness import freshness
    freshness.stamp_all()
    (probed.ws / "api" / API).write_text("package demo;\n\npublic class Api implements Runnable {\n    // calls worker over HTTP\n}\n", encoding="utf-8")
    (probed.ws / "worker" / "worker" / "main.py").unlink()
    snap = health.build(log=quiet)
    assert snap["docs"]["suspect"] == [{"path": "flows/a.md", "repos": ["api"]}]
    assert snap["docs"]["stale"] == [{"path": "flows/b.md", "repos": ["worker"]}]
    assert snap["areas"]["docs"]["state"] == "bad" and snap["areas"]["docs"]["next"] == {"key": "docs.stale", "row": "fresh"}


def test_one_failing_source_does_not_stop_the_rest(probed, monkeypatch):
    from lib import budget, health

    def boom():
        raise RuntimeError("no budget today")
    monkeypatch.setattr(budget, "standing", boom)
    snap = health.build(log=quiet)
    assert snap["docs"]["context"] == {"error": "no budget today"}
    assert isinstance(snap["docs"]["review"], int) and snap["machine"]["missing"]
    assert set(snap["areas"]) == {"machine", "docs", "code"} and set(snap["repos"]) == set(probed.docs.repo_names())
    assert snap["areas"]["docs"]["state"] == "warn" and "docs.unread" in [v["key"] for v in snap["verdict"]]
    assert health.load() == snap


def test_a_repo_not_cloned_is_listed_with_nothing_known(probed):
    import shutil
    from lib import health
    def writable(fn, p, _exc):                  # git objects are read-only on Windows
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(probed.common.repo_dir("web"), **({"onexc": writable} if sys.version_info >= (3, 12) else {"onerror": writable}))
    snap = health.build(log=quiet)
    web = snap["repos"]["web"]
    assert web["cloned"] is False and web["coverage"] is None and web["libraries"] == 0
    assert web["reports"] == [] and web["vulnerable"] == [] and web["sonar"]["used"] is False
    assert snap["repos"]["api"]["cloned"] is True and snap["repo_state"]["web"] is None
    assert snap["repo_state"]["api"] == "ok" and snap["areas"]["code"]["state"] == "warn"      # not scanned, not web


def test_load_refuses_corrupt_or_newer_snapshots(kit):
    from lib import health
    assert health.load() is None                              # never built
    health.SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    for text in ("{", "[]", '{"v": 2}', '{"v": 1.5}', "{}"):
        health.SNAPSHOT.write_text(text, encoding="utf-8")
        assert health.load() is None, text
    health.SNAPSHOT.write_text('{"v": 1}', encoding="utf-8")
    assert health.load() == {"v": 1}


def test_the_doctor_record_matches_the_snapshot(probed):
    from lib import doctor, health
    snap = health.build(log=quiet)
    rec = doctor.checked()
    assert rec["result"] == NO_PROBES and rec["at"] == snap["machine"]["at"]
    assert snap["machine"] == {"at": rec["at"], "missing": ["uv", "gitleaks"], "drift": 1, "tools": 2}


# ---- `camaron health` and GET /api/health ----

# The CLI runs in a child process; this driver gives its doctor the fixed result first, like `probed` does here.
DRIVER = ("import json, os, runpy, sys\n"
          "sys.path.insert(0, os.path.dirname(sys.argv[1]))\n"
          "from lib import doctor\n"
          "doctor.report = lambda: json.loads(os.environ['NO_PROBES'])\n"
          "sys.argv = sys.argv[1:]\n"
          "runpy.run_path(sys.argv[0], run_name='__main__')\n")


def health_cli(kit, *args):
    import subprocess
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root), "NO_PROBES": json.dumps(NO_PROBES)}
    return subprocess.run([sys.executable, "-c", DRIVER, str(kit.kit_dir / "camarones.py"), "health", *args], env=e,
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_health_builds_once_and_prints_the_verdict(wired):
    from lib import health
    assert not health.SNAPSHOT.exists()
    r = health_cli(wired)
    assert r.returncode == 0, r.stderr
    assert health.SNAPSHOT.exists()
    for area in ("Machine", "Docs", "Code"):
        assert area in r.stdout
    first = health.SNAPSHOT.stat().st_mtime_ns
    r = health_cli(wired)
    assert r.returncode == 0, r.stderr
    assert health.SNAPSHOT.stat().st_mtime_ns == first and "Machine" in r.stdout


def test_cli_health_json_is_the_snapshot(wired):
    r = health_cli(wired, "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["v"] == 1                   # only the JSON on stdout: the build's log goes to stderr
    assert "reading the machine" in r.stderr


def test_cli_health_refresh_rebuilds(wired):
    from lib import health
    assert health_cli(wired).returncode == 0
    before = health.SNAPSHOT.stat().st_mtime_ns
    r = health_cli(wired, "--refresh")
    assert r.returncode == 0, r.stderr
    assert health.SNAPSHOT.stat().st_mtime_ns != before


def put_snapshot(snap):
    from lib import health
    health.SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    health.SNAPSHOT.write_text(json.dumps(snap), encoding="utf-8")


def test_cli_health_text_says_every_reason_in_words(wired):
    from lib import health
    keys = list(health.ROWS) + ["docs.unread", "code.unread"]
    s = {**clean_snapshot(), "repos": {}, "repo_state": {}, "verdict": [{"key": k, "n": 3} for k in keys],
         "areas": {w: {"state": st, "figures": [], "next": None} for w, st in (("machine", "bad"), ("docs", "warn"), ("code", "ok"))}}
    put_snapshot(s)
    r = health_cli(wired)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    area = {w: next(ln for ln in lines if f" {w}:" in ln) for w in ("Machine", "Docs", "Code")}
    assert area["Machine"].startswith("✖") and area["Docs"].startswith("!") and area["Code"].startswith("✔")
    assert "3 stale pages" in area["Docs"] and "3 high or critical vulnerabilities" in area["Code"]
    assert "machine." not in r.stdout and "docs." not in r.stdout and "code." not in r.stdout


def test_cli_health_text_shows_the_figures_of_a_healthy_area_and_a_missing_one_as_a_dash(wired):
    figures = {"machine": [{"key": "machine.tools", "n": 6}, {"key": "machine.missing", "n": None}], "docs": [],
               "code": [{"key": "code.libraries", "n": None}, {"key": "code.vulnHigh", "n": 0}]}
    put_snapshot({**clean_snapshot(), "verdict": [], "repo_state": {},
                  "areas": {w: {"state": "ok", "figures": f, "next": None} for w, f in figures.items()}})
    lines = health_cli(wired).stdout.splitlines()
    area = {w: next(ln for ln in lines if f" {w}:" in ln) for w in ("Machine", "Code")}
    assert "tools checked: 6" in area["Machine"] and "missing: —" in area["Machine"]
    assert "libraries: —" in area["Code"] and "high or critical vulnerabilities: 0" in area["Code"]


def test_cli_health_text_has_a_row_per_repo(wired):
    s = clean_snapshot()
    s["repos"] = {"api": repo_block(vulns={"high": 2}, coverage={"type": "lcov", "percent": 41.5}, debt=[debt("high")],
                                    sonar={**repo_block()["sonar"], "used": True, "project": "api-key"}),
                  "web": repo_block(cloned=False), "worker": {"error": "boom"}}
    put_snapshot({**s, "verdict": [], "repo_state": {"api": "bad", "web": None, "worker": None},
                  "areas": {w: {"state": "ok", "figures": [], "next": None} for w in ("machine", "docs", "code")}})
    lines = health_cli(wired).stdout.splitlines()
    row = {n: next(ln for ln in lines if ln.split()[1:2] == [n] or ln.split()[:1] == [n]) for n in ("api", "web", "worker")}
    assert row["api"].startswith("✖") and all(x in row["api"] for x in ("yes", "41.5%", "2 high", "1 (1 high)"))
    assert row["web"].count("—") == 4 and "not cloned" in row["web"] and "unread" in row["worker"]
    header = next(ln for ln in lines if "Sonar" in ln)
    assert "coverage" in header and "vulns" in header and "debt" in header


def test_cli_health_text_sonar_column_is_the_gate_word_or_yes_no_and_marks_kept_values(wired):
    sonar = {**repo_block()["sonar"], "used": True, "project": "k"}
    server = {"at": "2026-10-20T08:00:00Z", "host": "https://sonar.test", "gate": "ERROR", "coverage": 80.0}
    s = clean_snapshot()
    s["repos"] = {"fresh": repo_block(sonar={**sonar, "server": {**server, "gate": "OK"}}),
                  "warned": repo_block(sonar={**sonar, "server": {**server, "gate": "WARN"}}),
                  "kept": repo_block(sonar={**sonar, "server": server, "error": "sin conexión"}),
                  "lost": repo_block(sonar={**sonar, "error": "token no válido"}),
                  "nogate": repo_block(sonar={**sonar, "server": {**server, "gate": None}}),
                  "plain": repo_block(sonar=sonar), "none": repo_block()}
    put_snapshot({**s, "verdict": [], "repo_state": {n: "ok" for n in s["repos"]},
                  "areas": {w: {"state": "ok", "figures": [], "next": None} for w in ("machine", "docs", "code")}})
    lines = health_cli(wired).stdout.splitlines()
    cell = {n: next(ln for ln in lines if ln.split()[1:2] == [n]).split()[2:] for n in s["repos"]}
    assert cell["fresh"][0] == "passed" and cell["warned"][0] == "warning"
    assert cell["kept"][:2] == ["failed", "(stale)"]
    assert cell["lost"][0] == "—" and "(stale)" not in cell["lost"]
    assert cell["nogate"][0] == "—" and cell["plain"][0] == "yes" and cell["none"][0] == "no"
    assert "sonar.test" not in "".join(lines)                      # the host the figures came from is never printed


@pytest.fixture
def server(kit):
    import threading
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_api_health_reads_and_never_builds(probed, server):
    import urllib.request
    from lib import health

    def get():
        with urllib.request.urlopen(f"{server}/api/health", timeout=10) as r:
            return json.loads(r.read())

    assert get() == {"snapshot": None} and not health.SNAPSHOT.exists()
    snap = health.build(log=quiet)
    assert get() == {"snapshot": snap}
