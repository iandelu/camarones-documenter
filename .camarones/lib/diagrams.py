"""Diagrams from the code (no AI): Mermaid blocks that `genblocks` writes, refreshes and checks like any generated block.

`ids(kind, repo)` says which blocks a repo has (`None` = one block without `id=`; `[]` = nothing to draw) and
`render(kind, repo, id)` draws one: (block body, sources), or None when that id no longer exists. A diagram shows what
the code states as fact (states, endpoints, who talks to whom); it never invents a transition or a flow: those wait for
a proposal that a person confirms. `states`: one diagram per status enum, the states only. `endpoints-map`: a repo's
endpoints grouped by first path segment, with its datastores, topics and the repos it calls (split over 25 nodes).
System-wide kinds (repo `_system`): `context`, the repos, datastores, brokers and identity providers with the edges of
the first-look scan (identity providers fold into one External node when crowded); `messaging`, one sequence per
topic: its producers, the broker and its consumers."""
from __future__ import annotations

import itertools, re
from pathlib import Path

from .common import DOCS, rel_file, repo_dir
from . import quickarch

KINDS = ("states", "endpoints-map", "context", "messaging")
NODE_LIMIT = 25                                                             # a bigger diagram is a wall, not a picture
SYSTEM = "_system"                                                          # reserved repo name: the whole system
STATE_SUFFIX = re.compile(r"(Status|State|Phase|Stage)$")
STATE_COLUMN = re.compile(r"(status|state|phase|stage)$", re.I)
STATE_SUFFIXES = {".java", ".kt", ".ts", ".py", ".cs", ".go", ".dart", ".sql"}
BRACE_ENUM = re.compile(r"\benum\s+(?:class\s+)?(\w+)[^{;]*\{")            # Java, Kotlin, TypeScript, C#, Dart
PY_ENUM = re.compile(r"^class\s+(\w+)\s*\([^)]*(?:Enum|Flag)\b[^)]*\)\s*:", re.M)    # Enum, IntEnum, StrEnum, IntFlag…
PY_MEMBER = re.compile(r"^(\s+)([A-Za-z]\w*)\s*(?::[^=\n]+)?=(?!=)")
GO_TYPE = re.compile(r"^type\s+(\w+)\s+\w", re.M)
GO_CONSTS = re.compile(r"^const\s*\(\n(.*?)^\)", re.M | re.S)
GO_CONST = re.compile(r"^\s*([A-Za-z]\w*)(?:\s+([A-Za-z_]\w*))?\s*(=.*)?$")
SQL_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?([\w.]+)[`\"\]]?", re.I)
SQL_IN = re.compile(r"[`\"\[]?(\w+)[`\"\]]?\s+IN\s*\(([^)]*)\)", re.I)
COMMENTS = re.compile(r"\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/", re.S)   # strings first
MERMAID_WORDS = {"end", "state", "note", "class", "classdef", "style", "direction", "click", "hide", "scale", "as", "title",
                 "subgraph", "graph", "flowchart",
                 # sequence diagrams: blocks, statements and participants a bare id would be read as
                 "loop", "alt", "opt", "par", "and", "else", "rect", "box", "break", "critical", "option", "link", "links",
                 "activate", "deactivate", "autonumber", "participant", "actor", "create", "destroy", "over", "sequencediagram"}
TRANSITIONS = "transitions: waiting for a proposal"


def _repo(repo: str) -> Path | None:
    d = repo_dir(repo)
    return d if repo != SYSTEM and d.is_dir() else None


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _files(repo: Path) -> list[Path]:
    """The scan files of the repo plus its .sql files, which the architecture scan does not read."""
    from . import genblocks
    skip = quickarch.SKIP_DIRS | genblocks.TEST_DIRS
    sql = itertools.islice((f for f in repo.rglob("*.sql") if f.is_file() and not skip & set(f.relative_to(repo).parts[:-1])),
                           quickarch.MAX_FILES)
    return sorted({*genblocks._scan_files(repo), *sql}, key=lambda f: f.relative_to(repo).as_posix())


def _constants(text: str, i: int) -> list[str]:
    """Names of the enum constants in `text` from `i` (just after the `{`): items split by top-level commas, up to the
    `;` that ends the list or the closing brace. Constructor arguments, bodies and annotations are skipped."""
    depth, quote, escaped, items, item = 0, None, False, [], []
    for c in text[i:]:
        if quote:
            quote, escaped = (None if c == quote and not escaped else quote), c == "\\" and not escaped
        elif c in "\"'`":
            quote = c
        elif c in "({[":
            depth += 1
        elif c in ")}]":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and c in ",;":
            items.append("".join(item))
            item = []
            if c == ";":
                break
            continue
        item.append(c)
    items.append("".join(item))
    names = (re.match(r"\s*(?:@\w+(?:\([^)]*\))?\s*)*([A-Za-z_]\w*)", it) for it in items)
    return [m.group(1) for m in names if m]


def _python_members(text: str, i: int) -> list[str]:
    names, indent = [], None
    for line in text[i:].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            break
        m = PY_MEMBER.match(line)
        if m and indent in (None, m.group(1)):
            indent = m.group(1)
            names.append(m.group(2))
    return names


def _go_enums(text: str) -> dict[str, list[str]]:
    """Constants per type from the `const ( … )` blocks: a line without a type repeats the one above (iota)."""
    out: dict[str, list[str]] = {}
    for block in GO_CONSTS.finditer(text):
        cur = None
        for line in block.group(1).splitlines():
            m = GO_CONST.match(line.split("//", 1)[0].rstrip())
            if not m:
                continue
            cur = m.group(2) or (None if m.group(3) else cur)
            if cur:
                out.setdefault(cur, []).append(m.group(1))
    return out


def status_enums(name: str, repo: Path) -> list[dict]:
    """Enums about state (`…Status|State|Phase|Stage`; SQL `CHECK (<…status|state…> IN (…))`), in file then declaration
    order: {"id", "states", "source": "repo:path#line"}. The first one of a name wins when two files declare it."""
    from . import genblocks
    found: dict[str, dict] = {}

    def add(eid, states, f, pos, text):
        if states and eid not in found:
            found[eid] = {"id": eid, "states": list(dict.fromkeys(states)), "source": genblocks._ref(name, repo, f, _line(text, pos))}
    for f in _files(repo):
        if f.suffix not in STATE_SUFFIXES:
            continue
        text = genblocks._read(f)
        if f.suffix == ".py":
            for m in PY_ENUM.finditer(text):
                if STATE_SUFFIX.search(m.group(1)):
                    add(m.group(1), _python_members(text, m.end()), f, m.start(), text)
        elif f.suffix == ".sql":
            for t in SQL_TABLE.finditer(text):
                stmt = text[t.end():].split(";", 1)[0]
                for c in SQL_IN.finditer(stmt):
                    if STATE_COLUMN.search(c.group(1)):
                        add(f"{t.group(1).rsplit('.', 1)[-1]}_{c.group(1)}", re.findall(r"'([^']*)'", c.group(2)), f,
                            t.end() + c.start(), text)
        elif f.suffix == ".go":
            consts = _go_enums(text)
            for m in GO_TYPE.finditer(text):
                if STATE_SUFFIX.search(m.group(1)):
                    add(m.group(1), consts.get(m.group(1), []), f, m.start(), text)
        else:
            code = COMMENTS.sub(lambda m: m.group() if m.group()[0] in "\"'`" else re.sub(r"[^\n]", " ", m.group()), text)
            for m in BRACE_ENUM.finditer(code):
                if STATE_SUFFIX.search(m.group(1)):
                    add(m.group(1), _constants(code, m.end()), f, m.start(), text)
    return list(found.values())


def _node(state: str, used: set[str]) -> str:
    node = re.sub(r"\W+", "_", state).strip("_") or "state"
    node = "s" + node if node[0].isdigit() else node
    node += "_" if node.lower() in MERMAID_WORDS else ""                    # `end`, `state`… would break the diagram
    while node in used:
        node += "_"
    used.add(node)
    return node


def _states(repo: str, d: Path, id: str | None) -> tuple[str, list[str]] | None:
    enum = next((e for e in status_enums(repo, d) if e["id"] == id), None)
    if enum is None:
        return None
    where, extra = enum["source"].split("#", 1)[0], len(enum["states"]) - NODE_LIMIT
    used: set[str] = set()
    nodes = [(s, _node(s, used)) for s in enum["states"][:NODE_LIMIT]]
    lines = ["stateDiagram-v2"] + [f'    state "{s.replace(chr(34), chr(39))}" as {n}' if s != n else f"    {n}" for s, n in nodes]
    lines.append(f"    note right of {nodes[0][1]} : {TRANSITIONS}")
    if extra > 0:
        lines.append(f"    note right of {nodes[0][1]} : {extra} more states in {where.split(':', 1)[1]}")
    body = f"**`{enum['id']}`** · `{where}`\n\n```mermaid\n" + "\n".join(lines) + "\n```"
    return body, [where]


def _label(text: str) -> str:
    """A Mermaid label, quoted: the characters that end or break a quoted label become entity codes."""
    t = text.replace("\n", " ").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;").replace("`", "#96;")
    return f'"{t}"'


def _group(path: str) -> str:
    """The id of a path's resource group: its first segment, safe inside `id=` (`/pets/{id}` → `pets`, `/` → `root`)."""
    first = next((p for p in path.split("/") if p), "")
    return re.sub(r"[^\w.\-]+", "-", first).strip("-") or "root"


def _endpoints_map(repo: str, d: Path) -> dict | None:
    """The map of a repo as data: {"groups": {id: {"name", "rows"}}, "deps": [(shape, label, edge, way, source)],
    "split": bool, "more": dependencies left out}; None when the repo has no endpoints. The architecture is scanned
    once, here. Over NODE_LIMIT nodes it is split by first path segment (a big group in chunks: `pets`, `pets-2`…)."""
    from . import genblocks
    seen, rows = set(), []
    for r in genblocks.endpoint_rows(repo, d):
        if (r["method"], r["path"]) not in seen:
            seen.add((r["method"], r["path"]))
            rows.append(r)
    if not rows:
        return None
    topics, model = genblocks.topic_rows(repo, d), quickarch.scan()
    deps, known = [], set()
    for a, b, kind, label in model["edges"]:
        if a != repo or b in known:
            continue
        if b in model["dbs"]:
            db = model["dbs"][b]
            deps.append(("db", db["label"] if db["name"].endswith(" db") else f"{db['label']} ({db['name']})", "reads/writes", "out", None))
        elif kind == "sync" and label.startswith("calls") and b in model["repos"] and b != repo:
            deps.append(("repo", b, label, "out", None))
        else:
            continue
        known.add(b)
    deps += [("topic", t["topic"], t["direction"], "out" if t["direction"] == "publishes" else "in", t["source"]) for t in topics]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(_group(r["path"]), []).append(r)
    split, more = 1 + len(rows) + len(deps) > NODE_LIMIT, 0
    if not split:
        return {"groups": {g: {"name": g, "rows": rs} for g, rs in groups.items()}, "deps": deps, "split": False, "more": 0}
    more, deps = max(0, len(deps) - NODE_LIMIT // 2), deps[:NODE_LIMIT // 2]  # keep room for the endpoints
    room, parts, taken = NODE_LIMIT - 1 - len(deps), {}, set(groups)
    for g, rs in groups.items():
        for n, i in enumerate(range(0, len(rs), room)):
            pid, k = g, n + 1
            while n and (pid := f"{g}-{k}") in taken:
                k += 1
            taken.add(pid)
            parts[pid] = {"name": g, "rows": rs[i:i + room]}
    return {"groups": parts, "deps": deps, "split": True, "more": more}


def _map_ids(m: dict) -> list[str | None]:
    return list(m["groups"]) if m["split"] else [None]


def _draw_map(repo: str, m: dict, id: str | None) -> tuple[str, list[str]] | None:
    if id not in _map_ids(m):
        return None
    groups = list(m["groups"].values()) if id is None else [m["groups"][id]]
    used: set[str] = set()
    me = _node(repo, used)
    lines = ["flowchart LR", f"    {me}[{_label(repo)}]"]
    count = 0
    for g in groups:
        gid = _node(g["name"], used)
        lines.append(f'    subgraph {gid}[{_label("/" + g["name"] if g["name"] != "root" else "/")}]')
        for r in g["rows"]:
            text = f'{r["method"]} {r["path"]}'
            lines.append(f"        {_node(text, used)}[{_label(text)}]")
        lines += ["    end", f"    {me} --- {gid}"]
        count += len(g["rows"])
    for shape, label, edge, way, _src in m["deps"]:
        n = _node(label, used)
        box = {"db": f"[({_label(label)})]", "topic": f"([{_label(label)}])"}.get(shape, f"[{_label(label)}]")
        lines += [f"    {n}{box}", f"    {me} -->|{_label(edge)}| {n}" if way == "out" else f"    {n} -->|{_label(edge)}| {me}"]
    sources = [r["source"] for g in groups for r in g["rows"]] + [s for *_, s in m["deps"] if s]
    head = f"**`{repo}`** · " + (f"`/{groups[0]['name']}` · " if id is not None else "") + f"{count} endpoints"
    if m["more"]:
        head += f" · {m['more']} more dependencies not drawn"
    return head + "\n\n```mermaid\n" + "\n".join(lines) + "\n```", list(dict.fromkeys(s.split("#", 1)[0] for s in sources))


EXTERNAL, CACHE = "\0external", "\0cache"                                   # node keys that cannot clash with a repo name


def _context_map() -> dict | None:
    """The system as data: {"nodes": [(key, shape, label)], "edges": [(from, to, label)], "folded": [identity providers
    folded into one External node], "dropped": nodes left out, "sources": [...]}; None when there are no repos. The
    architecture is scanned once, here. Over NODE_LIMIT nodes the identity providers fold into one `External` node; if
    that is still too much, the least connected repos and datastores are left out (and counted)."""
    model = quickarch.scan()
    if not model["repos"]:
        return None
    nodes = [(n, "repo", n) for n in model["repos"]]
    nodes += [(k, "db", db["label"] if db["name"].endswith(" db") else f"{db['label']} ({db['name']})") for k, db in model["dbs"].items()]
    nodes += [(b, "broker", b) for b in sorted(model["brokers"])]
    nodes += [(CACHE, "db", "Redis cache")] * bool(model["caches"])
    idps, folded = sorted(model["idps"]), []
    edges = [(a, b, label) for a, b, _kind, label in model["edges"]] + [(n, CACHE, "caches") for n in sorted(model["caches"])]
    if len(nodes) + len(idps) > NODE_LIMIT and len(idps) > 1:               # one provider alone: a fold saves no node
        folded, nodes = idps, nodes + [(EXTERNAL, "external", f"External ({len(idps)})")]
        edges = [(EXTERNAL if a in idps else a, EXTERNAL if b in idps else b, label) for a, b, label in edges]
    else:
        nodes += [(i, "external", i) for i in idps]
    dropped = 0
    if len(nodes) > NODE_LIMIT:
        degree = {k: sum(k in (a, b) for a, b, _ in edges) for k, *_ in nodes}
        droppable = sorted((k for k, shape, _ in nodes if shape in ("repo", "db")), key=lambda k: -degree[k])
        gone = set(droppable[max(0, NODE_LIMIT - (len(nodes) - len(droppable))):])
        nodes, dropped = [x for x in nodes if x[0] not in gone], len(gone)
    keep = {k for k, *_ in nodes}
    seen, kept = set(), []
    for e in edges:
        if e[0] in keep and e[1] in keep and e not in seen:
            seen.add(e)
            kept.append(e)
    return {"nodes": nodes, "edges": kept, "folded": folded, "dropped": dropped, "sources": sorted(model["sources"])}


def _draw_context(m: dict) -> tuple[str, list[str]]:
    used: set[str] = set()
    ident = {key: _node(label, used) for key, _shape, label in m["nodes"]}
    lines = ["flowchart LR"]
    for key, shape, label in m["nodes"]:
        box = {"db": f"[({_label(label)})]", "broker": f"([{_label(label)}])"}.get(shape, f"[{_label(label)}]")
        lines.append(f"    {ident[key]}{box}")
    lines += [f"    {ident[a]} -->|{_label(label)}| {ident[b]}" for a, b, label in m["edges"]]
    head = f"**System context** · elements: {len(m['nodes'])}"
    if m["folded"]:
        head += f" · {len(m['folded'])} identity providers folded into External: {', '.join(m['folded'])}"
    if m["dropped"]:
        head += f" · {m['dropped']} less connected elements not drawn"
    return head + "\n\n```mermaid\n" + "\n".join(lines) + "\n```", m["sources"]


def _topics() -> dict[str, dict]:
    """Per topic: {"pub": [repos], "sub": [repos], "files": [paths]}, in topic order; a repo that both publishes and
    consumes a topic is in both lists, so the topic is one diagram."""
    from . import docs, genblocks
    out: dict[str, dict] = {}
    for name in docs.repo_names():
        d = repo_dir(name)
        if not d.is_dir():
            continue
        for r in genblocks.topic_rows(name, d):
            t = out.setdefault(r["topic"], {"pub": [], "sub": [], "files": []})
            side = t["pub" if r["direction"] == "publishes" else "sub"]
            if name not in side:
                side.append(name)
            path = r["source"].split("#", 1)[0]
            if path not in t["files"]:
                t["files"].append(path)
    return dict(sorted(out.items()))


def _draw_topic(topic: str, t: dict, broker: str) -> tuple[str, list[str]]:
    used: set[str] = set()
    ident = {n: _node(n, used) for n in dict.fromkeys([*t["pub"], broker, *t["sub"]])}
    lines = ["sequenceDiagram"]
    lines += [f"    participant {i}" + (f" as {_label(n)[1:-1]}" if i != n else "") for n, i in ident.items()]
    lines += [f"    {ident[p]}->>{ident[broker]}: publish {topic}" for p in t["pub"]]
    lines += [f"    {ident[broker]}-->>{ident[c]}: deliver {topic}" for c in t["sub"]]
    head = f"**`{topic}`** · producers: {len(t['pub'])} · consumers: {len(t['sub'])} · via {broker}"
    return head + "\n\n```mermaid\n" + "\n".join(lines) + "\n```", t["files"]


def _messaging(id: str | None) -> tuple[str, list[str]] | None:
    t = _topics().get(id or "")
    if t is None:
        return None
    brokers = quickarch.scan()["brokers"]
    return _draw_topic(id, t, next(iter(brokers)) if len(brokers) == 1 else "Broker")


def ids(kind: str, repo: str) -> list[str | None]:
    d = _repo(repo)
    if d is not None and kind == "states":
        return [e["id"] for e in status_enums(repo, d)]
    if d is not None and kind == "endpoints-map":
        m = _endpoints_map(repo, d)
        return _map_ids(m) if m else []
    if repo == SYSTEM and kind == "context":
        return [None] if _context_map() else []
    if repo == SYSTEM and kind == "messaging":
        return list(_topics())
    return []


def render(kind: str, repo: str, id: str | None = None) -> tuple[str, list[str]] | None:
    d = _repo(repo)
    if d is not None and kind == "states":
        return _states(repo, d, id)
    if d is not None and kind == "endpoints-map":
        m = _endpoints_map(repo, d)
        return _draw_map(repo, m, id) if m else None
    if repo == SYSTEM and kind == "context":
        m = _context_map() if id is None else None
        return _draw_context(m) if m else None
    if repo == SYSTEM and kind == "messaging":
        return _messaging(id)
    return None


SYSTEM_PAGE = "architecture/system-map.md"
REPO_PAGE = "repos/{repo}/diagrams.md"
SYSTEM_SECTIONS = (("Context map", "context"), ("Messaging", "messaging"))
REPO_SECTIONS = (("Endpoints", "endpoints-map"), ("Lifecycles", "states"))
Key = tuple  # (kind, repo, id or None)


def _key(m) -> Key:
    return m["kind"], m["repo"], m["id"]


def _page_blocks(text: str) -> list:
    from . import genblocks
    return [m for m in genblocks.BLOCK_RE.finditer(text) if m["kind"] in KINDS]


def _heading(body: str, heading: str):
    return re.search(rf"^## {re.escape(heading)}[ \t]*$", body, re.M)


def _section_end(body: str, heading: str) -> int | None:
    """Where the `## heading` section ends (the next `## ` line, or the end of `body`); None when there is no such heading."""
    m = _heading(body, heading)
    if not m:
        return None
    nxt = re.compile(r"^## ", re.M).search(body, m.end())
    return nxt.start() if nxt else len(body)


def _edit_page(body: str, repo: str, managed: dict[str, str], wanted: list[Key], draw) -> tuple[str, list[str]]:
    """The body of an existing page brought up to date: an unconfirmed block whose key is no longer wanted (its id is
    gone, or the block lives in another page now) leaves; a confirmed block stays where it is, verbatim; the wanted keys
    the page lacks are added at the end of their section. Returns (body, sources of the blocks added)."""
    from . import genblocks
    parts, last, emptied = [], 0, set()
    for m in _page_blocks(body):
        edited = m["sha"] and m["sha"] != genblocks.sha(m["body"])         # a person's hand edit is kept like a confirmation
        if m["kind"] not in managed.values() or m["repo"] != repo or m["confirmed"] or edited or _key(m) in wanted:
            continue
        parts.append(body[last:m.start()])
        last = m.end()
        while body.startswith("\n", last):
            last += 1
        emptied.add(m["kind"])
    body = "".join(parts) + body[last:]
    for heading, kind in managed.items():                                  # a section a drop left with nothing goes too
        start, end = _heading(body, heading), _section_end(body, heading)
        if kind in emptied and start and not body[start.end():end].strip():
            body = body[:start.start()] + body[end:]
    present = {_key(m) for m in _page_blocks(body)}
    sources = []
    for key in wanted:
        if key in present:
            continue
        heading = next(h for h, kind in managed.items() if kind == key[0])
        text, src = draw(key)
        sources += src
        blk = genblocks.block(key[0], key[1], text, id=key[2])
        end = _section_end(body, heading)
        if end is None:
            body = body.rstrip("\n") + f"\n\n## {heading}\n\n{blk}\n"
        else:
            tail = body[end:]
            body = body[:end].rstrip("\n") + "\n\n" + blk + "\n" + ("\n" + tail if tail else "")
    return body, sources


def _new_page(repo: str, sections: list[tuple[str, list[Key]]], draw) -> str:
    """A whole page for `repo` (SYSTEM for the system map) with a block per key, under its section."""
    from . import docs, genblocks
    sources, body = [], ""
    for heading, keys in sections:
        blocks = []
        for key in keys:
            text, src = draw(key)
            sources += src
            blocks.append(genblocks.block(key[0], key[1], text, id=key[2]))
        body += f"\n## {heading}\n\n" + "\n\n".join(blocks) + "\n"
    if repo == SYSTEM:
        title, tags, h1 = "System map", [], "System map"
        description = ("The system as drawn from the code: how the repos, datastores and brokers connect, and who publishes "
                       "and consumes each topic (a static scan, no AI).")
        tldr = ("How the services, datastores and message brokers fit together, and who talks to whom over each topic. "
                "The diagrams are read from the code with no AI; `camaron diagrams` refreshes them. Flows are never "
                "guessed: they wait for a proposal that a person confirms.")
    else:
        title, tags, h1 = f"{repo} diagrams", [repo], f"{repo} diagrams"
        description = (f"Diagrams of {repo} drawn from its code: its endpoints with what they depend on, and the states of "
                       "its status enums (a static scan, no AI).")
        tldr = (f"What `{repo}` exposes and the states its status enums list. The diagrams are read from the code with no "
                "AI; `camaron diagrams` refreshes them. Transitions are never guessed: they wait for a proposal that a "
                "person confirms.")
    fm = {"type": "overview", "title": title, "description": description, **({"tags": tags} if tags else {}),
          "x-sources": list(dict.fromkeys(sources)), "x-owner": "ai", "x-generated": True}
    return docs.join_fm(fm, f"# {h1}\n\n> **TL;DR:** {tldr}\n{body}")


def write_pages(log=lambda _: None) -> list[str]:
    """Create or bring up to date `docs/architecture/system-map.md` (context map, one sequence per topic) and
    `docs/repos/<repo>/diagrams.md` (endpoints map, one state diagram per status enum). A block whose key (kind, repo,
    id) already lives in another docs page is not written again (an agent moved it there); a block a person confirmed
    stays; an unconfirmed one whose id is gone leaves; a page a person owns is never touched; a page that would have no
    block is not created. Returns the pages written."""
    from . import docs, genblocks
    names = [n for n in sorted(docs.repo_names()) if repo_dir(n).is_dir()]
    homes: dict[Key, set[Path]] = {}                                       # where each diagram block lives now
    for _row, f in genblocks._pages():
        for m in _page_blocks(f.read_text(encoding="utf-8")):
            homes.setdefault(_key(m), set()).add(f.resolve())
    cache: dict[Key, tuple[str, list[str]]] = {}

    def draw(key: Key):
        if key not in cache:
            cache[key] = render(*key)
        return cache[key]
    specs = [(SYSTEM_PAGE, SYSTEM, SYSTEM_SECTIONS)] + [(REPO_PAGE.format(repo=n), n, REPO_SECTIONS) for n in names]
    written = []
    for rel, repo, sections in specs:
        f = DOCS / rel
        elsewhere = {k for k, where in homes.items() if where - {f.resolve()}}
        per_section = [(h, [(kind, repo, i) for i in ids(kind, repo) if (kind, repo, i) not in elsewhere]) for h, kind in sections]
        wanted = [k for _h, keys in per_section for k in keys]
        if f.exists():
            text = f.read_text(encoding="utf-8")
            fm, body, _valid = docs.parse_fm(text)
            if fm.get("x-owner") == "human":
                continue
            if fm.get("x-generated") is not True and not _page_blocks(body):
                log(f"· {rel_file(f)} was not written by the kit: left as it is")
                continue
            new_body, sources = _edit_page(body, repo, {h: kind for h, kind in sections}, wanted, draw)
            if new_body == body:
                continue
            new = text[:len(text) - len(body)] + new_body
            if sources and fm.get("x-generated"):
                new = docs.join_fm({**fm, "x-sources": list(dict.fromkeys([*(fm.get("x-sources") or []), *sources]))}, new_body)
        elif wanted:
            new = _new_page(repo, [(h, keys) for h, keys in per_section if keys], draw)
        else:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(new, encoding="utf-8", newline="\n")
        written.append(rel_file(f))
        log(f"✔ {rel_file(f)}")
    return written
