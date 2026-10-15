"""AI drafts vs what people confirm (R18). When a unit is done, the AI-written pages it left (draft or
needs-reconfirm, never x-owner: human) are copied to docs/.work/ai-drafts.json; when a person confirms one, the share
of words they changed is recorded there (0 = confirmed as written, 1 = rewritten). Committed, so whoever confirms on
whichever machine adds to the same record."""
from __future__ import annotations

import datetime as dt
import difflib

from ..common import CTX, WORK, load_json, save_json
from .locks import FileLock

FILE = WORK / "ai-drafts.json"
LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "ai-drafts.lock"


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def _load() -> dict:
    data = load_json(FILE, {})
    return data if isinstance(data.get("pages"), dict) else {"v": 1, "pages": {}}


def edit_ratio(before: str, after: str) -> float:
    a, b = before.split(), after.split()
    if not a and not b:
        return 0.0
    return round(1 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)


def snapshot(unit: str) -> int:
    """Copy the AI-written pages that changed since their last copy. Returns how many were copied."""
    from .. import docs
    with FileLock(LOCK):
        data = _load()
        pages, changed = data["pages"], 0
        for logical, f in docs.iter_docs():
            fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
            if not fm or fm.get("x-owner") == "human":
                continue
            sha = docs.body_sha(body)
            prev = pages.get(logical) or {}
            if docs.trust_of(fm, sha) == "confirmed" or prev.get("sha") == sha:
                continue
            pages[logical] = {"sha": sha, "body": body, "unit": unit, "at": _now(),
                              "confirmations": prev.get("confirmations", [])}
            changed += 1
        if changed:
            save_json(FILE, data)
        return changed


def record_confirmation(logical: str, body: str, by: str) -> float | None:
    """How much `by` changed the AI's last copy of this page before confirming it (None: no AI copy known)."""
    with FileLock(LOCK):
        data = _load()
        entry = data["pages"].get(logical)
        if not entry:
            return None
        if not entry.get("body") and entry.get("confirmations"):
            return None                       # already measured; the AI has not rewritten the page since
        edit = edit_ratio(entry.get("body", ""), body)
        entry.setdefault("confirmations", []).append({"at": _now(), "by": by, "edit": edit})
        entry["body"] = ""                    # the copy was only needed until a person confirmed the page
        save_json(FILE, data)
        return edit


def stats() -> dict:
    last = [p["confirmations"][-1]["edit"] for p in _load()["pages"].values() if p.get("confirmations")]
    return {"ai_pages_confirmed": len(last), "ai_edit_avg": round(sum(last) / len(last), 3) if last else None}
