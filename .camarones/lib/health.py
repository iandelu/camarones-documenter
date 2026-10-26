"""Project health snapshot: what a team wants to know about a project at a glance, read without AI into
cam-docs/.cache/health.json. Three sides: the machine (what is installed and running), the docs (how current and
complete cam-docs is) and the code (coverage, vulnerabilities, quality gate). Each value says where it came from and
when, and a value that cannot be read stays missing instead of becoming zero.

Coverage comes from the reports a repo already holds: JaCoCo XML, lcov and Cobertura, at their usual paths. Report
files are untrusted input: an internal DTD subset or entity declaration, an oversized file or broken XML is reported
as an error and never parsed further. The external DTD a JaCoCo report names is never fetched or read.

Technical debt is read from the two quality pages (`quality/tech-debt.md`, `quality/architecture-review.md`): each table
row is an item, filed under the repos its evidence cites, or under `_project` when it cites none.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

MAX_REPORT_BYTES = 5_000_000
REPORT_GLOBS = (("jacoco", "target/site/jacoco/jacoco.xml"), ("jacoco", "build/reports/jacoco/**/*.xml"),
                ("lcov", "coverage/**/lcov.info"), ("cobertura", "coverage/**/cobertura*.xml"))


# A DOCTYPE that only names an external DTD (what JaCoCo writes). expat never loads it here: ElementTree sets no
# external-entity handler. An internal subset (`[`) or an entity declaration is what could expand, so both are refused.
LITERAL = r"(?:\"[^\"]*\"|'[^']*')"
DOCTYPE = re.compile(rf"<!DOCTYPE\s+[^\s\[>]+(?:\s+(?:SYSTEM\s+{LITERAL}|PUBLIC\s+{LITERAL}\s+{LITERAL}))?\s*>")


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
    """Parse UTF-8 text only: the DOCTYPE check reads the text, so another encoding (UTF-16, whose bytes hide
    `<!DOCTYPE` from a byte search) is refused instead of parsed."""
    if b"\x00" in data:
        raise ValueError("not UTF-8 text")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("not UTF-8 text") from None
    if "<!ENTITY" in text or any(not DOCTYPE.match(text, m.start()) for m in re.finditer("<!DOCTYPE", text)):
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


DEBT_PAGES = ("quality/tech-debt.md", "quality/architecture-review.md")
DEBT_COLUMNS = {"item": ("item", "ítem", "elemento", "area", "área"), "impact": ("impact", "impacto"),
                "effort": ("estimated effort", "effort", "esfuerzo", "esfuerzo estimado"),
                "evidence": ("evidence", "evidencia"), "owner": ("owner", "responsable", "dueño"),
                "recommendation": ("recommendation", "recomendación")}
IMPACTS = {"high": "high", "alto": "high", "alta": "high", "medium": "medium", "medio": "medium", "media": "medium",
           "low": "low", "bajo": "low", "baja": "low"}
IMPACT_WORD = re.compile(r"\b(" + "|".join(IMPACTS) + r")\b", re.I)
SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
EVIDENCE_TOKEN = re.compile(r"^[\w.-]+:\S")


def _row_cells(line: str) -> list[str]:
    """The cells of a pipe-table row; `\\|` is a literal pipe, not a column break."""
    cells = re.split(r"(?<!\\)\|", line.strip().removeprefix("|").removesuffix("|"))
    return [c.replace("\\|", "|").strip() for c in cells]


def _first_table(body: str, after: str | None) -> list[list[str]]:
    """Header row and data rows of the first pipe table, after the `## <after>` heading when the page has one."""
    lines = body.splitlines()
    start = next((i + 1 for i, l in enumerate(lines) if after and re.match(rf"##\s+{after}\s*$", l, re.I)), 0)
    rows: list[list[str]] = []
    for l in lines[start:]:
        if l.strip().startswith("|"):
            rows.append([] if SEPARATOR_ROW.match(l) else _row_cells(l))
        elif rows:
            break
    return [r for r in rows if r]


def _evidence(cell: str) -> list[str]:
    tokens = re.findall(r"`([^`]+)`", cell) or re.split(r"[,;\s]+", cell)
    return [t.strip() for t in tokens if EVIDENCE_TOKEN.match(t.strip())]


def debt_items(repos: list[str]) -> dict[str, list[dict]]:
    """The items of the quality pages, per repo plus `_project` for those citing no known repo. A page that is missing
    or has no table adds nothing; an absent column reads as "" (impact as "unknown")."""
    from . import docs                              # lazily: the coverage readers above need no project
    out: dict[str, list[dict]] = {**{r: [] for r in repos}, "_project": []}
    pages = [(p, docs.DOCS / p) for p in DEBT_PAGES]
    pages = [(p, f) for p, f in pages if f.is_file()]
    trust = {r["path"]: r["trust"] for r in docs.collect()} if pages else {}
    for page, f in pages:
        _, body = docs.split_fm(f.read_text(encoding="utf-8"))
        table = _first_table(body, "Items" if page.endswith("tech-debt.md") else None)
        if len(table) < 2:
            continue
        head = [re.sub(r"[*_`]", "", h).strip().lower() for h in table[0]]
        col = {k: next((head.index(a) for a in aliases if a in head), None) for k, aliases in DEBT_COLUMNS.items()}
        if col["item"] is None:
            continue
        for cells in table[1:]:
            if cells[0].startswith("<"):            # the skeleton's placeholder row
                continue
            cell = {k: cells[i] if i is not None and i < len(cells) else "" for k, i in col.items()}
            if not cell["item"]:
                continue
            impact = IMPACT_WORD.search(cell["impact"])
            item = {"source": page, "trust": trust.get(page, "unknown"), "item": cell["item"],
                    "impact": IMPACTS[impact.group(1).lower()] if impact else "unknown", "effort": cell["effort"],
                    "evidence": _evidence(cell["evidence"]), "owner": cell["owner"],
                    "recommendation": cell["recommendation"]}
            named = [r for r in repos if any(t.split(":", 1)[0] == r for t in item["evidence"])]
            for r in named or ["_project"]:
                out[r].append({**item, "evidence": list(item["evidence"])})
    return out
