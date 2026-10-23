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


# Rows top to bottom: people, apps, services, stores, external systems. Words come from the kind's name (mobileApp →
# mobile, app), so a project's own kinds land in a sensible row; anything else is a service.
PEOPLE = {"actor", "person", "user", "customer"}
APPS = {"app", "webapp", "web", "ui", "frontend", "front", "mobile", "browser", "spa", "site", "portal"}
STORES = {"database", "db", "datastore", "store", "storage", "queue", "topic", "cache", "bucket", "bus", "stream"}
BOX_H, ROW_GAP, COL_GAP, LANE, FONT = 100, 160, 64, 12, 16


def _row(kind: str) -> int:
    words = {w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", kind)} | {kind.lower()}
    if words & PEOPLE:
        return 0
    if "external" in words:
        return 4
    if words & STORES:
        return 3
    return 1 if words & APPS else 2


def _pairs(m: dict, els: dict, top) -> dict:
    """One edge per pair of shown elements, keyed (from, to) by its first relation: labels merged, `both` when the
    other direction exists too."""
    pairs: dict = {}
    for a, b, label in m["relations"]:
        sa, sb = _resolve(a, els), _resolve(b, els)
        ta, tb = (top(sa) if sa else None), (top(sb) if sb else None)
        if not ta or not tb or ta == tb:
            continue
        key = (tb, ta) if (tb, ta) in pairs else (ta, tb)
        e = pairs.setdefault(key, {"labels": [], "both": False})
        e["both"] = e["both"] or key != (ta, tb)
        if label and label not in e["labels"]:
            e["labels"].append(label)
    return pairs


def _simplify(pts: list) -> list:
    out = []
    for p in pts:
        if out and p == out[-1]:
            continue
        if len(out) >= 2 and (out[-2][0] == out[-1][0] == p[0] or out[-2][1] == out[-1][1] == p[1]):
            out[-1] = p
        else:
            out.append(p)
    return out


def _layout(chosen: list, els: dict, pairs: dict) -> tuple[dict, dict, dict]:
    """Layered layout without a layout engine: rows by kind, an invisible waypoint per row an edge crosses (so lines
    pass between boxes, never through them), order inside rows by barycentre, edges routed through lanes in the gaps
    between rows. Returns boxes {fqn: (x, y, w)}, paths {pair: [(x, y)…]} and widths."""
    used = sorted({_row(els[f]["kind"]) for f in chosen})
    rowof = {f: used.index(_row(els[f]["kind"])) for f in chosen}
    rows = [[f for f in chosen if rowof[f] == r] for r in range(len(used))]
    chains = {}
    for a, b in pairs:
        up, down = (a, b) if rowof[a] <= rowof[b] else (b, a)
        ways = [f"~{a}~{b}~{r}" for r in range(rowof[up] + 1, rowof[down])]
        for r, w in enumerate(ways, start=rowof[up] + 1):
            rows[r].append(w)
            rowof[w] = r
        chains[(a, b)] = [up, *ways, down]
    links: dict = {n: set() for ns in rows for n in ns}
    for chain in chains.values():
        for p, q in zip(chain, chain[1:]):
            if rowof[p] != rowof[q]:
                links[p].add(q)
                links[q].add(p)
    for sweep in range(6):
        down = sweep % 2 == 0
        for r in (range(1, len(rows)) if down else range(len(rows) - 2, -1, -1)):
            at = {n: i for ns in rows for i, n in enumerate(ns)}
            ref = r - 1 if down else r + 1

            def bary(n, at=at, ref=ref):
                near = [at[x] for x in links[n] if rowof[x] == ref]
                return sum(near) / len(near) if near else at[n]
            rows[r].sort(key=bary)
    width = {f: max(200, 40 + 10 * max(len(line) for line in _label(els[f]).splitlines())) for f in chosen}
    xs, spans = {}, []
    for ns in rows:
        x = 0
        for n in ns:
            xs[n] = x
            x += width.get(n, 0) + COL_GAP
        spans.append(x - COL_GAP)
    for r, ns in enumerate(rows):
        for n in ns:
            xs[n] += 80 + (max(spans) - spans[r]) / 2
    ys = [80 + r * (BOX_H + ROW_GAP) for r in range(len(rows))]
    centre = lambda n: xs[n] + width.get(n, 0) / 2  # noqa: E731
    sides: dict = {}
    for key, chain in chains.items():
        up, down = chain[0], chain[-1]
        if rowof[up] == rowof[down]:
            sides.setdefault((up, "top"), []).append((centre(down), key))
            sides.setdefault((down, "top"), []).append((centre(up), key))
        else:
            sides.setdefault((up, "bottom"), []).append((centre(chain[1]), key))
            sides.setdefault((down, "top"), []).append((centre(chain[-2]), key))
    port = {}
    for (n, _side), items in sides.items():
        items.sort(key=lambda it: it[0])
        for k, (_x, key) in enumerate(items):
            port[(n, key)] = round(xs[n] + width[n] * (k + 1) / (len(items) + 1), 1)
    lanes: dict = {}

    def lane(gap: int) -> float:
        k = lanes[gap] = lanes.get(gap, -1) + 1
        k %= (ROW_GAP - 48) // LANE
        return ys[gap] + BOX_H + 24 + k * LANE if gap >= 0 else ys[0] - 24 - k * LANE

    paths = {}
    for key, chain in chains.items():
        up, down = chain[0], chain[-1]
        a, b = port[(up, key)], port[(down, key)]
        if rowof[up] == rowof[down]:
            y = lane(rowof[up] - 1)
            pts = [(a, ys[rowof[up]]), (a, y), (b, y), (b, ys[rowof[down]])]
        else:
            stops = [a, *(xs[w] for w in chain[1:-1]), b]
            pts = [(a, ys[rowof[up]] + BOX_H)]
            for i in range(len(stops) - 1):
                y = lane(rowof[up] + i)
                pts += [(stops[i], y), (stops[i + 1], y)]
            pts.append((b, ys[rowof[down]]))
        pts = _simplify(pts)
        paths[key] = pts if chain[0] == key[0] else pts[::-1]
    return {f: (xs[f], ys[rowof[f]]) for f in chosen}, paths, width


def _label(el: dict) -> str:
    return f"{el['title']}\n[{el['kind']}]"


def sketch(view: str) -> dict:
    """An Excalidraw scene for a C4 view, laid out like a diagram (see _layout): a box per element, one arrow per pair
    of elements with its relations' labels as the arrow's text."""
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
    pairs = _pairs(m, els, top)
    at, paths, width = _layout(chosen, els, pairs)
    out, boxes = [], {}
    for fqn in chosen:
        (x, y), w = at[fqn], width[fqn]
        rid, tid = f"el-{fqn}", f"tx-{fqn}"
        seed = zlib.crc32(fqn.encode())
        boxes[fqn] = _base(seed, id=rid, type="rectangle", x=x, y=y, width=w, height=BOX_H,
                           boundElements=[{"type": "text", "id": tid}])
        label = _label(els[fqn])
        out += [boxes[fqn], _base(seed + 1, id=tid, type="text", x=x + 10, y=y + 30, width=w - 20, height=40,
                                  text=label, originalText=label, fontSize=FONT, fontFamily=1, textAlign="center",
                                  verticalAlign="middle", containerId=rid, lineHeight=1.25, roundness=None)]
    for n, ((a, b), edge) in enumerate(pairs.items()):
        pts, aid = paths[(a, b)], f"rel-{n}"
        x0, y0 = pts[0]
        rel = [[round(x - x0, 1), round(y - y0, 1)] for x, y in pts]
        arrow = _base(zlib.crc32(aid.encode()), id=aid, type="arrow", x=x0, y=y0,
                      width=max(p[0] for p in rel) - min(p[0] for p in rel),
                      height=max(p[1] for p in rel) - min(p[1] for p in rel), points=rel, roundness=None,
                      startBinding={"elementId": boxes[a]["id"], "focus": 0, "gap": 4},
                      endBinding={"elementId": boxes[b]["id"], "focus": 0, "gap": 4},
                      startArrowhead="arrow" if edge["both"] else None, endArrowhead="arrow", elbowed=False)
        out.append(arrow)
        boxes[a]["boundElements"].append({"type": "arrow", "id": aid})
        boxes[b]["boundElements"].append({"type": "arrow", "id": aid})
        if edge["labels"]:
            text, lid = " / ".join(edge["labels"]), f"lb-{aid}"
            (px, py), (qx, qy) = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            tw = 8 * len(text)
            arrow["boundElements"].append({"type": "text", "id": lid})
            out.append(_base(zlib.crc32(lid.encode()), id=lid, type="text", x=(px + qx) / 2 - tw / 2,
                             y=(py + qy) / 2 - 10, width=tw, height=20, text=text, originalText=text, fontSize=14,
                             fontFamily=1, textAlign="center", verticalAlign="middle", containerId=aid,
                             lineHeight=1.25, roundness=None))
    return {"type": "excalidraw", "version": 2, "source": "camaron", "elements": out,
            "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}
