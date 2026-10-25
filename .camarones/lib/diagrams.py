"""Diagrams from the code (no AI): Mermaid blocks that `genblocks` writes, refreshes and checks like any generated block.

`ids(kind, repo)` says which blocks a repo has (`None` = one block without `id=`; `[]` = nothing to draw) and
`render(kind, repo, id)` draws one: (block body, sources), or None when that id no longer exists. A diagram shows what
the code states as fact (states, endpoints, who talks to whom); it never invents a transition or a flow: those wait for
a proposal that a person confirms. `states`: one diagram per status enum, the states only."""
from __future__ import annotations

import itertools, re
from pathlib import Path

from .common import repo_dir
from . import quickarch

KINDS = ("states", "endpoints-map", "context", "messaging")
NODE_LIMIT = 25                                                             # a bigger diagram is a wall, not a picture
SYSTEM = "_system"                                                          # reserved repo name: the whole system
STATE_SUFFIX = re.compile(r"(Status|State|Phase|Stage)$")
STATE_COLUMN = re.compile(r"(status|state|phase|stage)$", re.I)
STATE_SUFFIXES = {".java", ".kt", ".ts", ".py", ".cs", ".go", ".dart", ".sql"}
BRACE_ENUM = re.compile(r"\benum\s+(?:class\s+)?(\w+)[^{;]*\{")            # Java, Kotlin, TypeScript, C#, Dart
PY_ENUM = re.compile(r"^class\s+(\w+)\s*\(([^)]*\bEnum\b[^)]*|[^)]*\bFlag\b[^)]*)\)\s*:", re.M)
PY_MEMBER = re.compile(r"^(\s+)([A-Za-z]\w*)\s*(?::[^=\n]+)?=(?!=)")
GO_TYPE = re.compile(r"^type\s+(\w+)\s+\w", re.M)
GO_CONSTS = re.compile(r"^const\s*\(\n(.*?)^\)", re.M | re.S)
GO_CONST = re.compile(r"^\s*([A-Za-z]\w*)(?:\s+([A-Za-z_]\w*))?\s*(=.*)?$")
SQL_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?([\w.]+)[`\"\]]?", re.I)
SQL_IN = re.compile(r"[`\"\[]?(\w+)[`\"\]]?\s+IN\s*\(([^)]*)\)", re.I)
COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
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
    depth, quote, items, item = 0, None, [], []
    for c in text[i:]:
        if quote:
            quote = None if c == quote else quote
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
            code = COMMENTS.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)
            for m in BRACE_ENUM.finditer(code):
                if STATE_SUFFIX.search(m.group(1)):
                    add(m.group(1), _constants(code, m.end()), f, m.start(), text)
    return list(found.values())


def _node(state: str, used: set[str]) -> str:
    node = re.sub(r"\W+", "_", state).strip("_") or "state"
    node = "s" + node if node[0].isdigit() else node
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


def ids(kind: str, repo: str) -> list[str | None]:
    d = _repo(repo)
    if d is not None and kind == "states":
        return [e["id"] for e in status_enums(repo, d)]
    return []


def render(kind: str, repo: str, id: str | None = None) -> tuple[str, list[str]] | None:
    d = _repo(repo)
    if d is not None and kind == "states":
        return _states(repo, d, id)
    return None
