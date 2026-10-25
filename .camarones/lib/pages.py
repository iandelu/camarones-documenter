"""Pages from the code (no AI): what a fresh install writes as the project's front door, from facts the static scans
already know. `facts(memo)` counts them per repo: stack, endpoints, tables, datastores, topics, the repos it calls, state
enums, environment variables and commands, plus the dependencies of the whole project, and says which files they were
read from. `repos_block(memo)` is the `repos` generated block of `docs/index.md`: one card line per repo, linking to its
page. Two layouts: the project home (`HOME`, `_system`) and one page per repo (`REPO_PAGE`). A fact that is zero is
said so plainly (`count`), never hidden and never invented."""
from __future__ import annotations

from .common import repo_dir
from . import diagrams, docs, genblocks, inventory, schemas

SYSTEM = "_system"                                                          # reserved repo name: the whole system
HOME = "index.md"
REPO_PAGE = "repos/{repo}/index.md"
MESSAGING = "architecture/messaging.md"


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
