# Spike: porting the kanban core to Kotlin with AI (2026-11-12)

**Question.** How much would it cost to migrate the kit from Python to Kotlin/Java with an AI agent doing the porting?
The desk estimate was 4–8 weeks for one person steering agents. This spike ports one bounded slice, measures it, and
checks the port against the Python kit as an oracle.

**Answer.** Translating logic is even cheaper than estimated. Keeping the exact semantics of Python, PyYAML and
Python's `re` is the real cost, and it is invisible without an oracle. The spike does not touch the platform risks
(distribution, 3.x/4.x back-compat shims, the TUI wizard, Windows), so the 4–8 week range holds: about a week moves from
"translate" to "fidelity layer", and JVM start-up is no longer a risk.

## Scope

`lib/kanban/` is not self-contained: `index`, `ops`, `xid`, `repair` and `cli` pull in `docs`, `codemap`, `stories`,
`harness.locks`/`freshness` and sqlite. The spike ports the four modules that only depend on YAML/JSON:

| Python | Lines | Kotlin |
|---|---|---|
| `state.py` (board.yaml reader/writer, ids, ordinals) | 123 | `State.kt` |
| `items.py` (Backlog.md task files, byte-compatible) | 199 | `Items.kt` |
| `deps.py` (dependencies, waves, start gate) | 301 | `Deps.kt` |
| `merge.py` (git merge driver for board.yaml) | 121 | `Merge.kt` |
| tests `test_kanban_{state,items,deps,merge}.py` | 649 | `*Test.kt` (52 tests) |

Two Python tests that need the kit's workspace fixture (`kit.root` paths, `wired`) were left out.

Stack: Maven, Kotlin 2.1.0 targeting JDK 8 (the only JDK on the bench machine), SnakeYAML 2.3, JUnit 5.11.
Code lives in `spikes/kotlin-kanban/`; the board templates are packaged as classpath resources, as a real port would.

## What was measured

Agent wall-clock, one session:

| Phase | Clock | Elapsed |
|---|---|---|
| Read the four modules and their tests, Maven scaffold compiling | 14:07 → 14:12 | 4.5 min |
| Port the four modules and the Python-compatibility layer (first compile clean) | → 14:20 | 8 min |
| Port the 52 tests, all green (one interop bug fixed) | → 14:24 | 4 min |
| Python oracle: 17,505 seeded cases, parity test, fix the cheap gaps | → 14:29 | 5.5 min |

Size: 744 Python lines became 1,161 Kotlin lines: 744 of port plus **417 of compatibility layer** (`PyCompat.kt`,
`PyYaml.kt`), a one-off cost later modules would reuse. Tests: 649 → 774 Kotlin lines plus a 268-line golden generator.

This is agent time on the easiest ~2% of the kit (744 of 34,874 lines): pure logic, no processes, no network, no UI.
Human review time is not counted, and in a real migration it dominates.

## Parity against the Python kit

`parity/gen_golden.py` runs the Python modules on seeded random inputs (tricky YAML scalars, Unicode, impossible
dates, random boards, merges, dependency graphs) and records each output or exception type. `ParityTest` replays them on
the Kotlin port and compares bytes.

| Area | Cases | First run | After fixes |
|---|---|---|---|
| graphs: waves, ready, blocked_by, conflicts, containers, sccs | 3,200 | 0 | 0 |
| norm_touch, overlap, id order, place, file names | 7,105 | 0 | 0 |
| `_scalar` (board.yaml quoting) | 4,082 | 7 | 0 |
| `dump_board` | 400 | 6 | 0 |
| `merge_boards` | 500 | 6 | 0 |
| `parse_item` | 600 | 24 | 0 |
| `stamp_time` | 511 | 1 | 0 |
| `load_board` | 707 | 2 | 2 (known) |
| `serialize_item` (task-file frontmatter) | 400 | 80 | 80 (known) |
| **Total** | **17,505** | **126** | **82** |

The pure logic matched on the first run. Every divergence was at a semantic edge that the existing tests never
exercise:

- **Tabs.** PyYAML's scanner refuses a tab inside a plain scalar; SnakeYAML takes it. Fixed for writing
  (`_scalar` quotes it, so board.yaml bytes match); left open for reading: the port accepts two files Python rejects.
- **Duplicate keys.** A Python `dict` keeps a repeated key where it first appeared, with the last value, and PyYAML
  builds every value on the way. SnakeYAML moves the key and skips the value it drops. Fixed by overriding
  `processDuplicateKeys`.
- **`=` keys.** PyYAML's `flatten_mapping` reads a `=` key as text; SnakeYAML has no such case. Fixed.
- **YAML 1.1 resolution.** SnakeYAML's float rule takes `1e3`, PyYAML's needs a dot; its int rule differs on
  `0b_`. Python's `re.match` lets `$` match before a final newline, where SnakeYAML uses `matches()`. Fixed with a
  `PyResolver` carrying PyYAML's exact regexes and matching semantics.
- **`repr()`** escapes every non-printable code point (e.g. a BOM inside a dict that gets stringified). Fixed.
- **Year 0** is valid for `java.time` but a `ValueError` for Python's `datetime`. Fixed.
- **Emitter (open).** SnakeYAML's `Emitter` is `final`: it writes `\x7f` where PyYAML writes `\x7F` (40 cases),
  leaves a BOM raw where PyYAML escapes `﻿` (35), escapes NBSP as `\_`, and folds multi-line scalars differently.
  Byte-identical task files need a small emitter of our own for the frontmatter subset (block maps, block lists, the
  three scalar styles). Estimate: 300–500 lines and 1–2 days with AI, checked against the same oracle.

Other traps the port had to handle, none of which the tests catch: `len()` and str ordering are per code point while
Kotlin counts UTF-16 units (emoji in titles, `🦐` sorting); Python's `re` has Unicode `\d`/`\s` and only `\n` ends a
line (`UNIX_LINES | UNICODE_CHARACTER_CLASS`); Python `\Z` is Java `\z`; `Path.read_text` translates `\r\n` and lone
`\r` and fails on bad UTF-8, where Kotlin's `readText` silently replaces bytes; `json.dumps` escapes with lowercase hex
and `ensure_ascii` by default; `int()` accepts `"1_000"` and Unicode digits; `str(True)` is `"True"`; floor division
on negative ordinals; JDK 8's Unicode tables (6.2) lag Python's.

## Latent bugs found in the Python kit

Porting means stating every behaviour exactly, which surfaced three problems in the current kit:

1. **One bad task file takes down the whole board.** `parse_item` lets PyYAML's `ValueError` through for an
   impossible date (`due_date: 2026-13-45`): it is not a `yaml.YAMLError`, so it never becomes an `ItemError`, and
   `load_dir` does not catch it. Reproduced: `load_dir` raises instead of reporting the file as a problem.
2. **`dump_board` crashes on some values.** `_scalar("2026-13-45")` and `_scalar("0b_")` raise `ValueError` for the
   same reason, so an assignee or stamp with that shape makes the board unwritable.
3. **Merge order is not fully deterministic.** `_merge_all` sorts a `set` by `id_key`; ids that tie (`WI-01`/`WI-1`)
   come out in hash order, which changes between runs. The port breaks the tie by the raw id.

## Start-up time

The merge driver runs on every `git merge` that touches board.yaml. Measured on the same three files, 10 runs each:
`uv run --script camarones.py board merge-driver` (what git runs today) takes a median of **194 ms**;
`java -cp … MergeDriverMain` on JDK 8 HotSpot takes **151 ms**. Both produce the same bytes. A small JVM CLI is not
slower; a full kit with more classes would load more, but start-up no longer argues for GraalVM native-image.
Native-image remains a *distribution* question (no JDK on the user's machine), not a performance one.

## Effect on the estimate

| Item | Desk estimate | After the spike |
|---|---|---|
| Translate logic + rewrite unit tests | 1.5–3 weeks | 1–2 weeks: translation is fast, review is the bottleneck |
| Fidelity layer (YAML, Unicode, regex, I/O semantics) + oracle per module | not counted | +1 week, including the emitter |
| Server, PTY, keyring, sqlite, MCP | ~1 week | unchanged (not exercised) |
| TUI wizard on three OSes | 1–2 weeks | unchanged (not exercised) |
| Distribution, `camarones.py` shim, hooks/MCP/CI migration | 1–2 weeks | unchanged; start-up risk gone |
| **Total** | **4–8 weeks** | **4–8 weeks**, with less risk in the logic and the same risk in the platform |

Lessons for any real migration:

- **An oracle is mandatory, not optional.** All 52 ported tests were green while 126 outputs still differed. Every module that writes a file a person or another tool reads (board.yaml, task files, `plan.yaml`,
  frontmatter) needs a golden generator before its port starts.
- **Typed data classes help where shapes are fixed** (`Card`, `Node`, `Reason`); frontmatter stays a
  `Map<Any?, Any?>`, so the typing gain there is small.
- **Java interop nullability bites**: SnakeYAML calls `resolve()` with a null value for collections; the Kotlin
  signature said non-null. Tests caught it at once.

## How to run it

```bash
uv run --with pyyaml python spikes/kotlin-kanban/parity/gen_golden.py
```

```bash
cd spikes/kotlin-kanban && mvn -B test
```

`target/parity-report.txt` holds the per-area tally and examples; `target/parity-mismatches.jsonl` every divergence in
full. `ParityTest` is a ratchet: it fails on any mismatch beyond the known `load` (2) and `item_dump` (80).
