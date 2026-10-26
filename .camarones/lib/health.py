"""Project health snapshot: what a team wants to know about a project at a glance, read without AI into
cam-docs/.cache/health.json. Three sides: the machine (what is installed and running), the docs (how current and
complete cam-docs is) and the code (coverage, vulnerabilities, quality gate). Each value says where it came from and
when, and a value that cannot be read stays missing instead of becoming zero.

Coverage comes from the reports a repo already holds: JaCoCo XML, lcov and Cobertura, at their usual paths. Report
files are untrusted input: a DTD or entity declaration, an oversized file or broken XML is reported as an error and
never parsed further.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

MAX_REPORT_BYTES = 5_000_000
REPORT_GLOBS = (("jacoco", "target/site/jacoco/jacoco.xml"), ("jacoco", "build/reports/jacoco/**/*.xml"),
                ("lcov", "coverage/**/lcov.info"), ("cobertura", "coverage/**/cobertura*.xml"))


def _count(text: str) -> int:
    n = int(text)
    if n < 0:
        raise ValueError("negative line count")
    return n


def _percent(covered: int, total: int) -> float:
    if total <= 0:
        raise ValueError("no lines counted")
    return round(100 * covered / total, 1)


def _xml_root(data: bytes) -> ET.Element:
    """Parse UTF-8 text only: the DTD check reads the text, so another encoding (UTF-16, whose bytes hide
    `<!DOCTYPE` from a byte search) is refused instead of parsed."""
    if b"\x00" in data:
        raise ValueError("not UTF-8 text")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("not UTF-8 text") from None
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ValueError("DTD or entity declarations are not accepted")
    return ET.fromstring(text)                  # a str: the document's own encoding declaration is ignored


def _jacoco(data: bytes) -> float:
    for c in _xml_root(data).findall("counter"):
        if c.get("type") == "LINE":
            missed, covered = _count(c.get("missed")), _count(c.get("covered"))
            return _percent(covered, missed + covered)
    raise ValueError("no report-level LINE counter")


def _lcov(data: bytes) -> float:
    found = hit = 0
    for line in data.decode("utf-8", errors="ignore").splitlines():
        if line.startswith("LF:"):
            found += _count(line[3:])
        elif line.startswith("LH:"):
            hit += _count(line[3:])
    if hit > found:
        raise ValueError("more lines hit than found")
    return _percent(hit, found)


def _cobertura(data: bytes) -> float:
    rate = _xml_root(data).get("line-rate")
    if rate is None:
        raise ValueError("no line-rate on the root")
    return round(float(rate) * 100, 1)


READERS = {"jacoco": _jacoco, "lcov": _lcov, "cobertura": _cobertura}


def _read_report(kind: str, f: Path) -> dict:
    try:
        st = f.stat()
        if st.st_size > MAX_REPORT_BYTES:
            raise ValueError(f"larger than {MAX_REPORT_BYTES} bytes")
        percent = READERS[kind](f.read_bytes())
        if not 0 <= percent <= 100:             # also false for NaN: health.json must stay valid JSON
            raise ValueError("coverage outside 0-100")
    except (OSError, ValueError, TypeError, ET.ParseError) as e:
        return {"type": kind, "error": str(e) or type(e).__name__}
    return {"type": kind, "percent": percent, "at": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")}


def coverage_reports(repo: Path) -> list[dict]:
    """Every coverage report found at the usual paths of `repo`, newest first. A report that cannot be read carries
    an `error` instead of a `percent`."""
    found: dict[Path, tuple[str, float]] = {}
    for kind, pattern in REPORT_GLOBS:
        for f in repo.glob(pattern):
            if f.is_file() and f not in found:
                try:
                    found[f] = (kind, f.stat().st_mtime)
                except OSError:
                    continue
    rows = []
    for f, (kind, _) in sorted(found.items(), key=lambda kv: (-kv[1][1], kv[0].as_posix())):
        rows.append({**_read_report(kind, f), "path": f.relative_to(repo).as_posix()})
    return rows


def repo_coverage(reports: list[dict]) -> dict | None:
    """The coverage of a repo: the newest report that could be read, or None."""
    for r in reports:
        if "error" not in r:
            return {"percent": r["percent"], "at": r["at"], "source": "report", "path": r["path"]}
    return None
