"""Pages from the code (no AI): what a fresh install writes as the project's front door, from facts the static scans
already know. `facts(memo)` counts them per repo: stack, endpoints, tables, datastores, topics, the repos it calls, state
enums, environment variables and commands, plus the dependencies of the whole project, and says which files they were
read from. `repos_block(memo)` is the `repos` generated block of `docs/index.md`: one card line per repo, linking to its
page. Two layouts: the project home (`HOME`, `_system`) and one page per repo (`REPO_PAGE`), plus the messaging page
(`MESSAGING`). A fact that is zero is said so plainly (`count`), never hidden and never invented. `layout()` says whether
a project still has the old pages (`reference.md`, `diagrams.md`, `first-look.md`…), which a fresh install no longer
writes. `home_page`, `repo_page` and `messaging_page` write a whole page as text from the facts, with a block for every
key the code has. `write` puts them in the docs (`_write_new`; the old layout keeps 2a's `diagrams.write_pages`): a page
with only kit text (`kit_only`) is rewritten whole with its confirmed and hand-edited blocks put back (`place`), a page
with anyone else's words only gets its blocks brought up to date. `adopt` (`camaron pages --adopt`) moves an old project
to the new pages: the old pages with only kit text give their blocks to the new pages and go, the others stay."""
from __future__ import annotations

import functools, re
from pathlib import Path
from types import SimpleNamespace

from .common import DOCS, rel_file, repo_dir
from . import diagrams, docs, genblocks, inventory, quickarch, schemas

SYSTEM = "_system"                                                          # reserved repo name: the whole system
HOME = "index.md"
REPO_PAGE = "repos/{repo}/index.md"
MESSAGING = "architecture/messaging.md"
Key = tuple                                                                 # (kind, repo, id or None), like diagrams.Key
TARGET: dict[str, tuple[str, str, str | None]] = {                          # kind → (page, section heading, :::details summary)
    "repos": (HOME, "", None), "context": (HOME, "Context map", None), "messaging": (MESSAGING, "Messaging", None),
    "endpoints-map": (REPO_PAGE, "What it exposes", None), "endpoints": (REPO_PAGE, "What it exposes", "Endpoints"),
    "schema": (REPO_PAGE, "Data", None), "states": (REPO_PAGE, "Lifecycles", None), "topics": (REPO_PAGE, "Messages", None),
    "env": (REPO_PAGE, "What it needs to run", "Environment variables"),
    "commands": (REPO_PAGE, "What it needs to run", "Commands")}
NOUNS = {"service": "service", "webapp": "web app", "mobileApp": "mobile app", "library": "library",
         "infra": "infrastructure repo"}
MORE = (("Stack and tooling", "overview/tooling.md", False), ("Libraries", "overview/libraries.md", False),
        ("Messaging", MESSAGING, True))                                     # (name, page, only with topics)
HOW = ":::details How this page is made"
DETAILS = ("Read from the code with no AI. `camaron pages` brings it up to date and `camaron blocks` refreshes the diagrams and\n"
           "tables in every page. A person can confirm a diagram so that no refresh rewrites it: see [the tutorial]({tutorial}).")


def count(n: int, noun: str, plural: str | None = None) -> str:
    """`no endpoints`, `1 endpoint`, `35 endpoints`; `plural` for a noun that does not just add an s."""
    return f"{n} {noun}" if n == 1 else f"{n} {plural or noun + 's'}" if n else f"no {plural or noun + 's'}"


def _engines(model: dict, repo: str) -> list[str]:
    return sorted({d["label"] for d in model["dbs"].values() if repo in d["users"]})


def _calls(model: dict, repo: str, names: list[str]) -> list[str]:
    """The sibling repos `repo` calls over HTTP, in workspace order, from the architecture scan's edges."""
    called = {b for a, b, kind, label in model["edges"] if a == repo and kind == "sync" and label.startswith("calls")}
    return [n for n in names if n in called and n != repo]


def _topics(rows: list[dict], direction: str) -> list[str]:
    return sorted({r["topic"] for r in rows if r["direction"] == direction})


def _repo_facts(name: str, model: dict, names: list[str], memo: dict | None) -> tuple[dict, list[str]]:
    d, mapped = repo_dir(name), model["repos"][name]
    endpoints = {(r["method"], r["path"]): r for r in genblocks.endpoint_rows(name, d)}
    topics, stores = genblocks.topic_rows(name, d), schemas.scan_repo(name, d)
    entities = [e for s in stores["stores"] for e in s["entities"]]
    facts = {"kind": mapped["kind"], "stack": mapped["tech"], "endpoints": len(endpoints), "tables": len(entities),
             "engines": _engines(model, name), "publishes": _topics(topics, "publishes"),
             "consumes": _topics(topics, "consumes"), "calls": _calls(model, name, names),
             "states": len(diagrams.ids("states", name, memo)), "env": len(genblocks.env_rows(name, d)),
             "commands": len(genblocks.command_rows(name, d))}
    read = [r["source"] for r in (*endpoints.values(), *topics)] + stores["sources"]
    return facts, [s.split("#", 1)[0] for s in read]


def _build_facts(memo: dict | None) -> dict:
    model = diagrams._scan(memo)
    names = [n for n in docs.repo_names() if repo_dir(n).is_dir() and n in model["repos"]]
    repos, sources = {}, set(model["sources"])
    for n in names:
        repos[n], read = _repo_facts(n, model, names, memo)
        sources.update(read)
    inv = inventory.load() or (inventory.scan() if names else {})
    return {"project": docs.workspace()["project"]["name"], "repos": repos,
            "dependencies": len(inv.get("libraries") or []), "sources": sorted(sources)}


def facts(memo: dict | None = None) -> dict:
    """{"project", "repos": {name: {kind, stack, endpoints, tables, engines, publishes, consumes, calls, states, env,
    commands}}, "dependencies", "sources"} for the repos on this machine, in workspace order. `stack` honours a fixed
    stack; `endpoints` are distinct (method, path); `dependencies` come from the last inventory, else a fresh scan.
    `memo`: the pass's shared cache (see `genblocks.Scanner`)."""
    return diagrams._memo(memo, ("facts",), lambda: _build_facts(memo))


def repos_block(memo: dict | None = None) -> tuple[str, list[str]] | None:
    """The `repos` block: one line per repo with its stack and what the code states. None when there is no repo or some
    repo is not on this machine (a list of part of the repos would be wrong)."""
    if not docs.repo_names() or not diagrams._complete():
        return None
    got = facts(memo)
    lines = []
    for name, f in got["repos"].items():
        topics = len({*f["publishes"], *f["consumes"]})
        lines.append(f"- [{name}]({REPO_PAGE.format(repo=name)}): {f['stack']} · {count(f['endpoints'], 'endpoint')} · "
                     f"{count(f['tables'], 'table')} · {count(topics, 'topic')}")
    return "\n".join(lines), got["sources"]


# ---------- which layout a project has ----------
def old_pages() -> list[Path]:
    """The old-layout pages that exist: per-repo `reference.md` and `diagrams.md`, the generated `data/<repo>.md` of a
    workspace repo (a hand-written one is not ours), `architecture/first-look.md` and `architecture/system-map.md`."""
    names = set(docs.repo_names())
    found = [*DOCS.glob("repos/*/reference.md"), *DOCS.glob("repos/*/diagrams.md")]
    found += [f for f in DOCS.glob("data/*.md") if f.stem in names
              and docs.split_fm(f.read_text(encoding="utf-8", errors="replace"))[0].get("x-generated") is True]
    found += [f for f in (DOCS / "architecture" / "first-look.md", DOCS / "architecture" / "system-map.md") if f.is_file()]
    return sorted(found)


def _has_cards() -> bool:
    for f in sorted(DOCS.rglob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if "generated:repos" in text and any(b["kind"] == "repos" for b in genblocks.BLOCK_RE.finditer(text)):
            return True
    return False


def layout() -> str:
    """`new` when a docs page holds a `repos` block (the project home of the new layout, even beside kept old pages);
    else `old` when any old page exists; else `new` (a fresh project)."""
    return "new" if _has_cards() else "old" if old_pages() else "new"


# ---------- the sentences ----------
def _join(items: list[str]) -> str:
    """`a`, `a and b`, `a, b and c`."""
    return items[0] if len(items) < 2 else ", ".join(items[:-1]) + " and " + items[-1]


def home_tldr(f: dict) -> str:
    repos = f["repos"].values()
    topics = {t for r in repos for t in (*r["publishes"], *r["consumes"])}
    stacks = list(dict.fromkeys(r["stack"] for r in repos))
    return (f"{f['project']} has {count(len(f['repos']), 'repo')} ({', '.join(stacks)}): "
            f"{count(sum(r['endpoints'] for r in repos), 'endpoint')}, {count(sum(r['tables'] for r in repos), 'table')}, "
            f"{count(len(topics), 'message topic')}, {count(f['dependencies'], 'direct dependency', 'direct dependencies')}.")


def repo_tldr(name: str, f: dict) -> str:
    tables = count(f["tables"], "table")
    if f["tables"] and f["engines"]:
        tables += f" in its {_join(f['engines'])} database" + ("s" if len(f["engines"]) > 1 else "")
    pub, con = len(f["publishes"]), len(f["consumes"])
    if not pub and not con:
        messages = "it publishes and consumes no messages"
    elif pub:
        messages = f"it publishes {count(pub, 'topic')}" + (f" and consumes {con}" if con else "")
    else:
        messages = f"it consumes {count(con, 'topic')}"
    calls = f"it calls {_join(f['calls'])}" if f["calls"] else "it calls no other repo"
    return (f"`{name}` is a {f['stack']} {NOUNS.get(f['kind'], 'repo')}: {count(f['endpoints'], 'endpoint')}, {tables}; "
            f"{messages}; {calls}.")


# ---------- the pages ----------
class _Draw:
    """The blocks of one page: drawn through a scanner that shares the pass's `memo` (so a page never scans twice),
    leaving out the keys in `skip` (they live in another page) and remembering what each block was read from."""

    def __init__(self, memo: dict, skip):
        self.scan, self.skip, self.sources = genblocks.Scanner(), skip, []
        self.scan.memo = memo

    def __call__(self, kind: str, repo: str, id: str | None = None) -> str | None:
        got = None if (kind, repo, id) in self.skip else self.scan.get(kind, repo, id)
        if got is None:
            return None
        self.sources += got[1]
        return genblocks.block(kind, repo, got[0], id=id)


def _wrap(kind: str, text: str) -> str:
    """A block in its directive: the cards in `:::cards`, a kind with a `TARGET` summary folded in `:::details`."""
    summary = TARGET.get(kind, (None, "", None))[2]
    return f":::cards\n{text}\n:::" if kind == "repos" else f":::details {summary}\n{text}\n:::" if summary else text


def _sections(items: list[tuple[str, str]]) -> str:
    """Blocks (kind, text) in page order as sections: consecutive kinds sharing a `TARGET` heading share a `## ` section
    (none for the cards), each block in its directive (`_wrap`)."""
    out, heading = [], None
    for kind, text in items:
        _page, h, _summary = TARGET[kind]
        if h and h != heading:
            out.append(f"## {h}")
        heading = h
        out.append(_wrap(kind, text))
    return "\n\n".join(out)


def _page(title: str, description: str, tags: list[str], draw: _Draw, tldr: str, body: str, tutorial: str) -> str:
    fm = {"type": "overview", "title": title, "description": description, **({"tags": tags} if tags else {}),
          "x-sources": list(dict.fromkeys(draw.sources)), "x-owner": "ai", "x-generated": True}
    details = f"{HOW}\n{DETAILS.format(tutorial=tutorial)}\n:::"
    return docs.join_fm(fm, f"# {title}\n\n> **TL;DR:** {tldr}\n\n{body}\n\n{details}\n")


def home_page(memo: dict, skip: set[Key] = frozenset()) -> str | None:
    """`docs/index.md` as a whole page: the TL;DR, a card per repo, the context map and where to read on (`MORE`: only
    the pages that exist now, so a link never breaks; messaging only with topics). None when there is no repo or some
    repo is not on this machine (the cards would show a part of the project)."""
    if repos_block(memo) is None:
        return None
    draw, f = _Draw(memo, skip), facts(memo)
    cards, context = draw("repos", SYSTEM), draw("context", SYSTEM)
    items = [("repos", cards)] if cards else []
    items += [("context", context)] if context else []
    topics = any(r["publishes"] or r["consumes"] for r in f["repos"].values())
    more = [f"- [{name}]({rel})" for name, rel, needs in MORE if (DOCS / rel).is_file() and (topics or not needs)]
    body = "\n\n".join(filter(None, [_sections(items), "## More\n\n" + "\n".join(more) if more else ""]))
    description = f"{f['project']} at a glance: its repos, how they connect and where to read on (a static scan, no AI)."
    return _page(f["project"], description, [], draw, home_tldr(f), body, "guides/tutorial.md")


def repo_page(repo: str, memo: dict, skip: set[Key] = frozenset()) -> str | None:
    """`docs/repos/<repo>/index.md` as a whole page: the TL;DR, then what the repo exposes, stores, goes through, sends
    and needs to run (a section, or a fold, with no block is left out). None when the repo is not on this machine."""
    f = facts(memo)["repos"].get(repo)
    if f is None:
        return None
    draw = _Draw(memo, skip)
    wanted = [("endpoints-map", i) for i in diagrams.ids("endpoints-map", repo, memo)]
    wanted += [("endpoints", None)] * bool(f["endpoints"]) + [("schema", None)] * bool(f["tables"])
    wanted += [("states", i) for i in diagrams.ids("states", repo, memo)]
    wanted += [("topics", None)] * bool(f["publishes"] or f["consumes"])
    wanted += [("env", None)] * bool(f["env"]) + [("commands", None)] * bool(f["commands"])
    items = [(kind, b) for kind, i in wanted if (b := draw(kind, repo, i))]
    description = f"What {repo} exposes, stores and needs to run, read from its code (a static scan, no AI)."
    return _page(repo, description, [repo], draw, repo_tldr(repo, f), _sections(items), "../../guides/tutorial.md")


def messaging_page(memo: dict, skip: set[Key] = frozenset()) -> str | None:
    """`docs/architecture/messaging.md` as a whole page: one sequence diagram per topic. None when no repo states a
    topic (or some repo is not on this machine: the topics would be a part of them)."""
    draw = _Draw(memo, skip)
    items = [("messaging", b) for i in diagrams.ids("messaging", SYSTEM, memo) if (b := draw("messaging", SYSTEM, i))]
    if not items:
        return None
    description = ("The message topics of the system and who publishes and consumes each, read from the code "
                   "(a static scan, no AI).")
    tldr = f"{count(len(items), 'message topic')} between the repos, with who publishes and who consumes each."
    return _page("Messaging", description, [], draw, tldr, _sections(items), "../guides/tutorial.md")


# ---------- writing them ----------
HEADING_LINE = re.compile(r"#{1,6} ")
LINK_ITEM = re.compile(r"[-*+] \[[^\]\n]*\]\(([^)\s]*)\)")                 # a list item that is only a link
MORE_PAGES = {rel for _name, rel, _needs in MORE}
KIT_DIRECTIVES = "\n".join([":::cards", HOW, *(f":::details {s}" for *_x, s in TARGET.values() if s)])
FENCE_CLOSE = re.compile(r"^:::[ \t]*$", re.M)
NEXT_SECTION = re.compile(r"^## ", re.M)
HOW_LINE = re.compile(rf"^{re.escape(HOW)}[ \t]*$", re.M)


def _outside_blocks(body: str) -> str:
    parts, last = [], 0
    for m in genblocks.BLOCK_RE.finditer(body):
        parts.append(body[last:m.start()])
        last = m.end()
    return "".join(parts) + body[last:]


def _tldr(lines: list[str]) -> set[int]:
    """The line numbers of the TL;DR: the contiguous `>` lines from a `> **TL;DR:**` line that is the first non-blank
    line under the H1 (an older kit's wording, over several lines, is still the kit's)."""
    h1 = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    i = len(lines) if h1 is None else next((j for j in range(h1 + 1, len(lines)) if lines[j]), len(lines))
    if i == len(lines) or not lines[i].startswith("> **TL;DR:**"):
        return set()
    out = set()
    while i < len(lines) and lines[i].startswith(">"):
        out.add(i)
        i += 1
    return out


def _more_link(line: str) -> bool:
    """A list item that is only a relative link to one of the home's `MORE` pages."""
    m = LINK_ITEM.fullmatch(line)
    target = m[1] if m else ""
    while target.startswith(("./", "../")):
        target = target.split("/", 1)[1]
    return target in MORE_PAGES


def kit_only(text: str, kit_text: str) -> bool:
    """Whether a page holds only what the kit writes, so that a rewrite loses nobody's words: every non-blank line
    outside its frontmatter and its generated blocks is a line of `kit_text` (what the kit would write today), a heading
    (`#… `), a line of the TL;DR under the H1, a bare `:::`, or a list item that is only a relative link to a `MORE`
    page. Any other `>`, `:::` or list line is someone's."""
    kit = {line.strip() for line in kit_text.splitlines()}
    lines = [line.strip() for line in _outside_blocks(docs.split_fm(text)[1]).splitlines()]
    tldr = _tldr(lines)
    return all(not line or line in kit or HEADING_LINE.match(line) or i in tldr or line == ":::" or _more_link(line)
               for i, line in enumerate(lines))


def _end(body: str, pos: int, sections: bool = True) -> int:
    """Where the section that runs from `pos` ends: the next `## ` line (unless not `sections`) or the `How this page
    is made` fold, else the end of `body`."""
    found = [m.start() for m in (NEXT_SECTION.search(body, pos) if sections else None, HOW_LINE.search(body, pos)) if m]
    return min(found, default=len(body))


def _insert(body: str, pos: int, piece: str, sep: str = "\n\n") -> str:
    """`piece` at `pos`, `sep` after the text before it and a blank line before what follows (none before a fold's
    closing `:::`)."""
    head, tail = body[:pos].rstrip("\n"), body[pos:]
    return head + sep + piece + ("\n" if tail.startswith(":::\n") or tail == ":::" else "\n\n" if tail else "\n") + tail


def place(body: str, text: str, key: Key) -> str:
    """`body` with `text` (a whole block, markers included) in it: in place of the block with the same key; else at the
    end of its `TARGET` section, inside its `:::details` fold when the target has one (the fold there, or a new one);
    else in a new section before `:::details How this page is made` (a kind with no heading, the cards: before the
    first section)."""
    for m in genblocks.BLOCK_RE.finditer(body):
        if diagrams._key(m) == tuple(key):
            return body[:m.start()] + text + body[m.end():]
    _page, heading, summary = TARGET.get(key[0], (None, "", None))
    start = diagrams._heading(body, heading) if heading else None
    if start:
        end = _end(body, start.end())
        fold = summary and re.compile(rf"^:::details {re.escape(summary)}[ \t]*$", re.M).search(body, start.end(), end)
        close = fold and FENCE_CLOSE.search(body, fold.end(), end)
        if close:
            return _insert(body, close.start(), text, "\n" if not body[fold.end():close.start()].strip() else "\n\n")
        return _insert(body, end, _wrap(key[0], text))
    if heading:
        return _insert(body, _end(body, 0, sections=False), f"## {heading}\n\n{_wrap(key[0], text)}")
    return _insert(body, _end(body, 0), _wrap(key[0], text))


def _tidy(body: str, gone: set[str]) -> str:
    """After `_edit_page` dropped the last block of some kinds: their empty folds go, then their sections left empty."""
    for kind in sorted(gone):
        _page, heading, summary = TARGET.get(kind, (None, "", None))
        if summary:
            body = re.sub(rf"^:::details {re.escape(summary)}[ \t]*\n\s*^:::[ \t]*(?:\n(?:[ \t]*\n)?|$)", "", body, flags=re.M)
        start = diagrams._heading(body, heading) if heading else None
        if start and not body[start.end():_end(body, start.end())].strip():
            body = body[:start.start()] + body[_end(body, start.end()):]
    return body


def _template(rel: str) -> str:
    return REPO_PAGE if rel.startswith("repos/") else rel


KEPT_FM = ("title", "description", "tags", "x-confirmed")                  # a person may have set them


def _rewrite(rel: str, repo: str, old: str, fresh: str, scan: genblocks.Scanner) -> str:
    """Rule 4: the fresh page, with the old page's confirmed, hand-edited and unknown blocks put back verbatim, and
    so are the blocks the page does not own (another repo's, or a kind another page holds: moved here, so the page they
    left skips them). The frontmatter is the fresh one with the old `KEPT_FM` keys and any key the fresh one lacks;
    `x-sources` is always the fresh one."""
    old_fm, old_body = docs.split_fm(old)
    fm, body = docs.split_fm(fresh)
    for m, state, _body in genblocks.states(old_body, scan):
        owned = m["repo"] == repo and TARGET.get(m["kind"], (None,))[0] == _template(rel)
        if m["confirmed"] or state in ("edited", "unknown") or not owned:
            body = place(body, m[0], diagrams._key(m))
    fm.update({k: old_fm[k] for k in KEPT_FM if k in old_fm})
    fm.update({k: v for k, v in old_fm.items() if k not in fm})
    return docs.join_fm(fm, body)


def _blocks_only(rel: str, repo: str, old: str, fresh: str | None, scan: genblocks.Scanner) -> str:
    """Rule 5: only the page's blocks brought up to date (`diagrams._edit_page` with the page's `TARGET` pairs, the
    missing ones put by `place`, the folds and sections a drop emptied removed); its TL;DR and every other line stay."""
    fm, body, _valid = docs.parse_fm(old)
    managed = [(h, kind) for kind, (page, h, _s) in TARGET.items() if page == _template(rel)]
    kinds = {kind for _h, kind in managed}
    wanted = [diagrams._key(m) for m in genblocks.BLOCK_RE.finditer(fresh or "")]
    before = {m["kind"] for m in genblocks.BLOCK_RE.finditer(body) if m["kind"] in kinds}
    new_body, sources = diagrams._edit_page(body, repo, managed, wanted, lambda key: scan.get(*key), put=place)
    new_body = _tidy(new_body, before - {m["kind"] for m in genblocks.BLOCK_RE.finditer(new_body)})
    if new_body == body:
        return old
    if sources and fm.get("x-generated"):
        return docs.join_fm({**fm, "x-sources": list(dict.fromkeys([*(fm.get("x-sources") or []), *sources]))}, new_body)
    return old[:len(old) - len(body)] + new_body


def _write_new(log=lambda _: None, exclude: frozenset[Path] = frozenset()) -> list[str]:
    """Create or bring up to date the new layout: the messaging page (with topics), each repo's page on this machine and
    the project home (last, so its `## More` sees the pages of this pass). Per page: a block whose key lives in another
    docs page is left out (2a's moved-block rule; a page in `exclude` does not count, and is never written); a missing
    page is written whole; a page a person owns, or one the kit did not write, is left as it is; a kit page with only
    kit text is rewritten whole, keeping its confirmed, hand-edited and unknown blocks; any other page gets only its
    blocks brought up to date. The home is left as it is while some repo is not on this machine. A file is written only
    when its text changed. Returns the pages written."""
    memo, scan, excluded = {}, genblocks.Scanner(), {Path(p).resolve() for p in exclude}
    scan.memo = memo
    homes: dict[Key, set[Path]] = {}                                       # where each block lives now
    for _row, f in genblocks._pages():
        if f.resolve() not in excluded:
            for m in genblocks.BLOCK_RE.finditer(f.read_text(encoding="utf-8")):
                homes.setdefault(diagrams._key(m), set()).add(f.resolve())
    specs = [(MESSAGING, SYSTEM, messaging_page)] * bool(diagrams.ids("messaging", SYSTEM, memo))
    specs += [(REPO_PAGE.format(repo=n), n, functools.partial(repo_page, n)) for n in docs.repo_names()
              if repo_dir(n).is_dir()]
    written = []
    for rel, repo, make in [*specs, (HOME, SYSTEM, home_page)]:
        f = DOCS / rel
        if f.resolve() in excluded:
            continue
        if repo == SYSTEM and not diagrams._complete():
            log(f"· {rel_file(f)}: not every repo is on this machine, so this page is left as it is")
            continue
        fresh = make(memo, {k for k, where in homes.items() if where - {f.resolve()}})
        old = f.read_text(encoding="utf-8") if f.exists() else None
        note = f"✔ {rel_file(f)}"
        if old is None:
            new = fresh
        else:
            fm, body, _valid = docs.parse_fm(old)
            if fm.get("x-owner") == "human":
                continue
            if fm.get("x-generated") is not True and not genblocks.BLOCK_RE.search(body):
                log(f"· {rel_file(f)} was not written by the kit: left as it is")
                continue
            if fm.get("x-generated") is True and fresh is not None and kit_only(old, fresh + "\n" + KIT_DIRECTIVES):
                new = _rewrite(rel, repo, old, fresh, scan)
            else:
                new = _blocks_only(rel, repo, old, fresh, scan)
                note = f"· {rel_file(f)}: has text a person or an agent wrote, only its blocks were brought up to date"
        if new is None or new == old:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(new, encoding="utf-8", newline="\n")
        written.append(rel_file(f))
        log(note)
    return written


def write(log=lambda _: None) -> list[str]:
    """`camaron pages`: in the old layout 2a's diagram pages (`diagrams.write_pages`, unchanged); in the new one the
    home, the repo pages and the messaging page (`_write_new`). Returns the pages written (`docs/…` paths)."""
    return diagrams.write_pages(log) if layout() == "old" else _write_new(log)


# ---------- adopting an old project ----------
FIRST_LOOK = "architecture/first-look.md"
FIRST_LOOK_TITLE = "Architecture — first look"                             # its page has no x-generated: the title says


def _old_kit_text(rel: str, scan: genblocks.Scanner) -> str:
    """What the 4.x kit would write today in the old page `rel` (`kit_only` skips the blocks, so a repo not on this
    machine still gets its page's words)."""
    parts, memo = rel.split("/"), scan.memo
    if rel == FIRST_LOOK:
        return quickarch.first_look_page(diagrams._scan(memo))
    if parts[0] == "data":
        repo = parts[1][:-len(".md")]
        return schemas.page(schemas.scan_repo(repo, repo_dir(repo)))
    if parts[-1] == "reference.md":
        anything = SimpleNamespace(get=lambda *key: scan.get(*key) or (genblocks.NOTHING, []))   # a repo not here
        return genblocks.reference_page(parts[1], anything)
    repo, sections = (SYSTEM, diagrams.SYSTEM_SECTIONS) if rel == diagrams.SYSTEM_PAGE else (parts[1], diagrams.REPO_SECTIONS)
    keys = [(h, [(kind, repo, i) for i in diagrams.ids(kind, repo, memo)]) for h, kind in sections]
    return diagrams._new_page(repo, [(h, k) for h, k in keys if k],
                              lambda key: diagrams.render(*key, memo=memo) or ("", []))


def _target(key: Key) -> str:
    """The new page (docs-relative) that holds a block of `key`."""
    return TARGET[key[0]][0].format(repo=key[1])


def _takes_blocks(rel: str, memo: dict) -> bool:
    """Whether `rel` will be a page `place` may put a block in once `_write_new` ran: an existing page the kit may write
    (not a person's, and the kit's or holding blocks), or one `_write_new` creates (the home, the page of a repo on this
    machine, the messaging page when the code has topics)."""
    f = DOCS / rel
    if f.exists():
        fm, body, _valid = docs.parse_fm(f.read_text(encoding="utf-8"))
        return fm.get("x-owner") != "human" and (fm.get("x-generated") is True or bool(genblocks.BLOCK_RE.search(body)))
    here = {REPO_PAGE.format(repo=n) for n in docs.repo_names() if repo_dir(n).is_dir()}
    return rel in here or rel == HOME or rel == MESSAGING and bool(diagrams.ids("messaging", SYSTEM, memo))


def _judge(rel: str, text: str, scan: genblocks.Scanner) -> tuple[str | None, list[tuple[str, Key]]]:
    """(why the old page `rel` stays, or None when it can go; the blocks it carries: confirmed, hand-edited or unknown,
    as (text, key)). The others are drawn fresh in the new pages."""
    fm, body, _valid = docs.parse_fm(text)
    if fm.get("x-owner") == "human":
        return "owned by a person", []
    blocks = list(genblocks.states(body, scan))
    carried = [(m[0], diagrams._key(m)) for m, state, _b in blocks
               if m["kind"] in TARGET and (m["confirmed"] or state in ("edited", "unknown"))]
    if any(m["kind"] not in TARGET for m, _s, _b in blocks) or any(
            not _takes_blocks(_target(key), scan.memo) for _t, key in carried):
        return "has a block the new pages have no place for", []
    if fm.get("x-generated") is not True and not (rel == FIRST_LOOK and fm.get("title") == FIRST_LOOK_TITLE):
        return "was not written by the kit", []
    if not kit_only(text, _old_kit_text(rel, scan) + "\n" + KIT_DIRECTIVES):
        return "has text a person or an agent wrote", []
    return None, carried


def adopt(log=lambda _: None) -> dict:
    """`camaron pages --adopt`: move an old-layout project to the new pages. An old page (`old_pages`) a person owns, or
    with a block the new pages have no place for, or with anyone's words besides the kit's (`kit_only` against what the
    4.x kit would write today) stays exactly as it is, blocks included. The new pages are written (`_write_new`, the
    removable pages not counting as a block's home); the removable pages' confirmed, hand-edited and unknown blocks go
    verbatim into their new page (`place`), the others are there fresh; then the removable pages are deleted (only once
    every page is written: a failure deletes nothing). While some repo is not on this machine nothing is done (the home
    would show a part of the project). Translations are left as they are. Returns {"moved": ["<kind> <repo>[ <id>] →
    docs/<page>"], "deleted", "kept": ["docs/<page>: <reason>"], "relinked", "links", "translations"} (`docs/…` paths;
    the last three are empty here)."""
    out = {k: [] for k in ("moved", "deleted", "kept", "relinked", "links", "translations")}
    old = {f.relative_to(DOCS).as_posix(): f for f in old_pages()}
    if not old:
        return out
    if not diagrams._complete():
        out["kept"] = [f"{rel_file(f)}: not every repo is on this machine" for f in old.values()]
        for line in out["kept"]:
            log(f"· kept {line}")
        return out
    scan = genblocks.Scanner()
    removable: dict[str, list[tuple[str, Key]]] = {}
    for rel, f in old.items():
        why, carried = _judge(rel, f.read_text(encoding="utf-8"), scan)
        if why:
            out["kept"].append(f"{rel_file(f)}: {why}")
        else:
            removable[rel] = carried
    _write_new(log, exclude=frozenset(old[rel] for rel in removable))
    moves: dict[str, list[tuple[str, Key]]] = {}
    for rel, carried in removable.items():
        if any(not (DOCS / _target(key)).is_file() for _t, key in carried):    # a page `_write_new` did not create
            out["kept"].append(f"{rel_file(old[rel])}: has a block the new pages have no place for")
            continue
        for text, key in carried:
            moves.setdefault(_target(key), []).append((text, key))
            out["moved"].append(f"{' '.join(filter(None, key))} → docs/{_target(key)}")
        out["deleted"].append(rel_file(old[rel]))
    for target, blocks in moves.items():
        f = DOCS / target
        text = f.read_text(encoding="utf-8")
        body = docs.parse_fm(text)[1]
        new_body = functools.reduce(lambda b, item: place(b, *item), blocks, body)
        if new_body != body:
            f.write_text(text[:len(text) - len(body)] + new_body, encoding="utf-8", newline="\n")
    for rel, f in old.items():
        if rel_file(f) in out["deleted"]:
            f.unlink()
    for mark, key in (("✔ moved", "moved"), ("✖ deleted", "deleted"), ("· kept", "kept")):
        for line in out[key]:
            log(f"{mark} {line}")
    return out
