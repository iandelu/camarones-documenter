# Dynamic ADRs — S1 (no AI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A *Decisiones* section in the desktop app and `camaron adr …` that list every ADR, frame a new or
retroactive one, build its evidence pack, offer decisions the code took without an ADR (*Candidatas*), write it without
AI, review it part by part in presentation mode with hand-made decision points, and accept, reject or supersede it —
with the portal showing each ADR's status and a computed banner on the pages an accepted ADR covers. No model call.

**Architecture:** Pure functions in `lib/adr_doc.py` read and write the ADR Markdown (numbering, status, sections,
the template). `lib/adr.py` owns the working state (`docs/.work/adr/NNNN.yaml`) and every action; `lib/adr_pack.py`
builds the evidence pack and the candidates from the code graph index, the docs, git, C4 and the inventory.
`lib/adr_api.py` is the app-token API that `lib/serve.py` delegates to; `lib/adr_cli.py` the CLI. The desktop app gets
`sections/Decisions.jsx` and its views under `sections/adr/`, over pure helpers in `renderer/src/adr.js`.

**Tech Stack:** Python 3 stdlib + PyYAML (already a dependency), pytest; React 19 + Vite + Vitest in
`.camarones/desktop/renderer` and `.camarones/portal/app`.

**Spec:** [docs/superpowers/specs/2026-10-27-dynamic-adrs-design.md](../specs/2026-10-27-dynamic-adrs-design.md)
(slice S1, §7). S1 narrows two things on purpose: a candidate's *Toca* is its manifests only (the person adds code
files with the search box), and the modes `light`/`jury` do not exist yet — an ADR written by hand has `mode: manual`.

## Global Constraints

- macOS, Windows, Linux: `pathlib` only, `encoding="utf-8"`, write text with `newline="\n"`, processes through
  `lib/common.py` helpers, OS branches on `IS_WIN`/`IS_MAC` (AGENTS.md §2.1).
- TDD: failing test first. Tests offline with the `kit` fixture (`tests/conftest.py`), the app server fixtures of
  `tests/test_app_api.py` (`app_server`, `portal_server`, `call`, `TOKEN`) and `tests/test_codemap.write_graph`.
  Python: `uv run pytest -n auto` from the repo root. Renderer: `npm test` in `.camarones/desktop/renderer`; portal:
  `npm test` in `.camarones/portal/app`.
- No new dependency.
- Paths: ADR `docs/decisions/<NNNN>-<slug>.md`; working state `WORK / "adr" / "<NNNN>.yaml"` (WORK = `docs/.work`, in
  git); cache `CACHE / "adr" / "<NNNN>" /` (`pack.json`, `pack.md`, git-ignored). `NNNN` = `f"{n:04d}"`.
- Slug: lowercase ASCII words (`[a-z0-9]+`, accents folded with `unicodedata.normalize("NFKD")`) joined by `-`, at most
  60 characters, `decision` when empty.
- Status tokens: `proposed`, `accepted`, `rejected`, `superseded`, `deprecated`, `unknown`. Read in English and Spanish
  (`Proposed/Propuesto/Propuesta`, `Accepted/Aceptado/Aceptada`, `Rejected/Rechazado/Rechazada`,
  `Superseded/Sustituido/Sustituida`, `Deprecated/Obsoleto/Obsoleta`), case-insensitive, ignoring HTML comments, from
  the `## Status` (`## Estado`) section or an inline `Status:` line. Written in English: `Proposed`,
  `Accepted (YYYY-MM-DD)`, `Rejected (YYYY-MM-DD): <why>`, `Superseded by [NNNN](<file name>)`.
- Section headings written in English: `Status`, `Context`, `Decision drivers`, `Considered options`, `Decision`,
  `Consequences`, `Confirmation`, `Diagram`, `Evidence`, `Decided by`. Read also in Spanish: `Estado`, `Contexto`,
  `Drivers`, `Opciones consideradas`, `Decisión`, `Consecuencias`, `Confirmación`, `Diagrama`, `Evidencia`,
  `Decidido por`.
- Ownership: a new ADR is written with `x-owner: ai` and `Status: Proposed`; accept/reject set `x-owner: human` and call
  `docs.confirm([file], by)`. A file with no working state (a legacy ADR) is never rewritten until the person accepts
  or rejects it in a session.
- Edits never re-render a whole existing file: they replace one section (`adr_doc.replace_section`) and keep every
  other byte. Only creation renders the full template.
- Pack caps: `NEIGHBOURS = 30`, `PAGES = 15`, `ADRS = 10`, `COMMITS = 40`, `MONTHS = 12`, `QUESTIONS = 10`,
  `LIMIT = 20000` characters of `pack.md`.
- Candidate categories: `("data", "cache", "messaging", "security", "framework")`, inventory scope `runtime` only, plus
  C4 technologies and deployment sources (`docker-compose*.y*ml`, `compose*.y*ml` at a repo's root; `Chart.yaml` up to
  three folders deep).
- App section id `decisions`, after `board` in `nav.PROJECT`; shortcut `g a`; hash routes `#/decisions`,
  `#/decisions/new`, `#/decisions/candidates`, `#/decisions/<NNNN>`.
- Every user-facing string in `es` and `en` (desktop `renderer/src/i18n.js`, keys `adr.*`; portal
  `portal/app/src/i18n/portal.js`). No joke on the review screen, in errors, or in `--json` (AGENTS.md §3); at most one
  on the list's empty state.
- API: app token only (`/api/app/adr…`); bad input `400`, unknown ADR `404`, stale save or number taken by a racing
  write `409`.
- `VERSIONS["kit"]` `4.71.0` → `4.72.0`; README, `lib/tutorial.py` (+ `TUTORIAL.md`) and both template tutorials move
  in the last task (precedent: the user-stories plan).

## Review Focus

- **An ADR the kit did not write** — no frontmatter, Spanish headings, `Propuesto <!-- … -->`, an inline
  `Status: accepted`, extra sections — lists with the right status, opens, and its bytes are unchanged until the person
  accepts it in a session (Task 1 and Task 2 tests).
- **The file changed under the person** (a pull, an editor) between reading and saving a part → `409`, nothing
  overwritten, the app reloads (Task 2, Task 6).
- **A number taken after it was reserved** (a pull brings `0013-…md`) → the next free number is used when the file is
  written, and the response says so (Task 2).
- **Accepting what is not decided** — a deferred point, a point with no choice, no points and an empty or placeholder
  *Decision* — is refused with a message saying which; superseding an old ADR with no frontmatter still marks it
  (Task 3).
- **A fresh project** with no code graph, no inventory, no C4, no git history and no `open-questions.md` → the pack
  builds with empty sections and candidates is an empty list, never an error (Task 4, Task 5).

---

### Task 1: The ADR document, pure (`lib/adr_doc.py`)

**Files:**
- Create: `.camarones/lib/adr_doc.py`
- Test: `tests/test_adr_doc.py`

**Interfaces:**
- Consumes: `docs.split_fm`, `docs.join_fm`, `docs.headings` / `docs.sections` (heading parsing), `docs.COMMENT_RE`.
- Produces:
  - `slugify(title: str) -> str`
  - `next_number(taken: Iterable[str]) -> str` — `taken` are `NNNN` strings; returns the lowest number above the max.
  - `number_of(name: str) -> str | None` — `"0012-foo.md"` → `"0012"`.
  - `status_of(body: str) -> tuple[str, str | None]` — `(token, superseded_by_number)`.
  - `section(body: str, key: str) -> str | None` — `key` in `KEYS`; the section's text without its heading.
  - `replace_section(text: str, key: str, new_body: str) -> str` — whole-file in, whole-file out (frontmatter kept).
  - `KEYS = ("status", "context", "drivers", "options", "decision", "consequences", "confirmation", "diagram",
    "evidence", "decided_by")` and `HEADINGS: dict[str, str]` (English heading per key), `ORDER` (insertion order for a
    missing section: the order of `KEYS`).
  - `render_new(fields: dict, number: str, today: str) -> str` — the full proposed file.
  - `render_points(points: list[dict]) -> str`, `render_decision(points: list[dict]) -> str`,
    `render_decided_by(date: str, attendees: list[str], driver: str, mode: str) -> str`,
    `evidence_table(rows: list[tuple[str, str]]) -> str`.
  - `PLACEHOLDER = "To be decided in review: see the decision points."`

- [ ] **Step 1: Write the failing tests**

```python
def test_slug_folds_accents_and_caps_length(adr_doc):
    assert adr_doc.slugify("Sesiones en Redis, ¿sí o no?") == "sesiones-en-redis-si-o-no"
    assert adr_doc.slugify("  ") == "decision"
    assert len(adr_doc.slugify("x" * 200)) == 60

def test_next_number_skips_gaps_and_ignores_junk(adr_doc):
    assert adr_doc.next_number([]) == "0001"
    assert adr_doc.next_number(["0001", "0007", "0003"]) == "0008"
    assert adr_doc.number_of("0012-sessions.md") == "0012" and adr_doc.number_of("notes.md") is None

@pytest.mark.parametrize("body, want", [
    ("## Status\n\nProposed <!-- agents only write \"Proposed\" -->\n", ("proposed", None)),
    ("## Estado\n\nAceptada (2026-10-21)\n", ("accepted", None)),
    ("Status: accepted\n\n## Context\n", ("accepted", None)),
    ("## Status\n\nSuperseded by [0010](0010-caffeine.md)\n", ("superseded", "0010")),
    ("## Estado\n\nSustituida por 0010\n", ("superseded", "0010")),
    ("## Context\n\nno status here\n", ("unknown", None)),
])
def test_status_is_read_in_both_languages(adr_doc, body, want):
    assert adr_doc.status_of(body) == want

def test_replace_section_keeps_every_other_byte(adr_doc):
    text = "---\ntitle: X\n---\n# 0001 — X\n\n## Status\n\nProposed\n\n## Contexto\n\nold\n\n## Notes\n\nmine\n"
    out = adr_doc.replace_section(text, "context", "new text")
    assert out == text.replace("old", "new text")
    added = adr_doc.replace_section(text, "decided_by", "2026-10-27 · LA")
    assert added.startswith(text.rstrip("\n")) and added.endswith("## Decided by\n\n2026-10-27 · LA\n")

def test_a_new_adr_renders_the_template(adr_doc, kit):
    fields = {"title": "Sessions in Redis", "kind": "new", "problem": "Pods lose sessions.", "drivers": ["No downtime"],
              "options_hint": ["Redis", "Postgres"], "touches": ["api:src/S.java", "cam-docs:docs/orders.md"]}
    text = adr_doc.render_new(fields, "0012", "2026-10-27")
    fm, body = kit.docs.split_fm(text)
    assert fm["type"] == "decision" and fm["x-owner"] == "ai" and fm["title"] == "0012 — Sessions in Redis"
    assert fm["x-sources"] == ["api:src/S.java", "docs/orders.md"]
    assert adr_doc.status_of(body) == ("proposed", None)
    assert adr_doc.section(body, "context") == "Pods lose sessions."
    assert "- No downtime" in adr_doc.section(body, "drivers")
    assert "### A · Redis" in adr_doc.section(body, "options") and "### B · Postgres" in adr_doc.section(body, "options")
    assert adr_doc.section(body, "decision") == adr_doc.PLACEHOLDER
    assert "| Named when the decision was framed | `api:src/S.java` |" in adr_doc.section(body, "evidence")
    assert "description" in fm and 40 <= len(fm["description"]) <= 300
```

`adr_doc` fixture: `importlib.import_module("lib.adr_doc")` after `kit`. Add `render_decision` and `render_points`
tests: a chosen point renders `**<question>** — <option name>. <rationale>`; an `other` choice renders its text; points
render as `#### P1 · <question>` with one `- **A · name**` line per option and its pros (`+`) and cons (`−`).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_doc.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.adr_doc'`

- [ ] **Step 3: Implement `lib/adr_doc.py`**

Section matching: an `##` heading whose text, lowercased, equals a key's English or Spanish heading; the section runs
to the next `##` (or end). `status_of` strips `docs.COMMENT_RE` first, reads the first non-empty line of the status
section, else the first `Status:`/`Estado:` line of the body. `render_new`: description = `"Why the project chose an
option for: <title>. Proposed decision with its options, evidence and the decision points the team reviews."` cut to
300 characters; `tags` = the repo names of the code touches (sorted, unique); `x-sources` = code touches as they are,
`cam-docs:docs/<p>` → `docs/<p>`; evidence rows `(claim, evidence)` = `("Named when the decision was framed",
"`<touch>`")` under the skeleton's `| Claim | Evidence |` header; options from `options_hint` (letters `A`, `B`, …),
none → the section says `TODO(question): which options were considered?`. `replace_section` on a missing section
inserts it before the first existing section whose key comes later in `KEYS`, else at the end of the file.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_doc.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr_doc.py tests/test_adr_doc.py
git commit -m "feat(adr): read and write ADR documents (numbering, status, sections, template)"
```

---

### Task 2: Working state, list, new, write, parts and points (`lib/adr.py`)

**Files:**
- Create: `.camarones/lib/adr.py`
- Test: `tests/test_adr.py`

**Interfaces:**
- Consumes: Task 1; `common.WORK`, `common.CACHE`, `common.DOCS`, `common.retry_busy`; `docs.iter_docs`,
  `docs.split_fm`, `docs.join_fm`, `docs.body_sha`, `docs.now`; `harness.locks.FileLock`.
- Produces:
  - `class AdrError(ValueError)`, `class AdrConflict(AdrError)`; unknown id → `KeyError`.
  - `KINDS = ("new", "retro")`, `PHASES = ("problem", "evidence", "review", "accepted", "rejected")`,
    `CHIPS = ("running", "review", "proposed", "accepted", "superseded", "rejected", "deprecated", "unknown")`.
  - `state_file(id: str) -> Path`, `load_state(id: str) -> dict | None`, `save_state(st: dict) -> None` (temp file +
    `os.replace` through `retry_busy`, under `FileLock(CACHE / "locks" / "adr.lock")`).
  - `chip(state: dict | None, status: str) -> str` — `problem`/`evidence` → `running`; `review` → `review`; otherwise
    the file's status (`proposed` for a legacy proposed ADR).
  - `list_adrs() -> list[dict]` — rows `{id, slug, title, kind, status, chip, repos, points: {total, decided}, path,
    updated, decided, legacy}`, sorted by id descending; `path` is the docs logical path (`decisions/0012-….md`).
  - `next_id() -> str`.
  - `new(fields: dict) -> dict` — validates (`title` non-empty, `kind` in `KINDS`, lists of text), reserves the next
    number, writes state `{id, slug, kind, mode: "manual", title, problem, drivers, constraints, options_hint, touches,
    phase: "problem", parts: {}, points: [], attendees: [], supersedes, implementation: "pending" | "n/a"}`; returns
    `get(id)`.
  - `get(id: str) -> dict` — the row plus `{state, sections: {key: text}, parts: [{id, status}], points, affected: [],
    sha, raw, notice}`; `sha` is `docs.body_sha` of the file's body (`""` before the file exists); `affected` stays
    `[]` until Task 4 fills it.
  - `write_without_ai(id: str) -> dict` — renders the file with `adr_doc.render_new`; if the number was taken meanwhile,
    renumbers (state file renamed) and sets `notice = {"renumbered": {"from": old, "to": new}}`; phase → `review`.
  - `start_review(id: str) -> dict` — for a legacy ADR (file, no state): creates the state from the file (kind `retro`,
    phase `review`, no points), never writes the ADR.
  - `part(id: str, part: str, action: str, text: str | None, base_sha: str) -> dict` — `action` in `("approve", "edit",
    "defer")`; `edit` replaces that section (`adr_doc.replace_section`); a `base_sha` that differs from the file's →
    `AdrConflict`.
  - `point(id: str, op: str, data: dict, base_sha: str) -> dict` — `op` in `("add", "choose", "defer", "remove")`;
    `add` needs `question` and ≥ 2 options with names (`AdrError("a decision point needs at least two options")`),
    ids `p1, p2…`, options `A, B…`; `choose` takes `chosen` (an option id) or `other` (text) and `rationale`; each op
    rewrites the `### Decision points` block inside *Decision* with `adr_doc.render_points`.
  - `set_attendees(id: str, names: list[str]) -> dict`.
  - `parts_of(state: dict, sections: dict) -> list[str]` — `["context", "drivers", *("point:" + p.id), "options",
    "diagram" (only when the section has text), "consequences", "confirmation", "affected"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_new_reserves_the_next_number_and_lists(adr, kit):
    (kit.root / "docs" / "decisions").mkdir(parents=True)
    (kit.root / "docs" / "decisions" / "0007-old.md").write_text("# 0007 — Old\n\n## Status\n\nAccepted\n", encoding="utf-8")
    got = adr.new({"title": "Sessions in Redis", "kind": "new", "touches": ["api:src/main/java/demo/Api.java"]})
    assert got["id"] == "0008" and got["state"]["phase"] == "problem" and got["state"]["implementation"] == "pending"
    rows = adr.list_adrs()
    assert [r["id"] for r in rows] == ["0008", "0007"]
    assert rows[1]["legacy"] is True and rows[1]["chip"] == "accepted" and rows[0]["chip"] == "running"

def test_a_legacy_adr_is_never_rewritten_by_reading_or_starting_a_review(adr, kit):
    f = kit.root / "docs" / "decisions" / "0003-jpa.md"
    f.parent.mkdir(parents=True)
    raw = "# 0003 — JPA\n\n## Estado\n\nPropuesto <!-- x -->\n\n## Contexto\n\nwhy\n\n## Notas\n\nkeep\n"
    f.write_text(raw, encoding="utf-8")
    assert adr.get("0003")["status"] == "proposed"
    st = adr.start_review("0003")["state"]
    assert st["phase"] == "review" and st["kind"] == "retro" and f.read_text(encoding="utf-8") == raw

def test_writing_without_ai_renumbers_when_the_number_was_taken(adr, kit):
    got = adr.new({"title": "A", "kind": "new"})
    (kit.root / "docs" / "decisions").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "decisions" / f"{got['id']}-pulled.md").write_text("# pulled\n", encoding="utf-8")
    out = adr.write_without_ai(got["id"])
    assert out["notice"] == {"renumbered": {"from": got["id"], "to": "0002"}} and out["id"] == "0002"
    assert not adr.state_file(got["id"]).exists() and adr.state_file("0002").exists()

def test_a_stale_save_is_refused(adr, kit):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "new"})["id"])
    f = kit.root / "docs" / a["path"]
    f.write_text(f.read_text(encoding="utf-8") + "\nedited elsewhere\n", encoding="utf-8")
    with pytest.raises(adr.AdrConflict):
        adr.part(a["id"], "context", "edit", "mine", base_sha=a["sha"])
    assert "edited elsewhere" in f.read_text(encoding="utf-8") and "mine" not in f.read_text(encoding="utf-8")

def test_points_need_two_options_and_render_into_the_decision(adr):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "new"})["id"])
    with pytest.raises(adr.AdrError, match="two options"):
        adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}]}, a["sha"])
    a = adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])
    assert a["points"][0]["id"] == "p1" and [o["id"] for o in a["points"][0]["options"]] == ["A", "B"]
    assert "#### P1 · Where?" in a["sections"]["decision"]
    assert [p["id"] for p in a["parts"]][:3] == ["context", "drivers", "point:p1"]
```

`adr` fixture: `importlib.import_module("lib.adr")` after `kit`. Also test: `part(..., "approve")` sets
`parts["context"] = "approved"` and leaves the file's bytes alone; `point(..., "choose", {"point": "p1", "chosen": "B",
"rationale": "zero infra"})` marks it decided in `list_adrs()[0]["points"] == {"total": 1, "decided": 1}`; a bad kind
or a non-list `touches` raises `AdrError`; `get("9999")` raises `KeyError`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.adr'`

- [ ] **Step 3: Implement `lib/adr.py`**

The points block is everything in *Decision* from its `### Decision points` line to the section's end; a point op
replaces only that block and keeps the text written before it.
ADR files are found by `number_of` over `docs/decisions/*.md`; state files by `WORK / "adr" / "*.yaml"`. YAML is
written with `yaml.safe_dump(sort_keys=False, allow_unicode=True)`. Every write takes the lock. Module docstring in the
style of `stories_save.py`: what it owns, what it never does (rewrite a legacy ADR, call a model).

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr.py tests/test_adr.py
git commit -m "feat(adr): working state, list, new, write without AI, parts and decision points"
```

---

### Task 3: Accept, reject, supersede, and what an ADR covers

**Files:**
- Modify: `.camarones/lib/adr.py`
- Test: `tests/test_adr_accept.py`

**Interfaces:**
- Consumes: Task 2; `docs.confirm(files, by)`.
- Produces:
  - `accept(id: str, by: str, attendees: list[str] | None, base_sha: str) -> dict`
  - `reject(id: str, why: str, by: str, base_sha: str) -> dict`
  - `covering(logical: str) -> list[dict]` — accepted ADRs whose `x-sources` share a reference with the page's
    `x-sources` (fragments after `#` and a `repo://` prefix ignored), or that cite `docs/<logical>`; never the page
    itself; rows `{id, title, path, kind, implementation}`.

- [ ] **Step 1: Write the failing tests**

```python
def with_point(adr):
    a = adr.write_without_ai(adr.new({"title": "Sessions", "kind": "new", "touches": ["api:src/S.java"]})["id"])
    return adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])

def decided(adr, **choice):
    a = with_point(adr)
    return adr.point(a["id"], "choose", {"point": "p1", **choice}, a["sha"])

def test_accept_writes_the_outcome_owns_and_confirms(adr, kit):
    a = decided(adr, chosen="A", rationale="already used by notifications")
    out = adr.accept(a["id"], by="Test", attendees=["LA", "MP"], base_sha=a["sha"])
    fm, body = kit.docs.split_fm((kit.root / "docs" / out["path"]).read_text(encoding="utf-8"))
    assert fm["x-owner"] == "human" and fm["x-confirmed"]["by"] == "Test"
    assert kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed"
    assert out["status"] == "accepted" and out["state"]["phase"] == "accepted"
    assert "**Where?** — Redis. already used by notifications" in out["sections"]["decision"]
    assert "#### P1" not in out["sections"]["decision"] and "LA, MP" in out["sections"]["decided_by"]

@pytest.mark.parametrize("defer, msg", [(True, "P1 is deferred"), (False, "P1 has no choice")])
def test_accept_refuses_what_is_not_decided(adr, defer, msg):
    a = with_point(adr)
    if defer:
        a = adr.point(a["id"], "defer", {"point": "p1"}, a["sha"])
    with pytest.raises(adr.AdrError, match=msg):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])

def test_accept_with_no_points_needs_a_written_decision(adr):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "retro"})["id"])
    with pytest.raises(adr.AdrError, match="Decision"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    a = adr.part(a["id"], "decision", "edit", "We keep JPA.", base_sha=a["sha"])
    assert adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])["status"] == "accepted"

def test_superseding_marks_an_old_adr_even_without_frontmatter(adr, kit):
    old = kit.root / "docs" / "decisions" / "0001-ehcache.md"
    old.parent.mkdir(parents=True)
    old.write_text("# 0001 — EhCache\n\n## Status\n\nAccepted\n\n## Context\n\nx\n", encoding="utf-8")
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "0001"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    text = old.read_text(encoding="utf-8")
    assert "Superseded by [0002](0002-caffeine.md)" in text and "## Context\n\nx\n" in text
    assert adr.get("0001")["chip"] == "superseded"

def test_covering_finds_accepted_adrs_through_shared_sources(adr, kit):
    page = kit.root / "docs" / "orders.md"
    page.parent.mkdir(exist_ok=True)
    page.write_text("---\ntitle: Orders\nx-sources:\n  - api:src/S.java#L1-L9\n---\n# Orders\n", encoding="utf-8")
    a = decided(adr, chosen="A", rationale="r")
    assert adr.covering("orders.md") == []                                  # proposed ADRs cover nothing
    adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert [(c["id"], c["implementation"]) for c in adr.covering("orders.md")] == [(a["id"], "pending")]
    assert adr.covering(a["path"]) == []
```

Also test `reject(id, why="", …)` raises `AdrError("a rejection needs a reason")` and a real one writes
`Rejected (YYYY-MM-DD): <why>`, `x-owner: human`, confirmed, phase `rejected`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_accept.py -q`
Expected: FAIL — `AttributeError: module 'lib.adr' has no attribute 'accept'`

- [ ] **Step 3: Implement `accept`, `reject`, `covering` in `lib/adr.py`**

`accept` order: check conditions → set `status` → `decision` (only when there are points: `render_decision`) →
`decided_by` (`mode` from state) → frontmatter `x-owner: human` → write → `docs.confirm` → old ADR (when `supersedes`):
replace its status section only, `docs.confirm` only if it has frontmatter → state. Messages: `"point P1 is deferred:
decide it or remove it"`, `"point P1 has no choice yet"`, `"write the Decision section or add a decision point"`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_accept.py tests/test_adr.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr.py tests/test_adr_accept.py
git commit -m "feat(adr): accept, reject and supersede an ADR; the pages an accepted one covers"
```

---

### Task 4: The evidence pack (`lib/adr_pack.py`)

**Files:**
- Create: `.camarones/lib/adr_pack.py`
- Modify: `.camarones/lib/kanban/index.py` (add `neighbours`), `.camarones/lib/history.py` (public `commits`),
  `.camarones/lib/adr.py` (add `pack`)
- Test: `tests/test_adr_pack.py`, `tests/test_kanban_index.py` (one test for `neighbours`)

**Interfaces:**
- Consumes: `kanban.index.connect/pages_citing`, `history.commits`, `c4edit.index`, `inventory.load`, `docs.iter_docs`,
  `adr.list_adrs`.
- Produces:
  - `index.neighbours(conn, touches: Iterable[str]) -> set[str]` — files one edge away (either direction) from any
    touched file, repo-qualified, excluding the touches themselves.
  - `history.commits(repo: str, months: int) -> list[dict]` — the existing `_commits`, made public (`_commits` stays as
    the name `mine` uses, or `mine` switches to it).
  - `adr_pack.build(state: dict) -> dict` — `{touches, neighbours, pages: [{page, title, description, trust}], adrs:
    [{id, title, status, path}], commits: [{repo, subject, author, files}], c4: [{fqn, title, technology, repo}],
    libraries: [{repo, name, version, category, manifest}], questions: [str]}`, each list capped (Global Constraints).
    `pages` leaves out `type: decision` pages and the ADR itself: ADRs citing the touches go to `adrs`.
  - `adr_pack.render(pack: dict) -> str` — Markdown, one `##` per non-empty part, cut at `LIMIT` with a final
    `…(cut)` line.
  - `adr_pack.summary(pack: dict) -> dict` — `{files, neighbours, pages, adrs, commits, c4, libraries, questions}`
    counts.
  - `adr.pack(id: str) -> dict` — writes `CACHE/adr/<id>/pack.json` and `pack.md`, phase `problem` → `evidence`,
    returns `{summary, markdown}`; `adr.read_pack(id) -> dict | None` returns the same from the cache.
  - `adr.get(id)["affected"]` — the doc pages (logical paths, no `type: decision`) citing the state's touches, from
    `index.pages_citing`; `[]` for a legacy ADR or when the index cannot be read. Test: in `pack_world`,
    `adr.get("0002")["affected"] == ["orders.md"]` once the state exists.

- [ ] **Step 1: Write the failing tests**

```python
def test_neighbours_are_one_edge_away(world):                       # tests/test_kanban_index.py
    kit, ops, index, *_ = world
    conn = index.connect()
    try:
        assert PAY in index.neighbours(conn, [ORDER]) and ORDER not in index.neighbours(conn, [ORDER])
    finally:
        conn.close()

def test_the_pack_gathers_what_the_project_knows(pack_world):        # tests/test_adr_pack.py
    kit, adr_pack, state = pack_world
    p = adr_pack.build(state)
    assert p["touches"] == [ORDER]
    assert PAY in p["neighbours"]
    assert [x["page"] for x in p["pages"]] == ["orders.md"] and p["pages"][0]["title"] == "Orders"
    assert [x["id"] for x in p["adrs"]] == ["0001"]                   # cites OrderService too
    assert p["commits"] and all("OrderService.java" in "".join(c["files"]) for c in p["commits"])
    assert adr_pack.summary(p)["pages"] == 1
    md = adr_pack.render(p)
    assert "## Doc pages" in md and "Orders" in md and len(md) <= adr_pack.LIMIT + 20

def test_a_fresh_project_gets_an_empty_pack(kit):
    adr_pack = importlib.import_module("lib.adr_pack")
    p = adr_pack.build({"id": "0001", "touches": ["api:src/main/java/demo/Api.java"]})
    assert p["neighbours"] == [] and p["pages"] == [] and p["c4"] == [] and p["libraries"] == [] and p["questions"] == []
    assert "api:src/main/java/demo/Api.java" in adr_pack.render(p)

def test_pack_moves_the_phase_and_is_cached(adr, kit):
    a = adr.new({"title": "A", "kind": "new", "touches": ["api:pom.xml"]})
    out = adr.pack(a["id"])
    assert out["summary"]["files"] == 1 and adr.get(a["id"])["state"]["phase"] == "evidence"
    assert adr.read_pack(a["id"])["markdown"] == out["markdown"]
```

`pack_world` fixture: the `world` setup of `test_kanban_index.py` (git init, `write_graph(kit)`, `docs/orders.md`
citing OrderService), plus a commit in the api repo touching OrderService (`fixtures.builder.git`), an accepted ADR
`docs/decisions/0001-orders.md` whose `x-sources` cite OrderService, and `state = {"id": "0002", "touches": [ORDER]}`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_pack.py tests/test_kanban_index.py -q`
Expected: FAIL — no `lib.adr_pack`, no `index.neighbours`

- [ ] **Step 3: Implement**

Each source is read inside its own `try/except Exception` that yields an empty list (a broken C4 model, a missing
graph or an unreadable repo must not stop the pack — the spec's "fresh project" case). Commits: per touched code repo,
those whose files include a touched path, in `git log` order, capped. Questions: open-question lines (`- [ ]`) that
contain a touched file's basename or a touched repo-qualified path.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_pack.py tests/test_kanban_index.py tests/test_history.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr_pack.py .camarones/lib/kanban/index.py .camarones/lib/history.py .camarones/lib/adr.py \
        tests/test_adr_pack.py tests/test_kanban_index.py
git commit -m "feat(adr): the evidence pack, built without AI from graph, docs, git, C4 and inventory"
```

---

### Task 5: *Candidatas* — decisions the code took without an ADR

**Files:**
- Modify: `.camarones/lib/adr_pack.py`
- Test: `tests/test_adr_candidates.py`

**Interfaces:**
- Consumes: `inventory.load`, `c4edit.index`, `common.repo_dir`, `docs.repo_names`, `adr.list_adrs` + `adr.get`
  (title, tags, TL;DR of each ADR).
- Produces:
  - `adr_pack.term(name: str) -> str` — the artifact after the last `:` or `/`, lowercased, without a leading
    `spring-boot-starter-` or `spring-`.
  - `adr_pack.candidates() -> list[dict]` — rows `{key, label, category, repos, manifests}` (`key` =
    `"<category>:<term>"`, `manifests` as `<repo>:<path>` touches), one per key across repos, sorted by category then
    label, those whose term appears (case-insensitive) in an ADR's title, tags or TL;DR left out.

- [ ] **Step 1: Write the failing tests**

```python
def seed_inventory(kit, rows):
    from lib.common import WORK, save_json
    save_json(WORK / "inventory.json", {"libraries": rows})

ROW = dict(ecosystem="maven", version="1", declared="1", language="java", scope="runtime")

def test_terms(adr_pack):
    assert adr_pack.term("org.springframework.boot:spring-boot-starter-data-jpa") == "data-jpa"
    assert adr_pack.term("org.postgresql:postgresql") == "postgresql" and adr_pack.term("@nestjs/core") == "core"

def test_candidates_group_repos_and_skip_tests_and_covered_ones(adr_pack, kit):
    seed_inventory(kit, [
        {**ROW, "repo": "api", "name": "org.postgresql:postgresql", "category": "data", "manifest": "pom.xml"},
        {**ROW, "repo": "web", "name": "org.postgresql:postgresql", "category": "data", "manifest": "pom.xml"},
        {**ROW, "repo": "api", "name": "junit", "category": "testing", "manifest": "pom.xml"},
        {**ROW, "repo": "api", "name": "kafka-clients", "category": "messaging", "manifest": "pom.xml", "scope": "test"},
        {**ROW, "repo": "api", "name": "spring-boot-starter-security", "category": "security", "manifest": "pom.xml"}])
    got = adr_pack.candidates()
    assert [(c["key"], c["repos"]) for c in got] == [("data:postgresql", ["api", "web"]), ("security:security", ["api"])]
    assert got[0]["manifests"] == ["api:pom.xml", "web:pom.xml"]
    d = kit.root / "docs" / "decisions"
    d.mkdir(parents=True)
    (d / "0001-db.md").write_text("---\ntitle: 0001 — Why PostgreSQL\n---\n# 0001 — Why PostgreSQL\n", encoding="utf-8")
    assert [c["key"] for c in adr_pack.candidates()] == ["security:security"]

def test_deployment_sources_are_candidates(adr_pack, kit):
    (kit.ws / "api" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    assert ("deploy:docker-compose", ["api:docker-compose.yml"]) in [(c["key"], c["manifests"]) for c in adr_pack.candidates()]

def test_a_fresh_project_has_no_candidates_and_no_error(adr_pack):
    assert adr_pack.candidates() == []
```

Add two C4 tests on a `docs/architecture/model.c4` with a container `technology 'PostgreSQL'` and
`metadata { repo 'api' }`: alone, it yields `("c4:postgresql", ["api"])`; next to an inventory row
`org.postgresql:postgresql` in `web`, there is one row, `("data:postgresql", ["api", "web"])`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_candidates.py -q`
Expected: FAIL — `AttributeError: … 'candidates'`

- [ ] **Step 3: Implement `term` and `candidates`**

When the same term comes from the inventory and from C4, keep the inventory row's category and key and add the C4
repos. Deployment labels: `Docker Compose`, `Helm`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_candidates.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr_pack.py tests/test_adr_candidates.py
git commit -m "feat(adr): candidate decisions from the inventory, C4 and deployment sources"
```

---

### Task 6: The app API and the doc page's decisions (`lib/adr_api.py`, `lib/serve.py`)

**Files:**
- Create: `.camarones/lib/adr_api.py`
- Modify: `.camarones/lib/serve.py` (`api_app_get`: names starting with `adr`; `do_POST`: `/api/app/adr/<action>`;
  `api_doc`: `d["decisions"] = adr.covering(path)`)
- Test: `tests/test_adr_api.py`

**Interfaces:**
- Consumes: Tasks 2–5; `serve._text`, `serve._text_list`, `serve.reviewer`.
- Produces (every route needs the app token — `/api/app/` is already guarded in `do_POST`; GETs go through
  `api_app_get`, which the existing guard covers too):
  - `adr_api.get(name: str, q: dict) -> tuple[dict, int]` for `adr` → `{"adrs": list_adrs(), "next": next_id()}`,
    `adr/candidates` → `{"candidates": [...]}`, `adr/<NNNN>` → `get(id)`, `adr/<NNNN>/pack` → `read_pack(id)` or 404.
  - `adr_api.post(action: str, b: dict, by: str) -> tuple[dict, int]` for `new`, `pack`, `write`, `review`
    (start_review), `part`, `point`, `attendees`, `accept`, `reject`. `AdrConflict` → 409 `{error, sha}` (the file's
    current sha); `AdrError`/`ValueError` → 400; `KeyError` → 404 `{"error": "no ADR <id>"}`.
  - `/api/doc` responses gain `decisions: [{id, title, path, kind, implementation}]` (portal token and static portal
    too: it is a read of the docs).

- [ ] **Step 1: Write the failing tests**

```python
from test_app_api import TOKEN, app_server, call, portal_server   # noqa: F401

@pytest.mark.parametrize("path, body", [("adr", None), ("adr/candidates", None), ("adr/new", {"title": "A", "kind": "new"})])
def test_adr_routes_need_the_app_token(app_server, portal_server, path, body):
    assert call(f"{app_server}/api/app/{path}", body)[0] == 403
    assert call(f"{app_server}/api/app/{path}", body, token="nope")[0] == 403
    assert call(f"{portal_server}/api/app/{path}", body)[0] == 403

def test_a_decision_from_new_to_accepted(app_server):
    u = f"{app_server}/api/app/adr"
    code, a = call(f"{u}/new", {"title": "Sessions", "kind": "new", "touches": ["api:pom.xml"]}, token=TOKEN)
    assert code == 200 and a["id"] == "0001"
    assert call(f"{u}/pack", {"id": "0001"}, token=TOKEN)[1]["summary"]["files"] == 1
    a = call(f"{u}/write", {"id": "0001"}, token=TOKEN)[1]
    a = call(f"{u}/point", {"id": "0001", "op": "add", "question": "Where?", "base_sha": a["sha"],
                            "options": [{"name": "Redis"}, {"name": "Postgres"}]}, token=TOKEN)[1]
    a = call(f"{u}/point", {"id": "0001", "op": "choose", "point": "p1", "chosen": "A", "rationale": "r",
                            "base_sha": a["sha"]}, token=TOKEN)[1]
    code, a = call(f"{u}/accept", {"id": "0001", "attendees": ["LA"], "base_sha": a["sha"]}, token=TOKEN)
    assert code == 200 and a["status"] == "accepted"
    assert call(u, token=TOKEN)[1]["adrs"][0]["chip"] == "accepted"

def test_a_stale_part_is_a_409_with_the_current_sha(app_server, kit):
    u = f"{app_server}/api/app/adr"
    call(f"{u}/new", {"title": "A", "kind": "new"}, token=TOKEN)
    a = call(f"{u}/write", {"id": "0001"}, token=TOKEN)[1]
    code, body = call(f"{u}/part", {"id": "0001", "part": "context", "action": "edit", "text": "x", "base_sha": "old"}, token=TOKEN)
    assert code == 409 and body["sha"] == a["sha"]

@pytest.mark.parametrize("body, code", [({"title": "", "kind": "new"}, 400), ({"title": "A", "kind": "maybe"}, 400),
                                        ({"title": "A", "kind": "new", "touches": "api:x"}, 400)])
def test_bad_input_is_a_400(app_server, body, code):
    assert call(f"{app_server}/api/app/adr/new", body, token=TOKEN)[0] == code

def test_unknown_adr_is_a_404(app_server):
    assert call(f"{app_server}/api/app/adr/0042", token=TOKEN)[0] == 404
```

Plus: `GET /api/doc?path=orders.md` on the `portal_server` returns `decisions` with the accepted ADR covering it (seed
the page and an accepted ADR through `lib.adr` directly).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_api.py -q`
Expected: FAIL — 404 on every `/api/app/adr…` route

- [ ] **Step 3: Implement `lib/adr_api.py` and the three hooks in `serve.py`**

`serve.py` gains only delegation lines (`return self.json(*adr_api.get(name, q))`,
`return self.json(*adr_api.post(action, b, by))`) and one line in `api_doc`; the validation lives in `adr_api.py`,
reusing `serve._text` / `serve._text_list` semantics (re-implemented there or imported; no circular import at module
load — import inside the functions, as `serve.py` does).

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_api.py tests/test_app_api.py tests/test_portal_data.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr_api.py .camarones/lib/serve.py tests/test_adr_api.py
git commit -m "feat(adr): app-token API for decisions; doc pages list the ADRs that cover them"
```

---

### Task 7: CLI `camaron adr …` and the catalog

**Files:**
- Create: `.camarones/lib/adr_cli.py`
- Modify: `.camarones/camarones.py` (`build_parser`: `adr_cli.add_parser(sp)`; `main`: `elif a.cmd == "adr"`),
  `.camarones/lib/catalog.py` (`"adr": _e("app", "team", "Decisiones (ADR): listar, crear, aceptar",
  "Decisions (ADRs): list, create, accept")`), `docs/research/cli-triage.md` (regenerated)
- Test: `tests/test_adr_cli.py`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces: `adr_cli.add_parser(sp) -> None` (positional `action` in `("list", "new", "show", "pack", "candidates",
  "write", "accept", "reject")`, `args` nargs `*`, `--kind`, `--problem`, `--touch` (append), `--supersedes`,
  `--attendee` (append), `--why`, `--json`); `adr_cli.run(a) -> int` — 0 ok; 2 on `AdrError`/`KeyError`, with
  `✖ <message>` on stderr and no joke, as `camaron board` does. Plain output: one line per ADR
  `NNNN  <chip>  <title>`; `--json` prints the function's result. `write` is the app's *Escribir sin IA*; `accept` and
  `reject` read the current sha themselves (a script has no stale read). `accept` on an ADR with no file yet fails
  with `"write the ADR first: camaron adr write <id>"`. (Spec §4.11 lists no `write`; it is added because a script
  could not create the file otherwise.)

- [ ] **Step 1: Write the failing tests**

```python
def cli(kit, *args):
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "adr", *args],
                          capture_output=True, text=True, encoding="utf-8", env={**os.environ})

def test_new_list_and_show(kit):
    r = cli(kit, "new", "Sessions in Redis", "--kind", "new", "--touch", "api:pom.xml", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["id"] == "0001"
    assert "0001  running  Sessions in Redis" in cli(kit, "list").stdout
    assert json.loads(cli(kit, "show", "0001", "--json").stdout)["state"]["touches"] == ["api:pom.xml"]

def test_accept_needs_a_file_and_a_decision(kit):
    cli(kit, "new", "A", "--kind", "retro")
    r = cli(kit, "accept", "0001")
    assert r.returncode == 2 and "camaron adr write 0001" in r.stderr
    assert cli(kit, "write", "0001").returncode == 0
    r = cli(kit, "accept", "0001")
    assert r.returncode == 2 and r.stderr.startswith("✖") and "write the Decision section" in r.stderr

def test_the_catalog_knows_adr(kit):
    from lib import catalog
    assert catalog.COMMANDS["adr"]["verdict"] == "app"
```

`cli` follows `tests/test_kanban_cli.py`'s helper (a subprocess of `camarones.py` with the kit's environment).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_adr_cli.py -q`
Expected: FAIL — `invalid choice: 'adr'`

- [ ] **Step 3: Implement `adr_cli.py`, register it, add the catalog row, regenerate the triage page**

Regenerate from `.camarones/`: `uv run --script camarones.py catalog --markdown > ../docs/research/cli-triage.md`.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/test_adr_cli.py tests/test_catalog.py -q && (cd .camarones && uv run --script camarones.py catalog --check)`
Expected: PASS, and `catalog --check` exits 0

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/adr_cli.py .camarones/camarones.py .camarones/lib/catalog.py docs/research/cli-triage.md \
        tests/test_adr_cli.py
git commit -m "feat(adr): camaron adr list|new|show|pack|candidates|accept|reject"
```

---

### Task 8: Desktop helpers, nav and strings (`renderer/src/adr.js`)

**Files:**
- Create: `.camarones/desktop/renderer/src/adr.js`, `.camarones/desktop/renderer/src/adr.test.js`
- Modify: `.camarones/desktop/renderer/src/nav.js` (`PROJECT` gains `'decisions'` after `'board'`),
  `nav.test.js`, `palette.js` (`GO.a = 'decisions'`), `i18n.js` (`nav.decisions`: `Decisiones` / `Decisions`, and the
  `adr.*` keys the views of Tasks 9–10 name), `i18n.test.js` (`nav` family gains `decisions`; an `adr.chip` family with
  every value of `CHIPS`)

**Interfaces:**
- Consumes: the API shapes of Task 6.
- Produces:
  - `route(hash: string) -> { view: 'list' | 'new' | 'candidates' | 'adr', id?: string }` — `#/decisions/0012` →
    `{ view: 'adr', id: '0012' }`; anything else under `#/decisions` → `list`.
  - `FILTERS = ['all', 'running', 'review', 'accepted', 'superseded']`, `counts(rows) -> {filter: n}`,
    `filterRows(rows, filter, q) -> rows` (q matches title, id, repos, case- and accent-insensitive).
  - `STEPS = ['problem', 'evidence', 'research', 'synthesis', 'review', 'accepted']`,
    `stepper(phase, mode) -> [{ id, state: 'done' | 'current' | 'todo' | 'skipped' }]` — `mode: 'manual'` marks
    `research` and `synthesis` `skipped`.
  - `nextPart(parts, current, dir: 1 | -1) -> string` (clamped, no wrap).
  - `presentKey(key: string, ctx: { typing: boolean, options: number }) -> null | { do: 'next' | 'prev' | 'choose'
    | 'edit' | 'defer' | 'accept' | 'exit' | 'toggle', n?: number }` — `→`/`←`, `1`–`9` (only up to `ctx.options`),
    `e`, `d`, `a`, `Escape`, `p`; always `null` while `ctx.typing`.
  - `acceptBlock(adr) -> null | { key: string, point?: string }` — the first reason accept is refused, mirroring
    Task 3's messages (`adr.why.deferred`, `adr.why.unchosen`, `adr.why.noDecision`), so the button explains itself.
  - `addHit(touches: string[], hit) -> string[]` — a search hit added to *Toca*: a group adds its `files`, a file or
    page its `touch`; sorted, unique (the portal's `pickHit` stays where it is: it depends on portal helpers).

- [ ] **Step 1: Write the failing tests**

```js
test('routes inside the section', () => {
  expect(route('#/decisions')).toEqual({ view: 'list' })
  expect(route('#/decisions/new')).toEqual({ view: 'new' })
  expect(route('#/decisions/candidates')).toEqual({ view: 'candidates' })
  expect(route('#/decisions/0012')).toEqual({ view: 'adr', id: '0012' })
  expect(route('#/decisions/x')).toEqual({ view: 'list' })
})

test('filters count and match accents', () => {
  const rows = [{ id: '0002', title: 'Sesión en Redis', chip: 'review', repos: ['api'] },
                { id: '0001', title: 'JPA', chip: 'accepted', repos: ['vets'] }]
  expect(counts(rows)).toEqual({ all: 2, running: 0, review: 1, accepted: 1, superseded: 0 })
  expect(filterRows(rows, 'all', 'sesion').map((r) => r.id)).toEqual(['0002'])
  expect(filterRows(rows, 'accepted', '').map((r) => r.id)).toEqual(['0001'])
})

test('a hand-written ADR skips the AI steps', () => {
  expect(stepper('review', 'manual').map((s) => s.state)).toEqual(['done', 'done', 'skipped', 'skipped', 'current', 'todo'])
})

test('presentation keys, never while typing', () => {
  expect(presentKey('ArrowRight', { typing: false, options: 3 })).toEqual({ do: 'next' })
  expect(presentKey('2', { typing: false, options: 3 })).toEqual({ do: 'choose', n: 2 })
  expect(presentKey('4', { typing: false, options: 3 })).toBeNull()
  expect(presentKey('ArrowRight', { typing: true, options: 3 })).toBeNull()
})

test('a hit adds its files once, sorted', () => {
  expect(addHit(['api:b.java'], { kind: 'group', touch: 'api:orders', files: ['api:c.java', 'api:b.java'] }))
    .toEqual(['api:b.java', 'api:c.java'])
  expect(addHit([], { kind: 'page', touch: 'cam-docs:docs/orders.md' })).toEqual(['cam-docs:docs/orders.md'])
})

test('accept explains why it cannot run yet', () => {
  const adr = (points, decision = 'To be decided in review: see the decision points.') => ({ points, sections: { decision } })
  expect(acceptBlock(adr([{ id: 'p1', deferred: true }]))).toEqual({ key: 'adr.why.deferred', point: 'P1' })
  expect(acceptBlock(adr([{ id: 'p1' }]))).toEqual({ key: 'adr.why.unchosen', point: 'P1' })
  expect(acceptBlock(adr([]))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([{ id: 'p1', chosen: 'A' }]))).toBeNull()
})
```

Update `nav.test.js` to the new `PROJECT` list (`['summary', 'board', 'decisions', 'plan', …]`) and its index
assertion (`PROJECT[1]` stays `'board'`).

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/desktop/renderer && npm test -- adr nav i18n palette`
Expected: FAIL — `adr.js` missing, nav list differs

- [ ] **Step 3: Implement `adr.js`, the nav/palette entries and the strings**

- [ ] **Step 4: Run them to see them pass**

Run: `cd .camarones/desktop/renderer && npm test`
Expected: PASS (all renderer tests)

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/adr.js .camarones/desktop/renderer/src/adr.test.js \
        .camarones/desktop/renderer/src/nav.js .camarones/desktop/renderer/src/nav.test.js \
        .camarones/desktop/renderer/src/palette.js .camarones/desktop/renderer/src/i18n.js \
        .camarones/desktop/renderer/src/i18n.test.js
git commit -m "feat(app): decisions section helpers, nav entry and strings"
```

---

### Task 9: Desktop — list, new, candidates and evidence

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/Decisions.jsx`,
  `sections/adr/AdrList.jsx`, `sections/adr/NewForm.jsx`, `sections/adr/TouchSearch.jsx`,
  `sections/adr/Candidates.jsx`, `sections/adr/Evidence.jsx`, `.camarones/desktop/renderer/src/Decisions.test.jsx`
- Modify: `.camarones/desktop/renderer/src/App.jsx` (`SECTIONS.decisions = Decisions`),
  `.camarones/desktop/renderer/src/app.css` (`.dk-adr-*` rules)

**Interfaces:**
- Consumes: Task 8; `server(token).get/post`; `@camaron/ui` (`Aviso`, `Button`, `Chip`, `EmptyState`, `Field`,
  `Skeleton`); `Page`, `Failed` from `parts.jsx`; `GET /api/stories/files` for the search box.
- Produces (presentational views exported for tests, like `BoardView`):
  - `AdrListView({ rows, filter, q, onFilter, onQ, candidates })` — the mock-up of spec §2.1: header buttons
    *Candidatas · N* and *Nuevo ADR*, filter chips with counts, rows (`NNNN`, title, `kind · repos · when`, chip), the
    dashed candidates strip when there are candidates, an `EmptyState` (the one allowed joke) when there are no rows.
  - `NewFormView({ fields, errors, onChange, onSubmit, prefilled })` — spec §2.2; title, kind (radio), problem,
    drivers / constraints / options (one per line), *Toca* (`TouchSearch`), supersedes (a select of accepted ADRs).
  - `CandidatesView({ rows, onPick })` — one row per candidate: label, category, repos; *Crear ADR retro* opens the
    new form prefilled (`kind: 'retro'`, title `¿Por qué <label>?` / `Why <label>?`, touches = manifests).
  - `EvidenceView({ adr, pack, onPack, onWrite })` — stepper, the pack's one-line summary, *Ver paquete* (a `<details>`
    with the pack Markdown as preformatted text), *Escribir sin IA*; *Investigar* is not rendered in S1.
  - `LegacyView({ adr, onReview })` — an ADR with no working state: its sections read-only, its status chip, and
    *Revisar en sesión* (posts `review`, then opens the review).
  - `Decisions({ srv })` — reads the hash (`useHash`) and `route`, loads with `srv.get('app/adr')` /
    `srv.get('app/adr/' + id)` / `srv.get('app/adr/candidates')`, posts, shows `Failed` with retry on a failed read,
    and on a `409` reloads and says `adr.reloaded`. An ADR opens by phase: `problem`/`evidence` → `EvidenceView`,
    `review`/`accepted`/`rejected` → `Review` (Task 10; until then a placeholder), no state → `LegacyView`.

- [ ] **Step 1: Write the failing tests**

```jsx
const row = (o) => ({ id: '0012', title: 'Sesiones en Redis', kind: 'new', chip: 'review', repos: ['api'],
  points: { total: 3, decided: 1 }, legacy: false, ...o })

test('the list shows rows, chips and the candidates strip in both languages', () => {
  const out = list({ rows: [row(), row({ id: '0011', title: 'JPA', kind: 'retro', chip: 'accepted' })],
                     candidates: [{ key: 'data:postgresql', label: 'postgresql', repos: ['api'] }] })
  for (const s of ['0012', 'Sesiones en Redis', 'En revisión', 'Aceptada', '1 decisión en el código sin ADR'])
    expect(out).toContain(s)
  expect(list({ rows: [row()], candidates: [{}, {}] })).toContain('2 decisiones en el código sin ADR')
  expect(list({ rows: [row()], candidates: [] }, 'en')).toContain('In review')
})

test('a legacy ADR opens read-only with a way into a session', () => {
  const out = legacy({ adr: { id: '0003', title: 'JPA', status: 'proposed', legacy: true, sections: { context: 'why' } } })
  expect(out).toContain('why')
  expect(out).toContain('Revisar en sesión')
  expect(out).not.toContain('<textarea')
})

test('an empty project invites the first decision', () => {
  expect(list({ rows: [], candidates: [] })).toContain('Nuevo ADR')
})

test('a candidate prefills a retroactive ADR', () => {
  const c = { key: 'data:postgresql', label: 'postgresql', manifests: ['api:pom.xml'] }
  expect(candidateFields(c, 'es')).toEqual({ kind: 'retro', title: '¿Por qué postgresql?', touches: ['api:pom.xml'] })
  expect(candidateFields(c, 'en').title).toBe('Why postgresql?')
})

test('the evidence step offers writing without AI and no research button in S1', () => {
  const out = evidence({ adr: { id: '0012', state: { phase: 'evidence', mode: 'manual' } },
                         pack: { summary: { files: 14, pages: 3, adrs: 1, commits: 31, c4: 2 }, markdown: '## Doc pages' } })
  expect(out).toContain('14 archivos')
  expect(out).toContain('Escribir sin IA')
  expect(out).not.toContain('Investigar')
})
```

`list`, `legacy`, `evidence` are small helpers in the test file over `renderToStaticMarkup` and the exported views
(as `view` in `Board.test.jsx`). Replace `candidateClick` with a direct test of `candidateFields(c, lang)`, exported
from `Candidates.jsx` (it builds the prefill the view passes to `onPick`). The candidates strip uses two strings
(`adr.cand.one`, `adr.cand.many`) so one candidate reads in the singular.

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/desktop/renderer && npm test -- Decisions`
Expected: FAIL — modules missing

- [ ] **Step 3: Implement the views and the section**

Glyphs only, no icon set (CAMARON.md): `✓ ● ○ ⌕ ▸`. Chips use the existing `Chip` tones (`warn` for review, `ok`
for accepted, neutral for superseded/rejected, `info` for running). Square corners and console density from the
theme tokens.

- [ ] **Step 4: Run them to see them pass**

Run: `cd .camarones/desktop/renderer && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src
git commit -m "feat(app): Decisions list, new ADR, candidates and the evidence pack"
```

---

### Task 10: Desktop — review and presentation mode

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/adr/Review.jsx`, `.camarones/desktop/renderer/src/Review.test.jsx`
- Modify: `sections/Decisions.jsx` (phase `review`/`accepted`/`rejected` → `Review`), `app.css` (`.dk-present`:
  hides `.dk-rail`, `.dk-side` and the breadcrumbs, one part per screen, a larger type scale from the theme's display
  tokens), `.claude/skills/cofundo-design-system/CAMARON.md` (a fifth approved exception: presentation mode's type
  scale)

**Interfaces:**
- Consumes: Task 8 (`nextPart`, `presentKey`, `acceptBlock`, `stepper`); `palette.typing(el)`; the API of Task 6
  (`part`, `point`, `attendees`, `accept`, `reject`).
- Produces:
  - `ReviewView({ adr, current, present, onPart, onPoint, onAttendees, onAccept, onReject, onPresent, onGo })` — spec
    §2.5: the parts list with `✓ ● ○` and their statuses; a text part pane (the section's text, *Aprobar*, *Editar*
    with a textarea and *Guardar*, *Aplazar*); a point pane (question, options as cards with `1…n`, pros/cons, *Elegir
    y seguir* with a one-line rationale field, *Otra* with a text field, *Aplazar punto*, *Quitar*); *Añadir punto*
    (question + at least two option names); attendees (initials as chips, an add field); the footer key hints; the
    *Docu afectada* part listing the pages an accepted ADR would cover (from `get().affected`, read-only in S1);
    *Aceptar ADR* (disabled-looking but focusable, saying `acceptBlock`'s reason when blocked) and *Rechazar* (asks
    for the reason).
  - Keyboard: a `keydown` listener on the review container maps `presentKey(e.key, { typing: typing(e.target),
    options })` to the handlers; `p` toggles presentation, `Escape` leaves it.

- [ ] **Step 1: Write the failing tests**

```jsx
const adr = (o = {}) => ({ id: '0012', title: 'Sesiones', status: 'proposed', sha: 's1',
  state: { phase: 'review', mode: 'manual', attendees: ['LA'] },
  parts: [{ id: 'context', status: 'approved' }, { id: 'point:p1', status: 'pending' }, { id: 'affected', status: 'pending' }],
  points: [{ id: 'p1', question: '¿Dónde viven las sesiones?', options: [{ id: 'A', name: 'Redis', pros: ['ya en uso'], cons: [] },
    { id: 'B', name: 'Postgres', pros: [], cons: ['escrituras'] }] }],
  sections: { context: 'Hoy en memoria.', decision: 'To be decided in review: see the decision points.' }, affected: ['orders.md'], ...o })

test('a decision point shows its options with keys and its question', () => {
  const out = review({ adr: adr(), current: 'point:p1' })
  for (const s of ['¿Dónde viven las sesiones?', 'A · Redis', 'B · Postgres', '>1<', '+ ya en uso', '− escrituras'])
    expect(out).toContain(s)
})

test('accept says why it is blocked', () => {
  expect(review({ adr: adr(), current: 'context' })).toContain('El punto P1 aún no tiene elección')
})

test('presentation mode drops the chrome and keeps the keys visible', () => {
  const out = review({ adr: adr(), current: 'point:p1', present: true })
  expect(out).toContain('dk-present')
  expect(out).toContain('Esc')
})

test('the review screen carries no joke', () => {
  for (const k of Object.keys(S.es).filter((k) => k.startsWith('adr.review.'))) expect(S.es[k]).not.toMatch(/camar[oó]n|🦐/i)
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/desktop/renderer && npm test -- Review`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `Review.jsx`, wire it in `Decisions.jsx`, add the CSS and the CAMARON.md exception**

Every write sends `base_sha: adr.sha`; the response replaces `adr`. `Elegir y seguir` posts `point choose` then
moves `nextPart(parts, current, 1)`.

- [ ] **Step 4: Run them to see them pass**

Run: `cd .camarones/desktop/renderer && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src .claude/skills/cofundo-design-system/CAMARON.md
git commit -m "feat(app): review an ADR part by part, decide its points, present it, accept or reject"
```

---

### Task 11: Portal — status pill, covering banner, tree chips

**Files:**
- Modify: `.camarones/portal/app/src/views/docpage.js` (`pageBanners` gains decision banners),
  `views/Doc.jsx` (a status pill in an ADR page's header), `views/tree.js` (a decision row's status for the tree),
  `views/DocsTree.jsx` (draw it), `i18n/portal.js` (es + en), the matching `*.test.js`
- Modify: `.camarones/lib/serve.py` `tree()` rows for `type: decision` gain `adr_status` (from `adr_doc.status_of`)
- Rebuild: `.camarones/portal/app/app-build/` (`npm run build`, committed)
- Test: `views/docpage.test.js`, `views/tree.test.js`, `tests/test_portal_data.py` (one assertion on `adr_status`)

**Interfaces:**
- Consumes: `/api/doc` `decisions` (Task 6); `tree()` rows.
- Produces:
  - `pageBanners(d, row, lang)` adds, for each `d.decisions` entry, `{ tone: 'info', key: 'banner.adrPending' |
    'banner.adr', adr: { id, title, path } }` — `adrPending` when `kind === 'new' && implementation === 'pending'`.
  - `adrStatusLabel(status) -> key` in `tree.js` (`adr.proposed`, `adr.accepted`, …).

- [ ] **Step 1: Write the failing tests**

```js
test('a page covered by an accepted ADR says so, pending implementation when new', () => {
  const d = { trust: 'confirmed', decisions: [{ id: '0012', title: '0012 — Sessions', path: 'decisions/0012-sessions.md', kind: 'new', implementation: 'pending' },
                                              { id: '0003', title: '0003 — JPA', path: 'decisions/0003-jpa.md', kind: 'retro', implementation: 'n/a' }] }
  expect(pageBanners(d, { space: 'docs' }, '').map((b) => b.key)).toEqual(['banner.adrPending', 'banner.adr'])
})
```

Strings: `banner.adrPending` = `Decisión {id} aceptada, pendiente de implementar: esta página describe el código de hoy.` /
`Decision {id} accepted, pending implementation: this page describes today's code.`; `banner.adr` =
`Esta página la cubre la decisión {id}.` / `Decision {id} covers this page.` — the banner links to the ADR page.

- [ ] **Step 2: Run them to see them fail**

Run: `cd .camarones/portal/app && npm test -- docpage tree`
Expected: FAIL

- [ ] **Step 3: Implement, then rebuild the portal**

Run: `cd .camarones/portal/app && npm run build`

- [ ] **Step 4: Run them to see them pass**

Run: `cd .camarones/portal/app && npm test && cd ../../.. && uv run pytest tests/test_portal_data.py tests/test_portal_app.py -q`
Expected: PASS (the build-matches-source check included)

- [ ] **Step 5: Commit**

```bash
git add .camarones/portal/app .camarones/lib/serve.py tests/test_portal_data.py
git commit -m "feat(portal): ADR status in the tree and on the page; banners on pages an accepted ADR covers"
```

---

### Task 12: Conventions, docs, version, build and the end-to-end check

**Files:**
- Modify: `.camarones/CONVENTIONS.md` (§6 *Decision*: the optional sections — Decision drivers, Considered options,
  Confirmation, Diagram, Decided by — and one rule: an ADR with a working state in `docs/.work/adr/` is being decided
  by people; agents never rewrite it), `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.72.0"`), `README.md` (badge
  and a *Decisiones* paragraph: what it does without AI, the commands), `.camarones/lib/tutorial.py` (one page, es + en)
  and the regenerated `.camarones/TUTORIAL.md`, `.camarones/templates/docs/guides/tutorial.md` and
  `.camarones/templates/docs/i18n/es/guides/tutorial.md` (the `camaron adr` commands)
- Rebuild: `.camarones/desktop/renderer-build/` (`npm run build` in `.camarones/desktop/renderer`, committed)

- [ ] **Step 1: Update the docs and the version; regenerate the tutorial**

From `.camarones/`:
`uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 2: Build the desktop renderer**

Run: `cd .camarones/desktop/renderer && npm run build`
Expected: `renderer-build/` updated, no errors

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -n auto` (repo root), `npm test` in `.camarones/desktop/renderer` and `.camarones/portal/app`,
`node --test "test/*.test.cjs"` in `.camarones/desktop`
Expected: all green; `test_wizard.py` (TUTORIAL.md), `test_desktop_renderer.py` and the portal build check included

- [ ] **Step 4: End to end on the sandbox (AGENTS.md §2.2)**

Run: `uv run scripts/sandbox.py reset`, then `uv run scripts/sandbox.py cli adr candidates`, `… cli adr new "Why
spring-data-jpa" --kind retro --touch <repo>:pom.xml`, and open the app on the sandbox (`uv run scripts/sandbox.py
open`) to write it without AI, add one point, present it with `P`, decide it and accept it; then
`uv run scripts/sandbox.py traces`.
Expected: the candidate list includes Spring Data JPA; the accepted ADR is confirmed in the sandbox's `cam-docs`;
`traces` exits 0. If the sandbox is missing, `reset` creates it (first run clones from GitHub) — say so.

- [ ] **Step 5: Commit**

```bash
git add .camarones/CONVENTIONS.md .camarones/lib/common.py README.md .camarones/lib/tutorial.py \
        .camarones/TUTORIAL.md .camarones/templates/docs/guides/tutorial.md \
        .camarones/templates/docs/i18n/es/guides/tutorial.md .camarones/desktop/renderer-build
git commit -m "feat(adr): Decisiones in the app without AI — docs, tutorial and kit 4.72.0

Existing projects keep their copy of the templates' tutorial; the new commands are in README and TUTORIAL.md."
```
