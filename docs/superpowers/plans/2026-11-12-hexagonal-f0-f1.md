# Hexagonal refactor F0 + F1 (guardrails and core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the guardrails of the layered refactor in CI (architecture test, facade guard, CLI and HTTP snapshots) and
move `common.py`, `harness/ctx.py` and `harness/locks.py` into `.camarones/lib/core/` behind facades, with no
behaviour change.

**Architecture:** F0 adds test-only code: an `ast` import-graph scanner, a layer table for every module, an allowlist
of today's debts that can only shrink, a `monkeypatch` that refuses to patch facades, and snapshots of the CLI parser
and of each HTTP route's access level. F1 creates `lib/core/` (`platform`, `fsutil`, `ctx`, `locks`, `process`,
`paths`) and leaves `lib/common.py`, `lib/harness/ctx.py` and `lib/harness/locks.py` as facades. Consumers keep
importing `common` in F1; they move when their own module moves in a later phase.

**Tech Stack:** Python 3.11+ stdlib (`ast`, `argparse`, `http.server`, `importlib`), pytest + pytest-xdist, PyYAML (all
already dev dependencies in `pyproject.toml`).

**Spec:** `docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md`

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read and write, processes through the kit
  helpers, `IS_WIN`/`IS_MAC` instead of `sys.platform` (AGENTS.md §2.1).
- No new dependency of any kind.
- Old import paths keep working: `lib.common`, `lib.harness.ctx`, `lib.harness.locks` become facades that set
  `__facade__ = "<new module>"` and list their re-exported names in `__all__` (explicit imports, never `import *`).
- `VERSIONS` stays a literal dict in `.camarones/lib/common.py`, with the `"kit": "4.81.0"` line unchanged:
  `install.py:115`, `upgrade.py:76,94,149-162` and every older installed kit find the kit version by searching that
  file's text.
- No `VERSIONS["kit"]` bump. Every commit body ends with "Nothing a user notices." (AGENTS.md §5.1).
- Conventional commits; no `Co-Authored-By` or "Generated with" trailer. Stage only this plan's files: other sessions
  edit the tree in parallel.
- Tests are offline and deterministic, use the `kit` / `isolated_env` fixtures, and pass with `uv run pytest -n auto`
  from the repository root.
- Code and comments in English, comments only for a non-obvious *why*.

## Review Focus

- An older 4.x kit upgrading to this one reads the version from `common.py` as text → it must still find
  `"kit": "<VERSIONS['kit']>"` there (test in Task 7).
- A module that imports only `lib.common` must still get the PATH extended at import (`ensure_path()` ran at import
  of `common`; it now runs at import of `core.process`) (test in Task 7).
- Code catching `harness.locks.LockBusy` or `plan`'s `LockBusy` must catch what `core.locks` raises → the facade
  re-exports the same class objects, not copies (test in Task 6).
- `KIT` is computed from `ctx.py`'s own location (`parents[2]`) → after the move it must still be `.camarones/`
  (test in Task 6).
- Probing a route for the HTTP snapshot must never run its handler (no job, no write, no git): every POST probe
  answers 400 or 403 (test in Task 5).

---

### Task 1: Import-graph scanner

**Files:**
- Create: `tests/fixtures/archscan.py`
- Test: `tests/test_archscan.py`

**Interfaces:**
- Produces (used by Tasks 2, 3):
  - `modules(kit_dir: Path) -> dict[str, Path]`: every `*.py` under `kit_dir / "lib"` keyed by its dotted name
    relative to `lib` (`"harness.locks"`; a package's `__init__.py` is the package name, `"adapters.runners"`), plus
    `"camarones"` for `kit_dir / "camarones.py"`. `lib/__init__.py` itself is left out.
  - `edges(mods: dict[str, Path]) -> set[tuple[str, str]]`: `(importer, imported)` for every import statement
    anywhere in a file (module level, inside functions, under `if TYPE_CHECKING:`), resolved as below, keeping only
    targets that are keys of `mods`, never a self-edge.
  - `largest_cycle(nodes: Iterable[str], edges: set[tuple[str, str]]) -> int`: size of the largest strongly
    connected component with more than one node (Tarjan, iterative); 0 when there is none.
  - `line_count(path: Path) -> int`: `len(path.read_text(encoding="utf-8").splitlines())`.

Resolution rules for `edges`:
- `from <dots><mod> import a, b` (level L ≥ 1) in module X: the package of X is X itself when X is a package,
  otherwise X without its last part; drop L−1 trailing parts to get the base; target = base + mod. For each name:
  if `target.name` is a module, that is the edge; otherwise the edge goes to `target` when it is a module.
- `from lib[.mod] import a` (level 0): the same, with the leading `lib`/`lib.` removed (`from lib import a` → target
  is the root, so the name decides).
- `import lib.x.y` → `x.y`.

- [ ] **Step 1: Write the failing tests**

```python
TREE = {
    "lib/__init__.py": "",
    "lib/a.py": "from .pkg import b\nimport json\n",
    "lib/pkg/__init__.py": "from .c import Y\n",
    "lib/pkg/b.py": "from ..a import X\n\ndef f():\n    from . import c\n",
    "lib/pkg/c.py": "Y = 1\nfrom typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from . import Y as _\n",
    "camarones.py": "from lib import a\nfrom lib.pkg import c\nimport lib.pkg.b\n",
}

def test_modules_are_named_from_lib(tmp_path):
    assert set(archscan.modules(build(tmp_path, TREE))) == {"a", "pkg", "pkg.b", "pkg.c", "camarones"}

def test_edges_resolve_relative_absolute_and_nested_imports(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.edges(mods) == {
        ("a", "pkg.b"), ("pkg", "pkg.c"), ("pkg.b", "a"), ("pkg.b", "pkg.c"), ("pkg.c", "pkg"),
        ("camarones", "a"), ("camarones", "pkg.c"), ("camarones", "pkg.b")}

def test_largest_cycle_is_the_biggest_strongly_connected_component(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.largest_cycle(mods, archscan.edges(mods)) == 2
    assert archscan.largest_cycle(["x", "y"], {("x", "y")}) == 0

def test_imports_inside_functions_count_on_the_real_kit():
    found = archscan.edges(archscan.modules(KIT_DIR))
    assert ("camarones", "adr_cli") in found and ("serve", "adr_api") in found
```

`build(tmp_path, tree)` writes each entry under `tmp_path / "kit"` with `encoding="utf-8"` and returns that folder;
`KIT_DIR` comes from `conftest`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_archscan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fixtures.archscan'`

- [ ] **Step 3: Implement `modules`, `edges`, `largest_cycle`, `line_count` in `tests/fixtures/archscan.py`**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_archscan.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/archscan.py tests/test_archscan.py
git commit -m "test(arch): an import-graph scanner that sees imports inside functions" -m "Nothing a user notices."
```

### Task 2: The architecture test and today's allowlist

**Files:**
- Modify: `tests/fixtures/archscan.py` (add the rule)
- Create: `tests/architecture/layers.yaml`, `tests/architecture/allowlist.yaml`
- Test: `tests/test_architecture.py`

**Interfaces:**
- Consumes: Task 1's `modules`, `edges`, `largest_cycle`, `line_count`.
- Produces:
  - `ALLOWED: dict[str, frozenset[str]]`, exactly:
    `core: {core}`, `domain: {core, domain}`, `ports: {core, domain, ports}`,
    `adapters: {core, domain, ports, adapters}`, `app: {core, domain, ports, app}`,
    `interfaces: {core, domain, ports, app, interfaces, bootstrap}`, `bootstrap: {core, domain, ports, adapters, app}`.
  - `layer_of(name: str, table: dict[str, str]) -> str | None`: an exact key wins; otherwise the longest key `X.*`
    with `name == X` or `name.startswith(X + ".")`.
  - `violations(edges: set[tuple[str, str]], table: dict[str, str]) -> set[tuple[str, str]]`: edges whose imported
    layer is not in `ALLOWED[importer layer]`.
  - `load_layers() -> dict[str, str]` and `load_allowlist() -> dict` reading the two YAML files.
  - `MAX_LINES = 600`.

`tests/architecture/layers.yaml` (each flat module gets the layer spec §3 sends it to; a module that will be split
gets `app` if any target is `app`, else the highest of `adapters` > `ports` > `domain`):

```yaml
# Layer of every kit module (docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md §2-3).
# Keys are dotted names relative to .camarones/lib (`camarones` is the CLI entry script). "X.*" covers X and below.
core.*: core
domain.*: domain
ports.*: ports
adapters.*: adapters
app.*: app
interfaces.*: interfaces
bootstrap: bootstrap
camarones: interfaces
common: core
harness: core
harness.ctx: core
harness.locks: core
harness.ports: ports
harness.pipeline: domain
harness.routing: domain
harness.pricing: domain
harness.ledger: domain
harness.events: adapters
harness.handoff: adapters
harness.symbols: adapters
harness.transcripts: adapters
harness.awake: adapters
harness.worktrees: adapters
harness.ab: app
harness.comply: app
harness.drafts: app
harness.evals: app
harness.freshness: app
harness.integrate: app
harness.kpis: app
harness.plugin_store: app
harness.plugins: app
harness.runs: app
harness.scheduler: app
adr_doc: domain
stories: domain
kanban.deps: domain
kanban.items: domain
kanban.merge: domain
kanban.state: domain
kanban.xid: domain
kanban: adapters
kanban.index: adapters
binaries: adapters
codemap: adapters
creds: adapters
diagrams: adapters
history: adapters
inventory: adapters
latest: adapters
machine: adapters
osv: adapters
quickarch: adapters
radar: adapters
schemas: adapters
sonar: adapters
terminals: adapters
kanban.ops: app
kanban.repair: app
adr: app
adr_pack: app
agents: app
answers: app
budget: app
bump: app
c4edit: app
ci: app
docs: app
doctor: app
env: app
exporters: app
genblocks: app
guide: app
health: app
hooks: app
install: app
install_state: app
migrate: app
onboard: app
pages: app
plan: app
pr: app
projects: app
propose: app
quality: app
questionnaire: app
removed: app
reset: app
review: app
sessions: app
sourcelinks: app
stories_ai: app
stories_save: app
takeover: app
trust: app
uninstall: app
upgrade: app
usage: app
kanban.cli: interfaces
adr_api: interfaces
adr_cli: interfaces
appapi: interfaces
catalog: interfaces
desktop: interfaces
kitdev: interfaces
mcp: interfaces
serve: interfaces
session_run: interfaces
tutorial: interfaces
wizard: interfaces
```

`tests/architecture/allowlist.yaml` starts as below and is filled in Step 4:

```yaml
# Today's debts against the layer rule (spec §5). Entries only ever leave this file.
largest_cycle: 0
oversize: []
violations: []
```

- [ ] **Step 1: Write the failing tests in `tests/test_architecture.py`**

Each test reads `mods = archscan.modules(KIT_DIR)`, `found = archscan.edges(mods)`, `table = archscan.load_layers()`,
`allow = archscan.load_allowlist()`; an edge is written `"a -> b"`.

- `test_every_module_has_a_layer`: `[m for m in mods if archscan.layer_of(m, table) is None] == []`.
- `test_every_layer_is_known`: `set(table.values()) <= set(archscan.ALLOWED)`.
- `test_no_new_layer_violation`: `violations(found, table)` minus `allow["violations"]` is empty; the message lists
  each offending edge as a YAML line (`  - "a -> b"`) and names spec §2.
- `test_the_allowlist_holds_no_fixed_debt`: `allow["violations"]` minus today's violations is empty; the message says
  to remove those lines.
- `test_core_imports_only_core`: every edge whose importer's layer is `core` imports a `core` module; the allowlist
  does not apply.
- `test_the_largest_cycle_never_grows`: `largest_cycle(mods, found) == allow["largest_cycle"]`; when lower, the
  message says "lower largest_cycle to N".
- `test_big_files_are_listed`: `{m for m, p in mods.items() if line_count(p) > MAX_LINES} == set(allow["oversize"])`.
- `test_every_exact_layer_key_is_a_module`: every key of `layers.yaml` without `.*`, except `bootstrap`, is a key of
  `mods` (a module that leaves the kit leaves the table too).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: FAIL with `AttributeError: module 'fixtures.archscan' has no attribute 'load_layers'`

- [ ] **Step 3: Implement `ALLOWED`, `layer_of`, `violations`, `load_layers`, `load_allowlist`, `MAX_LINES`**

- [ ] **Step 4: Run them to see today's debts**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: `test_no_new_layer_violation`, `test_the_largest_cycle_never_grows` and `test_big_files_are_listed` FAIL,
printing today's violations, the largest cycle and the big files; the other five pass.

- [ ] **Step 5: Seed `allowlist.yaml` from that output**

Copy the printed violation lines (sorted), the largest cycle (about 61 on 2026-11-12) and the big files (12 on
2026-11-12: `camarones`, `wizard`, `env`, `serve`, `plan`, `tutorial`, `docs`, `pages`, `adr`, `kanban.ops`,
`stories`, `schemas`) into the file.

- [ ] **Step 6: Run them to see them pass**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/archscan.py tests/architecture tests/test_architecture.py
git commit -m "test(arch): the layer rule in CI, with today's debts in an allowlist that only shrinks" -m "Nothing a user notices."
```

### Task 3: A monkeypatch that refuses facades

**Files:**
- Create: `tests/fixtures/facade_guard.py`
- Modify: `tests/conftest.py` (a `monkeypatch` fixture that overrides pytest's)
- Modify: `tests/test_architecture.py` (facade shape)
- Test: `tests/test_facade_guard.py`

**Interfaces:**
- Produces:
  - `class GuardedMonkeyPatch(pytest.MonkeyPatch)` whose `setattr(self, target, *args, **kwargs)` resolves the
    owner and the attribute name for both forms (`setattr(obj, "name", value)` and `setattr("pkg.mod.name", value)`:
    import the longest importable prefix, then `getattr` down the rest), raises `AssertionError` when the owner is a
    module with `__facade__` and the name is in its `__all__`, and otherwise calls `super().setattr(target, *args,
    **kwargs)`. Message: `f"{owner.__name__}.{name} is re-exported by a facade: patch it in {owner.__facade__}"`.
  - conftest: `@pytest.fixture def monkeypatch(): mp = GuardedMonkeyPatch(); yield mp; mp.undo()`.
  - A facade is a module that sets `__facade__`. Its body holds only a docstring, imports, and assignments whose value
    `ast.literal_eval` accepts; its `__all__` lists only names bound by its imports. Its own literal data (such as
    `VERSIONS`) stays out of `__all__` and can be patched.

- [ ] **Step 1: Write the failing tests**

```python
def facade(monkeypatch, name="fake_facade"):
    mod = types.ModuleType(name)
    mod.__facade__, mod.__all__, mod.thing, mod.VERSIONS = "lib.core.fake", ["thing"], 1, {"kit": "0"}
    monkeypatch.setitem(sys.modules, name, mod)
    return mod

def test_patching_a_re_exported_name_is_refused(monkeypatch):
    mod = facade(monkeypatch)
    mp = GuardedMonkeyPatch()
    with pytest.raises(AssertionError, match=r"fake_facade\.thing is re-exported by a facade: patch it in lib\.core\.fake"):
        mp.setattr(mod, "thing", 2)
    mp.undo()

def test_the_dotted_string_form_is_refused_too(monkeypatch):
    facade(monkeypatch)
    with pytest.raises(AssertionError, match="facade"):
        GuardedMonkeyPatch().setattr("fake_facade.thing", 2)

def test_a_facade_s_own_data_can_be_patched(monkeypatch):
    mod = facade(monkeypatch)
    monkeypatch.setattr(mod, "VERSIONS", {"kit": "9"})
    assert mod.VERSIONS == {"kit": "9"}

def test_the_fixture_is_the_guarded_one(monkeypatch):
    assert isinstance(monkeypatch, GuardedMonkeyPatch)
```

In `tests/test_architecture.py`: `test_facades_hold_only_imports_and_literals` — for every module of
`archscan.modules(KIT_DIR)` that assigns `__facade__`, check the body rule and the `__all__` rule above (it finds no
facade yet and passes; it bites from Task 6 on).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_facade_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fixtures.facade_guard'`

- [ ] **Step 3: Implement `GuardedMonkeyPatch` and the conftest fixture**

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: `uv run pytest tests/test_facade_guard.py tests/test_architecture.py -v`
Expected: all passed

Run: `uv run pytest -n auto`
Expected: green; no module is a facade yet, so no existing test changes behaviour.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/facade_guard.py tests/conftest.py tests/test_facade_guard.py tests/test_architecture.py
git commit -m "test(arch): patching a name through a facade fails instead of passing for the wrong reason" -m "Nothing a user notices."
```

### Task 4: CLI snapshot

**Files:**
- Create: `tests/fixtures/cli_shape.py`
- Create: `tests/snapshots/cli.json` (generated in Step 4)
- Test: `tests/test_cli_snapshot.py`

**Interfaces:**
- Produces:
  - `shape(parser: argparse.ArgumentParser) -> dict`:
    `{"args": [row, …], "subcommands": {name: {"aliases": [...], "args": [...], "subcommands": {...}}}}`.
    Subparser names that map to the same parser object are one entry: the first registered name is the key, the rest
    are its `aliases`. A row is
    `{"dest", "options": sorted(option_strings), "nargs", "default", "const", "choices", "required", "action"}`
    with `action = type(a).__name__`; `_HelpAction` is skipped; a `_SubParsersAction` becomes `subcommands`; actions
    with `help=SUPPRESS` are kept (they are part of the surface).
  - `jsonable(v)`: `None`/`bool`/`int`/`float`/`str` as is; list/tuple → list of `jsonable`; any `PurePath` →
    `"<Path>"`; anything else → `f"<{type(v).__name__}>"`.
  - Run as a script, it puts `.camarones/` on `sys.path`, imports `camarones`, and prints
    `json.dumps(shape(camarones.build_parser()), indent=1, sort_keys=True)`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_cli_surface_is_unchanged(kit):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(TESTS / "fixtures" / "cli_shape.py")], env=env, cwd=kit.root,
                       capture_output=True, text=True, encoding="utf-8", check=True)
    now = json.loads(r.stdout)
    snap = TESTS / "snapshots" / "cli.json"
    if os.environ.get("CAMARONES_UPDATE_SNAPSHOTS") == "1":
        snap.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    assert now == json.loads(snap.read_text(encoding="utf-8")), (
        "the CLI changed; if on purpose, rerun with CAMARONES_UPDATE_SNAPSHOTS=1 and review the diff")
```

Plus `test_aliases_fold_into_one_entry`: a small parser with `add_parser("camaron", aliases=["camarones"])` gives
`shape(p)["subcommands"] == {"camaron": {"aliases": ["camarones"], "args": [], "subcommands": {}}}`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_cli_snapshot.py -v`
Expected: FAIL (`fixtures/cli_shape.py` missing)

- [ ] **Step 3: Implement `shape`, `jsonable` and the script entry in `tests/fixtures/cli_shape.py`**

- [ ] **Step 4: Record the snapshot and check it is stable**

Run: `CAMARONES_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_snapshot.py -v`, then `uv run pytest tests/test_cli_snapshot.py -v`
Expected: both pass; `tests/snapshots/cli.json` lists every command of `camarones.build_parser()`, and contains no
absolute path, user name or machine-specific value (`grep -n "/Users\|/home\|C:" tests/snapshots/cli.json` prints
nothing).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/cli_shape.py tests/snapshots/cli.json tests/test_cli_snapshot.py
git commit -m "test(cli): a snapshot of every command, flag, default and alias" -m "Nothing a user notices."
```

### Task 5: HTTP access snapshot

**Files:**
- Create: `tests/snapshots/routes.json`
- Test: `tests/test_routes_snapshot.py`

**Interfaces:**
- Produces: `tests/snapshots/routes.json`, a list sorted by `(path, method)` of
  `{"method": "GET" | "POST", "path": "<a concrete sample path>", "access": "public" | "portal" | "app"}`.
  F3 will check its router against this file.

The list is written by hand from `.camarones/lib/serve.py`:
- GET: every name `Handler.api_get` compares (`name == …`, `name in (…)`, one sample per `startswith`) as
  `/api/<name>`; every name `Handler.api_app_get` compares as `/api/app/<name>`; any other `/api/…` literal in
  `do_GET`.
- POST: every `p == "/api/…"` in `do_POST`; each alternative of `APP_ONLY` not already listed (`/api/runs/r1/cancel`
  for the `runs/<id>/cancel` one); `TERMINAL_POST` as `/api/app/terminals/t-a-1/{input,resize,close}`; `UNIT_POST` as
  `/api/app/units/u1/{takeover,handback,stop}`; `/api/app/adr/<action>` for each action `adr_api.post` dispatches;
  `/api/kanban/{init,add,move,assign,link,archive}`; `/api/stories/{lint,analyze,save,suggest}`; one sample per other
  regex branch.
- Access as the code says today: `/api/app/…` and `APP_ONLY` → `app`; the board writes and `stories/save`,
  `stories/suggest` → `portal`; everything else → `public`. The test is the oracle: fix the file where it disagrees.

Server fixture: `kit.serve.APP_TOKEN = "app-token"` and `kit.serve.PORTAL_TOKEN = "portal-token"` through
`monkeypatch`, a `ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)` on a daemon thread, shut down after the
test (the pattern of `tests/test_app_api.py:17-31`). Every request sends `X-Camarones: 1` and
`Content-Type: application/json`, and decodes the JSON body of error answers.

- [ ] **Step 1: Write the failing tests**

Parametrize over the entries of `routes.json` (id = `"METHOD path"`):

- `app`: GET with no body, or POST with body `b"{"` → 403 with `"app": true`; the same POST with
  `X-Camaron-Token: portal-token` → 403 with `"app": true`.
- `portal`: GET, or POST with body `b"{}"`, no token → 403 with `"token": true`.
- `public` GET: status is not 403. Read only the status (`urlopen(…, timeout=10)`, closed without reading the body),
  so a route that streams events does not hold the test.
- `public` POST with body `b"{"` → exactly 400 (the body is refused before any handler runs).

And `test_every_literal_route_in_serve_is_listed`: with `ast` on `serve.py`, every string constant matching
`^/api/[\w/.-]*\w$`, every constant `api_get` compares `name` with (as `/api/<c>`) and every constant `api_app_get`
compares `name` with (as `/api/app/<c>`) is the `path` of some entry.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_routes_snapshot.py -v`
Expected: FAIL (no `routes.json`)

- [ ] **Step 3: Write `routes.json` by the rules above**

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_routes_snapshot.py -v`
Expected: all passed. A mismatch means the entry's access is wrong: read the branch in `serve.py` and fix the entry,
never the probe.

- [ ] **Step 5: Commit**

```bash
git add tests/snapshots/routes.json tests/test_routes_snapshot.py
git commit -m "test(serve): a snapshot of who may call each route, probed without running handlers" -m "Nothing a user notices."
```

### Task 6: core leaves — platform, fsutil, ctx, locks

**Files:**
- Create: `.camarones/lib/core/__init__.py` (a docstring: the kit's base, which imports nothing from `lib` outside
  `core`)
- Create: `.camarones/lib/core/platform.py`, `.camarones/lib/core/fsutil.py`
- Move: `git mv .camarones/lib/harness/ctx.py .camarones/lib/core/ctx.py` (content unchanged)
- Move: `git mv .camarones/lib/harness/locks.py .camarones/lib/core/locks.py`
- Create: facades `.camarones/lib/harness/ctx.py`, `.camarones/lib/harness/locks.py`
- Modify: `.camarones/lib/common.py` (import the moved names instead of defining them)
- Modify: `tests/test_locks.py:12`, `tests/test_plan_wiki.py:132` (`from lib.core import locks`)
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: Task 3's facade rule; Task 2's architecture test.
- Produces:
  - `lib.core.platform`: `IS_WIN`, `IS_MAC`, `HOME` (same expressions as `common.py` lines 9-11).
  - `lib.core.fsutil`: `retry_busy(fn, tries: int = 50)`, `load_json(p: Path, default)`,
    `save_json(p: Path, data) -> None`, `rmtree(path: Path) -> None`, moved verbatim from `common.py`.
  - `lib.core.ctx`: `KIT`, `CAM_DIR`, `find_project_marker`, `docs_root`, `find_root`, `Ctx` (unchanged).
  - `lib.core.locks`: `LockBusy`, `pid_alive`, `FileLock` (unchanged), importing `IS_WIN` from `.platform` and
    `retry_busy` from `.fsutil`.
  - `lib.harness.ctx`: facade, `__facade__ = "lib.core.ctx"`,
    `__all__ = ["KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root"]`.
  - `lib.harness.locks`: facade, `__facade__ = "lib.core.locks"`, `__all__ = ["FileLock", "LockBusy", "pid_alive"]`.

- [ ] **Step 1: Write the failing tests in `tests/test_core.py`**

```python
def test_kit_is_still_the_kit_folder(kit):
    from lib.core import ctx
    assert ctx.KIT.resolve() == KIT_DIR.resolve()

def test_old_lock_paths_give_the_same_objects(kit):
    from lib.core import locks as new
    from lib.harness import locks as old
    assert (old.FileLock, old.LockBusy, old.pid_alive) == (new.FileLock, new.LockBusy, new.pid_alive)
    assert old.LockBusy is new.LockBusy

def test_old_ctx_path_gives_the_same_objects(kit):
    from lib.core import ctx as new
    from lib.harness import ctx as old
    for name in ("KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root"):
        assert getattr(old, name) is getattr(new, name)

def test_common_still_offers_the_file_helpers(kit):
    from lib.core import fsutil
    for name in ("retry_busy", "load_json", "save_json", "rmtree"):
        assert getattr(kit.common, name) is getattr(fsutil, name)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.core'`

- [ ] **Step 3: Create `core/`, move `ctx` and `locks` with `git mv`, write the two facades, point `common.py` at them**

- [ ] **Step 4: Retarget the two tests that patch `locks`, then run the affected tests**

Run: `uv run pytest tests/test_core.py tests/test_locks.py tests/test_plan_wiki.py tests/test_harness_ctx.py tests/test_architecture.py tests/test_facade_guard.py -v`
Expected: all passed. If `test_the_largest_cycle_never_grows` or `test_the_allowlist_holds_no_fixed_debt` fail, apply
exactly what their messages say: an entry may leave the allowlist, none may be added.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: green. A failure saying "is re-exported by a facade" names a test still patching `lib.harness.locks` or
`lib.harness.ctx`: point it at `lib.core.locks` / `lib.core.ctx`.

- [ ] **Step 6: Commit**

```bash
git add .camarones/lib/core .camarones/lib/harness/ctx.py .camarones/lib/harness/locks.py .camarones/lib/common.py tests/test_core.py tests/test_locks.py tests/test_plan_wiki.py tests/architecture/allowlist.yaml
git commit -m "refactor(core): platform, file helpers, ctx and locks move to lib/core behind facades" -m "Nothing a user notices."
```

### Task 7: core/process and core/paths; common becomes a facade

**Files:**
- Create: `.camarones/lib/core/process.py`, `.camarones/lib/core/paths.py`
- Modify: `.camarones/lib/common.py` (a facade that keeps `VERSIONS`)
- Modify: `tests/test_which.py:13,20-28`, `tests/test_host_tools.py:113-120`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: Task 6's `lib.core.platform`, `lib.core.ctx`.
- Produces:
  - `lib.core.process` (from `common.py`, verbatim): `sdkman_dir`, `extra_bin_dirs`, `ensure_path`, `which`, `run`,
    `out`, `PARENT_SESSION`, `leave_parent_session`, `kill_tree`, `uv`, `py`; it calls `ensure_path()` at import, as
    `common.py` does today, and imports nothing from `core` but `.platform`.
  - `lib.core.paths` (from `common.py`, verbatim): `PREFS`, `CTX`, `ROOT`, `CAM_LAYOUT`, `WORKSPACE`, `DOCS`, `WORK`,
    `WS_FILE`, `CACHE`, `GRAPHS`, `repo_dir`, `ws_rel`, `rel_file`, `cli_cmd`; imports `.ctx`, `.platform`, and
    `which` from `.process`.
  - `lib.common`: a docstring, `__facade__ = "lib.core"`, the `VERSIONS` literal exactly as today, the imports, and
    `__all__` with these 38 names: `IS_WIN`, `IS_MAC`, `HOME`, `PREFS`, `CTX`, `ROOT`, `CAM_LAYOUT`, `WORKSPACE`,
    `DOCS`, `WORK`, `WS_FILE`, `CACHE`, `GRAPHS`, `KIT`, `CAM_DIR`, `Ctx`, `docs_root`, `find_project_marker`,
    `find_root`, `repo_dir`, `ws_rel`, `rel_file`, `cli_cmd`, `sdkman_dir`, `extra_bin_dirs`, `ensure_path`, `which`,
    `run`, `out`, `PARENT_SESSION`, `leave_parent_session`, `kill_tree`, `uv`, `retry_busy`, `load_json`, `save_json`,
    `py`, `rmtree`.

- [ ] **Step 1: Write the failing tests in `tests/test_core.py`**

```python
COMMON_NAMES = [...]  # the 38 names above, plus "VERSIONS"

def test_common_re_exports_every_name_it_had(kit):
    from lib.core import paths, process
    assert [n for n in COMMON_NAMES if not hasattr(kit.common, n)] == []
    assert kit.common.run is process.run and kit.common.ROOT == paths.ROOT
    assert kit.common.__facade__ == "lib.core"

def test_the_kit_version_is_still_written_in_common_py(kit):
    from lib import upgrade
    text = (KIT_DIR / "lib" / "common.py").read_text(encoding="utf-8")
    assert upgrade._version_in(text) == kit.common.VERSIONS["kit"]
    assert re.search(r'"kit":\s*"([\d.]+)"', text).group(1) == kit.common.VERSIONS["kit"]   # install.py:115

def test_importing_common_alone_extends_path(isolated_env, monkeypatch):
    extra = isolated_env / ".local" / "bin"
    extra.mkdir(parents=True)
    monkeypatch.delenv("CAMARONES_KEEP_PATH", raising=False)
    monkeypatch.setenv("PATH", "base")
    purge_kit_modules()
    try:
        importlib.import_module("lib.common")
        assert str(extra) in os.environ["PATH"].split(os.pathsep)
    finally:
        purge_kit_modules()
```

(`purge_kit_modules` from `conftest`; `isolated_env` is the test's HOME.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_core.py -v`
Expected: `test_common_re_exports_every_name_it_had` FAILS (`No module named 'lib.core.paths'`); the other two pass
already and must keep passing.

- [ ] **Step 3: Create `process.py` and `paths.py`, rewrite `common.py` as the facade**

- [ ] **Step 4: Retarget `test_which.py` and `test_host_tools.py`**

They patch `IS_WIN` and `extra_bin_dirs` on `kit.common`; patch them on `lib.core.process` (`from lib.core import
process` inside the test) and call `process.which` / `process.ensure_path`.

Run: `uv run pytest tests/test_core.py tests/test_which.py tests/test_host_tools.py tests/test_architecture.py tests/test_facade_guard.py tests/test_upgrade.py tests/test_install.py -v`
Expected: all passed.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: green. Each "is re-exported by a facade" failure names a test still patching `kit.common`: retarget it to
the `lib.core` module that defines the name.

- [ ] **Step 6: Commit**

```bash
git add .camarones/lib/core .camarones/lib/common.py tests/test_core.py tests/test_which.py tests/test_host_tools.py tests/architecture/allowlist.yaml
git commit -m "refactor(core): processes and project paths move to lib/core; common keeps VERSIONS and re-exports the rest" -m "Nothing a user notices: install and upgrade still read the kit version from lib/common.py."
```

### Task 8: Docs and end-to-end check

**Files:**
- Modify: `AGENTS.md` (lines 30, 32, the `.camarones/lib/` and `.camarones/lib/harness/` rows of §4, a new §4 row,
  one bullet in §5)
- Modify: `.camarones/templates/docs/guides/internals.md:255`,
  `.camarones/templates/docs/i18n/es/guides/internals.md:264`

**Interfaces:**
- Consumes: the modules of Tasks 6-7.

- [ ] **Step 1: Update AGENTS.md**

- Line 30: the helpers are in `lib/core/process.py` (`run`, `out`, `which`), which `lib/common.py` re-exports.
- Line 32: `IS_WIN` / `IS_MAC` come from `lib/core/platform.py`.
- Line 70 stays: `VERSIONS` is still in `lib/common.py`.
- §4 `.camarones/lib/` row: `common` becomes "`VERSIONS` (install and upgrade read it as text) and a facade over
  `core/`".
- New §4 row `.camarones/lib/core/`: the base every layer may use
  ([spec](docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md)): `ctx` (project paths as a value),
  `paths` (this process's project: `ROOT`, `DOCS`, `WORKSPACE`…), `process` (`run`, `out`, `which`, PATH), `platform`
  (`IS_WIN`, `IS_MAC`, `HOME`), `fsutil` (json files, `rmtree`), `locks` (cross-process file locks); imports nothing
  from `lib` outside `core`.
- §4 `harness/` row: drop `ctx` and `locks` (they are in `core/`; their old paths are facades).
- §5, one bullet: `tests/test_architecture.py` enforces the layers of the spec; `tests/architecture/allowlist.yaml`
  only shrinks; a module that moves leaves a facade (`__facade__`, `__all__`), and tests patch the module that
  defines a name, never a facade.

- [ ] **Step 2: Update the internals guide in both languages**

`PARENT_SESSION` in `lib/common.py` → in `lib/core/process.py` (en line 255, es line 264). The `VERSIONS` lines
(en 361, es 376) stay.

Run: `uv run pytest tests/test_guide.py -v`
Expected: all passed

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: green. Report the totals line.

- [ ] **Step 4: Check the kit end to end on the sandbox**

Run: `uv run scripts/sandbox.py cli doctor`, `uv run scripts/sandbox.py cli status`, `uv run scripts/sandbox.py cli plan`
Expected: each exits 0 with the same output as on `main`. If the sandbox does not exist, `uv run scripts/sandbox.py
reset` creates it (it clones from GitHub the first time): say so in the report rather than skipping.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md .camarones/templates/docs/guides/internals.md .camarones/templates/docs/i18n/es/guides/internals.md
git commit -m "docs: lib/core in the repo map and the internals guide" -m "Nothing a user notices. Templates are copied once: existing projects keep their copy of the internals guide, which still points at lib/common.py (it re-exports PARENT_SESSION)."
```
