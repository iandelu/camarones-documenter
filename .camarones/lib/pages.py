"""Pages from the code (no AI): what a fresh install writes as the project's front door, from facts the static scans
already know. `facts(memo)` counts them per repo: stack, endpoints, tables, datastores, topics, the repos it calls, state
enums, environment variables and commands, plus the dependencies of the whole project, and says which files they were
read from. `repos_block(memo)` is the `repos` generated block of `docs/index.md`: one card line per repo, linking to its
page. Two layouts: the project home (`HOME`, `_system`) and one page per repo (`REPO_PAGE`), plus the messaging page
(`MESSAGING`). A fact that is zero is said so plainly (`count`), never hidden and never invented. `layout()` says whether
a project still has the old pages (`reference.md`, `diagrams.md`, `first-look.md`…), which a fresh install no longer
writes. `home_page`, `repo_page` and `messaging_page` write a whole page as text from the facts, with a block for every
key the code has."""
from __future__ import annotations

from pathlib import Path

from .common import DOCS, repo_dir
from . import diagrams, docs, genblocks, inventory, schemas

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


def _sections(items: list[tuple[str, str]]) -> str:
    """Blocks (kind, text) in page order as sections: consecutive kinds sharing a `TARGET` heading share a `## ` section
    (none for the cards), a kind with a summary is folded in `:::details`."""
    out, heading = [], None
    for kind, text in items:
        _page, h, summary = TARGET[kind]
        if h and h != heading:
            out.append(f"## {h}")
        heading = h
        out.append(f":::details {summary}\n{text}\n:::" if summary else text)
    return "\n\n".join(out)


def _page(title: str, description: str, tags: list[str], draw: _Draw, tldr: str, body: str, tutorial: str) -> str:
    fm = {"type": "overview", "title": title, "description": description, **({"tags": tags} if tags else {}),
          "x-sources": list(dict.fromkeys(draw.sources)), "x-owner": "ai", "x-generated": True}
    details = f":::details How this page is made\n{DETAILS.format(tutorial=tutorial)}\n:::"
    return docs.join_fm(fm, f"# {title}\n\n> **TL;DR:** {tldr}\n\n{body}\n\n{details}\n")


def home_page(memo: dict, skip: set[Key] = frozenset()) -> str | None:
    """`docs/index.md` as a whole page: the TL;DR, a card per repo, the context map and where to read on. None when
    there is no repo or some repo is not on this machine (the cards would show a part of the project)."""
    if repos_block(memo) is None:
        return None
    draw, f = _Draw(memo, skip), facts(memo)
    cards, context = draw("repos", SYSTEM), draw("context", SYSTEM)
    items = [("repos", f":::cards\n{cards}\n:::")] if cards else []
    items += [("context", context)] if context else []
    more = ["- [Stack and tooling](overview/tooling.md)", "- [Libraries](overview/libraries.md)"]
    if any(r["publishes"] or r["consumes"] for r in f["repos"].values()):
        more.append("- [Messaging](architecture/messaging.md)")
    body = "\n\n".join(filter(None, [_sections(items), "## More\n\n" + "\n".join(more)]))
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
