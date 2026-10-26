"""Edit and confirm the C4 model from the portal (S13). Elements and relations are read from the .c4 files with their
line ranges; a change rewrites only the element's own block (or one relation's lines), so the rest of each file stays
byte for byte. Changes that cannot be valid are refused before writing, and when LikeC4 is installed the model is
validated after writing and put back if it broke. Confirming removes #ai-draft, adds #confirmed and records who and
when in the element's metadata."""
from __future__ import annotations

import datetime as dt
import re

from .common import CTX, DOCS, which
from .harness.locks import FileLock
from .harness.symbols import _strip

ARCH = DOCS / "architecture"
LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "c4-model.lock"
STR = r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\""
NAME = r"[A-Za-z_][\w-]*"
HEADER = re.compile(rf"^(\s*)({NAME})\s*=\s*({NAME})\b(\s*(?:{STR}))?(\s*(?:{STR}))?")
EXTEND = re.compile(r"^\s*extend\s+([\w.-]+)\s*\{")
RELATION = re.compile(rf"^\s*(\w[\w.-]*?)?\s*(?:-\[({NAME})\]->|->)\s*([\w.-]+)(?:\s*({STR}))?")
PROP = re.compile(rf"^\s*(technology|description|title|link|icon|notation)\s+({STR})\s*$")
META_PAIR = re.compile(rf"({NAME})\s+({STR})")
VIEW = re.compile(r"^\s*(?:dynamic\s+|deployment\s+)?view\s+([\w-]+)(?:\s+of\s+([\w.-]+))?")
EDITABLE = ("title", "technology", "description", "kind")


class C4Error(ValueError):
    """LikeC4 rejected the model after a change (the change was put back)."""


def unquote(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    return re.sub(r"\\(.)", r"\1", s[1:-1])


def quote(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    return '"' + value.replace('"', "'") + '"'


def validate() -> tuple[bool, str]:
    """LikeC4's own check when it is installed; without it only the structural checks done before writing apply."""
    if not which("likec4"):
        return True, ""
    from . import env
    return env.arch_validate()


# ---------- reading ----------
def _load() -> dict[str, str]:
    return {f.relative_to(ARCH).as_posix(): f.read_text(encoding="utf-8")
            for f in sorted(ARCH.rglob("*.c4"))} if ARCH.is_dir() else {}


def _depths(lines: list[str]) -> list[int]:
    """Brace depth before each line (strings and comments ignored)."""
    out, d = [], 0
    for line in lines:
        out.append(d)
        code = _strip(line)
        d += code.count("{") - code.count("}")
    return out


def _end(lines: list[str], i: int, depths: list[int]) -> int:
    code = _strip(lines[i])
    if code.count("{") <= code.count("}"):
        return i
    for j in range(i + 1, len(lines)):
        if depths[j + 1 if j + 1 < len(depths) else j] <= depths[i] and j + 1 < len(depths) or \
                (j + 1 == len(depths) and depths[j] + _strip(lines[j]).count("{") - _strip(lines[j]).count("}") <= depths[i]):
            return j
    return len(lines) - 1


def _own(lines: list[str], el: dict, depths: list[int]) -> list[int]:
    """Indexes of the lines directly inside an element's block (not inside a child or a nested block)."""
    base = depths[el["start"]]
    return [i for i in range(el["start"] + 1, el["end"]) if depths[i] == base + 1]


def _parse_file(rel: str, text: str, elements: dict, relations: list, kinds: set, rel_kinds: set) -> None:
    lines = text.split("\n")
    depths = _depths(lines)
    stack: list[tuple[str, str | None, int]] = []        # (what, fqn, depth at its opening line)
    for i, line in enumerate(lines):
        code = _strip(line)
        d = depths[i]
        while stack and d <= stack[-1][2]:
            stack.pop()
        top = stack[-1] if stack else None
        scope = next((f for what, f, _ in reversed(stack) if what in ("element", "extend")), None)
        opens = code.count("{") > code.count("}")
        if top is None:
            if re.match(r"^\s*specification\s*\{", code):
                stack.append(("spec", None, d)) if opens else None
            elif re.match(r"^\s*model\s*\{", code):
                stack.append(("model", None, d)) if opens else None
            elif opens:
                stack.append(("other", None, d))
            continue
        if top[0] == "spec":
            if m := re.match(rf"^\s*element\s+({NAME})", code):
                kinds.add(m.group(1))
            elif m := re.match(rf"^\s*relationship\s+({NAME})", code):
                rel_kinds.add(m.group(1))
            if opens:
                stack.append(("other", None, d))
            continue
        if top[0] not in ("model", "element", "extend"):
            if opens:
                stack.append(("other", None, d))
            continue
        if m := EXTEND.match(code):
            stack.append(("extend", m.group(1), d))
        elif (m := HEADER.match(line)) and m.group(2) not in ("metadata", "style"):
            fqn = f"{scope}.{m.group(2)}" if scope else m.group(2)
            end = _end(lines, i, depths)
            elements[fqn] = {"fqn": fqn, "name": m.group(2), "kind": m.group(3), "file": rel, "start": i, "end": end,
                             "indent": m.group(1), "title": unquote(m.group(4)) or m.group(2),
                             "headerDescription": m.group(5) is not None, "description": unquote(m.group(5))}
            if opens:
                stack.append(("element", fqn, d))
        elif m := RELATION.match(line):
            end = _end(lines, i, depths)
            relations.append({"from": m.group(1) or scope, "rawTo": m.group(3), "label": unquote(m.group(4)),
                              "kind": m.group(2), "file": rel, "start": i, "end": end, "scope": scope})
            if opens:
                stack.append(("other", None, d))
        elif opens:
            stack.append(("other", None, d))


def _details(texts: dict[str, str], el: dict) -> dict:
    lines = texts[el["file"]].split("\n")
    depths = _depths(lines)
    own = _own(lines, el, depths)
    inline = ""
    if el["start"] == el["end"] and "{" in lines[el["start"]]:
        head = lines[el["start"]]
        inline = head[head.index("{") + 1:head.rindex("}")] if "}" in head else ""
    body = [lines[i] for i in own] + [inline]
    tags = [t for line in body if line.strip().startswith("#") for t in re.findall(r"#([\w-]+)", _strip(line))]
    props, meta = {}, {}
    for i in own:
        if m := PROP.match(lines[i]):
            props[m.group(1)] = unquote(m.group(2))
        elif re.match(r"^\s*metadata\s*\{", lines[i]):
            j = _end(lines, i, depths)
            meta = {k: unquote(v) for k, v in META_PAIR.findall(" ".join(lines[i:j + 1]).split("{", 1)[1])}
    el = {**el, "tags": tags, "technology": props.get("technology", ""), "metadata": meta}
    if not el["headerDescription"] and "description" in props:
        el["description"] = props["description"]
    if "title" in props:
        el["title"] = props["title"]
    el.update(draft="ai-draft" in tags, confirmed="confirmed" in tags,
              confirmedBy=meta.get("confirmed-by"), confirmedAt=meta.get("confirmed-at"), line=el["start"] + 1)
    return el


def _resolve(name: str, scope: str | None, elements: dict) -> str | None:
    if not name:
        return None
    parts = scope.split(".") if scope else []
    for n in range(len(parts), -1, -1):
        cand = ".".join(parts[:n] + [name])
        if cand in elements:
            return cand
    hits = [f for f in elements if f.endswith("." + name)]
    return hits[0] if len(hits) == 1 else None


def index(texts: dict[str, str] | None = None) -> dict:
    """{elements: {fqn: {...}}, relations: [{from, to, label, kind, file, start, end}], kinds, relKinds}."""
    texts = _load() if texts is None else texts
    elements: dict = {}
    raw: list = []
    kinds: set = set()
    rel_kinds: set = set()
    for rel, text in texts.items():
        _parse_file(rel, text, elements, raw, kinds, rel_kinds)
    elements = {f: _details(texts, el) for f, el in elements.items()}
    relations = []
    for r in raw:
        src = r["from"] if r["from"] in elements else _resolve(r["from"], r["scope"], elements)
        dst = _resolve(r["rawTo"], r["scope"], elements)
        if src and dst:
            relations.append({k: v for k, v in {**r, "from": src, "to": dst}.items() if k not in ("rawTo", "scope")})
    return {"elements": elements, "relations": relations, "kinds": sorted(kinds), "relKinds": sorted(rel_kinds)}


def view_elements(view: str, idx: dict | None = None, texts: dict[str, str] | None = None) -> list[str]:
    """The elements a view shows: its scope and the scope's children for `include *` (top-level elements in a view
    without scope), `x.*` children, named elements and the ends of a dynamic view's steps."""
    texts = _load() if texts is None else texts
    idx = idx or index(texts)
    els = idx["elements"]
    children = lambda p: [f for f in els if f.rsplit(".", 1)[0] == p and "." in f]  # noqa: E731
    for text in texts.values():
        lines = text.split("\n")
        depths = _depths(lines)
        for i, line in enumerate(lines):
            m = VIEW.match(_strip(line))
            if not m or m.group(1) != view:
                continue
            scope, out = m.group(2), []
            body = " ".join(_strip(l) for l in lines[i:_end(lines, i, depths) + 1])
            for inc in re.findall(r"\binclude\s+([^{}]*?)(?=\binclude\b|\bexclude\b|\bstyle\b|\bautoLayout\b|}|$)", body):
                for token in (t.strip() for t in inc.split(",")):
                    if token == "*":
                        out += [scope, *children(scope)] if scope else [f for f in els if "." not in f]
                    elif token.endswith(".*"):
                        out += children(_resolve(token[:-2], scope, els) or token[:-2])
                    elif re.fullmatch(r"[\w.-]+", token):
                        out.append(_resolve(token, scope, els) or token)
            for a, b in re.findall(r"(\w[\w.-]*?)\s*(?:-\[[\w-]+\]->|->)\s*([\w.-]+)", body):
                out += [_resolve(a, scope, els) or a, _resolve(b, scope, els) or b]
            return [f for f in dict.fromkeys(out) if f in els]
    raise KeyError(view)


# ---------- writing ----------
def _expand(lines: list[str], el: dict) -> list[str]:
    """A one-line element as a block, so properties can go inside it."""
    if el["start"] != el["end"]:
        return lines
    head, indent = lines[el["start"]], el["indent"]
    inline = ""
    if "{" in head:
        inline = head[head.index("{") + 1:head.rindex("}")].strip() if "}" in head else ""
        head = head[:head.index("{")]
    block = [head.rstrip() + " {", *([indent + "  " + inline] if inline else []), indent + "}"]
    return lines[:el["start"]] + block + lines[el["start"] + 1:]


def _relocate(lines: list[str], fqn: str, rel: str) -> dict:
    texts = {rel: "\n".join(lines)}
    elements: dict = {}
    _parse_file(rel, texts[rel], elements, [], set(), set())
    return _details(texts, elements[fqn])


def _set_prop(lines: list[str], el: dict, prop: str, value: str) -> list[str]:
    depths = _depths(lines)
    own = _own(lines, el, depths)
    at = next((i for i in own if (m := PROP.match(lines[i])) and m.group(1) == prop), None)
    new = [f"{el['indent']}  {prop} {quote(value)}"] if value else []
    if at is not None:
        return lines[:at] + new + lines[at + 1:]
    if not value:
        return lines
    after = el["start"]
    for i in own:
        if not (lines[i].strip().startswith("#") or PROP.match(lines[i])):
            break
        after = i
    return lines[:after + 1] + new + lines[after + 1:]


def _set_header(lines: list[str], el: dict, group: int, value: str | None) -> list[str]:
    m = HEADER.match(lines[el["start"]])
    head = lines[el["start"]]
    if group == 3:
        head = head[:m.start(3)] + value + head[m.end(3):]
    elif group == 4:
        new = f" {quote(value)}"
        head = head[:m.start(4)] + new + head[m.end(4):] if m.group(4) else head[:m.end(3)] + new + head[m.end(3):]
    elif group == 5:
        new = f" {quote(value)}" if value else ""
        head = head[:m.start(5)] + new + head[m.end(5):]
    return lines[:el["start"]] + [head] + lines[el["start"] + 1:]


def _set_tags(lines: list[str], el: dict, tags: list[str]) -> list[str]:
    lines = _expand(lines, el)
    el = _relocate(lines, el["fqn"], el["file"])
    own = _own(lines, el, _depths(lines))
    tagged = [i for i in own if lines[i].strip().startswith("#")]
    keep = [l for i, l in enumerate(lines) if i not in tagged]
    row = [f"{el['indent']}  " + " ".join(f"#{t}" for t in tags)] if tags else []
    return keep[:el["start"] + 1] + row + keep[el["start"] + 1:]


def _set_meta(lines: list[str], el: dict, meta: dict) -> list[str]:
    lines = _expand(lines, el)
    el = _relocate(lines, el["fqn"], el["file"])
    depths = _depths(lines)
    own = _own(lines, el, depths)
    ind = el["indent"] + "  "
    block = [f"{ind}metadata {{", *(f"{ind}  {k} {quote(v)}" for k, v in meta.items()), f"{ind}}}"]
    at = next((i for i in own if re.match(r"^\s*metadata\s*\{", lines[i])), None)
    if at is not None:
        return lines[:at] + block + lines[_end(lines, at, depths) + 1:]
    after = el["start"]
    for i in own:
        if not (lines[i].strip().startswith("#") or PROP.match(lines[i])):
            break
        after = i
    return lines[:after + 1] + block + lines[after + 1:]


def _apply_edit(texts: dict[str, str], fqn: str, changes: dict, kinds: list[str]) -> None:
    idx = index(texts)
    if fqn not in idx["elements"]:
        raise KeyError(fqn)
    for k, v in changes.items():
        if k not in EDITABLE:
            raise ValueError(f"{k} cannot be edited here")
        if not isinstance(v, str) or "\n" in v or "\r" in v:
            raise ValueError(f"{k}: one line of text")
    if "title" in changes and not changes["title"].strip():
        raise ValueError("title: an element needs a title")
    if "kind" in changes and changes["kind"] not in kinds:
        raise ValueError(f"kind: one of {', '.join(kinds)}")
    el = idx["elements"][fqn]
    rel = el["file"]
    lines = texts[rel].split("\n")
    if "kind" in changes:
        lines = _set_header(lines, el, 3, changes["kind"])
    if "title" in changes:
        lines = _set_header(lines, _relocate(lines, fqn, rel), 4, changes["title"].strip())
    if "description" in changes and el["headerDescription"]:
        lines = _set_header(lines, _relocate(lines, fqn, rel), 5, changes["description"].strip())
    for prop in ("technology", *(("description",) if not el["headerDescription"] else ())):
        if prop in changes:
            lines = _expand(lines, _relocate(lines, fqn, rel))
            lines = _set_prop(lines, _relocate(lines, fqn, rel), prop, changes[prop].strip())
    texts[rel] = "\n".join(lines)


def _apply_confirm(texts: dict[str, str], fqn: str, by: str, today: str) -> None:
    el = index(texts)["elements"].get(fqn)
    if el is None:
        raise KeyError(fqn)
    tags = [t for t in el["tags"] if t != "ai-draft"] + ([] if "confirmed" in el["tags"] else ["confirmed"])
    meta = {**el["metadata"], "confirmed-by": el["metadata"].get("confirmed-by", by) if el["confirmed"] else by,
            "confirmed-at": el["metadata"].get("confirmed-at", today) if el["confirmed"] else today}
    if tags == el["tags"] and meta == el["metadata"]:
        return
    lines = texts[el["file"]].split("\n")
    if tags != el["tags"]:
        lines = _set_tags(lines, el, tags)
    if meta != el["metadata"]:
        lines = _set_meta(lines, _relocate(lines, fqn, el["file"]), meta)
    texts[el["file"]] = "\n".join(lines)


def _write(change) -> dict:
    """Apply `change(texts)` to the files under the model lock, validate, put everything back if LikeC4 says no."""
    with FileLock(LOCK, info={"what": "c4 edit"}):
        before = _load()
        texts = dict(before)
        result = change(texts)
        changed = {rel: t for rel, t in texts.items() if t != before.get(rel)}
        for rel, t in changed.items():
            (ARCH / rel).write_text(t, encoding="utf-8", newline="\n")
        if changed:
            ok, msg = validate()
            if not ok:
                for rel in changed:
                    (ARCH / rel).write_text(before[rel], encoding="utf-8", newline="\n")
                raise C4Error(f"LikeC4 rejected the change, nothing was saved: {msg}")
        return result


def edit(fqn: str, **changes) -> dict:
    """Change an element's title, technology, description or kind (to a kind the specification declares)."""
    kinds = index()["kinds"]
    _write(lambda texts: _apply_edit(texts, fqn, changes, kinds))
    return index()["elements"][fqn]


def confirm(fqns: list[str], by: str, today: str | None = None) -> list[str]:
    today = today or dt.date.today().isoformat()

    def change(texts):
        for f in fqns:
            _apply_confirm(texts, f, by, today)
        return list(fqns)
    return _write(change)


def confirm_view(view: str, by: str, today: str | None = None) -> list[str]:
    return confirm(view_elements(view), by, today)


def add_relation(src: str, dst: str, label: str = "", kind: str | None = None) -> dict:
    def change(texts):
        idx = index(texts)
        els = idx["elements"]
        for name in (src, dst):
            if name not in els:
                raise ValueError(f"{name} is not an element of the model")
        if kind and kind not in idx["relKinds"]:
            raise ValueError(f"kind: one of {', '.join(idx['relKinds'])}")
        if "\n" in label:
            raise ValueError("label: one line of text")
        rel = els[src]["file"]
        lines = texts[rel].split("\n")
        depths = _depths(lines)
        model = next(i for i, l in enumerate(lines) if re.match(r"^\s*model\s*\{", _strip(l))
                     and i <= els[src]["start"] <= _end(lines, i, depths))
        close = _end(lines, model, depths)
        indent = re.match(r"^\s*", lines[model]).group(0) + "  "
        arrow = f"-[{kind}]->" if kind else "->"
        row = f"{indent}{src} {arrow} {dst}" + (f" {quote(label.strip())}" if label.strip() else "")
        texts[rel] = "\n".join(lines[:close] + [row] + lines[close:])
        return {"from": src, "to": dst, "label": label.strip(), "kind": kind}
    return _write(change)


def remove_relation(src: str, dst: str, label: str = "") -> dict:
    def change(texts):
        r = next((r for r in index(texts)["relations"]
                  if (r["from"], r["to"], r["label"]) == (src, dst, label or "")), None)
        if r is None:
            raise KeyError(f"{src} -> {dst} '{label}'")
        lines = texts[r["file"]].split("\n")
        texts[r["file"]] = "\n".join(lines[:r["start"]] + lines[r["end"] + 1:])
        return {"from": src, "to": dst, "label": label}
    return _write(change)


def _mentions(token: str, scope: str | None, els: dict, gone: set[str]) -> bool:
    """Whether a view's include/exclude token, or a dynamic step, names an element that is going."""
    names = (n.rstrip(".") for n in re.findall(r"[A-Za-z_][\w.-]*", token))
    return any(_resolve(n, scope, els) in gone for n in names if n and n not in ("where", "with"))


def _prune_view(lines: list[str], start: int, end: int, scope: str | None, dynamic: bool, els: dict,
                gone: set[str]) -> set[int]:
    """Lines of one view to drop or rewrite so it no longer names `gone`: tokens out of include/exclude lists (a list
    may go on over the next lines), steps out of a dynamic view. Lines with a block of their own are left to LikeC4."""
    depths = _depths(lines)
    drop: set[int] = set()
    listing = False                                               # inside an include/exclude list that goes on
    for i in range(start + 1, end):
        code = _strip(lines[i]).rstrip()
        if depths[i] != depths[start] + 1 or not code.strip():
            continue
        if "{" in code or "}" in code:
            listing = False
            continue
        if dynamic and (m := RELATION.match(code)) and m.group(1) and _mentions(f"{m.group(1)} {m.group(3)}", scope, els, gone):
            drop.add(i)
            continue
        m = re.match(r"^(\s*)(include|exclude)\b\s*(.*)$", code)
        if not m and not listing:
            continue
        indent, word, rest = (m.group(1), m.group(2) + " ", m.group(3)) if m else (re.match(r"^\s*", code).group(0), "", code.strip())
        more = rest.endswith(",") or (m is not None and not rest)
        tokens = [x.strip() for x in rest.rstrip(",").split(",") if x.strip()]
        keep = [x for x in tokens if not _mentions(x, scope, els, gone)]
        listing = more
        if keep == tokens:
            continue
        if not keep and not (m and more):
            drop.add(i)
        else:
            lines[i] = indent + word + ", ".join(keep) + ("," if more and keep else "")
    # a list whose last item went: no trailing comma, and a keyword left with nothing after it goes too
    alive = [i for i in range(start + 1, end) if i not in drop and _strip(lines[i]).strip()]
    for n, i in enumerate(alive):
        nxt = alive[n + 1] if n + 1 < len(alive) else None
        follows = nxt is not None and not re.match(r"^\s*(include|exclude|style|autoLayout|title|description|link|"
                                                   r"navigateTo|global|\}|[\w.-]+\s*(->|-\[))", _strip(lines[nxt]))
        if lines[i].rstrip().endswith(",") and not follows:
            lines[i] = lines[i].rstrip()[:-1]
        if re.fullmatch(r"\s*(include|exclude)\s*", _strip(lines[i])) and not follows:
            drop.add(i)
    return drop


def _apply_remove(texts: dict[str, str], fqn: str) -> dict:
    idx = index(texts)
    els = idx["elements"]
    if fqn not in els:
        raise KeyError(fqn)
    gone = {f for f in els if f == fqn or f.startswith(fqn + ".")}
    views = []
    for rel, text in texts.items():
        lines = text.split("\n")
        depths = _depths(lines)
        for i, line in enumerate(lines):
            m = VIEW.match(_strip(line))
            if m and m.group(2) and _resolve(m.group(2), None, els) in gone:
                views.append(m.group(1))
    if views:
        raise ValueError(f"{fqn} is what view(s) {', '.join(views)} show: remove or change those views first")
    removed_rels = [r for r in idx["relations"] if r["from"] in gone or r["to"] in gone]
    for rel, text in texts.items():
        lines = text.split("\n")
        depths = _depths(lines)
        drop: set[int] = set()
        for f in gone:
            if els[f]["file"] == rel:
                drop.update(range(els[f]["start"], els[f]["end"] + 1))
        for r in removed_rels:
            if r["file"] == rel:
                drop.update(range(r["start"], r["end"] + 1))
        for i, line in enumerate(lines):
            code = _strip(line)
            if (m := EXTEND.match(code)) and _resolve(m.group(1), None, els) in gone:
                drop.update(range(i, _end(lines, i, depths) + 1))
            elif m := VIEW.match(code):
                drop |= _prune_view(lines, i, _end(lines, i, depths), m.group(2), code.lstrip().startswith("dynamic"),
                                    els, gone)
        if not drop:
            continue
        kept = [l for i, l in enumerate(lines) if i not in drop]
        out: list[str] = []
        for line in kept:                                   # a block that went leaves no double blank line behind
            if not line.strip() and out and not out[-1].strip():
                continue
            out.append(line)
        texts[rel] = "\n".join(out)
    return {"removed": sorted(gone), "relations": len(removed_rels)}


def remove_element(fqn: str) -> dict:
    """Remove an element with its children (fragments that extend it included), every relation to or from them and the
    places views name them. An element a view is scoped to (`view x of it`) is refused: that view would be empty."""
    return _write(lambda texts: _apply_remove(texts, fqn))
