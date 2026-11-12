# Hexagonal refactor F2 (CLI command registry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `camarones.py`'s 505-line if/elif `main()` with command classes discovered by a registry under
`.camarones/lib/interfaces/cli/`, a two-step middleware chain and a catalog generated from the commands' decorators,
with nothing a user can notice.

**Architecture:** A frozen copy of today's entry script is the parity oracle: the same command lines run through it and
through the real CLI on twin workspaces, and exit code, stdout and stderr must match. Task 4 moves `camarones.py`'s body
verbatim into a transitional `legacy.py` behind the new `main()`, so the CLI keeps working while each group of commands
moves into `commands/<group>.py` in its own commit. The last task deletes `legacy.py`, builds `catalog.COMMANDS` from the
decorators and leaves facades at `lib/catalog.py`, `lib/kanban/cli.py` and `lib/adr_cli.py`.

**Tech Stack:** Python ≥ 3.10 stdlib (`argparse`, `pkgutil`, `importlib`, `dataclasses`, `ast`, `inspect`, `runpy`),
pytest + pytest-xdist. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md` (§4.1, §5, §6 row F2, §7). Read it first, and
the F0/F1 rulings in this plan's "Decisions" table.

## Decisions this plan takes

The spec leaves these open; each is final for F2.

| # | Decision | Why |
|---|---|---|
| P1 | `Command.run(self, args, cli: CliContext) -> int`. `CliContext` holds `parser` now and gains `services` when `bootstrap.py` exists (F4+) | No `Services` exists yet; `help`, `catalog` and `stack` need the root parser |
| P2 | The spec's `needs_workspace` is the `project` flag, read by the global-install prelaunch (`launch.needs_project`), not a middleware inside `main()` | Today the only "needs a project" behaviour is the project picker in `camarones.py`'s module body, which runs before parsing and relaunches the process |
| P3 | The chain is `errors_to_exit`, then `record_usage`. No JSON middleware | Today's `main()` has no shared JSON behaviour; every command prints its own |
| P4 | `camaron` with no argument parses as `wizard` | Same result as today (no usage record, `W().run()`, exit 0) through one code path |
| P5 | Subcommand order is kept by `registry.ORDER` (today's 77 names); a command not in it sorts after them, by name | argparse prints the order in `--help` and in "invalid choice"; `tests/snapshots/cli.json` does not pin it |
| P6 | Command modules import kit modules only inside functions; loading the registry imports nothing outside `lib.interfaces.cli` (a test enforces it). F7 keeps this exception to "top-level imports where the layer allows" | The registry loads on every CLI start, in `lib.catalog` (read without a project) and in the prelaunch: importing every command's dependencies there would slow every `camaron` call |
| P7 | The help text moves verbatim to `interfaces/cli/help_text.py` (`TEXT`); `camarones.py` keeps a one-line docstring | `help` and `--help` print it; it stops depending on the entry script's `__doc__` |
| P8 | The one call-time read through a facade (`machine.py:47`, `common.HOME`) reads the defining module, and an architecture test forbids new ones | F1 ruling: F2 decides. The facade guard covers patches, not reads |
| P9 | The parity oracle (`tests/fixtures/cli_reference.py`, `catalog_reference.json`, `cli_help.py`, `test_cli_parity.py`) lives during F2 only | Once the CLI layer stops moving, a frozen copy only rots with intended changes |
| P10 | Groups follow the catalog zones, except `stack` (zone `machine`) lives in `analyze.py` because it uses `radar` | Each adapter is imported from one command module, so no allowlist line is duplicated |
| P11 | Kit imports inside `lib/interfaces/` are absolute (`from lib import docs`), as `camarones.py`'s are today | `commands/adr.py`, `machine.py`, `projects.py` share names with `lib/adr.py`, `lib/machine.py`, `lib/projects.py`; relative imports four levels up would be unreadable |

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read and write, processes through the kit
  helpers, `IS_WIN`/`IS_MAC` instead of `sys.platform` (AGENTS.md §2.1).
- No new dependency of any kind.
- Nothing a user notices: `tests/snapshots/cli.json` stays byte-identical; subcommand order, help texts, outputs and
  exit codes match the oracle (`tests/test_cli_parity.py`). Code moves verbatim; the only edits are the ones a task
  names.
- `.camarones/camarones.py` keeps its `# /// script` header unchanged, reconfigures stdout/stderr to UTF-8 before
  anything can print, and binds `build_parser` at module level (`tests/fixtures/cli_shape.py` imports it).
- Old import paths keep working: `lib/catalog.py`, `lib/kanban/cli.py` and `lib/adr_cli.py` become facades that set
  `__facade__ = "<new module>"` and list every imported name in `__all__` (explicit imports, never `import *`). The
  kanban and ADR facades keep `add_parser` and `run`: the oracle calls them.
- A command module's top-level imports are the standard library and `lib.interfaces.cli.registry` only (P6).
- A name `lib/common.py` re-exports is imported from the module that defines it (`lib.core.paths`, `lib.core.process`,
  `lib.core.fsutil`, `lib.core.ctx`, `lib.core.platform`); `VERSIONS` comes from `lib.common`.
- `tests/architecture/allowlist.yaml`: a moved violation is renamed (the old line removed, the new line added); the
  number of `violations` never grows. Each commit body states the count before → after.
- One class per command, named in CamelCase from the command (`arch-draft` → `ArchDraft`, `self-update` →
  `SelfUpdate`). No module name differs from another in its package only by case.
- No `VERSIONS["kit"]` bump. Every commit body ends with "Nothing a user notices." (AGENTS.md §5.1).
- Conventional commits (`refactor(cli): …`, `test(cli): …`); no `Co-Authored-By` or "Generated with" trailer. Stage only
  this plan's files: other sessions edit the tree in parallel.
- `uv run pytest -n auto` from the repository root is green before every commit.
- If `main` changes `.camarones/camarones.py` while F2 is in flight, port the change into its new home on rebase, and
  into `tests/fixtures/cli_reference.py` while it exists.
- Code and comments in English, comments only for a non-obvious *why*.

## Review Focus

- A global install run outside a project skips the project picker for exactly `help`, `version`, `self-update`, `mcp`,
  `catalog`, `projects`, `app` and `board merge-driver` (git runs it from any folder) → truth table in Task 4.
- A Windows pipe in cp1252: the prelaunch prints `🦐 …` for `new`/`join`, so the UTF-8 reconfigure must still come
  first → `test_help_prints_utf8_on_a_cp1252_pipe` in Task 4.
- An error inside a command prints one `🦐✖ …` line and exits 1, never a traceback; usage errors stay exit 2;
  `SystemExit` and `KeyboardInterrupt` pass through → middleware tests in Task 3.
- Startup: loading the registry (every CLI start, `lib.catalog` without a project, the prelaunch) imports no kit
  module outside `lib.interfaces.cli` → purity test in Task 3, kept green by every group task.
- `camaron` with no argument opens the wizard and records no usage, like `camaron wizard` → Task 4.

## File map (end state)

```
.camarones/camarones.py                  uv header, UTF-8 streams, launch.prelaunch(), then main()
.camarones/lib/interfaces/__init__.py    empty
.camarones/lib/interfaces/cli/
  __init__.py                            empty
  registry.py      Spec, Command, CliContext, command(), load(), find(), add_all(), entries(), ORDER, VERDICTS, ZONES
  middleware.py    Invocation, errors_to_exit, record_usage, CHAIN, dispatch()
  main.py          build_parser(), main()
  launch.py        prelaunch(), needs_project(): today's module-level new/join/switch/init/picker block
  help_text.py     TEXT: today's camarones.py docstring
  catalog.py       moved from lib/catalog.py; COMMANDS built from the decorators
  commands/        __init__.py (empty), meta, projects, machine, analyze, check, generate, team, interviews, board, adr
.camarones/lib/catalog.py, lib/kanban/cli.py, lib/adr_cli.py        facades
```

Transitional, Task 4 → Task 13: `interfaces/cli/legacy.py`, `launch.LEGACY_NO_PROJECT`, `main.command_for`,
`main._keep_order`, the literal rows left in `lib/catalog.py`.

---

### Task 1: Parity oracle

**Files:**
- Create: `tests/fixtures/cli_reference.py`, `tests/fixtures/cli_help.py`, `tests/fixtures/catalog_reference.json`
- Test: `tests/test_cli_parity.py`

**Interfaces:**
- Produces (later tasks only read them, and may add `CASES`):
  - `tests/fixtures/cli_reference.py`: `.camarones/camarones.py` as of this commit, with two edits only: a first
    docstring line "Frozen copy of .camarones/camarones.py before F2, the oracle of tests/test_cli_parity.py; deleted
    when F2 ends." and `HERE = Path(__file__).resolve().parents[2] / ".camarones"`.
  - `python tests/fixtures/cli_help.py <script>` prints JSON `{"order": [<subcommand names>], "help": {"": <root
    format_help()>, "<name>": <that subparser's format_help()>}}` for `build_parser()` of `<script>`, loaded with
    `runpy.run_path(script, run_name="cli_help")` after `sys.argv = [script]`.
  - `catalog_reference.json`: `json.dumps(lib.catalog.COMMANDS, indent=1, sort_keys=True, ensure_ascii=False)` as of
    this commit.
  - In `tests/test_cli_parity.py`: `REFERENCE: Path`, `REAL: Path` (`KIT_DIR / "camarones.py"`),
    `CASES: list[tuple[str, ...]]`, `normalize(text: str, base: Path) -> str`,
    `side(script: Path, argv: tuple[str, ...], base: Path) -> tuple[int, str, str]`.

- [ ] **Step 1: Create the three fixtures**

`cli_reference.py` per the Interfaces block (copy, then the two edits). Generate `catalog_reference.json` from
`.camarones/` with `uv run python -c "…"` printing the dump above, written with `newline="\n"`.

- [ ] **Step 2: Write `tests/test_cli_parity.py`**

`side()` builds `make_workspace(base)` (twin folders `tmp_path/"a"` and `tmp_path/"b"`, both named `demo`), runs
`[sys.executable, script, *argv]` with `{ws}` in `argv` replaced by that side's workspace, under `os.environ` plus
`HOME`/`USERPROFILE = base/"home"` (created), `CAMARONES_ROOT = <ws>/cam-docs`, `COLUMNS = "100"`, `cwd = <ws>`,
`stdin=DEVNULL`, `timeout=120`, and returns `(returncode, normalize(stdout, base), normalize(stderr, base))`.
`normalize` replaces `base` in its `str()`, `as_posix()`, JSON-escaped (`\\`) and `os.path.realpath` forms with
`<BASE>`, and ISO timestamps (`\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:\d\d)?`) with `<TS>`.

```python
def test_normalize_hides_the_side_folder_and_timestamps(tmp_path):
    base = tmp_path / "a"
    text = f"{base}/demo at 2026-11-12T10:00:01Z; {base.as_posix()}/x"
    assert normalize(text, base) == "<BASE>/demo at <TS>; <BASE>/x"

@pytest.mark.parametrize("argv", CASES, ids=" ".join)
def test_cli_matches_the_reference(argv, tmp_path, isolated_env):
    assert side(REAL, argv, tmp_path / "b") == side(REFERENCE, argv, tmp_path / "a")

def test_help_and_order_match_the_reference(tmp_path, isolated_env):
    # cli_help.py on REFERENCE and on REAL (same env as side(), one workspace): equal JSON
    ...

def test_catalog_rows_are_unchanged():
    from lib import catalog
    assert catalog.COMMANDS == json.loads((FIXTURES / "catalog_reference.json").read_text(encoding="utf-8"))

def test_the_oracle_is_not_vacuous(tmp_path, isolated_env):
    code, out, _ = side(REAL, ("help",), tmp_path / "a")
    assert code == 0 and "plan [sync|next|start" in out
    assert side(REAL, ("nosuch",), tmp_path / "b")[0] == 2
```

`CASES`, grouped by the task that moves them:

```python
CASES = [
    # meta (Task 5)
    ("help",), ("-h",), ("nosuch",), ("catalog",), ("catalog", "--json"), ("catalog", "--markdown"),
    ("catalog", "--check"),
    # projects (Task 6)
    ("projects",), ("projects", "--json"), ("projects", "--add", "{ws}", "--json"),
    ("projects", "--inspect", "{ws}", "--json"), ("projects", "--inspect", "{ws}/nope"), ("init",), ("new",), ("join",),
    # machine (Task 7)
    ("version",), ("config",), ("config", "--json"), ("config", "get", "lang"), ("config", "set", "lang"),
    ("config", "get", "nope"), ("detect",), ("profile", "quick"), ("repair",), ("migrate", "--dry-run"),
    ("uninstall", "--dry-run"), ("install", "{ws}/copy", "--dry-run"), ("sync",),
    # analyze (Task 8)
    ("changes",), ("llms",), ("mark-documented",), ("history",), ("fresh",), ("fresh", "--json"), ("fresh", "--ack", "x"),
    ("fresh", "--plan"), ("blocks", "--json"), ("pages", "--json"), ("diagrams", "--json"), ("arch-draft",),
    ("radar", "--json"), ("schemas", "--json"), ("inventory", "--json"), ("bump", "api", "nope", "1.0"), ("stack", "api"),
    ("stack", "api", "Java 21"), ("stack", "api", "--reset"), ("stack", "nope", "x"),
    # check (Task 9)
    ("status",), ("status", "--json"), ("check",), ("check", "--strict"), ("pipeline", "show"),
    ("pipeline", "show", "--json"), ("pipeline", "validate"), ("eval",), ("eval", "list", "--json"), ("eval", "confirm"),
    ("eval", "comply"), ("eval", "draft"), ("ab",), ("ab", "sampling"), ("kpis", "--compare", "a", "b"),
    ("kpis", "--no-check", "--json"), ("stats", "--json"), ("doctor", "--context", "--json"),
    # generate (Task 10)
    ("plan",), ("plan", "--json"), ("plan", "next"), ("plan", "next", "--json"), ("plan", "start"), ("plan", "note"),
    ("plan", "approve"), ("plan", "redo"), ("plan", "add", "x"), ("plan", "add", "flow-x", "Flow X"),
    ("plan", "done", "nope"), ("runs",), ("runs", "--json"), ("runs", "nope"), ("prompt", "update"),
    ("pr", "fresh", "nope"), ("pr", "fresh", "api", "--files", "README.md", "--json"),
    ("docs", "reset", "--redo", "--dry-run"), ("run", "--per-runner", "bad"),
    # team + interviews (Task 11)
    ("remote",), ("share", "--auto", "on"), ("checkpoint",), ("trust", "--json"), ("hooks",), ("hooks", "--json"),
    ("plugins",), ("plugins", "--json"), ("plugins", "enable", "nope"), ("plugins", "add"),
    ("plugins", "outdated", "--json"), ("export", "tour"), ("removed", "add", "old api", "--why", "gone"),
    ("feedback", "docs/overview.md", "too short", "--by", "ana"), ("review", "list"), ("review", "wait"),
    ("review", "wait", "nope", "--timeout", "0"), ("ci", "gitlab"), ("interview", "status", "--json"),
    ("interview", "mode"), ("interview", "import"),
    # board + adr (Task 12)
    ("board", "list", "--json"), ("board", "show"), ("board", "add", "story", "First card", "--json"),
    ("board", "merge-driver", "O"), ("adr", "list", "--json"), ("adr", "show"),
]
```

- [ ] **Step 3: Run it; every case passes (both sides run today's code)**

Run: `uv run pytest tests/test_cli_parity.py -n auto`
Expected: PASS. A case that fails here is not deterministic: add a `normalize` rule only when the difference is a
timestamp or a duration; otherwise drop the case and name it in the commit body. A case slower than 30 s is dropped too.

- [ ] **Step 4: Full suite, then commit**

```bash
uv run pytest -n auto
git add tests/fixtures/cli_reference.py tests/fixtures/cli_help.py tests/fixtures/catalog_reference.json tests/test_cli_parity.py
git commit -m "test(cli): parity oracle: today's entry script, frozen, against the real CLI on twin workspaces"
```

---

### Task 2: No call-time read through a facade

**Files:**
- Modify: `.camarones/lib/machine.py:11,47`
- Test: `tests/test_architecture.py`

**Interfaces:**
- Produces: `_facade_reads(mods: dict[str, Path]) -> list[str]` in `tests/test_architecture.py`, offences shaped
  `"machine reads common.HOME: import it from lib.core"` (the facade's `__facade__`).

- [ ] **Step 1: Write the failing tests**

A facade is a module whose source assigns `__facade__`; its re-exports are its literal `__all__`. An offence is an
`ast.Attribute` whose value is a `Name` bound in that module to a facade (`from . import common`, `from lib import
common`, `import lib.common as common`) and whose `attr` is in that facade's `__all__`.

```python
def test_no_module_reads_a_facade_reexport_at_call_time():
    assert _facade_reads(archscan.modules(KIT_DIR)) == []

def test_the_facade_read_check_sees_one(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "f.py").write_text('from os import sep\n__facade__ = "lib.g"\n__all__ = ["sep"]\n', encoding="utf-8")
    (lib / "m.py").write_text("from . import f\n\ndef g():\n    return f.sep\n", encoding="utf-8")
    assert _facade_reads(archscan.modules(tmp_path)) == ["m reads f.sep: import it from lib.g"]
```

- [ ] **Step 2: Run them to see the first fail**

Run: `uv run pytest tests/test_architecture.py -k facade_read -v`
Expected: `test_no_module_reads…` FAILS listing `machine reads common.HOME: import it from lib.core`.

- [ ] **Step 3: Retarget `machine.py`**

`from .core import platform` and `platform.HOME` at line 47, so a patch of `lib.core.platform.HOME` is seen at call
time. Drop `from . import common` if nothing else uses it.

- [ ] **Step 4: Run, full suite, commit**

```bash
uv run pytest tests/test_architecture.py tests/test_machine.py -n auto && uv run pytest -n auto
git add tests/test_architecture.py .camarones/lib/machine.py
git commit -m "refactor(machine): read HOME from lib.core; no module reads a facade's re-export at call time"
```

---

### Task 3: Registry and middleware

**Files:**
- Create: `.camarones/lib/interfaces/__init__.py`, `.camarones/lib/interfaces/cli/__init__.py`,
  `.camarones/lib/interfaces/cli/commands/__init__.py` (all empty), `.camarones/lib/interfaces/cli/registry.py`,
  `.camarones/lib/interfaces/cli/middleware.py`
- Test: `tests/test_cli_registry.py`, `tests/test_cli_middleware.py`

**Interfaces:**
- Produces, `registry.py` (every later task uses it):

```python
VERDICTS = ("portal", "app", "both", "cli")
ZONES = ("projects", "generate", "analyze", "check", "interviews", "team", "machine")
PACKAGE = "lib.interfaces.cli.commands"
ORDER: tuple[str, ...] = (
    "help", "setup", "install", "upgrade", "new", "switch", "self-update", "unlink", "profile", "init", "sync",
    "detect", "changes", "llms", "graph", "arch", "arch-validate", "portal", "down", "wizard", "version", "repair",
    "history", "removed", "review", "hook", "hooks", "mcp", "doctor", "plugins", "export", "run", "eval", "ab", "pr",
    "blocks", "pages", "diagrams", "fresh", "kpis", "runs", "pipeline", "mark-documented", "status", "check", "confirm",
    "translated", "up", "wiki", "migrate", "uninstall", "docs", "ci", "plan", "checkpoint", "remote", "share", "trust",
    "join", "stats", "feedback", "arch-draft", "radar", "inventory", "bump", "health", "schemas", "interview", "stack",
    "prompt", "autopilot", "catalog", "board", "adr", "projects", "app", "config",
)

@dataclass(frozen=True)
class Spec:
    name: str
    verdict: str
    zone: str | None = None
    es: str = ""
    en: str = ""
    ai: bool = False
    destructive: bool = False
    reads: str | None = None
    aliases: tuple[str, ...] = ()
    project: bool = True        # a global install run outside a project picks one first
    usage: bool = True          # `cli:<name>` goes to the usage log

@dataclass(frozen=True)
class CliContext:
    parser: argparse.ArgumentParser

class Command:
    spec: ClassVar[Spec]
    def configure(self, parser: argparse.ArgumentParser) -> None: ...      # default: no arguments
    def run(self, args: argparse.Namespace, cli: CliContext) -> int: ...  # raises NotImplementedError
    def needs_project(self, rest: list[str]) -> bool: ...                 # default: self.spec.project
    def records_usage(self, args: argparse.Namespace) -> bool: ...        # default: self.spec.usage

def command(name: str, verdict: str, zone: str | None = None, *, es: str = "", en: str = "", ai: bool = False,
            destructive: bool = False, reads: str | None = None, aliases: tuple[str, ...] = (), project: bool = True,
            usage: bool = True) -> Callable[[type[Command]], type[Command]]
def load(package: str = PACKAGE) -> dict[str, Command]   # primary name → instance; ORDER first, the rest by name
def find(commands: dict[str, Command], name: str) -> Command | None   # by name or alias
def add_all(subparsers: argparse._SubParsersAction, commands: dict[str, Command]) -> None
def entries(commands: dict[str, Command]) -> dict[str, dict]   # catalog rows
```

  `command()` sets `cls.spec` and returns the class (no global state). It raises `ValueError` for a verdict outside
  `VERDICTS`; for `app`/`both` without a zone in `ZONES` or without `es` and `en`; for `portal`/`cli` with a zone.
  `load()` imports every module of `package` with `pkgutil.iter_modules` + `importlib.import_module`, keeps each
  `Command` subclass with a `spec` defined in that module, and raises `ValueError` when a name or alias is used twice;
  cache it per package name (`functools.cache`). `add_all` calls `subparsers.add_parser(spec.name,
  aliases=list(spec.aliases))` then `configure` for each command, in the dict's order. `entries` maps each name to
  `{"verdict", "zone", "es", "en", "ai", "destructive", "reads"}`, the shape `catalog._e` builds.
- Produces, `middleware.py`:

```python
Next = Callable[[], int]

@dataclass(frozen=True)
class Invocation:
    command: Command
    args: argparse.Namespace
    cli: CliContext

Middleware = Callable[[Invocation, Next], int]
def errors_to_exit(inv: Invocation, nxt: Next) -> int   # RuntimeError, KeyError, ValueError, OSError → "🦐✖ {e}" on stderr, 1
def record_usage(inv: Invocation, nxt: Next) -> int     # usage.record(f"cli:{inv.args.cmd}") if records_usage, then nxt()
CHAIN: tuple[Middleware, ...] = (errors_to_exit, record_usage)
def dispatch(inv: Invocation, chain: Sequence[Middleware] = CHAIN) -> int   # chain, then inv.command.run(inv.args, inv.cli)
```

- [ ] **Step 1: Write the failing registry tests (`tests/test_cli_registry.py`)**

```python
def test_command_sets_the_spec_and_returns_the_class():
    @command("zz", "app", "check", es="Prueba", en="Test", project=False)
    class Zz(Command): ...
    assert Zz.spec == Spec("zz", "app", "check", es="Prueba", en="Test", project=False) and Zz().needs_project([]) is False

@pytest.mark.parametrize("kw", [dict(verdict="nope"), dict(verdict="app"), dict(verdict="app", zone="check"),
                                dict(verdict="cli", zone="check")])
def test_a_bad_catalog_row_is_refused(kw):
    with pytest.raises(ValueError):
        command("zz", **kw)

def test_a_new_module_is_picked_up_with_no_other_edit(tmp_path, monkeypatch):
    pkg = tmp_path / "zz_cmds"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "extra.py").write_text(
        "from lib.interfaces.cli.registry import Command, command\n\n"
        '@command("zz-extra", "cli")\nclass ZzExtra(Command):\n'
        "    def configure(self, p):\n        p.add_argument('--n', type=int, default=1)\n\n"
        "    def run(self, args, cli):\n        return args.n\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    cmds = registry.load("zz_cmds")
    p = argparse.ArgumentParser()
    registry.add_all(p.add_subparsers(dest="cmd"), cmds)
    args = p.parse_args(["zz-extra", "--n", "3"])
    assert cmds["zz-extra"].run(args, CliContext(p)) == 3
```

Also, with temp packages built the same way:
- `test_a_name_used_twice_is_refused`: two modules declaring `"zz-a"` (or one's alias equal to the other's name) →
  `load` raises `ValueError`.
- `test_order_comes_first_and_the_rest_by_name`: commands `"zz-b"`, `"zz-a"`, `"version"` → `list(load(...)) ==
  ["version", "zz-a", "zz-b"]`.
- `test_an_alias_parses_and_finds_the_same_command`: `aliases=("zz-old",)` → `parse_args(["zz-old"])` works and
  `find(cmds, "zz-old") is cmds["zz-new"]`; `find(cmds, "nope") is None`.
- `test_entries_have_the_catalog_shape`: `entries(cmds)["zz"] == {"verdict": "app", "zone": "check", "es": "Prueba",
  "en": "Test", "ai": False, "destructive": False, "reads": None}`.
- `test_loading_the_registry_imports_nothing_outside_the_cli`: in a subprocess with `.camarones` on `sys.path`,
  `from lib.interfaces.cli import registry; registry.load()`, then print the loaded `lib` modules; every one is
  `lib`, `lib.interfaces`, or starts with `lib.interfaces.cli`.
- `test_moved_commands_are_registry_commands`: `MOVED: set[str] = set()` at module level;
  `assert MOVED <= set(registry.load())`. Each group task adds its names first.

- [ ] **Step 2: Write the failing middleware tests (`tests/test_cli_middleware.py`)**

```python
@pytest.mark.parametrize("err,line", [(ValueError("boom"), "🦐✖ boom"), (KeyError("k"), "🦐✖ 'k'"),
                                      (RuntimeError("r"), "🦐✖ r"), (OSError("o"), "🦐✖ o")])
def test_a_command_error_is_one_line_and_exit_1(err, line, capsys):
    def boom():
        raise err
    assert middleware.errors_to_exit(None, boom) == 1
    assert capsys.readouterr().err == line + "\n"

@pytest.mark.parametrize("err", [SystemExit(2), KeyboardInterrupt()])
def test_exit_and_interrupt_pass_through(err):
    def stop():
        raise err
    with pytest.raises(type(err)):
        middleware.errors_to_exit(None, stop)

def test_usage_is_recorded_before_the_command_runs(monkeypatch):
    # fake Command recording "run"; monkeypatch lib.usage.record to record "usage:<name>"
    # dispatch(Invocation(cmd, Namespace(cmd="zz"), CliContext(parser))) == 0 and calls == ["usage:cli:zz", "run"]

def test_a_command_that_records_no_usage_logs_nothing(monkeypatch): ...   # Spec(usage=False): calls == ["run"]
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/test_cli_registry.py tests/test_cli_middleware.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.interfaces'`.

- [ ] **Step 4: Implement `registry.py` and `middleware.py` per the Interfaces block**

`middleware.record_usage` imports `lib.usage` inside the function (P6).

- [ ] **Step 5: Run them, then the architecture test**

Run: `uv run pytest tests/test_cli_registry.py tests/test_cli_middleware.py tests/test_architecture.py -n auto`
Expected: PASS (the new modules sit under `interfaces.*` in `layers.yaml`; no allowlist change).

- [ ] **Step 6: Full suite, commit**

```bash
uv run pytest -n auto
git add .camarones/lib/interfaces tests/test_cli_registry.py tests/test_cli_middleware.py
git commit -m "feat(cli): command registry and middleware chain under lib/interfaces/cli, not wired yet"
```

---

### Task 4: The new entry pipeline, with today's dispatch behind it

**Files:**
- Move: `git mv .camarones/camarones.py .camarones/lib/interfaces/cli/legacy.py`, then create a new
  `.camarones/camarones.py`
- Create: `.camarones/lib/interfaces/cli/{main,launch,help_text}.py`
- Modify: `.camarones/lib/catalog.py`, `tests/architecture/allowlist.yaml`, `AGENTS.md` (§4 repo map),
  `.camarones/templates/docs/guides/internals.md:36`, `.camarones/templates/docs/i18n/es/guides/internals.md:36`
- Test: `tests/test_cli_main.py`, `tests/test_catalog.py`

**Interfaces:**
- Consumes: Task 3's `registry` and `middleware`.
- Produces:

```python
# help_text.py
TEXT: str                       # today's camarones.py docstring, byte for byte

# main.py
def build_parser() -> argparse.ArgumentParser   # prog=cli_cmd(), description=help_text.TEXT, RawDescriptionHelpFormatter;
                                                # add_subparsers(dest="cmd", required=True); legacy.add_legacy(sp);
                                                # registry.add_all(sp, registry.load()); _keep_order(sp)
def command_for(name: str) -> Command           # transitional: registry.find(...) or legacy.Legacy(name)
def main(argv: list[str] | None = None) -> int  # leave_parent_session(); argv None → sys.argv[1:]; [] → ["wizard"];
                                                # parse; middleware.dispatch(Invocation(command_for(args.cmd), args, CliContext(parser)))

# launch.py
LEGACY_NO_PROJECT = frozenset({"help", "version", "self-update", "mcp", "catalog", "projects", "app"})   # transitional
def needs_project(rest: list[str]) -> bool      # rest = argv after the script; [] and unknown names → True
def prelaunch(argv: list[str], entry: str) -> None   # today's module-level block; argv is sys.argv, edited in place

# legacy.py (transitional)
def add_legacy(sp: argparse._SubParsersAction) -> None   # today's build_parser body after add_subparsers
def run_legacy(a: argparse.Namespace, p: argparse.ArgumentParser) -> int   # today's if/elif dispatch
class Legacy(Command):          # a command run_legacy still dispatches
    def __init__(self, name: str) -> None
    # run → run_legacy(args, cli.parser); records_usage → not (args.cmd in {"help", "mcp", "wizard"}
    #                                                           or (args.cmd == "board" and args.action == "merge-driver"))
```

  `needs_project`: a registry command answers `command.needs_project(rest[1:])`; otherwise
  `rest[0] not in LEGACY_NO_PROJECT and rest[:2] != ["board", "merge-driver"]`.
  `_keep_order(sp)` reorders `sp.choices` in place (it is also `sp._name_parser_map`) by `registry.ORDER`, others after
  by name; it exists only while two sources add subparsers.

- [ ] **Step 1: Write the failing tests (`tests/test_cli_main.py`)**

```python
from lib.interfaces.cli.registry import ORDER      # pure (Task 3's purity test): safe at collection time

NO_PROJECT = {"help", "version", "self-update", "mcp", "catalog", "projects", "app"}
NO_USAGE = {"help", "mcp", "wizard"}

def test_order_is_the_parser():
    from lib.interfaces.cli import main
    from lib.catalog import subparsers
    assert list(subparsers(main.build_parser())) == list(ORDER)

def test_main_is_short():
    from lib.interfaces.cli import main
    assert len(inspect.getsource(main.main).splitlines()) < 50

@pytest.mark.parametrize("name", ORDER)
def test_which_commands_a_global_install_runs_outside_a_project(name):
    from lib.interfaces.cli import launch
    assert launch.needs_project([name]) is (name not in NO_PROJECT)

def test_git_runs_the_board_merge_driver_outside_a_project():
    from lib.interfaces.cli import launch
    assert launch.needs_project(["board", "merge-driver", "O", "A", "B"]) is False
    assert launch.needs_project(["board", "list"]) is True
    assert launch.needs_project([]) is True and launch.needs_project(["nosuch"]) is True

@pytest.mark.parametrize("name", ORDER)
def test_which_commands_record_usage(name):
    from lib.interfaces.cli import main
    assert main.command_for(name).records_usage(argparse.Namespace(cmd=name, action=None)) is (name not in NO_USAGE)

def test_the_board_merge_driver_records_no_usage():
    from lib.interfaces.cli import main
    assert main.command_for("board").records_usage(argparse.Namespace(cmd="board", action="merge-driver")) is False

def test_no_argument_opens_the_wizard_and_logs_nothing(kit, monkeypatch):
    # monkeypatch lib.wizard.W with a class whose run() appends "wizard"; lib.usage.record appends "usage"
    # main.main([]) == 0 and calls == ["wizard"]

def test_help_prints_utf8_on_a_cp1252_pipe(kit):
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "help"], capture_output=True,
                       env={**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0 and "🦐 Camarón" in r.stdout.decode("utf-8")
```

Import only `registry` at module level: anything that imports `lib.common` at collection time runs `ensure_path()` in
the collecting process. `conftest.py` already puts `.camarones` on `sys.path`.

In `tests/test_catalog.py`:

```python
def test_an_alias_is_not_a_second_command():
    from lib import catalog
    p = argparse.ArgumentParser()
    p.add_subparsers(dest="cmd").add_parser("new-name", aliases=["old-name"])
    assert list(catalog.subparsers(p)) == ["new-name"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_cli_main.py tests/test_catalog.py -v`
Expected: FAIL (`lib.interfaces.cli.main` does not exist; `subparsers` returns both names).

- [ ] **Step 3: Move the dispatch into `legacy.py`**

`git mv` as above. In `legacy.py`, keep the imports (`argparse, json, os, subprocess, sys`, `Path`,
`from lib import projects`) and everything from `from lib import docs, env, plan` to the end of `cmd_plan` verbatim,
with exactly these edits:
- `build_parser()` → `add_legacy(sp)`: its body from `sp.add_parser("help")` on (the root parser and `add_subparsers`
  move to `main.build_parser`).
- `main()` → `run_legacy(a, p)`: its `if a.cmd == "help": … elif …` chain and final `return 0`; `print(__doc__)` →
  `print(p.description)`. The `leave_parent_session()`, wizard, parse, merge-driver early return and usage recording
  lines go (`main()`, `Legacy.records_usage` and `middleware.record_usage` do them).
- The two `stats` branches add `from lib import usage` (today they use the name `main()` bound while recording).
- `HERE.parent` → `KIT.parent`, with `from lib.core.ctx import KIT`.
- The module docstring, `HERE`, `sys.path`, the stream reconfigure, `_relaunch`, `_team`, the `_cmd0`/`_no_open`
  prelaunch block and the `if __name__ == "__main__"` block leave this file.
- Add `class Legacy` per the Interfaces block.

- [ ] **Step 4: Write `help_text.py`, `launch.py`, `main.py` and the new `camarones.py`**

`help_text.TEXT` is the old docstring, unchanged. `launch.py` holds `_relaunch`, `_team` and the prelaunch block moved
verbatim into `prelaunch(argv, entry)`, with these edits: `sys.argv` → `argv`; `__file__` in `_relaunch` → `entry`;
`_no_open` passed to `_team` as an argument; the picker's skip test (`_cmd0 not in ("help", …) and not (board
merge-driver)`) → `needs_project(argv[1:])`. Its top-level kit import is `from lib import projects`, as today.
The new `camarones.py`:

```python
# /// script                                          (today's header, unchanged)
"""🦐 Camarón — project documentation wizard + CLI. No arguments opens the wizard; `help` lists the commands."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

for _stream in (sys.stdout, sys.stderr):           # before the first print: a Windows pipe is cp1252, not UTF-8
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from lib.interfaces.cli import launch              # noqa: E402

launch.prelaunch(sys.argv, __file__)

from lib.interfaces.cli.main import build_parser, main   # noqa: E402,F401 — tests/fixtures/cli_shape.py reads build_parser

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Catalog, allowlist, docs**

`lib/catalog.py`: `VERDICTS`, `ZONES` imported from `registry`; the literal dict renamed `_LEFT` and
`COMMANDS = {**_LEFT, **registry.entries(registry.load())}`; `subparsers()` keeps the first name per parser object
(argparse maps aliases to the same parser). Run `uv run pytest tests/test_architecture.py` and apply what it prints:
the eight `camarones -> X` lines become `interfaces.cli.legacy -> X` (seven) and `interfaces.cli.launch -> creds`;
`oversize` drops `camarones` and adds `interfaces.cli.legacy`. AGENTS.md §4: a row for `.camarones/lib/interfaces/cli/`
("the CLI: `registry` discovers one class per command in `commands/`, `middleware` maps errors and records usage,
`main` parses and dispatches, `launch` the global install's project picker; `camarones.py` only calls it") and the
`camarones.py` row says it calls `lib/interfaces/cli`. Both `internals.md` CLI rows list
`.camarones/lib/interfaces/cli/`.

- [ ] **Step 6: Run the CLI tests, then the full suite**

Run: `uv run pytest tests/test_cli_main.py tests/test_catalog.py tests/test_cli_parity.py tests/test_cli_snapshot.py tests/test_architecture.py tests/test_guide.py tests/test_projects_cli.py tests/test_machine.py tests/test_parent_session.py -n auto`
Expected: PASS. Then `uv run pytest -n auto`: PASS.

- [ ] **Step 7: Commit**

```bash
git add .camarones/camarones.py .camarones/lib/interfaces .camarones/lib/catalog.py tests/test_cli_main.py tests/test_catalog.py tests/architecture/allowlist.yaml AGENTS.md .camarones/templates/docs/guides/internals.md .camarones/templates/docs/i18n/es/guides/internals.md
git commit -m "refactor(cli): camarones.py calls lib/interfaces/cli; today's dispatch moves behind it as legacy"
```

---

### Group move procedure (Tasks 5–11)

Each group task applies these steps to its own table row. Names: module `M`, commands `C`.

- [ ] **Step 1: Test first.** Add `C` to `MOVED` in `tests/test_cli_registry.py`. Run
  `uv run pytest tests/test_cli_registry.py -k moved -v`. Expected: FAIL (`C` not in the registry).
- [ ] **Step 2: Create `.camarones/lib/interfaces/cli/commands/M.py`.** One class per command in `C`, decorated with
  `@command(name, …)`: the catalog row copied from `_LEFT[name]` in `lib/catalog.py` (verdict, zone, es, en, ai,
  destructive, reads; skip defaults) plus the row's flags. `configure(self, parser)` holds that command's lines from
  `add_legacy`, without the `sp.add_parser(...)` call. `run(self, args, cli)` holds its branch of `run_legacy`, with
  `a` → `args` and the root parser `p` → `cli.parser` (only `stack`'s `p.error`; `bump`'s `p` is a local plan); a
  branch that only calls a `cmd_*` helper becomes `return cmd_x(args)`, and the helper and the constants only it uses
  move unchanged as module-level code. Kit imports go inside the functions (Global Constraints). Then delete the moved lines,
  branches and helpers from `legacy.py`, the moved rows from `_LEFT`, and the row's names from
  `launch.LEGACY_NO_PROJECT`.
- [ ] **Step 3: Allowlist.** Run `uv run pytest tests/test_architecture.py`; for each `interfaces.cli.legacy -> X` it
  reports fixed, add the `interfaces.cli.commands.M -> X` it reports new; follow its `oversize` message. The count must
  match the row's "allowlist" column.
- [ ] **Step 4: Run the CLI tests.**
  `uv run pytest tests/test_cli_registry.py tests/test_cli_main.py tests/test_cli_parity.py tests/test_cli_snapshot.py tests/test_catalog.py tests/test_architecture.py -n auto`
  Expected: PASS. A parity difference is a slip in the move: fix the moved code, never the oracle. Sandbox smoke for
  the flows the group touches (spec §6): if the sandbox exists, `uv run scripts/sandbox.py cli <one read-only command
  of the group>` behaves as before.
- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`, then
  `git add` the new module, `legacy.py`, `launch.py`, `lib/catalog.py`, `allowlist.yaml` and
  `tests/test_cli_registry.py`, and commit
  `refactor(cli): <group> commands move to interfaces/cli/commands/<M>.py`; the body lists the commands, the allowlist
  count before → after, and ends with "Nothing a user notices."

### Tasks 5–11: the groups

| Task | `M` | Commands, in today's order | Flags | Allowlist renames (`legacy ->` → `commands.M ->`) | Notes |
|---|---|---|---|---|---|
| 5 | `meta` | help, wizard, catalog, app | help: `project=False, usage=False`; wizard: `usage=False`; catalog, app: `project=False` | none | `help` prints `cli.parser.description`; `catalog` calls `cmd_catalog(args, cli.parser)` |
| 6 | `projects` | new, switch, init, join, projects | projects: `project=False` | none | `new`, `join`, `switch` return 0: the prelaunch handles them and today's `main()` falls through to `return 0` for them |
| 7 | `machine` | setup, install, upgrade, self-update, unlink, profile, sync, detect, arch, down, version, repair, mcp, up, migrate, uninstall, config | self-update, version: `project=False`; mcp: `project=False, usage=False` | `machine` (1) | `install` uses `KIT.parent` |
| 8 | `analyze` | changes, llms, graph, history, blocks, pages, diagrams, fresh, mark-documented, arch-draft, radar, inventory, bump, schemas, stack | — | `history`, `inventory`, `quickarch`, `radar`, `schemas` (5) | `diagrams` runs `cmd_pages`; `stack` calls `cli.parser.error(...)`; `stack` keeps its `machine` zone |
| 9 | `check` | arch-validate, doctor, eval, ab, kpis, pipeline, status, check, stats, health | — | `adapters.runners.local` (1) | `HEALTH_*` and `_health_*` move with `health`; `stats` imports `usage` itself |
| 10 | `generate` | run, pr, runs, wiki, docs, plan, prompt, autopilot | — | none | `_run_line` moves with `runs` |
| 11 | `team`, `interviews` | team: portal, removed, review, hook, hooks, plugins, export, confirm, translated, ci, checkpoint, remote, share, trust, feedback · interviews: interview | — | none | `trust` keeps `cmd_trust`; `plugins` keeps both branches and `cmd_plugin_store`; one commit for both modules |

After Task 11, `legacy.py` registers and dispatches only `board` and `adr`.

---

### Task 12: Board and ADR faces move in

**Files:**
- Move: `git mv .camarones/lib/kanban/cli.py .camarones/lib/interfaces/cli/commands/board.py`,
  `git mv .camarones/lib/adr_cli.py .camarones/lib/interfaces/cli/commands/adr.py`; new facades at both old paths
- Modify: `.camarones/lib/interfaces/cli/legacy.py`, `.camarones/lib/interfaces/cli/launch.py`,
  `.camarones/lib/catalog.py`, `tests/architecture/allowlist.yaml`, `AGENTS.md` (§4: `adr_cli` and `kanban` entries)
- Test: `tests/test_cli_registry.py`, `tests/test_kanban_cli.py`, `tests/test_adr_cli.py`

**Interfaces:**
- Produces: `class Board(Command)` (`board`, verdict `both`, zone `team`; `needs_project(rest)` →
  `rest[:1] != ["merge-driver"]`; `records_usage(args)` → `args.action != "merge-driver"`) and `class Adr(Command)`
  (`adr`, verdict `app`, zone `team`). Each `run(args, cli)` returns the module's existing `run(args)`. Each module
  keeps `add_parser(sp)`, now `Board().configure(sp.add_parser("board"))` (and `Adr` alike).
- Facades: `lib/kanban/cli.py` (`__facade__ = "lib.interfaces.cli.commands.board"`) and `lib/adr_cli.py`
  (`__facade__ = "lib.interfaces.cli.commands.adr"`) re-export every public name of their new module, `add_parser` and
  `run` included.

- [ ] **Step 1: Write the failing tests**

Add `{"board", "adr"}` to `MOVED`. In `test_kanban_cli.py` and `test_adr_cli.py`, import the modules from
`lib.interfaces.cli.commands` (patches of `ops` and `adr` stay where they are: those modules define the names).

```python
def test_the_old_cli_modules_are_facades():
    from lib import adr_cli
    from lib.kanban import cli as board_cli
    from lib.interfaces.cli.commands import adr, board
    assert board_cli.__facade__ == "lib.interfaces.cli.commands.board" and board_cli.run is board.run
    assert adr_cli.__facade__ == "lib.interfaces.cli.commands.adr" and adr_cli.add_parser is adr.add_parser
```

- [ ] **Step 2: Run them to see them fail.** `uv run pytest tests/test_cli_registry.py -k "moved or facades" -v` → FAIL.
- [ ] **Step 3: Move.** `git mv` both files; their relative imports become absolute (`from lib.kanban import ops`,
  `from lib.core.locks import LockBusy`, `from lib import adr`, `from lib.adr_api import BUSY`), all inside functions;
  add the classes; write the facades. In `legacy.py` drop the `board_cli`/`adr_cli` parser calls and branches; in
  `launch.needs_project` drop the board fallback; drop `board` and `adr` from `_LEFT`.
- [ ] **Step 4: Allowlist and docs.** `kanban.cli -> kanban.index` becomes `interfaces.cli.commands.board ->
  kanban.index` (count unchanged). AGENTS.md §4 names `interfaces/cli/commands/{board,adr}` for `camaron board` and
  `camaron adr`, the old modules as facades.
- [ ] **Step 5: Run.** The Task 4 Step 6 list plus `tests/test_kanban_cli.py tests/test_adr_cli.py
  tests/test_kanban_merge.py tests/test_facade_guard.py`, then `uv run pytest -n auto`. Expected: PASS.
- [ ] **Step 6: Commit** `refactor(cli): board and adr faces move to interfaces/cli/commands; old modules are facades`.

---

### Task 13: Close-out — no legacy, catalog from the registry, oracle retired

**Files:**
- Delete: `.camarones/lib/interfaces/cli/legacy.py`
- Move: `git mv .camarones/lib/catalog.py .camarones/lib/interfaces/cli/catalog.py`; a facade at `lib/catalog.py`
- Modify: `main.py`, `launch.py`, `commands/meta.py`, `tests/architecture/allowlist.yaml`, `AGENTS.md` (§4 `catalog`)
- Test: `tests/test_cli_registry.py`, `tests/test_catalog.py`, `tests/test_cli_main.py` (`main.command_for(name)` →
  `registry.find(registry.load(), name)`)
- Delete after Step 6: `tests/fixtures/cli_reference.py`, `tests/fixtures/cli_help.py`,
  `tests/fixtures/catalog_reference.json`, `tests/test_cli_parity.py`

**Interfaces:**
- Produces: `lib/interfaces/cli/catalog.py` with `COMMANDS = registry.entries(registry.load())`, `VERDICTS`/`ZONES`
  imported from `registry`, and `subparsers`, `drift`, `args_of`, `describe`, `triage_markdown` unchanged.
  `lib/catalog.py` facade (`__facade__ = "lib.interfaces.cli.catalog"`) re-exports `VERDICTS`, `ZONES`, `COMMANDS`,
  `subparsers`, `drift`, `args_of`, `describe`, `triage_markdown`. `main.main` dispatches `registry.find(commands,
  args.cmd)`.

- [ ] **Step 1: Write the failing tests**

Replace `test_moved_commands_are_registry_commands` and `MOVED` with:

```python
def test_every_parser_command_is_a_registry_command():
    from lib.interfaces.cli import main
    from lib.interfaces.cli.catalog import subparsers
    assert set(subparsers(main.build_parser())) == set(registry.load())

def test_catalog_rows_come_from_the_decorators():
    from lib import catalog
    assert catalog.__facade__ == "lib.interfaces.cli.catalog"
    assert catalog.COMMANDS == registry.entries(registry.load())
```

- [ ] **Step 2: Run them to see them fail.** `uv run pytest tests/test_cli_registry.py -v` → FAIL.
- [ ] **Step 3: Remove the transition.** `git rm` `legacy.py` (it registers and dispatches nothing now); in `main.py`
  drop `legacy`, `command_for` and `_keep_order`; in `launch.py` drop `LEGACY_NO_PROJECT` (unknown names → `True`);
  `git mv` the catalog with `_LEFT` gone, write its facade; `commands/meta.py` imports `lib.interfaces.cli.catalog`.
  Apply what `tests/test_architecture.py` prints (the `interfaces.cli.legacy` lines and `oversize` entry go if any
  remain). AGENTS.md §4: the `catalog` entry points to `interfaces/cli/catalog` ("rows from each command's
  `@command` decorator; `catalog --check` still compares them with the parser").
- [ ] **Step 4: Run with the oracle still in place.** `uv run pytest -n auto` → PASS, `test_cli_parity.py` included.
  Also `uv run --script .camarones/camarones.py catalog --check` → exit 0 (real `uv`, the script's own header).
- [ ] **Step 5: Sandbox against `main`.** If the sandbox exists (AGENTS.md §2.2; `reset` creates it otherwise, say
  so): `git worktree add <scratchpad>/main-kit main`. For each of `init`, `detect`, `status --json`, `pipeline show`,
  `plan`, `plan next`, `inventory --json`, `radar --json`, `schemas --json`, `pages --json`, `arch-draft`, `history`,
  `fresh --json`, `catalog --json`, `board list --json`, `adr list --json`: after `uv run scripts/sandbox.py reset`,
  run the list in order with `main`'s kit (`uv run --quiet --script <scratchpad>/main-kit/.camarones/camarones.py …`,
  `cwd` the sandbox, `CAMARONES_ROOT=<sandbox>/cam-docs`, as `sandbox.py`'s `kit_env` sets it); `reset` again and run
  it with `uv run scripts/sandbox.py cli …`; diff exit code, stdout and stderr after replacing the kit path. Expected:
  no difference beyond timestamps. Run `uv run scripts/sandbox.py traces` after; remove the worktree.
- [ ] **Step 6: Retire the oracle.** `git rm` the four oracle files; `uv run pytest -n auto` → PASS.
- [ ] **Step 7: Commit**

```bash
git add -A .camarones/lib/interfaces .camarones/lib/catalog.py tests/test_cli_registry.py tests/test_catalog.py tests/test_cli_main.py tests/architecture/allowlist.yaml AGENTS.md
git commit -m "refactor(cli): catalog generated from the registry; the transitional legacy dispatch and the parity oracle go"
```

The body states: main() is N lines (from 505), the allowlist count before → after, the sandbox commands compared,
and "Nothing a user notices."
