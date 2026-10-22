"""Whiteboards (R34, H24): Excalidraw boards versioned in cam-docs (docs/boards/<name>.excalidraw), free-form or
started from a C4 view — one box per element, an arrow per relation — for people to annotate. Plain JSON in git; the
portal edits them, nothing else reads them."""
from __future__ import annotations

import json, re, zlib
from pathlib import Path

from .common import DOCS

BOARDS = DOCS / "boards"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
ELEMENT = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*(?:'([^']*)'|\"([^\"]*)\")?")
RELATION = re.compile(r"^\s*([\w.]*)\s*(?:-\[[\w-]+\])?->\s*([\w.]+)(?:\s*(?:'([^']*)'|\"([^\"]*)\"))?")
VIEW = re.compile(r"^\s*(?:dynamic\s+)?view\s+(\w+)(?:\s+of\s+([\w.]+))?")


class BoardError(ValueError):
    """A board name or content the portal cannot store."""


def _file(name: str) -> Path:
    if not NAME.fullmatch(name or ""):
        raise BoardError("board names use lowercase letters, digits and dashes")
    return BOARDS / f"{name}.excalidraw"


def boards() -> list[dict]:
    return [{"name": f.stem, "updated": int(f.stat().st_mtime)} for f in sorted(BOARDS.glob("*.excalidraw"))] \
        if BOARDS.is_dir() else []


def read(name: str) -> dict:
    f = _file(name)
    if not f.is_file():
        raise KeyError(name)
    return json.loads(f.read_text(encoding="utf-8"))


def save(name: str, data: dict) -> dict:
    if not isinstance(data, dict) or data.get("type") != "excalidraw" or not isinstance(data.get("elements"), list):
        raise BoardError("not an Excalidraw scene (type: excalidraw, elements: [...])")
    keep = {"type": "excalidraw", "version": data.get("version", 2), "source": "camaron",
            "elements": data["elements"], "appState": {k: v for k, v in (data.get("appState") or {}).items()
                                                      if k in ("viewBackgroundColor", "gridSize")},
            "files": data.get("files") or {}}
    f = _file(name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(keep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"name": name, "elements": len(keep["elements"])}


# ---------- a sketch from a C4 view ----------
def model() -> dict:
    """{elements: {fqn: {kind, title}}, relations: [(from, to, label)], views: {id: scope or None}} from the .c4 files."""
    elements, relations, views = {}, [], {}
    arch = DOCS / "architecture"
    for f in sorted(arch.rglob("*.c4")) if arch.is_dir() else []:
        stack: list[tuple[str | None, int]] = []
        depth = 0
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            code = re.sub(r"//.*$", "", line)
            if m := VIEW.match(code):
                views[m.group(1)] = m.group(2)
            elif m := RELATION.match(code):
                parent = next((n for n, _ in reversed(stack) if n), None)
                src = m.group(1) or parent                     # `-> target` inside an element: that element
                if src:
                    relations.append((src, m.group(2), m.group(3) or m.group(4) or ""))
            elif (m := ELEMENT.match(code)) and m.group(2) not in ("model", "views", "specification", "deployment"):
                parent = next((n for n, _ in reversed(stack) if n), None)
                fqn = f"{parent}.{m.group(1)}" if parent else m.group(1)
                elements[fqn] = {"kind": m.group(2), "title": m.group(3) or m.group(4) or m.group(1)}
                if "{" in code:
                    stack.append((fqn, depth))
            elif "{" in code and not code.strip().startswith(("model", "views", "specification")):
                stack.append((None, depth))
            depth += code.count("{") - code.count("}")
            while stack and depth <= stack[-1][1]:
                stack.pop()
    return {"elements": elements, "relations": relations, "views": views}


def _resolve(name: str, elements: dict) -> str | None:
    if name in elements:
        return name
    return next((fqn for fqn in elements if fqn.endswith("." + name)), None)


def _base(seed: int, **kw) -> dict:
    return {"angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent", "fillStyle": "solid",
            "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "roundness": {"type": 3}, "seed": seed, "version": 1, "versionNonce": seed, "isDeleted": False,
            "boundElements": [], "updated": 1, "link": None, "locked": False, **kw}


def sketch(view: str) -> dict:
    """An Excalidraw scene for a C4 view: its elements in a grid, an arrow per relation between them."""
    m = model()
    if view not in m["views"]:
        raise KeyError(view)
    scope = m["views"][view]
    els = m["elements"]
    if scope:
        chosen = [f for f in els if f.startswith(scope + ".") and f.count(".") == scope.count(".") + 1]
    else:
        chosen = [f for f in els if "." not in f or f.count(".") == 1 and f.split(".")[0] not in els]
        chosen = chosen or list(els)
    top = lambda f: next((c for c in chosen if f == c or f.startswith(c + ".")), None)  # noqa: E731
    out, ids = [], {}
    for i, fqn in enumerate(chosen):
        x, y = 80 + (i % 3) * 320, 80 + (i // 3) * 200
        rid, tid = f"el-{fqn}", f"tx-{fqn}"
        seed = zlib.crc32(fqn.encode())
        ids[fqn] = rid
        out.append(_base(seed, id=rid, type="rectangle", x=x, y=y, width=240, height=100,
                         boundElements=[{"type": "text", "id": tid}]))
        label = f"{els[fqn]['title']}\n[{els[fqn]['kind']}]"
        out.append(_base(seed + 1, id=tid, type="text", x=x + 10, y=y + 30, width=220, height=40, text=label,
                         originalText=label, fontSize=16, fontFamily=1, textAlign="center", verticalAlign="middle",
                         containerId=rid, lineHeight=1.25, roundness=None))
    for n, (a, b, label) in enumerate(m["relations"]):
        sa, sb = _resolve(a, els), _resolve(b, els)
        ta, tb = top(sa) if sa else None, top(sb) if sb else None
        if not ta or not tb or ta == tb:
            continue
        ra = next(e for e in out if e["id"] == ids[ta])
        rb = next(e for e in out if e["id"] == ids[tb])
        x0, y0 = ra["x"] + ra["width"] / 2, ra["y"] + ra["height"] / 2
        x1, y1 = rb["x"] + rb["width"] / 2, rb["y"] + rb["height"] / 2
        aid = f"rel-{n}"
        out.append(_base(zlib.crc32(aid.encode()), id=aid, type="arrow", x=x0, y=y0, width=abs(x1 - x0),
                         height=abs(y1 - y0), points=[[0, 0], [x1 - x0, y1 - y0]], roundness={"type": 2},
                         startBinding={"elementId": ra["id"], "focus": 0, "gap": 4},
                         endBinding={"elementId": rb["id"], "focus": 0, "gap": 4}, startArrowhead=None,
                         endArrowhead="arrow", label=label))
        ra["boundElements"].append({"type": "arrow", "id": aid})
        rb["boundElements"].append({"type": "arrow", "id": aid})
    return {"type": "excalidraw", "version": 2, "source": "camaron", "elements": out,
            "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}
