"""Compliance evals for the PLAYBOOK (R36, X7): does a unit's output follow the method? Deterministic: the pages it
wrote are scored with the kit's own checks (structure, links, sources that exist). `camaron eval comply <unit>` runs
one real unit (the sandbox is the place for it, never CI) and keeps the score in docs/.work/evals/comply/, so a
prompt or playbook change can be compared before and after."""
from __future__ import annotations

import datetime as dt
import hashlib

from ..common import DOCS, ROOT, WORK, save_json
from .. import docs

RESULTS = WORK / "evals" / "comply"


def score(paths: list[str]) -> dict:
    from .. import quality
    every = docs.collect()
    rows = {r["path"]: r for r in every}
    chosen = [rows[p] for p in paths if p in rows]
    found = []
    for check in (quality.check_structure, quality.check_links):    # over every page: links reach pages not written now
        errors, warns = check(every)
        found += errors + warns
    by_page = {}
    for r in chosen:
        problems = [p.split(": ", 1)[-1] for p in found if p.startswith(r["file"] + ":")]
        by_page[r["path"]] = {"issues": problems, "orphan_sources": list(r.get("orphan_sources") or [])}
    compliant = sum(1 for v in by_page.values() if not v["issues"] and not v["orphan_sources"])
    return {"pages": len(by_page), "compliant": compliant,
            "score": round(compliant / len(by_page), 3) if by_page else None, "by_page": by_page}


def _snapshot() -> dict[str, str]:
    return {f.relative_to(DOCS).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in DOCS.rglob("*.md") if not any(p.startswith(".") for p in f.relative_to(DOCS).parts)}


def run(unit: str, runner: str | None = None, echo=print) -> dict:
    """Run one ready unit (through the scheduler, so it is recorded like any run) and score the pages it wrote."""
    from . import scheduler
    from .. import plan
    data = plan.sync()
    if unit not in {u["id"] for u in plan.available(data)}:
        u = plan.get(data, unit)
        waits = [d for d in u["deps"] if plan.get(data, d)["status"] not in plan.DONE]
        raise ValueError(f"{unit} is not ready ({u['status']})" + (f": it waits for {', '.join(waits)}" if waits else "")
                         + " — finish those first, or pick a ready unit (`plan next`)")
    before = _snapshot()
    if runner:
        from ..common import PREFS, load_json
        prefs = load_json(PREFS, {})
        prefs.setdefault("routing", {})["agentic-heavy"] = [runner]
        save_json(PREFS, prefs)
    scheduler.run_parallel(max_parallel=1, only={unit}, echo=echo, lang="en")
    after = _snapshot()
    written = sorted(p for p, h in after.items() if before.get(p) != h)
    status = next((u["status"] for u in plan.load()["units"] if u["id"] == unit), "unknown")
    result = {"at": dt.datetime.now().replace(microsecond=0).isoformat(), "unit": unit, "status": status,
              "written": written, **score(written)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    save_json(RESULTS / f"{result['at'].replace(':', '').replace('-', '')}-{unit.replace(':', '-')}.json", result)
    return result
