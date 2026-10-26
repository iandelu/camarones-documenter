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
    put(tmp_path, "target/site/jacoco/jacoco.xml", '<!DOCTYPE r [<!ENTITY x "y">]>' + JACOCO)
    put(tmp_path, "build/reports/jacoco/test/huge.xml", "<report>" + " " * health.MAX_REPORT_BYTES + "</report>")
    put(tmp_path, "build/reports/jacoco/test/cut.xml", "<report><counter type=")
    put(tmp_path, "coverage/lcov.info", "LF:4\nLH:1\n")
    reports = {r["path"]: r for r in health.coverage_reports(tmp_path)}
    assert len(reports) == 4
    for path in ("target/site/jacoco/jacoco.xml", "build/reports/jacoco/test/huge.xml", "build/reports/jacoco/test/cut.xml"):
        assert reports[path]["error"] and "percent" not in reports[path]
    assert reports["coverage/lcov.info"]["percent"] == 25.0


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
