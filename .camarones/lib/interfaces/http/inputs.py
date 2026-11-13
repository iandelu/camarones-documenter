"""A request body's fields, checked before anything is written: a wrong type is a ValueError, which the server answers
with a 400 that names the field."""
from __future__ import annotations


def text(b: dict, key: str, required: bool = False) -> str | None:
    v = b.get(key)
    if v is None and not required:
        return None
    if not isinstance(v, str):
        raise ValueError(f"{key} must be text")
    return v


def dim(b: dict, key: str, bounds: tuple[int, int], default: int | None = None) -> int:
    """A terminal's columns or rows: a whole number within `bounds` (true is not one), `default` when not given."""
    v = default if b.get(key) is None else b[key]
    if isinstance(v, bool) or not isinstance(v, int) or not bounds[0] <= v <= bounds[1]:
        raise ValueError(f"{key}: a whole number from {bounds[0]} to {bounds[1]}")
    return v


def text_list(b: dict, key: str) -> list[str]:
    v = b.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{key} must be a list of text")
    return v


def doc_refs(b: dict) -> list[str]:
    v = b.get("docs")
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("docs must be a list")
    refs = []
    for d in v:
        if isinstance(d, str):
            refs.append(d)
        elif isinstance(d, dict) and isinstance(d.get("path"), str) and isinstance(d.get("section", ""), (str, type(None))):
            refs.append(f"{d['path']}#{d['section']}" if d.get("section") else d["path"])
        else:
            raise ValueError("each doc is a text ref or {path, section} with text values")
    return refs
