"""The kit's guides (templates/docs/guides): how to use Camarón, the desktop app, the portal and how it works inside.
The desktop app reads them from the installed kit, so its Guide never shows a copy that went stale in a project."""
from __future__ import annotations

from pathlib import Path

from . import docs, env

ORDER = ("using", "app", "portal", "internals", "tutorial")


def guides(lang: str, base: Path | None = None) -> list[dict]:
    """Each guide that ships in English, in ORDER, from its Spanish twin when lang is es and the twin exists."""
    base = base or env.TEMPLATES / "docs"
    out = []
    for name in ORDER:
        en = base / "guides" / f"{name}.md"
        if not en.is_file():
            continue
        es = base / "i18n" / "es" / "guides" / f"{name}.md"
        fm, body = docs.split_fm((es if lang == "es" and es.is_file() else en).read_text(encoding="utf-8"))
        out.append({"name": name, "title": str(fm.get("title") or name), "description": str(fm.get("description") or ""),
                    "markdown": body})
    return out
