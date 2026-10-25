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
from urllib.parse import unquote

from .common import DOCS, rel_file, repo_dir
from . import diagrams, docs, genblocks, inventory, quality, quickarch, schemas

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


def _tldr(lines: list[str]) -> int | None:
    """The line number of the TL;DR: a `> **TL;DR:**` line that is the first non-blank line under the H1 (an older
    kit's wording is still the kit's). Only that line: a `>` line under it is the kit's only when the kit writes it."""
    h1 = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    i = len(lines) if h1 is None else next((j for j in range(h1 + 1, len(lines)) if lines[j]), len(lines))
    return i if i < len(lines) and lines[i].startswith("> **TL;DR:**") else None


def _more_link(line: str) -> bool:
    """A list item that is only a relative link to one of the home's `MORE` pages."""
    m = LINK_ITEM.fullmatch(line)
    target = m[1] if m else ""
    while target.startswith(("./", "../")):
        target = target.split("/", 1)[1]
    return target in MORE_PAGES


def kit_only(text: str, kit_text: str) -> bool:
    """Whether a page holds only what the kit writes, so that a rewrite loses nobody's words: every non-blank line
    outside its frontmatter and its generated blocks is a line of `kit_text` (what the kit would write today) outside
    `kit_text`'s own frontmatter and blocks (a person's copy of a table row is theirs), a heading (`#… `), the TL;DR
    line under the H1, a bare `:::`, or a list item that is only a relative link to a `MORE` page. Any other `>`, `:::`
    or list line is someone's."""
    kit = {line.strip() for line in _outside_blocks(docs.split_fm(kit_text)[1]).splitlines()}
    lines = [line.strip() for line in _outside_blocks(docs.split_fm(text)[1]).splitlines()]
    tldr = _tldr(lines)
    return all(not line or line in kit or HEADING_LINE.match(line) or i == tldr or line == ":::" or _more_link(line)
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


def _homes(excluded: set[Path] = frozenset()) -> dict[Key, set[Path]]:
    """Where each block lives now: key → the docs pages (resolved) that hold it, the `excluded` ones aside."""
    homes: dict[Key, set[Path]] = {}
    for _row, f in genblocks._pages():
        if f.resolve() not in excluded:
            for m in genblocks.BLOCK_RE.finditer(f.read_text(encoding="utf-8")):
                homes.setdefault(diagrams._key(m), set()).add(f.resolve())
    return homes


def _specs(memo: dict) -> list[tuple[str, str, object]]:
    """The new layout's pages in writing order, as (docs-relative page, repo, make(memo, skip)): the messaging page
    (with topics), each repo's page on this machine, the home last."""
    specs = [(MESSAGING, SYSTEM, messaging_page)] * bool(diagrams.ids("messaging", SYSTEM, memo))
    specs += [(REPO_PAGE.format(repo=n), n, functools.partial(repo_page, n)) for n in docs.repo_names()
              if repo_dir(n).is_dir()]
    return [*specs, (HOME, SYSTEM, home_page)]


def _write_new(log=lambda _: None, exclude: frozenset[Path] = frozenset(),
               frozen: frozenset[Path] = frozenset()) -> list[str]:
    """Create or bring up to date the new layout: the messaging page (with topics), each repo's page on this machine and
    the project home (last, so its `## More` sees the pages of this pass). Per page: a block whose key lives in another
    docs page is left out (2a's moved-block rule; a page in `exclude` does not count, and is never written; one in
    `frozen` counts but is never written either); a missing
    page is written whole; a page a person owns, or one the kit did not write, is left as it is; a kit page with only
    kit text and no `x-confirmed` is rewritten whole, keeping its confirmed, hand-edited and unknown blocks; any other
    page (a confirmed one too) gets only its blocks brought up to date. The home is left as it is while some repo is not on this machine. A file is written only
    when its text changed. Returns the pages written."""
    memo, scan, excluded = {}, genblocks.Scanner(), {Path(p).resolve() for p in exclude}
    scan.memo = memo
    homes, frozen = _homes(excluded), {Path(p).resolve() for p in frozen}
    written = []
    for rel, repo, make in _specs(memo):
        f = DOCS / rel
        if f.resolve() in excluded or f.resolve() in frozen:
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
            if (fm.get("x-generated") is True and not fm.get("x-confirmed") and fresh is not None
                    and kit_only(old, fresh + "\n" + KIT_DIRECTIVES)):
                new = _rewrite(rel, repo, old, fresh, scan)
            else:
                new = _blocks_only(rel, repo, old, fresh, scan)
                why = ("is confirmed by a person (x-confirmed)" if fm.get("x-confirmed")
                       else "has text a person or an agent wrote")
                note = f"· {rel_file(f)}: {why}, only its blocks were brought up to date"
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


DIFFERS = "differs from what this kit writes (text a person or an agent added, or an older kit's wording)"
TLDR_END = re.compile(r"^# [^\n]*(?:\n|$)(?:[ \t]*\n)*(?:> \*\*TL;DR:\*\*[^\n]*(?:\n|$)(?:>[^\n]*(?:\n|$))*)?", re.M)


def _persons(fm: dict) -> list[tuple[str, str]]:
    """What makes a page a person's, as (frontmatter key, how to undo it): `x-owner: human`, any `x-confirmed`."""
    return ([("x-owner: human", "set x-owner: ai")] * (fm.get("x-owner") == "human")
            + [("x-confirmed", "remove x-confirmed")] * bool(fm.get("x-confirmed")))


def _status(f: Path) -> str:
    """How the existing page `f` takes blocks from `adopt`: `closed` (a person's: `x-owner: human` or any `x-confirmed`;
    never written), `kit` (`x-generated: true` or holding a block: `_write_new` writes it) or `draft` (an agent's page
    with no block, `x-owner: ai` or no `x-owner` at all, the kit's default as in `doc_status` and the 4.x skeletons:
    `adopt` adds the blocks, nothing else)."""
    fm, body, _valid = docs.parse_fm(f.read_text(encoding="utf-8"))
    if _persons(fm):
        return "closed"
    return "kit" if fm.get("x-generated") is True or genblocks.BLOCK_RE.search(body) else "draft"


def _persons_page(f: Path, what: str) -> str:
    """Why `adopt` cannot put `what` in the person's page `f`, with the key that makes it theirs and how to go on."""
    why = _persons(docs.split_fm(f.read_text(encoding="utf-8"))[0])
    return (f"{rel_file(f)} is a person's page ({', '.join(k for k, _u in why)}): add {what} by hand, or "
            f"{_join([u for _k, u in why])} and run --adopt again")


def _held(f: Path) -> dict[Key, str]:
    """The blocks of page `f`, key → whole block text."""
    return {diagrams._key(m): m[0] for m in genblocks.BLOCK_RE.finditer(f.read_text(encoding="utf-8"))}


def _keys(f: Path) -> set[Key]:
    return set(_held(f))


def _no_place(key: Key, text: str | None, memo: dict) -> str | None:
    """Why the new pages cannot take a block of `key` (None when they can; `text` is the block when it is carried
    verbatim): its page is a person's and lacks it, or holds another copy of a carried block (the very same text is
    fine: nothing to move), or it is a page `_write_new` will not create (a repo not on this machine, messaging with no
    topic in the code)."""
    rel = _target(key)
    f = DOCS / rel
    if f.exists():
        held = _held(f) if _status(f) == "closed" else None
        if held is None or key in held and text in (None, held[key]):
            return None
        if key not in held:
            return _persons_page(f, "its blocks")
        return f"{rel_file(f)} is a person's page and holds a different copy of {' '.join(filter(None, key))}"
    here = {REPO_PAGE.format(repo=n) for n in docs.repo_names() if repo_dir(n).is_dir()}
    if rel in here or rel == HOME or rel == MESSAGING and diagrams.ids("messaging", SYSTEM, memo):
        return None
    return "has a block the new pages have no place for"


def _judge(rel: str, text: str, scan: genblocks.Scanner) -> tuple[str | None, list[tuple[str, Key]], set[Key]]:
    """(why the old page `rel` stays, or None when it can go; the blocks it carries verbatim: confirmed, edited by hand
    or unknown, whatever their state, as (text, key); the keys that must have a home once it is gone: all but the
    others the code no longer has, `gone` diagrams and tables with nothing found, which the new pages drop as 2a drops
    them). The others are drawn fresh."""
    fm, body, _valid = docs.parse_fm(text)
    if fm.get("x-owner") == "human":
        return "owned by a person", [], set()
    if fm.get("x-confirmed"):
        return "confirmed by a person", [], set()
    blocks = list(genblocks.states(body, scan))
    if any(m["kind"] not in TARGET for m, _s, _b in blocks):
        return "has a block the new pages have no place for", [], set()
    carried = [(m[0], diagrams._key(m)) for m, state, _b in blocks
               if m["confirmed"] or (m["sha"] and m["sha"] != genblocks.sha(m["body"])) or state == "unknown"]
    keys = {k for _t, k in carried} | {diagrams._key(m) for m, state, fresh in blocks           # what the code still has
                                       if state != "gone" and (fresh or "").strip() != genblocks.NOTHING}
    texts = {k: t for t, k in carried}
    order = sorted(keys, key=lambda k: (k not in texts, str(k)))            # a carried block's conflict says most
    why = next(filter(None, (_no_place(k, texts.get(k), scan.memo) for k in order)), None)
    if why:
        return why, [], set()
    if fm.get("x-generated") is not True and not (rel == FIRST_LOOK and fm.get("title") == FIRST_LOOK_TITLE):
        return "was not written by the kit", [], set()
    if not kit_only(text, _old_kit_text(rel, scan) + "\n" + KIT_DIRECTIVES):
        return DIFFERS, [], set()
    return None, carried, keys


def _put(body: str, text: str, key: Key) -> str:
    """`place`, but a page's first cards go in `:::cards` right under its TL;DR (under its H1 when it has none)."""
    if key[0] != "repos" or any(diagrams._key(m) == tuple(key) for m in genblocks.BLOCK_RE.finditer(body)):
        return place(body, text, key)
    m = TLDR_END.search(body)
    return _insert(body, m.end(), _wrap("repos", text)) if m else _wrap("repos", text) + "\n\n" + body


def _draft_blocks(excluded: set[Path], scan: genblocks.Scanner) -> dict[str, tuple[list[tuple[str, Key]], list[str]]]:
    """For each existing home or repo page that is an agent's draft (`_status` `draft`, which `_write_new` leaves
    alone): the blocks its fresh version has, as (text, key), and their sources."""
    homes, out = _homes(excluded), {}
    for rel, _repo, make in _specs(scan.memo):
        f = DOCS / rel
        if rel == MESSAGING or not f.exists() or _status(f) != "draft":
            continue
        fresh = make(scan.memo, {k for k, where in homes.items() if where - {f.resolve()}})
        blocks = [(m[0], diagrams._key(m)) for m in genblocks.BLOCK_RE.finditer(fresh or "")]
        out[rel] = blocks, [s for _t, k in blocks for s in (scan.get(*k) or ("", []))[1]]
    return out


def _homeless(removable: dict[str, set[Key]], old: dict[str, Path]) -> list[str]:
    """The removable pages with a key that no page that stays holds (kept pages count, and so do these once kept)."""
    present, kept = set(_homes({old[rel].resolve() for rel in removable})), []
    while more := [rel for rel, keys in removable.items() if rel not in kept and not keys <= present]:
        kept += more
        for rel in more:
            present |= removable[rel]
    return kept


def _logged(out: dict, log) -> dict:
    for mark, key in (("✔ moved", "moved"), ("✖ deleted", "deleted"), ("· kept", "kept"), ("✔ relinked", "relinked"),
                      ("· links to a removed page, left as they are:", "links"),
                      ("· translation of a removed page, left as it is:", "translations")):
        for line in out[key]:
            log(f"{mark} {line}")
    return out


# ---------- the links to the removed pages ----------
def _successor(rel: str) -> str:
    """The new page (docs-relative) that took over the removed old page `rel`: a repo's page, else the home."""
    parts = rel.split("/")
    if parts[0] == "repos":
        return REPO_PAGE.format(repo=parts[1])
    return REPO_PAGE.format(repo=parts[1][:-len(".md")]) if parts[0] == "data" else HOME


def _relative(target: str, page: str) -> str:
    """The path of docs page `target` as seen from docs page `page` (both docs-relative, posix)."""
    t, base, n = target.split("/"), page.split("/")[:-1], 0
    while n < len(base) and n < len(t) - 1 and base[n] == t[n]:
        n += 1
    return "/".join([".."] * (len(base) - n) + t[n:])


def _link_spans(body: str):
    """(start, end, href) of every Markdown link target in `body` outside code: inline `[text](target)` and reference
    definitions `[id]: target` (the quality check's own patterns, so it sees what this sees)."""
    fence, pos = None, 0
    for line in body.splitlines(keepends=True):
        m = quality.FENCE_RE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
        elif fence is None:
            prose = quality.INLINE_CODE_RE.sub(lambda c: " " * len(c.group(0)), line)
            for rx in (quality.LINK_RE, quality.REF_DEF_RE):
                for link in rx.finditer(prose):
                    yield pos + link.start(1), pos + link.end(1), link.group(1)
        pos += len(line)


def _removed_target(href: str, page: str, gone: set[str]) -> str | None:
    """The removed page (docs-relative) that `href`, written in docs page `page`, points to; None for any other link."""
    if re.match(r"^[a-z][a-z0-9+.-]*:|^/", href, re.I):
        return None
    target = unquote(href.split("?", 1)[0]).partition("#")[0]
    page_to = quality.resolve(page, target) if target.endswith(".md") else None
    return page_to if page_to in gone else None


def _relink(gone: set[str]) -> tuple[list[str], list[str]]:
    """After the deletes: point the links to the pages in `gone` (docs-relative) at the page that took over (`_successor`,
    as a path relative to the linking page, `#anchor` dropped) and return (the pages rewritten, the pages left with such
    a link, `docs/…`). Every docs page is looked at but the translations (`i18n/`) and the dot folders: the pages adopt
    wrote too, since those it filled keep their prose (a page written whole from kit text links only to new pages). Only
    the target changes, in the text of the page, frontmatter and the rest byte for byte, and never inside a generated
    block (an edit there would read as made by hand); only a page that is not a person's (`_status`) is rewritten, and
    only when the page that took over exists. A page that is not UTF-8 is never written: with such a link it is listed,
    and so is a page that cannot be read or written (a lock, a permission)."""
    relinked, left = [], []
    for f in sorted(DOCS.rglob("*.md")):
        rel = f.relative_to(DOCS).as_posix()
        if rel.split("/")[0] == "i18n" or any(p.startswith(".") for p in rel.split("/")):
            continue
        try:
            done = _relink_page(f, rel, gone)
        except OSError:
            done = False
        if done is not None:
            (relinked if done else left).append(rel_file(f))
    return relinked, left


def _relink_page(f: Path, rel: str, gone: set[str]) -> bool | None:
    """`_relink` on one page: True when its links were rewritten, False when it has such a link left as it is, None
    when it has none."""
    raw = f.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        return False if any(_removed_target(h, rel, gone) for _a, _b, h in _link_spans(docs.parse_fm(text)[1])) else None
    _fm, body, _valid = docs.parse_fm(text)
    start = len(text) - len(body)
    blocks = [(m.start(), m.end()) for m in genblocks.BLOCK_RE.finditer(body)]
    hits = [(a, b, t) for a, b, href in _link_spans(body) if (t := _removed_target(href, rel, gone))
            and not any(x <= a < y for x, y in blocks)]
    if not hits:
        return None
    if _status(f) == "closed" or not all((DOCS / _successor(t)).is_file() for _a, _b, t in hits):
        return False
    for a, b, t in reversed(hits):
        body = body[:a] + _relative(_successor(t), rel) + body[b:]
    f.write_bytes((text[:start] + body).encode("utf-8"))
    return True


def _translations(gone: set[str]) -> list[str]:
    """The translations (`docs/i18n/<lang>/<page>`) that exist of the pages in `gone`; they are only listed."""
    langs = sorted(d for d in (DOCS / "i18n").glob("*") if d.is_dir())
    return [rel_file(d / rel) for rel in sorted(gone) for d in langs if (d / rel).is_file()]


def adopt(log=lambda _: None) -> dict:
    """`camaron pages --adopt`: move an old-layout project to the new pages. An old page (`old_pages`) stays exactly as
    it is, blocks included, when a person owns or confirmed it, when the new pages have no place for one of its blocks (a kind with
    no `TARGET`, a person's page that lacks it or holds another copy of it, a page that will not exist), when it is
    not the kit's, when it has anyone's words besides the kit's (`kit_only` against what the 4.x kit would write today),
    or when another old page carries a different copy of one of its blocks. The new pages are written (`_write_new`, the
    removable pages not counting as a block's home; a person's page, `_status` `closed`, is never written); an agent's
    draft home or repo page gets only the blocks (`_draft_blocks`, the cards under its TL;DR, its x-sources extended);
    the removable pages' confirmed, hand-edited and unknown blocks go verbatim into their new page (`place`), the
    others are there fresh. Then a removable page is deleted only when every block it held (but the dropped `gone`
    ones) is in a page that stays, and its carried blocks' pages exist; a failure while writing deletes nothing. Nothing is
    done while some repo is not on this machine, or while the home is a person's page without the cards. Only after the
    deletes, the links to the deleted pages are pointed at the pages that took over (`_relink`) and their translations
    are listed, never edited or deleted; then `docs/llms.txt` is regenerated (a failure is only logged). Returns
    {"moved": ["<kind> <repo>[ <id>] → docs/<page>"], "deleted", "kept": ["docs/<page>: <reason>"], "relinked" (pages
    whose links were rewritten), "links" (pages with a link to a deleted page that were not rewritten), "translations"}
    (`docs/…` paths)."""
    out = {k: [] for k in ("moved", "deleted", "kept", "relinked", "links", "translations")}
    old = {f.relative_to(DOCS).as_posix(): f for f in old_pages()}
    home = DOCS / HOME
    why = ("not every repo is on this machine" if not diagrams._complete() else
           _persons_page(home, "the cards")
           if home.exists() and _status(home) == "closed" and not any(k[0] == "repos" for k in _keys(home)) else None)
    if not old or why:
        out["kept"] = [f"{rel_file(f)}: {why}" for f in old.values()]
        return _logged(out, log)
    scan = genblocks.Scanner()
    removable: dict[str, tuple[list[tuple[str, Key]], set[Key]]] = {}
    for rel, f in old.items():
        why, carried, keys = _judge(rel, f.read_text(encoding="utf-8"), scan)
        if why:
            out["kept"].append(f"{rel_file(f)}: {why}")
        else:
            removable[rel] = carried, keys
    copies: dict[Key, set[str]] = {}
    for carried, _k in removable.values():
        for text, key in carried:
            copies.setdefault(key, set()).add(text)
    for rel in [r for r, (carried, _k) in removable.items() if any(len(copies[k]) > 1 for _t, k in carried)]:
        out["kept"].append(f"{rel_file(old[rel])}: another old page holds a different copy of the same block")
        del removable[rel]
    closed = frozenset(DOCS / rel for rel, _r, _m in _specs(scan.memo)
                       if (DOCS / rel).exists() and _status(DOCS / rel) == "closed")
    _write_new(log, exclude=frozenset(old[rel] for rel in removable), frozen=closed)
    drafts = _draft_blocks({old[rel].resolve() for rel in removable}, scan)
    puts = {rel: list(blocks) for rel, (blocks, _sources) in drafts.items()}
    for rel in [r for r, (carried, _k) in removable.items()
                if any(not (DOCS / _target(k)).is_file() for _t, k in carried)]:   # a page `_write_new` did not create
        out["kept"].append(f"{rel_file(old[rel])}: some of its blocks have no other home")
        del removable[rel]
    for carried, _k in removable.values():
        for text, key in carried:
            if _status(DOCS / _target(key)) == "closed":                    # it holds this very block (`_no_place`)
                continue
            puts.setdefault(_target(key), []).append((text, key))
            out["moved"].append(f"{' '.join(filter(None, key))} → docs/{_target(key)}")
    for rel, blocks in puts.items():                                         # every page first, then any deletion
        f = DOCS / rel
        text = f.read_text(encoding="utf-8")
        fm, body, _valid = docs.parse_fm(text)
        new_body = functools.reduce(lambda b, item: _put(b, *item), blocks, body)
        if new_body == body:
            continue
        sources = drafts.get(rel, ((), ()))[1]
        new = (docs.join_fm({**fm, "x-sources": list(dict.fromkeys([*(fm.get("x-sources") or []), *sources]))}, new_body)
               if sources else text[:len(text) - len(body)] + new_body)
        f.write_text(new, encoding="utf-8", newline="\n")
        log(f"✔ {rel_file(f)}")
    homeless = _homeless({rel: keys for rel, (_c, keys) in removable.items()}, old)
    gone = set()
    for rel in removable:
        if rel in homeless:
            out["kept"].append(f"{rel_file(old[rel])}: some of its blocks have no other home")
        else:
            old[rel].unlink()
            out["deleted"].append(rel_file(old[rel]))
            gone.add(rel)
    out["relinked"], out["links"] = _relink(gone) if gone else ([], [])
    out["translations"] = _translations(gone)
    _logged(out, log)
    if gone:                                                                 # llms.txt still lists the deleted pages
        try:
            docs.llms()
        except Exception as e:                                               # the move is done: say it, don't undo it
            log(f"· docs/llms.txt not regenerated ({e}): run camaron llms")
    return out
