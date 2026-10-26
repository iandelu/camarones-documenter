"""Project health snapshot: coverage read from the reports a repo already holds (JaCoCo, lcov, Cobertura)."""
from __future__ import annotations

import os
from pathlib import Path

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
