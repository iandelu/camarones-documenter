# Coding workflow, slice 1: skill pack, team copies and notes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `cam-task` skill pack (with `cam-difficulty`, `cam-verify`, `cam-ship`, `cam-retro`) so an agent in a Camarón project follows the docs-first workflow with today's commands, and let a team fork, diff and reset any kit skill and collect feedback notes per skill.

**Architecture:** A new `lib/skills.py` (layer `app`, imports only `lib/common`) knows the kit's skills, the team's copies in `cam-docs/.camarones/skills/`, the fork stamps and the notes. `env.write_kit_skills` renders the *effective* skills (team copy, else kit text) into `.claude/skills` and `.agents/skills`; trust keeps approving only the kit's own text, so a team copy is asked for once per machine. `lib/skills_cli.py` is the `camaron skills` command.

**Tech Stack:** Python 3.10+ stdlib (`difflib`, `re`, `pathlib`), pytest + xdist, the kit's `lib/common` helpers.

**Spec:** `docs/superpowers/specs/2026-11-12-coding-workflow-design.md` (§4, §5.1, §5.2, §6 first bullets, §8, §11, §12 slice 1).

## Global Constraints

- macOS, Windows and Linux: `pathlib` only; every file read/written with `encoding="utf-8"`, text written with `newline="\n"`; processes only through `lib/core/process.py` helpers (re-exported by `lib/common`).
- TDD: each behaviour starts as a failing test; tests are offline, use the `kit` / `wired` fixtures (`tests/conftest.py`), never the real `~/.camarones`.
- `lib/skills.py` imports nothing from `lib` except `lib/common`: `env`, `doctor`, `trust`, `install_state` and `budget` sit in the largest import cycle and `tests/test_architecture.py` forbids it to grow (`largest_cycle: 66`, `cycle_modules: 68` in `tests/architecture/allowlist.yaml`).
- Layers (`tests/architecture/layers.yaml`): `skills: app`, `skills_cli: interfaces`. No new file over 600 lines.
- Context budget: the wired project's standing context stays ≤ `KIT_SHARE = 2500` tokens (`tests/test_context_budget.py`, unchanged). `cam-task`'s `name: description` ≤ 60 tokens, each step skill's ≤ 24, the new `AGENTS.md` line ≤ 30 (tokens = `(len(text) + 3) // 4`).
- Backward compatibility (AGENTS.md 2.3): a 3.x/4.x project gets the new skills and the `AGENTS.md` line on its next refresh with no manual step; nothing is renamed; team copies and notes are never rewritten by the kit except by an explicit `skills reset`.
- Locations, verbatim from the spec: team copies `cam-docs/.camarones/skills/<name>/`; fork stamps `cam-docs/.camarones/.kit-skills.json`; notes `cam-docs/docs/.work/skill-notes/<skill>.md`.
- Note line format (one line per note, fields `-` when empty, text last):
  `- {date} · {source} · step {step} · change {change} · ref {ref} · {by} — {text}`
- Note sources: `retro`, `review`, `board`.
- Skills are agent-facing and in English. CLI messages follow `lib/adr_cli.py`: English, errors one plain line on stderr starting `✖`, exit 2, no jokes; `--json` prints data and no prose.
- The slice-1 skills use only commands that exist today (`camaron check`, `camaron pr fresh`, `camaron board add|link`, `camaron skills note`, `git`, `gh`/`glab`); agents never move board columns (U4).
- Every user-visible change updates `README.md` (es), the guides `using`/`internals` in en and es, and the tutorial, in the same commit as Task 7. `VERSIONS["kit"]` becomes `"4.82.0"`.
- Conventional commits, small; never a `Co-Authored-By: Claude` trailer or "Generated with Claude Code" line.

**One deliberate change to the spec:** `skills reset` keeps the team's copy aside as the folder `cam-docs/.camarones/skills/.reset/<name>-<YYYYMMDD-HHMMSS>/`, not as `SKILL.md.<date>` inside the skill folder (a file left there would keep the folder a team copy). Task 3 updates spec §5.1 to match.

## Review Focus

1. A folder in `.camarones/skills/` with an invalid name (`My Skill`, `.hidden`, `Cam_Task`) or without a `SKILL.md` → never rendered; `skills list` names it as skipped with the reason. (Task 1)
2. A team copy saved with CRLF line endings (Windows editor) → rendered with LF, and an unedited fork stays recognised as the kit's text. (Task 2)
3. The legacy single-folder layout, where the project's `.camarones/` is the kit itself → no team copies are read, `skills fork` exits 2 with "team copies need the cam-docs layout". (Task 3)
4. A team skill deleted from `.camarones/skills/` → its rendered folders disappear from `.claude/skills` and `.agents/skills` on the next render; files the kit never rendered are left alone. (Task 2)
5. `skills note` with an unknown skill or a source outside `retro|review|board` → exit 2, one line, nothing written. (Task 5)

---

### Task 1: `lib/skills.py` — kit skills, team copies, effective sources

**Files:**
- Create: `.camarones/lib/skills.py`
- Modify: `tests/architecture/layers.yaml` (add `skills: app` next to the other `app` entries)
- Test: `tests/test_team_skills.py`

**Interfaces:**
- Produces (all in `lib/skills.py`):
  - `KIT_SKILLS: Path = KIT / "templates" / "skills"`
  - `NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")`
  - `team_dir() -> Path | None` — `ROOT / ".camarones" / "skills"`, or `None` when `(ROOT / ".camarones").resolve() == KIT.resolve()` (legacy layout)
  - `stamp_path() -> Path | None` — `ROOT / ".camarones" / ".kit-skills.json"`, same `None` rule
  - `load_stamp() -> dict` / `save_stamp(data: dict) -> None` — `{"forks": {name: {"files": {rel: raw}, "kit": "<version>"}}}`, `{"forks": {}}` when the file is missing; `save_stamp` is a no-op when `stamp_path()` is `None`. The file only appears with the first `fork`
  - `kit_names() -> list[str]` — sorted folder names under `KIT_SKILLS`
  - `kit_files(name: str) -> dict[str, str]` — rel posix path → raw text (placeholders unfilled, `\r\n` → `\n`)
  - `team_names() -> list[str]` — sorted valid team folders (name fully matches `NAME_RE`, contains `SKILL.md`)
  - `ignored() -> list[dict]` — `[{"name": str, "why": "invalid name" | "no SKILL.md"}]`, folders starting with `.` are skipped silently (they hold `.reset/`)
  - `origin(name: str) -> str | None` — `"team"` (team copy of a kit skill), `"team-only"`, `"kit"`, or `None` for a name neither has
  - `sources() -> dict[str, dict[str, str]]` — effective raw files per skill name: the team folder's files when `origin` is `team`/`team-only`, else `kit_files(name)`; keys sorted
  - `description(name: str) -> str` — the `description:` value from the effective `SKILL.md` frontmatter, `""` if absent

- [ ] **Step 1: Write the failing tests**

```python
import importlib

def skills(kit):
    return importlib.import_module("lib.skills")

def team(kit, name, text="---\nname: x\ndescription: Team text.\n---\n# x\n", extra=None):
    d = kit.root / ".camarones" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    for rel, body in (extra or {}).items():
        (d / rel).write_text(body, encoding="utf-8")
    return d

def test_kit_skills_are_listed_with_their_raw_text(kit):
    s = skills(kit)
    assert {"cam-docs-lookup", "cam-docs-update"} <= set(s.kit_names())
    assert "{{CLI}}" in s.kit_files("cam-docs-update")["SKILL.md"]
    assert s.origin("cam-docs-update") == "kit" and s.origin("nope") is None

def test_a_team_copy_wins_and_a_team_only_skill_is_added(kit):
    s = skills(kit)
    team(kit, "cam-docs-update", extra={"notes.md": "n"})
    team(kit, "our-review")
    assert s.origin("cam-docs-update") == "team" and s.origin("our-review") == "team-only"
    src = s.sources()
    assert src["cam-docs-update"]["SKILL.md"].startswith("---\nname: x")
    assert set(src["cam-docs-update"]) == {"SKILL.md", "notes.md"}
    assert "our-review" in src and s.description("our-review") == "Team text."

def test_bad_team_folders_are_skipped_with_a_reason(kit):
    s = skills(kit)
    team(kit, "My Skill"); team(kit, "Cam_Task")
    (kit.root / ".camarones" / "skills" / "empty-one").mkdir()
    (kit.root / ".camarones" / "skills" / ".reset").mkdir()
    assert s.team_names() == []
    assert sorted((i["name"], i["why"]) for i in s.ignored()) == [
        ("Cam_Task", "invalid name"), ("My Skill", "invalid name"), ("empty-one", "no SKILL.md")]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_team_skills.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.skills'`

- [ ] **Step 3: Implement the interfaces above in `.camarones/lib/skills.py`**

Module docstring states the module's job and that it imports only `lib.common` (the cycle rule). Frontmatter for `description` is read with a regex on the first `---` block (no `docs` import).

- [ ] **Step 4: Add `skills: app` to `tests/architecture/layers.yaml`**

- [ ] **Step 5: Run the tests and the architecture suite**

Run: `uv run pytest tests/test_team_skills.py tests/test_architecture.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .camarones/lib/skills.py tests/test_team_skills.py tests/architecture/layers.yaml
git commit -m "feat(skills): know the kit's skills and the team's copies in cam-docs/.camarones/skills"
```

---

### Task 2: Render the effective skills; drift, trust and budget follow

**Files:**
- Modify: `.camarones/lib/env.py` (`kit_skill_files` unchanged; new `skill_files`; `write_kit_skills` rewritten)
- Modify: `.camarones/lib/install_state.py` (`drift()` uses `env.skill_files()`)
- Modify: `.camarones/lib/trust.py` (`items()` labels team skill files)
- Modify: `.camarones/lib/budget.py` (`_skills()` kit flag)
- Test: `tests/test_team_skills.py`

**Interfaces:**
- Consumes: `skills.sources()`, `skills.origin()` (Task 1); `env.fill(text, name)`; `CACHE`, `load_json`, `save_json` from `lib.common`.
- Produces:
  - `env.skill_files(project_name: str | None = None) -> dict[str, str]` — `f"{host}/skills/{name}/{rel}"` → `fill(raw, project)` for every `(name, files)` in `skills.sources()`, hosts `.claude` and `.agents`
  - `env.RENDERED_SKILLS = CACHE / "skills-rendered.json"` — the git-ignored list of paths the last render wrote on this machine
  - `env.write_kit_skills(project_name: str | None = None) -> None` — writes `skill_files()`; then deletes each path in `RENDERED_SKILLS` that is not in the new set (and its folder when left empty); then saves the new sorted path list there. Its docstring now says a copy edited in `.claude/skills` goes back to the effective text (the team's copy, else the kit's); `refresh_agent_config`'s docstring the same
  - `env.kit_skill_files()` keeps returning the kit's own text only — `trust.owned()` keeps using it, so a team copy that differs from the kit is pending approval

- [ ] **Step 1: Write the failing tests** (in `tests/test_team_skills.py`)

```python
def test_a_team_copy_is_rendered_in_both_hosts_and_repair_keeps_it(wired):
    team(wired, "cam-docs-update", text="---\nname: cam-docs-update\ndescription: Ours.\n---\nUse {{CLI}} check.\n")
    wired.env.write_kit_skills()
    for host in (".claude", ".agents"):
        text = (wired.root / host / "skills" / "cam-docs-update" / "SKILL.md").read_text(encoding="utf-8")
        assert "Ours." in text and "{{CLI}}" not in text
    assert [d for d in importlib.import_module("lib.install_state").drift() if "skills" in d["path"]] == []

def test_a_crlf_team_copy_renders_with_lf(wired):
    d = team(wired, "cam-docs-unit")
    (d / "SKILL.md").write_bytes(b"---\r\nname: cam-docs-unit\r\ndescription: Ours.\r\n---\r\nbody\r\n")
    wired.env.write_kit_skills()
    assert b"\r\n" not in (wired.root / ".claude" / "skills" / "cam-docs-unit" / "SKILL.md").read_bytes()

def test_a_removed_team_skill_leaves_no_rendered_copy_and_foreign_files_stay(wired):
    d = team(wired, "our-review")
    wired.env.write_kit_skills()
    mine = wired.root / ".claude" / "skills" / "handmade" / "SKILL.md"
    mine.parent.mkdir(parents=True); mine.write_text("x", encoding="utf-8")
    import shutil; shutil.rmtree(d)
    wired.env.write_kit_skills()
    assert not (wired.root / ".claude" / "skills" / "our-review").exists()
    assert not (wired.root / ".agents" / "skills" / "our-review").exists()
    assert mine.exists()

def test_trust_asks_for_an_edited_team_copy_once_and_names_it(wired):
    trust = importlib.import_module("lib.trust")
    team(wired, "cam-docs-update", text="---\nname: cam-docs-update\ndescription: Ours.\n---\nbody\n")
    wired.env.write_kit_skills()
    rows = [(it, st) for it, st in trust.pending() if "cam-docs-update" in it.id]
    assert rows and all(it.kind == "skill" and "(team copy)" in it.detail for it, _ in rows)
    trust.approve()
    assert [it for it, _ in trust.pending() if "cam-docs-update" in it.id] == []

def test_budget_counts_only_kit_skills_as_the_kits(wired):
    team(wired, "our-review"); wired.env.write_kit_skills()
    rows = {i["path"]: i["kit"] for i in importlib.import_module("lib.budget").standing()["items"] if i["kind"] == "skill"}
    assert rows[".claude/skills/our-review/SKILL.md"] is False
    assert rows[".claude/skills/cam-docs-lookup/SKILL.md"] is True
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_team_skills.py -q`
Expected: the five new tests FAIL (team text not rendered, no "(team copy)" label, `our-review` counted as kit or missing)

- [ ] **Step 3: Implement `env.skill_files` and the new `env.write_kit_skills`**

- [ ] **Step 4: `install_state.drift()` builds `expected` from `env.skill_files()` instead of `env.kit_skill_files()`**

- [ ] **Step 5: `trust.items()` appends `" (team copy)"` (origin `team`) or `" (team skill)"` (origin `team-only`) to the detail of a `kind == "skill"` file whose third path part is that skill's name; the digest is unchanged**

- [ ] **Step 6: `budget._skills()` sets `"kit": skills.origin(f.parent.name) == "kit"`**

- [ ] **Step 7: Run the touched suites**

Run: `uv run pytest tests/test_team_skills.py tests/test_agent_trust.py tests/test_install_state.py tests/test_context_budget.py tests/test_architecture.py tests/test_agent_guidance.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add .camarones/lib/env.py .camarones/lib/install_state.py .camarones/lib/trust.py .camarones/lib/budget.py tests/test_team_skills.py
git commit -m "feat(skills): render a team's copy of a skill; trust asks for it once, repair keeps it"
```

---

### Task 3: Fork, diff, reset, outdated — and `doctor` says when the kit moved on

**Files:**
- Modify: `.camarones/lib/skills.py`
- Modify: `.camarones/lib/doctor.py` (`report()` gains `"skills_outdated"`)
- Modify: `.camarones/camarones.py` (plain `doctor` output, after the drift lines)
- Modify: `docs/superpowers/specs/2026-11-12-coding-workflow-design.md` (§5.1 `reset` bullet: aside folder `.camarones/skills/.reset/<name>-<YYYYMMDD-HHMMSS>/`)
- Test: `tests/test_team_skills.py`

**Interfaces:**
- Consumes: Task 1's functions; `VERSIONS["kit"]` from `lib.common`.
- Produces:
  - `skills.fork(name: str) -> Path` — copies `kit_files(name)` into `team_dir()/name`, records `forks[name] = {"files": kit_files(name), "kit": VERSIONS["kit"]}` in the stamp, returns the team folder. Raises `ValueError` with `"team copies need the cam-docs layout"` when `team_dir()` is `None`, `"<name> is not a kit skill"` when not in `kit_names()`, `"<name> already has a team copy"` when it exists.
  - `skills.diff(name: str, against_fork: bool = False) -> str` — unified diff (`difflib.unified_diff`, `lineterm=""`), per file: default `kit/<rel>` (kit now) → `team/<rel>` (team copy); with `against_fork`, `fork/<rel>` (stamp) → `kit/<rel>` (kit now). `""` when equal. `ValueError` `"no team copy of <name>"` / `"<name> has no kit version"` / `"<name> was not forked with skills fork"` as applicable.
  - `skills.reset(name: str, now: str | None = None) -> Path` — moves the team folder to `team_dir()/".reset"/f"{name}-{now}"` (`now` default `%Y%m%d-%H%M%S`), drops `forks[name]`, returns the aside folder. `ValueError` `"no team copy of <name>"`, or `"<name> is a team skill: delete its folder to remove it"` for origin `team-only`.
  - `skills.outdated() -> list[str]` — sorted names with origin `team` whose `forks[name]["files"]` differ from `kit_files(name)`.
  - `doctor.report()["skills_outdated"]: list[str]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_fork_copies_the_kit_text_and_stays_trusted_until_edited(wired):
    s = skills(wired)
    d = s.fork("cam-docs-update")
    assert (d / "SKILL.md").read_text(encoding="utf-8") == s.kit_files("cam-docs-update")["SKILL.md"]
    assert s.load_stamp()["forks"]["cam-docs-update"]["kit"] == wired.env.VERSIONS["kit"]
    wired.env.write_kit_skills()
    assert [it for it, _ in importlib.import_module("lib.trust").pending() if "cam-docs-update" in it.id] == []
    assert s.diff("cam-docs-update") == ""

def test_diff_shows_the_team_edit_and_what_the_kit_changed_since(wired, monkeypatch):
    s = skills(wired)
    d = s.fork("cam-docs-update")
    (d / "SKILL.md").write_text("team line\n", encoding="utf-8")
    assert "+team line" in s.diff("cam-docs-update")
    real = s.kit_files
    monkeypatch.setattr(s, "kit_files", lambda n: {"SKILL.md": real(n)["SKILL.md"] + "kit line\n"})
    assert s.outdated() == ["cam-docs-update"] and "+kit line" in s.diff("cam-docs-update", against_fork=True)

def test_reset_puts_the_team_copy_aside_and_follows_the_kit(wired):
    s = skills(wired)
    s.fork("cam-docs-update")
    aside = s.reset("cam-docs-update", now="20261112-101500")
    assert aside == wired.root / ".camarones" / "skills" / ".reset" / "cam-docs-update-20261112-101500"
    assert (aside / "SKILL.md").exists() and s.origin("cam-docs-update") == "kit"
    assert "cam-docs-update" not in s.load_stamp()["forks"]

def test_reset_refuses_a_team_only_skill_and_fork_refuses_twice(wired):
    s = skills(wired)
    team(wired, "our-review")
    with pytest.raises(ValueError, match="team skill"):
        s.reset("our-review")
    s.fork("cam-docs-unit")
    with pytest.raises(ValueError, match="already has a team copy"):
        s.fork("cam-docs-unit")

def test_legacy_layout_has_no_team_copies(kit, monkeypatch):
    s = skills(kit)
    monkeypatch.setattr(s, "team_dir", lambda: None)
    assert s.team_names() == [] and s.origin("cam-docs-update") == "kit"
    with pytest.raises(ValueError, match="cam-docs layout"):
        s.fork("cam-docs-update")

def test_doctor_reports_outdated_team_copies(wired, monkeypatch):
    s = skills(wired)
    monkeypatch.setattr(s, "outdated", lambda: ["cam-docs-update"])
    assert importlib.import_module("lib.doctor").report()["skills_outdated"] == ["cam-docs-update"]
```

(`import pytest` at the top of the file.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_team_skills.py -q`
Expected: the six new tests FAIL with `AttributeError: module 'lib.skills' has no attribute 'fork'` (and `KeyError: 'skills_outdated'`)

- [ ] **Step 3: Implement `fork`, `diff`, `reset`, `outdated` in `lib/skills.py`, and the `skills_outdated` key in `doctor.report()`**

- [ ] **Step 4: In `camarones.py`'s plain `doctor` branch, after the drift block (inside `if WS_FILE.exists():`), print one line per outdated skill**

Exact copy: `f"⚠ skill {name}: the kit's version changed since your team copy — `{cli_cmd()} skills diff {name} --kit`"`

- [ ] **Step 5: Update spec §5.1's `reset` bullet to the `.reset/<name>-<YYYYMMDD-HHMMSS>/` folder**

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_team_skills.py tests/test_doctor.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .camarones/lib/skills.py .camarones/lib/doctor.py .camarones/camarones.py tests/test_team_skills.py docs/superpowers/specs/2026-11-12-coding-workflow-design.md
git commit -m "feat(skills): fork, diff and reset a kit skill; doctor says when the kit's version moved on"
```

---

### Task 4: Skill notes

**Files:**
- Modify: `.camarones/lib/skills.py`
- Test: `tests/test_skill_notes.py`

**Interfaces:**
- Consumes: `skills.origin()` (Task 1); `DOCS` from `lib.common`.
- Produces:
  - `SOURCES = ("retro", "review", "board")`
  - `notes_dir() -> Path` — `DOCS / ".work" / "skill-notes"`
  - `format_note(n: dict) -> str` — keys `date, source, step, change, ref, by, text`; empty → `-`; every field except `text` has `" · "` and `" — "` replaced by `" - "`; `text` whitespace collapsed to single spaces
  - `parse_note(line: str) -> dict | None` — inverse of `format_note` (`-` → `""`), `None` for any line not in the format
  - `add_note(skill: str, text: str, source: str, by: str, step: str = "", change: str = "", ref: str = "", today: str | None = None) -> Path` — `ValueError` `"unknown skill: <skill>"` when `origin(skill)` is `None`, `"source must be one of: retro, review, board"`, `"empty note"`; creates the file with the header below if missing, appends one line, returns the file
  - `notes(skill: str | None = None) -> list[dict]` — every parsed note (with `"skill"` added) of one file or all files, newest `date` first, file order kept within a date

Header written once per file (exact copy):

```
# Skill notes: {skill}

Where the `{skill}` skill got in the way. One line per note, added with `camaron skills note`.

```

- [ ] **Step 1: Write the failing tests**

```python
import importlib, pytest

def test_a_note_round_trips_through_its_line_format(kit):
    skills = importlib.import_module("lib.skills")
    n = {"date": "2026-11-12", "source": "retro", "step": "verify", "change": "wi-12", "ref": "", "by": "Ana López",
         "text": "the plan missed the  integration\ntests"}
    line = skills.format_note(n)
    assert line == ("- 2026-11-12 · retro · step verify · change wi-12 · ref - · Ana López — "
                    "the plan missed the integration tests")
    assert skills.parse_note(line) == {**n, "text": "the plan missed the integration tests"}
    assert skills.parse_note("# Skill notes: x") is None

def test_add_note_writes_one_file_per_skill_and_notes_reads_them_newest_first(kit):
    s = importlib.import_module("lib.skills")
    f = s.add_note("cam-docs-update", "first", "retro", "ana", today="2026-11-10")
    s.add_note("cam-docs-update", "second", "review", "bo", ref="https://git.example/pr/3#c1", today="2026-11-12")
    assert f == kit.root / "docs" / ".work" / "skill-notes" / "cam-docs-update.md"
    assert f.read_text(encoding="utf-8").startswith("# Skill notes: cam-docs-update\n")
    assert [n["text"] for n in s.notes("cam-docs-update")] == ["second", "first"]
    assert s.notes()[0]["skill"] == "cam-docs-update"

def test_add_note_refuses_unknown_skills_sources_and_empty_text(kit):
    s = importlib.import_module("lib.skills")
    for args, msg in ((("nope", "x", "retro", "a"), "unknown skill"), (("cam-docs-update", "x", "chat", "a"), "source"),
                      (("cam-docs-update", "  ", "retro", "a"), "empty")):
        with pytest.raises(ValueError, match=msg):
            s.add_note(*args)
    assert not (kit.root / "docs" / ".work" / "skill-notes").exists()

def test_notes_never_become_pages(kit):
    s = importlib.import_module("lib.skills")
    s.add_note("cam-docs-update", "x", "retro", "ana")
    assert not [r for r in kit.docs.collect() if "skill-notes" in r["path"]]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_skill_notes.py -q`
Expected: FAIL with `AttributeError: module 'lib.skills' has no attribute 'format_note'`

- [ ] **Step 3: Implement the interfaces above in `lib/skills.py`**

Appends open the file with `"a", encoding="utf-8", newline="\n"`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skill_notes.py tests/test_team_skills.py tests/test_architecture.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/skills.py tests/test_skill_notes.py
git commit -m "feat(skills): feedback notes per skill in docs/.work/skill-notes"
```

---

### Task 5: `camaron skills`

**Files:**
- Create: `.camarones/lib/skills_cli.py`
- Modify: `.camarones/camarones.py` (parser registration next to `adr_cli.add_parser(sp)`; dispatch `elif a.cmd == "skills": return skills_cli.run(a)`; the help text, a `skills` entry after `removed`)
- Modify: `.camarones/lib/catalog.py` (`"skills": CLI` in the CLI-only group)
- Modify: `tests/architecture/layers.yaml` (`skills_cli: interfaces`)
- Modify: `tests/snapshots/cli.json` (regenerated)
- Test: `tests/test_skills_cli.py`

**Interfaces:**
- Consumes: Tasks 1, 3 and 4; `env.write_kit_skills()`; `serve.reviewer()` for `by`.
- Produces: `skills_cli.ACTIONS = ("list", "fork", "diff", "reset", "note", "notes")`, `skills_cli.add_parser(sp) -> None`, `skills_cli.run(a) -> int`. Arguments: `action`, `args` (`nargs="*"`), `--kit`, `--source`, `--step`, `--change`, `--ref`, `--json`. Positionals: `fork NAME`, `diff NAME`, `reset NAME`, `note SKILL TEXT…` (text = the remaining args joined by spaces), `notes [SKILL]`. `--kit` only with `diff`; `--source/--step/--change/--ref` only with `note`; `--source` required for `note`.

Output (exact copy):
- `list` plain: one line per skill `f"{name}  {origin}"` plus `"  (kit changed since your copy)"` when outdated; each ignored folder on stderr: `f"· skipped .camarones/skills/{name}: {why}"`. `--json`: `{"skills": [{"name", "origin", "outdated", "description"}], "ignored": [...]}`.
- `fork`: `f"✔ team copy of {name}: {rel} — edit it and commit it in a docs PR"` (`rel` relative to cam-docs, posix), then re-render.
- `diff`: the diff text, or `f"{name}: same as the kit"` when empty. `--json`: `{"name", "diff"}`.
- `reset`: `f"✔ {name} follows the kit again (your copy: {rel})"`, then re-render.
- `note`: `f"✔ note added to {rel}"`.
- `notes` plain: grouped by skill, then step (`-` for none), newest first: `f"{skill} ({n})"`, `f"  {step} ({m})"`, `f"    {date} {source} {change} {by} — {text}"`; none → `"No skill notes yet."` on stderr. `--json`: the `notes()` list.
- Every `ValueError` from `lib/skills.py` → `f"✖ {message}"` on stderr, exit 2.

- [ ] **Step 1: Write the failing tests**

```python
import json, os, subprocess, sys
from conftest import KIT_DIR

def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "skills", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")

def test_list_fork_diff_reset_from_the_command_line(wired):
    (wired.root / ".camarones" / "skills" / "My Skill").mkdir(parents=True)
    (wired.root / ".camarones" / "skills" / "My Skill" / "SKILL.md").write_text("x", encoding="utf-8")
    assert "· skipped .camarones/skills/My Skill: invalid name" in cli(wired, "list").stderr
    r = cli(wired, "list", "--json")
    assert r.returncode == 0, r.stderr
    rows = {s["name"]: s for s in json.loads(r.stdout)["skills"]}
    assert rows["cam-docs-update"]["origin"] == "kit" and rows["cam-docs-update"]["description"]
    assert cli(wired, "fork", "cam-docs-update").stdout.startswith("✔ team copy of cam-docs-update: .camarones/skills/")
    assert cli(wired, "diff", "cam-docs-update").stdout.strip() == "cam-docs-update: same as the kit"
    assert "follows the kit again" in cli(wired, "reset", "cam-docs-update").stdout

def test_note_and_notes(wired):
    r = cli(wired, "note", "cam-docs-update", "the", "check", "step", "came", "too", "late", "--source", "retro",
            "--step", "verify", "--change", "wi-12")
    assert r.returncode == 0, r.stderr
    out = cli(wired, "notes").stdout
    assert "cam-docs-update (1)" in out and "  verify (1)" in out and "the check step came too late" in out
    assert json.loads(cli(wired, "notes", "--json").stdout)[0]["change"] == "wi-12"

def test_bad_input_is_one_line_and_exit_2(wired):
    for args in (("note", "nope", "x", "--source", "retro"), ("note", "cam-docs-update", "x", "--source", "chat"),
                 ("note", "cam-docs-update", "x"), ("fork",), ("list", "--kit"), ("diff", "cam-docs-update", "--source", "retro")):
        r = cli(wired, *args)
        assert r.returncode == 2 and r.stderr.startswith("✖") and len(r.stderr.strip().splitlines()) == 1, args
    assert not (wired.root / "docs" / ".work" / "skill-notes").exists()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_skills_cli.py -q`
Expected: FAIL (`invalid choice: 'skills'`, exit 2 from argparse on every call)

- [ ] **Step 3: Implement `lib/skills_cli.py`, register it in `camarones.py`, add `"skills": CLI` to `catalog.py` and `skills_cli: interfaces` to `layers.yaml`**

Help text entry in `camarones.py` (exact copy, after the `removed` entry):

```
  skills list | fork NAME | diff NAME [--kit] | reset NAME | note SKILL TEXT --source retro|review|board
         [--step S] [--change ID] [--ref URL] | notes [SKILL]   [--json]
                            the agents' skills: a team copy in .camarones/skills wins over the kit's; notes say
                            where a skill got in the way (docs/.work/skill-notes)
```

- [ ] **Step 4: Regenerate the CLI snapshot and review its diff**

Run: `CAMARONES_UPDATE_SNAPSHOTS=1 uv run pytest tests/test_cli_snapshot.py -q && git diff --stat tests/snapshots/cli.json`
Expected: PASS; the diff only adds the `skills` subcommand

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_skills_cli.py tests/test_cli_snapshot.py tests/test_catalog.py tests/test_architecture.py -q`
Expected: PASS (including `catalog --check`)

- [ ] **Step 6: Commit**

```bash
git add .camarones/lib/skills_cli.py .camarones/camarones.py .camarones/lib/catalog.py tests/architecture/layers.yaml tests/snapshots/cli.json tests/test_skills_cli.py
git commit -m "feat(cli): camaron skills — list, fork, diff, reset, note, notes"
```

---

### Task 6: The skill pack and the `AGENTS.md` line

**Files:**
- Create: `.camarones/templates/skills/cam-task/SKILL.md`
- Create: `.camarones/templates/skills/cam-difficulty/SKILL.md`
- Create: `.camarones/templates/skills/cam-verify/SKILL.md`
- Create: `.camarones/templates/skills/cam-ship/SKILL.md`
- Create: `.camarones/templates/skills/cam-retro/SKILL.md`
- Modify: `.camarones/templates/AGENTS.md` (inside `<!-- camarones:start -->` … `<!-- camarones:end -->`)
- Test: `tests/test_coding_workflow_skills.py`

**Interfaces:**
- Consumes: `camaron skills note` (Task 5), `env.kit_skill_files()`, `budget.tokens()`.
- Produces: five kit skills rendered into every project (no code interface).

Frontmatter, exact copy (each file starts with it):

```
---
name: cam-task
description: Start here for any code change (feature, fix, refactor) in {{PROJECT_NAME}} — read cam-docs first, judge difficulty, test first, verify, pass the guardrails, state the impact, then open linked code and docs PRs.
---
```
```
---
name: cam-difficulty
description: Step of cam-task — score a change's difficulty, then escalate or split it.
---
```
```
---
name: cam-verify
description: Step of cam-task — build and run the change's verification plan.
---
```
```
---
name: cam-ship
description: Step of cam-task — guardrails, impact, then the linked code and docs PRs.
---
```
```
---
name: cam-retro
description: Step of cam-task — notes on where the workflow got in the way.
---
```

`AGENTS.md`: first line under `## Implementing a feature (any repo)` (exact copy):
`0. Any code change: follow skill `cam-task` (docs first, difficulty, verification, guardrails, linked PRs).`

What each body must carry (the tests below pin the phrases in quotes; the rest is the implementer's wording, short numbered steps, placeholders `{{CLI}}`/`{{CAM}}`/`{{PROJECT_NAME}}` where paths or the CLI appear):

- **`cam-task`** — steps in this order: 1 name the change (`<id>` = the board item in lower case, e.g. `wi-12`, else a short slug; branch `"cam/<id>-<slug>"` in each service repo you change, and the docs in their own worktree: `"git -C {{CAM}}. worktree add ../.cw/<id> -b cam/<id>-<slug>"`, run from the workspace root); 2 read the docs with `"cam-docs-lookup"` and summarise them with citations `[path#section]` before changing code; 3 `"cam-difficulty"`; 4 design and plan as the level says; 5 implement test-first; 6 update the docs in the worktree with `"cam-docs-update"`; 7 `"cam-verify"`; 8 `"cam-ship"`; 9 `"cam-retro"`. A paragraph on superpowers: when its skills are available, step 4 uses `"brainstorming"` and `"writing-plans"` (medium and high), step 5 `"test-driven-development"`, failures `"systematic-debugging"`; without them, write the failing test, watch it fail, make it pass; `cam-ship` replaces `"finishing-a-development-branch"` while a change is open; steps 1–3 and 6–9 are "never skipped". When to ask the person: plan approval (medium/high), a raised difficulty level, before opening PRs. "Never merge"; never write `x-confirmed`.
- **`cam-difficulty`** — the signal table with these names and default weights: `repos` 2, `contract` 2, `migration` 2, `auth` 2, `messaging` 1, `weak-docs` 1 each max 2, `open-questions` 1, `hotspot` 1, `big-item` 1; levels `"0–2 low"` (short plan in chat), `"3–5 medium"` (written plan the person approves before code; may suggest more effort or a stronger model), `"6+ high"` (spec and plan approved, then a split); signals you infer are listed apart as `"inferred"` and do not count; split with `"{{CLI}} board add story"` `--label draft` per part (`--repo`, `--doc` as needed) and the person accepts them; re-score with the real diff at ship time and, if the level went up, stop and ask; the report line `Difficulty: <score> (<level>) — signals: …; inferred: …`.
- **`cam-verify`** — the profile table (detect → run): `mvnw`/`pom.xml` → `./mvnw -q test` (`verify` with `migration`/`contract`); `gradlew` → `./gradlew test` (`check`); `package.json` → `npm|pnpm|yarn test` by lockfile, plus its `lint` script; `pyproject.toml` → `uv run pytest` (or `pytest`); `go.mod` → `go test ./...`; `Cargo.toml` → `cargo test`; `*.sln`/`*.csproj` → `dotnet test`; extra checks from `repos[].verify` in `{{CAM}}.camarones/workspace.yaml` when present; `"{{CLI}} check"` from the docs worktree; JVM with SDKMAN: `source ~/.sdkman/bin/sdkman-init.sh && sdk env` first. Evidence: per check the command, exit code and `git rev-parse HEAD`; "a new commit makes it stale" — run again; failed-then-passed is `"flaky"` and needs the person's word; a check that cannot run (no Docker…) is `"not green"`. Additions for risk are allowed with a one-line why. A closing line that `camaron change verify` will produce this evidence itself in a later version.
- **`cam-ship`** — 1 guardrails: re-score (`cam-difficulty`); forbidden paths `".env*"`, `*.pem`, `*.key`, `id_rsa*`, `secrets/` in the diff → stop; `"gitleaks"` on the branch's commits when it is on PATH (say so when it is not); `"{{CLI}} pr fresh <repo> --base <base>"` lists pages the code leaves stale — each updated in the worktree or explained in the PR; `{{CLI}} check` in the worktree with no errors; trust rules (no `x-confirmed`, no `<!-- human -->` or `x-owner: human` edits); verification green for the current commits. 2 impact: repos and files, the risk signals, docs pages updated and confirmed pages that need re-confirming, C4 elements and their consumers (likec4 MCP or `{{CAM}}docs/architecture/*.c4`), decisions citing the files. 3 ask once: `"Open the PRs?"` with impact, verification and warnings. 4 on yes: commit the docs in the worktree (`docs: <title>`), push, open the code PR(s) as drafts first (`"gh pr create --draft"` / `"glab mr create --draft"`), then the docs PR linking them, then add the docs PR link to the code PR bodies; body sections Linked PRs ("merge the code first, the docs right after"), Impact, Difficulty, Verification, Warnings; without `gh`/`glab`, push and give the person the URLs. `"{{CLI}} board link"` the item to each PR; "never move" board columns — tell the person to move it. "Never merge". Then `cam-retro`.
- **`cam-retro`** — at the end of every change, 0–3 notes, only for friction in the workflow (a missing step, a wrong gate, noise, a doc that misled); none is a fine outcome; code problems are not skill notes; `"{{CLI}} skills note <skill> \"<text>\" --source retro --step <step> --change <id>"`; later, addressing PR review comments or board items (reopened, bugs, label `skill-feedback`) about the change: per entry decide code-only (no note) or a step that should have caught it (`--source review|board --ref <link>`); tuning: `"{{CLI}} skills notes"`, then `{{CLI}} skills fork <name>` and edit it in a docs PR.

- [ ] **Step 1: Write the failing tests**

```python
import importlib, re, sys
from conftest import KIT_DIR

SKILLS = KIT_DIR / "templates" / "skills"
PACK = ("cam-task", "cam-difficulty", "cam-verify", "cam-ship", "cam-retro")
MUST = {
    "cam-task": ["cam/<id>-<slug>", "worktree add ../.cw/<id>", "cam-docs-lookup", "cam-difficulty", "cam-docs-update",
                 "cam-verify", "cam-ship", "cam-retro", "brainstorming", "writing-plans", "test-driven-development",
                 "systematic-debugging", "finishing-a-development-branch", "never skipped", "Never merge"],
    "cam-difficulty": ["repos", "contract", "migration", "auth", "messaging", "weak-docs", "open-questions", "hotspot",
                       "big-item", "0–2 low", "3–5 medium", "6+ high", "inferred", "{{CLI}} board add story", "--label draft"],
    "cam-verify": ["./mvnw", "./gradlew", "go test ./...", "cargo test", "dotnet test", "repos[].verify", "{{CLI}} check",
                   "sdk env", "rev-parse HEAD", "flaky", "not green"],
    "cam-ship": [".env*", "gitleaks", "{{CLI}} pr fresh", "x-confirmed", "Open the PRs?", "gh pr create --draft",
                 "glab mr create --draft", "{{CLI}} board link", "never move", "Never merge", "cam-retro"],
    "cam-retro": ["{{CLI}} skills note", "--source retro", "review|board", "skill-feedback", "{{CLI}} skills notes",
                  "skills fork"],
}

def fm(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    return text, re.search(r"^name: (.*)$", head, re.M)[1], re.search(r"^description: (.*)$", head, re.M)[1]

def test_the_pack_says_what_each_step_needs():
    for name, parts in MUST.items():
        text, n, _ = fm(name)
        assert n == name
        missing = [p for p in parts if p not in text]
        assert not missing, (name, missing)

def test_descriptions_stay_inside_their_token_caps():
    for name in PACK:
        _, n, d = fm(name)
        cap = 60 if name == "cam-task" else 24
        assert (len(f"{n}: {d}") + 3) // 4 <= cap, name          # budget.tokens()

def test_agents_md_sends_every_code_change_to_cam_task():
    t = (KIT_DIR / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    block = t[t.index("<!-- camarones:start -->"):t.index("<!-- camarones:end -->")]
    line = next(l for l in block.splitlines() if "cam-task" in l)
    assert line.startswith("0. Any code change") and (len(line) + 3) // 4 <= 30

def test_every_project_gets_the_pack_rendered_in_both_hosts(kit):
    files = kit.env.kit_skill_files("Demo")
    for name in PACK:
        for host in (".claude", ".agents"):
            assert "{{" not in files[f"{host}/skills/{name}/SKILL.md"]

def test_an_old_projects_agents_md_gets_the_line_on_refresh(wired):
    f = wired.root / "AGENTS.md"
    old = [l for l in f.read_text(encoding="utf-8").splitlines() if "cam-task" not in l]
    f.write_text("\n".join(old) + "\n", encoding="utf-8")                     # what a 4.81 project has
    wired.env.init_templates(log=lambda _: None)
    assert "follow skill `cam-task`" in f.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_coding_workflow_skills.py -q`
Expected: FAIL with `FileNotFoundError` for `templates/skills/cam-task/SKILL.md`

- [ ] **Step 3: Write the five `SKILL.md` files and the `AGENTS.md` line**

- [ ] **Step 4: Run the pack tests and the budget**

Run: `uv run pytest tests/test_coding_workflow_skills.py tests/test_context_budget.py tests/test_agent_guidance.py tests/test_agent_trust.py tests/test_install_state.py -q`
Expected: PASS; if `test_the_kit_wiring_stays_under_its_budget` fails, shorten the skill bodies' descriptions or the new line (bodies do not count), never raise `KIT_SHARE`

- [ ] **Step 5: Commit**

```bash
git add .camarones/templates/skills/cam-task .camarones/templates/skills/cam-difficulty .camarones/templates/skills/cam-verify .camarones/templates/skills/cam-ship .camarones/templates/skills/cam-retro .camarones/templates/AGENTS.md tests/test_coding_workflow_skills.py
git commit -m "feat(skills): cam-task workflow — docs first, difficulty, verification, guardrails, linked PRs, retro"
```

---

### Task 7: User docs, tutorial and version

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.82.0"`)
- Modify: `README.md` (version badge `4.82.0`; a new section `## Programar con Camarón` after `## El día a día en cinco pasos`; `skills` in the `Agentes` row of `## Mapa de comandos`)
- Modify: `.camarones/templates/docs/guides/using.md` and `.camarones/templates/docs/i18n/es/guides/using.md` (new `## Coding with Camarón` / `## Programar con Camarón` after `## Keeping the docs current` / its twin)
- Modify: `.camarones/templates/docs/guides/internals.md` and its es twin (in `## The MCP servers`, the skills sentence lists the pack; in `## Plugins and trust`, one paragraph on team copies and trust)
- Modify: `.camarones/lib/tutorial.py` (one page per language, after the page about keeping the docs current) and regenerate `.camarones/TUTORIAL.md`
- Modify: `.camarones/templates/docs/guides/tutorial.md` and its es twin (`## 9. Commands`: the `skills` rows)

What the texts say (in each language, natural, at most one joke per screen and only in the tutorial page):

- Opening Claude Code or Codex in the workspace and asking for a change starts `cam-task`: docs first, difficulty (low / medium / high and the split into draft board items), test first, verification, guardrails, impact, one question, then a draft code PR and a draft docs PR that link each other. The kit never merges.
- With superpowers installed, its brainstorming, plans and TDD are used for those steps.
- Tuning: `camaron skills list | fork | diff [--kit] | reset`; a team copy lives in `cam-docs/.camarones/skills/<name>/`, wins over the kit's, survives upgrades, and each machine approves it once in `camaron trust`; `doctor` says when the kit's version moved on.
- Notes: `camaron skills note … --source retro|review|board` and `camaron skills notes`; files in `docs/.work/skill-notes/`.
- What comes in later versions: `camaron change` (the kit producing the evidence, the guardrails and opening the PRs itself).
- Existing projects get the skills on their next refresh; their copy of the command guide (`guides/tutorial.md`) stays as it was — say so in the commit body.

- [ ] **Step 1: Make the changes above**

- [ ] **Step 2: Regenerate `TUTORIAL.md`**

Run (from `.camarones/`): `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`
Expected: `git diff --stat .camarones/TUTORIAL.md` shows only the new pages

- [ ] **Step 3: Run the docs tests**

Run: `uv run pytest tests/test_guide.py tests/test_wizard.py -q`
Expected: PASS (markers, links and es/en twins match; `TUTORIAL.md` equals `tutorial.markdown()`)

- [ ] **Step 4: Commit**

```bash
git add README.md .camarones/lib/common.py .camarones/lib/tutorial.py .camarones/TUTORIAL.md .camarones/templates/docs/guides .camarones/templates/docs/i18n/es/guides
git commit -m "docs: coding with Camarón — the cam-task workflow and team skills (4.82.0)" -m "Existing projects keep their copy of guides/tutorial.md; the skills and the AGENTS.md line reach them on the next refresh."
```

---

### Task 8: Whole suite and the sandbox

**Files:** none changed (fix-ups go back to the task they belong to).

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: all passed (the e2e and eval markers are excluded by default)

- [ ] **Step 2: Check the sandbox end to end with this checkout's kit**

Run: `uv run scripts/sandbox.py reset && uv run scripts/sandbox.py cli repair && uv run scripts/sandbox.py cli skills list`
Expected: the five `cam-*` pack skills listed with origin `kit`; `.claude/skills/cam-task/SKILL.md` and `.agents/skills/cam-task/SKILL.md` exist in the sandbox's cam-docs with no `{{`

Run: `uv run scripts/sandbox.py cli skills fork cam-ship && uv run scripts/sandbox.py cli trust --json && uv run scripts/sandbox.py cli skills reset cam-ship`
Expected: an unedited fork is not pending in trust; reset prints "follows the kit again". If the sandbox is missing, `reset` creates it (first run clones from GitHub): say so in the report rather than skipping.

- [ ] **Step 3: Report**

Say which commands ran and their result; anything that failed is reported with its output.
