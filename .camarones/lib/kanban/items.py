"""An item is a Backlog.md (v1.55.3) task file: YAML frontmatter + Markdown body. Written the way Backlog.md writes it
(gray-matter + js-yaml: block lists, quoted dates, a blank line after the closing ---) so both tools can share the folder."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "board"

FIELD_ORDER = ("id", "title", "status", "assignee", "reporter", "created_date", "updated_date", "due_date", "labels",
               "milestone", "dependencies", "references", "documentation", "modified_files", "parent_task_id", "subtasks",
               "priority", "type", "project", "ordinal", "onStatusChange")


class ItemError(ValueError):
    pass


@dataclass
class Item:
    fm: dict = field(default_factory=dict)
    body: str = ""
    path: Path | None = None

    @property
    def id(self) -> str: return str(self.fm.get("id", ""))
    @property
    def uid(self) -> str: return str(self.fm.get("x-uid", ""))
    @property
    def title(self) -> str: return str(self.fm.get("title", ""))
    @property
    def type(self) -> str: return str(self.fm.get("type", ""))


class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):     # js-yaml indents list items under their key
        return super().increase_indent(flow, False)


_DATEISH = re.compile(r"^\d{4}-\d{2}-\d{2}([ T].*)?$")


def _str(dumper, data):
    # dates stay text: single-quoted like js-yaml does, so a YAML reader never turns them into datetimes
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'" if _DATEISH.match(data) else None)


_Dumper.add_representer(str, _str)


def _plain(v):
    """A date written unquoted by hand arrives as date/datetime; keep it as text."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.strftime("%Y-%m-%d %H:%M") if hasattr(v, "hour") else v.isoformat()
    return v


def _as_list(v) -> list:
    """A reference field as people write it: a list, or a lone value."""
    return [] if v is None else [v] if isinstance(v, str) else list(v)


def parse_item(text: str, path: Path | None = None) -> Item:
    text = text.removeprefix("﻿").replace("\r\n", "\n")       # a BOM some Windows editors add
    m = re.match(r"\A---\n(.*?\n)?---[ \t]*(?:\n|\Z)", text, re.S)
    if not m:
        raise ItemError("no frontmatter")
    try:
        fm = yaml.safe_load(m.group(1) or "") or {}
    except yaml.YAMLError as e:
        raise ItemError(f"invalid frontmatter: {str(e).splitlines()[0]}") from e
    if not isinstance(fm, dict):
        raise ItemError("frontmatter is not a mapping")
    if not fm.get("id"):
        raise ItemError("missing id")
    body = text[m.end():]
    if body.startswith("\n"):                                     # Backlog.md's blank line after the closing ---
        body = body[1:]
    return Item(_plain(fm), body, path)


def _ordered(fm: dict) -> dict:
    fm = {k: v for k, v in fm.items() if v is not None}
    known = [k for k in FIELD_ORDER if k in fm]
    other = [k for k in fm if k not in FIELD_ORDER and not str(k).startswith("x-")]
    xs = [k for k in fm if str(k).startswith("x-")]
    return {k: fm[k] for k in known + other + xs}


def serialize_item(item: Item) -> str:
    fm = yaml.dump(_ordered(item.fm), Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False,
                   width=10**9)
    return f"---\n{fm}---\n\n{item.body}"


_BAD = re.compile(r'[/\\:*?"<>|]')


def sanitize_title(title: str) -> str:
    s = " ".join(_BAD.sub("", title).split()).rstrip(". ")
    if len(s) > 60:
        cut = s[:60]
        if s[60] != " " and " " in cut:                          # at a word boundary
            cut = cut.rsplit(" ", 1)[0]
        s = cut.rstrip(". ")
    return s or "untitled"


def file_name(item_id: str, title: str) -> str:
    return f"{item_id.lower()} - {sanitize_title(title)}.md"


def _block(body: str, tag: str) -> str | None:
    m = re.search(rf"<!-- {tag}:BEGIN -->\n?(.*?)<!-- {tag}:END -->", body, re.S)
    return m.group(1) if m else None


def checklist(body: str, kind: Literal["AC", "DOD"]) -> list[dict]:
    block = _block(body, kind) or ""
    return [{"n": int(n), "done": mark.lower() == "x", "text": text.strip()}
            for mark, n, text in re.findall(r"^- \[([ xX])\] #(\d+) (.*)$", block, re.M)]


def description(body: str) -> str:
    return (_block(body, "SECTION:DESCRIPTION") or "").strip()


def _read_template(name: str, lang: str) -> str:
    f = TEMPLATES / lang / name
    if not f.exists():
        f = TEMPLATES / "en" / name
    return f.read_text(encoding="utf-8")


def default_dod(lang: str) -> list[str]:
    return [ln.strip() for ln in _read_template("dod.txt", lang).splitlines() if ln.strip()]


def new_body(type_: str, lang: str, dod: list[str]) -> str:
    """Section headers and markers are Backlog.md's (English) in every language; only the prompts inside are translated."""
    desc = _read_template(f"{type_}.md", lang).strip()
    checks = "".join(f"- [ ] #{i} {t}\n" for i, t in enumerate(dod, 1))
    return ("## Description\n<!-- SECTION:DESCRIPTION:BEGIN -->\n" + desc + "\n<!-- SECTION:DESCRIPTION:END -->\n\n"
            "## Acceptance Criteria\n<!-- AC:BEGIN -->\n<!-- AC:END -->\n\n"
            "## Definition of Done\n<!-- DOD:BEGIN -->\n" + checks + "<!-- DOD:END -->\n")


def load_dir(d: Path) -> tuple[list[Item], list[dict]]:
    items, problems = [], []
    if not d.is_dir():
        return items, problems
    for f in sorted(d.glob("*.md")):
        try:
            items.append(parse_item(f.read_text(encoding="utf-8"), f))
        except (ItemError, UnicodeDecodeError, OSError) as e:
            problems.append({"path": f, "error": str(e)})
    return items, problems
