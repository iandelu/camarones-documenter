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
