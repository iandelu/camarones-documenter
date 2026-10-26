"""The board's index: a derived SQLite database of footprints, code-map edges and doc citations.

It answers the questions the screen and `board next` ask on every interaction (who touches this file, which pages cite
it, what depends on what) without re-reading every card and graph. Nothing in it is the source of truth: it is rebuilt
from the cards, graphify's graphs and the docs' `x-sources` whenever their stats change, and losing the file loses
nothing. It lives under the cache, so uninstall removes it with the rest.

Safety (spec §5): one short-lived connection per call; `journal_mode=DELETE` (no WAL side files to leave behind on
Windows); a rebuild is written to a temp file named with the pid and moved into place with `os.replace`, so a crash
never leaves a half-built db and two processes rebuilding at once cannot corrupt it; any `sqlite3.Error` deletes the
file and rebuilds once; if that fails too the index is built in `:memory:` for this call and a warning is logged.

Beyond the six tables of the spec, the schema has additive columns/tables the queries need: `items.repos` (the declared
`x-repos`, which `deps.Node` carries), `cites.grp` (the group of a cited file), `files` (every file of every repo's
code map with its group, so a story being drafted can search and group files no card touches yet) and `pages` (every
doc page and its title). `edges` holds every file-level edge of every graph, so code order works for subtasks that are
not saved yet.

Queries return plain Python data (lists, sets, dicts of str), never sqlite rows. The caller closes the connection."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import PurePosixPath

from .. import codemap, docs
from ..common import CACHE, CAM_DIR, ROOT, WS_FILE
from . import ARCHIVE, BOARD, TASKS
from .deps import Node, norm_touch
from .items import load_dir
from .state import id_key

log = logging.getLogger("camaron.board.index")

DB = CACHE / "board.db"
FORMAT = 1
DOCS_REPO = "cam-docs"                        # the repo name of doc pages in touches
DOCS_GROUP = "docs"
REPLACE_TRIES, REPLACE_WAIT = 10, 0.03        # Windows: os.replace onto a db another process holds open
STALE_TMP = 3600                              # seconds before another process's leftover temp db is swept
_CHUNK = 400                                  # bound variables per statement (sqlite allows at least 999)

SCHEMA = """
create table meta(key text primary key, value text);
create table items(id text primary key, uid text, type text, status text, priority text, parent text, title text,
                   archived integer, repos text);
create table touches(id text, repo text, path text, grp text);
create index touches_file on touches(repo, path);
create index touches_grp on touches(repo, grp);
create table deps(id text, dep text);
create table edges(repo text, src text, dst text);
create index edges_src on edges(repo, src);
create table cites(page text, repo text, path text, grp text);
create index cites_file on cites(repo, path);
create index cites_page on cites(page);
create table pages(touch text primary key, title text);
create table files(repo text, path text, grp text);
create index files_file on files(repo, path);
create index files_grp on files(repo, grp);
"""


# ── freshness ────────────────────────────────────────────────────────────────────────────────────────────────────

def _stats() -> Iterator[tuple[str, int, int]]:
    """(name, size, mtime_ns) of every file the index is derived from. Stats only: no file is opened."""
    files = [("workspace", WS_FILE), ("board", BOARD)]
    files += [(f"task/{f.name}", f) for f in TASKS.glob("*.md")]
    files += [(f"archive/{f.name}", f) for f in ARCHIVE.glob("*.md")]
    for logical, f in docs.iter_docs():
        files.append((f"doc/{logical}", f))
    for repo in docs.repo_names():
        files.append((f"graph/{repo}", codemap.graph_file(repo)))
    for name, f in files:
        try:
            st = f.stat()
        except OSError:
            continue
        yield name, st.st_size, st.st_mtime_ns


def snapshot() -> str:
    """sha256 over the sorted stats of the board, its cards, the docs and each repo's graph."""
    h = hashlib.sha256()
    for name, size, mtime in sorted(_stats()):
        h.update(f"{name}\0{size}\0{mtime}\n".encode("utf-8"))
    return h.hexdigest()


# ── building ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _split(touch: str) -> tuple[str, str] | None:
    try:
        repo, _, path = norm_touch(touch, fold=False).partition(":")
    except ValueError:
        return None
    return (repo, path) if path else None


def _source(ref: object) -> tuple[str, str] | None:
    """`(repo, path)` of an `x-sources` entry (`repo:path#Symbol` or `repo://repo/path`); None when it is not a file."""
    if not isinstance(ref, str):
        return None
    ref = ref.split("#", 1)[0].strip()
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    repo, sep, path = ref.partition(":")
    if not sep:
        return None
    if repo.strip() in ("umbrella", ".", CAM_DIR):
        repo = DOCS_REPO
    return _split(f"{repo}:{path}")


def _folder(repo: str, path: str) -> str:
    """The group of a file the code map does not know: the name of its folder (the repo's for a top-level file)."""
    return PurePosixPath(path).parent.name or repo


class _Groups:
    """The group of a file: the code map's, else the folder it is in; doc pages are all in `docs`."""

    def __init__(self) -> None:
        self._maps: dict[str, dict[str, str]] = {}

    def map(self, repo: str) -> dict[str, str]:
        if repo not in self._maps:
            try:
                self._maps[repo] = codemap.group_of(repo) if codemap.graph_file(repo).is_file() else {}
            except (ValueError, OSError, KeyError, TypeError) as e:         # one bad graph must not break the index
                log.warning("code map of %s unreadable, using folders as groups: %s", repo, e)
                self._maps[repo] = {}
        return self._maps[repo]

    def of(self, repo: str, path: str) -> str:
        if repo == DOCS_REPO:
            return DOCS_GROUP
        return self.map(repo).get(path) or _folder(repo, path)


def _item_rows() -> list[tuple[dict, bool]]:
    from . import ops
    try:
        cards, items, _ = ops.load_state()
    except ops.BoardError:                      # no board yet, or an unreadable board.yaml: the cards still list
        found, _ = load_dir(TASKS)
        cards, items = {}, {i.id: i for i in found}
    rows = [(ops._row(item, cards.get(item_id)), False) for item_id, item in items.items()]
    archived, _ = load_dir(ARCHIVE)                 # sorted by file name
    seen = set(items)
    for i in archived:
        if i.id in seen:
            log.warning("board index: %s is in more than one file; keeping the first, ignoring %s", i.id, i.path)
            continue
        seen.add(i.id)
        rows.append((ops._row(i, None), True))
    return rows


def _text(v: object) -> str | None:
    """A scalar as text for a column; hand-written lists and numbers must not make a bind fail."""
    return None if v is None else v if isinstance(v, str) else str(v)


def _strings(v: object) -> list[str]:
    """A field people write as a list or as a lone value; anything that is not text is dropped."""
    return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, (list, tuple)) else []


def _page_touch(logical: str, f) -> str:
    try:
        rel = f.relative_to(ROOT).as_posix()
    except ValueError:
        rel = f"{DOCS_GROUP}/{logical}"
    return f"{DOCS_REPO}:{rel}"


def _build(conn: sqlite3.Connection, snap: str) -> None:
    conn.execute("pragma journal_mode=delete")
    conn.execute("pragma synchronous=off")           # a temp file: until os.replace it is not the database
    conn.executescript(SCHEMA)
    groups = _Groups()

    items, touches, deps = [], [], []
    for row, archived in _item_rows():
        items.append((row["id"], _text(row["uid"]), _text(row["type"]), _text(row["status"]), _text(row["priority"]),
                      _text(row["parent"]), _text(row["title"]), int(archived), json.dumps(row["repos"])))
        seen = set()
        for ref in row["touches"]:
            rp = _split(ref)
            if rp and rp not in seen:
                seen.add(rp)
                touches.append((row["id"], rp[0], rp[1], groups.of(*rp)))
        deps += [(row["id"], d) for d in sorted(set(row["dependencies"]))]

    cites, pages = [], []
    for logical, f in docs.iter_docs():
        try:
            fm, body, _ = docs.parse_fm(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        page = _page_touch(logical, f)
        pages.append((page, str(fm.get("title") or docs.first_heading(body) or logical)))
        for rp in sorted({s for s in map(_source, _strings(fm.get("x-sources"))) if s}):
            cites.append((page, rp[0], rp[1], groups.of(*rp)))

    files, edges = [], []                            # the whole code map of every repo that has a graph
    for repo in docs.repo_names():
        if codemap.graph_file(repo).is_file():
            files += [(repo, path, grp) for path, grp in sorted(groups.map(repo).items())]
            edges += [(repo, s, d) for s, d in sorted(codemap.file_edges(repo))]

    conn.executemany("insert into items values (?,?,?,?,?,?,?,?,?)", items)
    conn.executemany("insert into touches values (?,?,?,?)", touches)
    conn.executemany("insert into deps values (?,?)", deps)
    conn.executemany("insert into edges values (?,?,?)", edges)
    conn.executemany("insert into cites values (?,?,?,?)", cites)
    conn.executemany("insert into files values (?,?,?)", files)
    conn.executemany("insert or replace into pages values (?,?)", pages)
    conn.executemany("insert into meta values (?,?)", [("format", str(FORMAT)), ("snapshot", snap)])
    conn.commit()


# ── connecting ───────────────────────────────────────────────────────────────────────────────────────────────────

def _unlink(path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:                                 # still open in another process (Windows): let it be
        pass


def _fresh(snap: str) -> sqlite3.Connection | None:
    """A connection to the db on disk when it is of this format and snapshot, else None. sqlite3.Error if unreadable."""
    if not DB.exists():
        return None
    conn = sqlite3.connect(DB)
    try:
        meta = dict(conn.execute("select key, value from meta").fetchall())
        if meta.get("format") == str(FORMAT) and meta.get("snapshot") == snap:
            return conn
    except BaseException:
        conn.close()
        raise
    conn.close()
    return None


def _replace(tmp, dest) -> bool:
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(tmp, dest)
            return True
        except PermissionError:                     # Windows: another process has `dest` open
            if attempt + 1 < REPLACE_TRIES:
                time.sleep(REPLACE_WAIT)
    return False


def _sweep_temps() -> None:
    """Leftovers of rebuilds that were killed half way (other pids' temp files, long idle)."""
    for f in DB.parent.glob(DB.name + ".tmp-*"):
        try:
            if time.time() - f.stat().st_mtime > STALE_TMP:
                f.unlink()
        except OSError:
            pass


def _in_memory(snap: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    try:
        _build(conn, snap)
    except BaseException:
        conn.close()
        raise
    return conn


def _rebuild(snap: str) -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB.with_suffix(f".db.tmp-{os.getpid()}")
    _unlink(tmp)
    conn = sqlite3.connect(tmp)
    try:
        _build(conn, snap)
        conn.close()
        replaced = _replace(tmp, DB)
    except BaseException:
        conn.close()
        _unlink(tmp)
        raise
    _unlink(tmp)
    _sweep_temps()
    if replaced:
        return sqlite3.connect(DB)
    conn = _fresh(snap)                              # someone else holds the db: they may have rebuilt it just now
    if conn is not None:
        return conn
    log.warning("board index: %s is locked by another process; using an in-memory index for this call", DB)
    return _in_memory(snap)


def connect() -> sqlite3.Connection:
    """A connection to an index that matches the files on disk, rebuilding it first when they changed. Caller closes."""
    snap = snapshot()
    for _ in range(2):
        try:
            return _fresh(snap) or _rebuild(snap)
        except (sqlite3.Error, OSError) as e:
            log.info("board index unusable (%s); rebuilding", e)
            _unlink(DB)
    log.warning("board index: cannot write %s; using an in-memory index for this call", DB)
    return _in_memory(snap)


# ── queries ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _chunks(values: list, n: int = _CHUNK) -> Iterator[list]:
    for i in range(0, len(values), n):
        yield values[i:i + n]


def _by_repo(touches: Iterable[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for t in touches:
        rp = _split(t)
        if rp:
            out[rp[0]].add(rp[1])
    return out


def _marks(n: int) -> str:
    return ",".join("?" * n)


def nodes(conn: sqlite3.Connection) -> list[Node]:
    """Every item, open or archived, as the pure functions of `deps` take it; sorted by id."""
    touches: dict[str, set[str]] = defaultdict(set)
    for item_id, repo, path in conn.execute("select id, repo, path from touches"):
        touches[item_id].add(f"{repo}:{path}")
    needs: dict[str, set[str]] = defaultdict(set)
    for item_id, dep in conn.execute("select id, dep from deps"):
        needs[item_id].add(dep)
    out: list[Node] = [
        {"id": i, "status": status, "priority": priority, "touches": sorted(touches[i]),
         "repos": json.loads(repos or "[]"), "deps": sorted(needs[i], key=id_key), "archived": bool(archived)}
        for i, status, priority, archived, repos in conn.execute(
            "select id, status, priority, archived, repos from items")]
    return sorted(out, key=lambda n: id_key(n["id"]))


def edges(conn: sqlite3.Connection, touches: Iterable[str]) -> set[tuple[str, str]]:
    """Code-map dependencies `(src, dst)`, repo-qualified, between files that are both in `touches`."""
    out: set[tuple[str, str]] = set()
    for repo, paths in _by_repo(touches).items():
        for chunk in _chunks(sorted(paths)):
            for src, dst in conn.execute(
                    f"select src, dst from edges where repo = ? and src in ({_marks(len(chunk))})", [repo, *chunk]):
                if dst in paths:
                    out.add((f"{repo}:{src}", f"{repo}:{dst}"))
    return out


def pages_citing(conn: sqlite3.Connection, touches: Iterable[str]) -> list[str]:
    """Doc pages (as `cam-docs:<path>`) whose `x-sources` cite any of these files; sorted."""
    pages: set[str] = set()
    for repo, paths in _by_repo(touches).items():
        for chunk in _chunks(sorted(paths)):
            pages.update(p for (p,) in conn.execute(
                f"select distinct page from cites where repo = ? and path in ({_marks(len(chunk))})", [repo, *chunk]))
    return sorted(pages)


def cites(conn: sqlite3.Connection, touches: Iterable[str]) -> dict[str, set[str]]:
    """`{page touch: the code files it cites}` for the pages among `touches` and for the pages citing any other
    entry of `touches`. A page that cites nothing is left out."""
    given = list(touches)
    pages = {t for t in given if t.startswith(DOCS_REPO + ":")} | set(pages_citing(conn, given))
    out: dict[str, set[str]] = defaultdict(set)
    for chunk in _chunks(sorted(pages)):
        for page, repo, path in conn.execute(
                f"select page, repo, path from cites where page in ({_marks(len(chunk))})", chunk):
            out[page].add(f"{repo}:{path}")
    return dict(out)


def groups(conn: sqlite3.Connection, touches: Iterable[str]) -> dict[str, str]:
    """`{touch: group label}` for every valid entry of `touches`: the code map's group, else the one a card or page
    recorded, else (a file the graph does not know yet, or a repo without a graph) the name of its folder."""
    out: dict[str, str] = {}
    for repo, paths in _by_repo(touches).items():
        if repo == DOCS_REPO:
            out.update({f"{repo}:{p}": DOCS_GROUP for p in paths})
            continue
        for table in ("files", "touches", "cites"):
            for chunk in _chunks(sorted(paths)):
                for path, grp in conn.execute(
                        f"select distinct path, grp from {table} where repo = ? and path in ({_marks(len(chunk))})",
                        [repo, *chunk]):
                    out.setdefault(f"{repo}:{path}", grp)
        out.update({f"{repo}:{p}": _folder(repo, p) for p in paths if f"{repo}:{p}" not in out})
    return out


_KIND_ORDER = {"file": 0, "group": 1, "page": 2}


def search(conn: sqlite3.Connection, q: str, limit: int = 20) -> list[dict]:
    """Files, groups and doc pages whose name starts with `q` (first) or contains it, case-insensitive. A group's touch
    is `repo:<group label>`. Files are the code map's, plus any a card or page names."""
    q = q.strip().lower()
    if not q:
        return []
    found: list[tuple[int, int, str, dict]] = []

    def consider(kind: str, touch: str, group: str, names: list[str], title: str | None = None) -> None:
        low = [n.lower() for n in names] + [touch.lower()]
        rank = 0 if any(n.startswith(q) for n in low) else 1 if any(q in n for n in low) else None
        if rank is None:
            return
        hit = {"touch": touch, "group": group, "kind": kind}
        if title:
            hit["title"] = title
        found.append((rank, _KIND_ORDER[kind], touch.lower(), hit))

    conn.create_function("plower", 1, lambda v: v.lower(), deterministic=True)
    every = " union ".join(f"select repo, path, grp from {t} where repo != ?1" for t in ("files", "touches", "cites"))
    for repo, path, grp in conn.execute(
            f"select * from ({every}) where instr(plower(repo || ':' || path), ?2) > 0", (DOCS_REPO, q)):
        consider("file", f"{repo}:{path}", grp, [PurePosixPath(path).name, path])
    for repo, grp in conn.execute(f"select distinct repo, grp from ({every})", (DOCS_REPO,)):
        consider("group", f"{repo}:{grp}", grp, [grp])
    for touch, title in conn.execute("select touch, title from pages"):
        consider("page", touch, DOCS_GROUP, [title, PurePosixPath(touch).name], title)
    found.sort(key=lambda x: x[:3])
    return [hit for *_, hit in found[:max(limit, 0)]]
