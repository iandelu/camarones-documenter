"""Project health snapshot: what a team wants to know about a project at a glance, read without AI into
cam-docs/.cache/health.json. Three sides: the machine (what is installed and running), the docs (how current and
complete cam-docs is) and the code (coverage, vulnerabilities, quality gate). Each value says where it came from and
when, and a value that cannot be read stays missing instead of becoming zero.

Coverage comes from the reports a repo already holds: JaCoCo XML, lcov and Cobertura, at their usual paths. Report
files are untrusted input: an internal DTD subset or entity declaration, an oversized file or broken XML is reported
as an error and never parsed further. The external DTD a JaCoCo report names is never fetched or read.

Technical debt is read from the two quality pages (`quality/tech-debt.md`, `quality/architecture-review.md`): each table
row is an item, filed under the repos its evidence cites, or under `_project` when it cites none.

`build()` reads every source into the snapshot (`SNAPSHOT`), one `try` per source so a failing one becomes
`{"error"}` and the rest is still built; `areas()` is the pure part that turns a snapshot into states, figures, next
actions and the verdict.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from .common import CACHE, load_json, save_json

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


# ---- the snapshot ----

SNAPSHOT = CACHE / "health.json"
VERSION = 1
VULN_SCAN_MAX_DAYS = 30
COVERAGE_MIN = 50

# Reason key -> the row of the screen that fixes it (the UI turns keys into words and rows into links).
ROWS = {"machine.missing": "doctor", "machine.unchecked": "doctor", "machine.drift": "drift",
        "docs.stale": "fresh", "docs.suspect": "fresh", "docs.context": "context", "docs.noEvals": "evals",
        "docs.review": "review", "code.vulnHigh": "libs", "code.vulnMedium": "libs", "code.noScan": "libs",
        "code.oldScan": "libs", "code.lowCoverage": "repos", "code.highDebt": "repos"}
STATE_ORDER = ("ok", "warn", "bad")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _guard(fn, *args):
    """A source that fails becomes `{"error"}`: the rest of the snapshot is still built."""
    try:
        return fn(*args)
    except Exception as e:                      # any source may break in its own way
        return {"error": str(e) or type(e).__name__}


def _failed(block) -> bool:
    return isinstance(block, dict) and isinstance(block.get("error"), str)


def _worst(states) -> str:
    return max(states, key=STATE_ORDER.index, default="ok")


# ---- reading the sources ----

def _machine(log) -> dict:
    from . import doctor
    rec = doctor.check(log)                     # also keeps the record the doctor row reads
    p = doctor.problems(rec["result"])
    return {"at": rec["at"], "missing": p["missing"] + p["tools"], "drift": p["drift"],
            "tools": len(rec["result"].get("tools", []))}


def _stale_and_suspect(known: set[str]) -> dict:
    from .harness import freshness
    out: dict[str, list] = {"stale": [], "suspect": []}
    for path, st in sorted(freshness.states().items()):
        if st["state"] in out:
            repos = {freshness.parse(ref)[0] for ref in [*st.get("changed", []), *st.get("missing", [])]}
            out[st["state"]].append({"path": path, "repos": sorted(repos & known)})
    return out


def _evals() -> dict:
    from .harness import evals
    qs = evals.load()
    return {"total": len(qs), "confirmed": sum(1 for q in qs if q.get("x-confirmed"))}


def _context() -> dict:
    from . import budget
    s = budget.standing()
    return {"total": s["total"], "budget": s["budget"], "over": s["over"]}


def _review() -> int:
    from . import docs
    return len(docs.review_queue())


def _docs(now: str, names: list[str]) -> dict:
    pages = _guard(_stale_and_suspect, set(names))
    return {"at": now, "stale": pages if _failed(pages) else pages["stale"],
            "suspect": pages if _failed(pages) else pages["suspect"],
            "evals": _guard(_evals), "context": _guard(_context), "review": _guard(_review)}


def _vulns_of(libs: list[dict]) -> list[dict]:
    return [{"name": lib.get("name", ""), "version": lib.get("version", ""), "severity": v.get("severity", "unknown"),
             "id": v.get("id", ""), "cve": v.get("cve"), "fixed": v.get("fixed")}
            for lib in libs for v in lib.get("vulns") or []]


def _sonar(name: str, path: Path) -> dict:
    from . import radar
    tool = next((t for t in radar.scan_repo(name, path) if t["id"] == "sonar"), None)
    info = tool["info"] if tool else {}
    return {"used": tool is not None, "project": info.get("project", ""), "organization": info.get("organization", ""),
            "host": "", "link": info.get("link", "")}


def _repo(name: str, inv: dict, debt: dict) -> dict:
    from .common import repo_dir
    path = repo_dir(name)
    row: dict = {"cloned": path.is_dir(), "libraries": 0, "vulns": {}, "vulnerable": [],
                 "sonar": {"used": False, "project": "", "organization": "", "host": "", "link": ""},
                 "coverage": None, "reports": [], "debt": debt if _failed(debt) else debt.get(name, [])}
    if not row["cloned"]:                       # listed, with nothing known
        return row
    if _failed(inv):
        row["libraries"] = row["vulns"] = row["vulnerable"] = inv
    else:
        libs = [lib for lib in inv.get("libraries") or [] if lib.get("repo") == name]
        row["libraries"] = len({(lib.get("ecosystem"), lib.get("name")) for lib in libs})
        row["vulnerable"] = _vulns_of(libs)
        row["vulns"] = dict(Counter(v["severity"] for v in row["vulnerable"]))
    row["sonar"] = _guard(_sonar, name, path)
    row["reports"] = _guard(coverage_reports, path)
    row["coverage"] = row["reports"] if _failed(row["reports"]) else repo_coverage(row["reports"])
    return row


def _inventory() -> dict:
    from . import inventory
    return inventory.load()


def build(log=print) -> dict:
    """Read every source, compute the areas, save the snapshot and return it."""
    from . import docs
    log("reading the machine…")
    machine = _guard(_machine, log)
    names = _guard(lambda: [r["name"] for r in docs.workspace()["repos"]])
    log("reading the docs, the inventory and the repos…")
    inv = _guard(_inventory)
    debt = _guard(debt_items, names) if not _failed(names) else names
    now = _now()
    snap = {"v": VERSION, "at": now, "machine": machine, "docs": _docs(now, [] if _failed(names) else names),
            "inventory": inv if _failed(inv) else {"at": (inv.get("vulns") or {}).get("at"), "scanned": bool(inv.get("vulns"))},
            "repos": names if _failed(names) else {n: _repo(n, inv, debt) for n in names},
            "debt_project": debt if _failed(debt) else debt.get("_project", [])}
    snap.update(areas(snap))
    save_json(SNAPSHOT, snap)
    return snap


def load() -> dict | None:
    """The last snapshot, or None: never built, unreadable, not an object, or written by another version."""
    try:
        snap = load_json(SNAPSHOT, None)
    except (OSError, ValueError):
        return None
    return snap if isinstance(snap, dict) and snap.get("v") == VERSION else None


# ---- the state rules ----

def _list(block) -> list:
    return block if isinstance(block, list) else []


def _good(block) -> bool:
    return isinstance(block, dict) and not _failed(block)


def _counts(repo: dict) -> dict:
    """Vulnerabilities by severity: the repo's own tally, else counted from its rows."""
    tally = repo.get("vulns")
    if _good(tally) and tally:
        return tally
    return dict(Counter(v.get("severity") for v in _list(repo.get("vulnerable"))))


def _repo_percent(repo: dict) -> float | None:
    cov = repo.get("coverage")
    p = cov.get("percent") if isinstance(cov, dict) else None
    return p if isinstance(p, (int, float)) and not isinstance(p, bool) else None


def _high_debt(items) -> set[tuple]:
    return {(d.get("source"), d.get("item")) for d in _list(items) if d.get("impact") == "high"}


def _age_days(at, today: date) -> int | None:
    try:
        when = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo:
        when = when.astimezone(timezone.utc)
    return (today - when.date()).days


def _reason(state: str, key: str, n, row: str | None = None) -> tuple:
    """(state, reason key, n, row to open): the row is the key's own unless a failed source names another."""
    return (state, key, n, row or ROWS[key])


def _unread(failed: list[tuple[str, str]], key: str) -> list:
    """`docs.unread` / `code.unread`: sources that could not be read make their area `warn`, never `ok`. It opens the
    row of the first failed source; `failed` is [(source, row)]."""
    return [_reason("warn", key, len(failed), failed[0][1])] if failed else []


def _machine_reasons(snap: dict) -> tuple[list, list]:
    m = snap.get("machine")
    if not _good(m):                            # never checked here, or the check failed
        return [_reason("warn", "machine.unchecked", None)], [("machine.tools", None), ("machine.missing", None)]
    missing, drift = _list(m.get("missing")), m.get("drift") or 0
    reasons = ([_reason("bad", "machine.missing", len(missing))] if missing else []) + \
              ([_reason("warn", "machine.drift", drift)] if drift else [])
    return reasons, [("machine.tools", m.get("tools")), ("machine.missing", len(missing))]


def _docs_reasons(snap: dict) -> tuple[list, list]:
    d = snap.get("docs")
    if not _good(d):
        return _unread([("docs", "fresh")], "docs.unread"), [("docs.stale", None), ("docs.review", None)]
    stale, suspect, ctx, evals, review = (d.get(k) for k in ("stale", "suspect", "context", "evals", "review"))
    reasons = []
    if _list(stale):
        reasons.append(_reason("bad", "docs.stale", len(stale)))
    if _list(suspect):
        reasons.append(_reason("warn", "docs.suspect", len(suspect)))
    if _good(ctx) and ctx.get("over"):
        reasons.append(_reason("warn", "docs.context", ctx["total"] - ctx["budget"]))
    if _good(evals) and not evals.get("confirmed"):
        reasons.append(_reason("warn", "docs.noEvals", evals.get("total")))
    if isinstance(review, int) and review > 0:
        reasons.append(_reason("warn", "docs.review", review))
    reasons += _unread([(k, row) for k, row in (("stale", "fresh"), ("evals", "evals"), ("context", "context"),
                                                ("review", "review")) if _failed(d.get(k))], "docs.unread")
    return reasons, [("docs.stale", len(stale) if isinstance(stale, list) else None),
                     ("docs.review", review if isinstance(review, int) else None)]


def _code_reasons(snap: dict, today: date) -> tuple[list, list]:
    all_repos = snap.get("repos")
    repos = [r for r in all_repos.values() if _good(r) and r.get("cloned") is not False] if _good(all_repos) else []
    counts = [_counts(r) for r in repos]
    high = sum(c.get("critical", 0) + c.get("high", 0) for c in counts)
    medium = sum(c.get("medium", 0) for c in counts)
    low = sum(1 for r in repos if (p := _repo_percent(r)) is not None and p < COVERAGE_MIN)
    debt = _high_debt(snap.get("debt_project")).union(*(_high_debt(r.get("debt")) for r in repos))
    inv = snap.get("inventory") if _good(snap.get("inventory")) else None
    reasons = []
    if high:
        reasons.append(_reason("bad", "code.vulnHigh", high))
    if medium:
        reasons.append(_reason("warn", "code.vulnMedium", medium))
    if inv is not None and not inv.get("scanned"):
        reasons.append(_reason("warn", "code.noScan", None))
    elif inv is not None and (age := _age_days(inv.get("at"), today)) is not None and age > VULN_SCAN_MAX_DAYS:
        reasons.append(_reason("warn", "code.oldScan", age))
    if low:
        reasons.append(_reason("warn", "code.lowCoverage", low))
    if debt:
        reasons.append(_reason("warn", "code.highDebt", len(debt)))
    failed = [("inventory", "libs")] if _failed(snap.get("inventory")) else []
    if (_failed(all_repos) or _failed(snap.get("debt_project"))
            or any(_failed(r.get(k)) for r in repos for k in ("sonar", "coverage", "reports", "debt"))):
        failed.append(("repos", "repos"))
    reasons += _unread(failed, "code.unread")
    libs = [r["libraries"] for r in repos if isinstance(r.get("libraries"), int)]
    known = inv is not None and bool(libs) and (sum(libs) > 0 or inv.get("scanned"))
    return reasons, [("code.libraries", sum(libs) if known else None), ("code.vulnHigh", high)]


def _repo_state(repo: dict) -> str | None:
    """None for a repo that is not cloned: nothing is known about it."""
    if repo.get("cloned") is False:
        return None
    c, p = _counts(repo), _repo_percent(repo)
    if c.get("critical", 0) + c.get("high", 0):
        return "bad"
    low = p is not None and p < COVERAGE_MIN
    return "warn" if c.get("medium", 0) or low or _high_debt(repo.get("debt")) else "ok"


def areas(snapshot: dict, today: date | None = None) -> dict:
    """Pure: the three area states with their figures and next action, the state of each repo and the verdict.
    A source that failed makes its area `warn` (`docs.unread`, `code.unread`; the machine: `machine.unchecked`). A repo
    that is not cloned has no state and does not count."""
    today = today or datetime.now(timezone.utc).date()
    out, verdict = {}, []
    for area, (reasons, figures) in (("machine", _machine_reasons(snapshot)), ("docs", _docs_reasons(snapshot)),
                                     ("code", _code_reasons(snapshot, today))):
        state = _worst(r[0] for r in reasons)
        out[area] = {"state": state, "figures": [{"key": k, "n": n} for k, n in figures],
                     "next": {"key": reasons[0][1], "row": reasons[0][3]} if reasons else None}
        if state != "ok":
            verdict += [{"key": r[1], "n": r[2]} for r in reasons]
    repos = snapshot.get("repos")
    return {"areas": out, "verdict": verdict,
            "repo_state": {n: _repo_state(r) for n, r in repos.items() if _good(r)} if _good(repos) else {}}
