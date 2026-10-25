# Remove the Excalidraw boards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the portal's Excalidraw boards (server API, module, view, dependency, docs) while leaving every
existing `docs/boards/*.excalidraw` file untouched.

**Architecture:** Pure removal in three layers — Python (`lib/boards.py`, routes in `lib/serve.py`), portal (React view,
legacy shell routing and strings, Vite config, npm dependency, rebuilt `app-build/`), user docs. Old `#/boards…`
addresses redirect to `#/arch`; old API routes fall through to the existing 404.

**Tech Stack:** Python 3.10+ (pytest via `uv`), React 19 + Vite 8 + Vitest 5 (`npm` in `.camarones/portal/app` only).

**Spec:** `docs/superpowers/specs/2026-10-24-remove-boards-design.md`

Work in the worktree `.claude/worktrees/remove-boards` (branch `worktree-remove-boards`). Never in the main checkout:
another session has uncommitted edits there.

## Global Constraints

- macOS, Windows and Linux: no OS-specific code is added; tests use `pathlib` and `encoding="utf-8"`.
- Existing `cam-docs/docs/boards/*.excalidraw` files are never touched, moved or deleted by any code path.
- Kept: the Pipeline's "Board" mode (`src/board.js`, `board.test.js`, `Board` in `Pipeline.jsx`, `#native .board` CSS).
- User-facing strings removed in both `en` and `es`; nothing new is added that would need translating.
- `VERSIONS["kit"]` `4.48.0` → `4.49.0`, README badge to match.
- The branch lands as one commit: `feat(portal): remove Excalidraw boards; existing board files are kept` (Task 4).

## Review Focus

1. A project that already has `docs/boards/*.excalidraw`: the portal serves, `check` says nothing about it, the file is
   byte-identical afterwards — Task 1 test `test_old_board_files_are_left_alone`.
2. A bookmarked `#/boards/<name>` lands on the Architecture zone, not a blank page — Task 2 (`app.js` redirect test).
3. ⌘K palette offers no Boards entry — Task 2 (`zones.test.js` palette assertion).
4. The Pipeline kanban still renders after the Excalidraw dependency is gone — Task 2 keeps `board.test.js` green and
   builds the bundle.
5. The rebuilt bundle has no Excalidraw chunk or `excalidraw/` folder, and the static export does not reference one —
   Task 2 step "check the build".

---

### Task 1: Server — drop the boards API and module

**Files:**
- Delete: `.camarones/lib/boards.py`, `tests/test_board_layout.py`
- Modify: `.camarones/lib/serve.py` (GET `boards`, `board`, `sketch` ≈ lines 638–646; POST `/api/board` ≈ 752–754)
- Rename + modify: `tests/test_boards_review.py` → `tests/test_ask_review.py`
- Modify: `tests/test_portal_smoke.py` (fixture line `boards.save(...)`, `CALLS` entries `boards`, `board?name=ideas`, `sketch?…`)
- Create: `tests/test_boards_removed.py`

**Interfaces:**
- Consumes: fixtures `kit` (`kit.root`, `kit.serve.Handler`) from `tests/conftest.py`.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the failing test** `tests/test_boards_removed.py` (module docstring: boards removed in 4.49; old
  files stay). Fixture `portal(kit)` serves `kit.serve.Handler` on `ThreadingHTTPServer(("127.0.0.1", 0), …)` like
  `test_boards_review.py` does. Tests:

```python
def test_board_routes_are_gone(portal):
    for path in ("boards", "board?name=ideas", "sketch?view=index"):
        assert status(f"{portal}/api/{path}") == 404
    assert post_status(f"{portal}/api/board", {"name": "x", "scene": {"type": "excalidraw", "elements": []}}) == 404

def test_old_board_files_are_left_alone(kit, portal):
    old = kit.root / "docs" / "boards" / "team-map.excalidraw"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b'{"type": "excalidraw", "elements": []}\n')
    before = old.read_bytes()
    assert status(f"{portal}/api/tree") == 200
    assert "boards" not in json.dumps(get(f"{portal}/api/check"))
    assert old.read_bytes() == before
```

  `status`/`post_status` return the HTTP code (catch `urllib.error.HTTPError` → `e.code`); POST sends the
  `X-Camarones: 1` header as the other portal tests do.

- [ ] **Step 2: Run it to see it fail**

  Run: `uv run pytest tests/test_boards_removed.py -v`
  Expected: `test_board_routes_are_gone` FAILS (routes answer 200); the other may pass already.

- [ ] **Step 3: Remove the code and the board tests**
  - Delete the three GET branches and the `POST /api/board` branch in `serve.py`; delete `lib/boards.py`.
  - `git mv tests/test_boards_review.py tests/test_ask_review.py`; delete `test_a_board_round_trips_through_the_api`,
    `test_bad_boards_are_refused`, `test_a_c4_view_becomes_a_sketch`, the `C4` constant and the three fixture lines
    that write `model.c4`; docstring starts at "Ask the docs" (drop "whiteboards").
  - Delete `tests/test_board_layout.py`.
  - `test_portal_smoke.py`: `from lib import ci` (no `boards`), drop the `boards.save` line and the three `CALLS` rows.

- [ ] **Step 4: Run the suite**

  Run: `uv run pytest`
  Expected: all pass; `grep -rn "boards" .camarones/lib tests` shows only `test_boards_removed.py`.

- [ ] **Step 5: Commit**

```bash
git add -A .camarones/lib tests
git commit -m "feat(serve): drop the boards API; old board files are left alone"
```

### Task 2: Portal — remove the Boards view and Excalidraw

**Files:**
- Delete: `.camarones/portal/app/src/Boards.jsx`, `BoardCanvas.jsx`, `boardName.js`, `boardName.test.js`,
  `src/stubs/mermaid-to-excalidraw.js` (and `src/stubs/` if empty), `public/excalidraw/`
- Modify (`.camarones/portal/app/`): `src/zones.js`, `src/zones.test.js`, `src/Native.jsx`, `src/main.jsx`,
  `src/i18n.js`, `src/styles.css`, `public/legacy/app.js`, `public/legacy/core.js`, `index.html` (comment),
  `vite.config.js`, `package.json`, `package-lock.json`
- Modify: `tests/test_portal_app.py`
- Regenerate: `.camarones/portal/app-build/`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `zones.js` exports unchanged (`ZONES`, `TALLER`, `zonesFor`, `crumbs`, `paletteEntries`, `homeKpis`).

- [ ] **Step 1: Write the failing tests**
  - `zones.test.js`, test "live: every zone…": Architecture views `toEqual(['c4', 'data', 'libs'])`; add
    `expect(paletteEntries('live', idx).map((e) => e.href)).not.toContain('#/boards')`.
  - `zones.test.js`, the crumbs test: `expect(crumbs('#/boards/team-map', 'live', idx)).toEqual([])`.
  - `test_portal_app.py::test_the_react_views_are_reached_through_zones`: drop `"#/boards"` from the href loop; add
    `assert "'#/boards'" not in zones` and
    `assert "if (view === 'boards') return location.replace('#/arch');" in app`; docstring line 2 drops "Boards".

- [ ] **Step 2: Run them to see them fail**

  Run: `cd .camarones/portal/app && npm ci && npm test` → the two zones tests FAIL.
  Run: `uv run pytest tests/test_portal_app.py -v` → the zones test FAILS.

- [ ] **Step 3: Remove the view**
  - `zones.js`: drop the `boards` view from `arch` and `boards` from `ROUTES`; header comment unchanged.
  - `app.js` `routeNow()`: drop `'boards'` from the native-view list; first line inside the `try`, add
    `if (view === 'boards') return location.replace('#/arch');` (comment: `// boards were removed in 4.49`).
  - `core.js` (en and es): drop `boards:`, `'view.boards'`, `'viewd.boards'`; `zoned.arch` becomes
    `'C4 model, code, data and libraries'` / `'Modelo C4, código, datos y librerías'` (match the existing es wording
    for the other three).
  - `Native.jsx`: drop the `Boards` lazy import and map entry. `main.jsx`: drop the `wide` toggle line, and the
    `.wide` CSS rule if nothing else sets it (`grep -rn "wide" src public/legacy`).
  - `i18n.js`: drop `boardsTitle`, `boardsLead`, `newBoard`, `blank`, `fromView`, `allBoards`, `noBoards`, and any of
    `name`, `open`, `save`, `saved`, `readOnly`, `loading` that no other `src/` file uses (grep `t('<key>')` first).
  - `styles.css`: drop the `/* Boards */` block (`.boards-bar`, `.boards-stage`, `.boards-list`); comment line 1 drops
    "Boards". Keep `#native .board`.
  - `index.html` comment drops "Boards".
  - `vite.config.js`: drop `offlineExcalidraw`, its comment, the `resolve.alias`, and the `fileURLToPath` import.
  - `npm uninstall @excalidraw/excalidraw` (updates `package.json` and the lock); `git rm -r public/excalidraw`.
  - Delete the React files listed above.

- [ ] **Step 4: Run tests and build**

  Run: `npm test && npm run build` (in `.camarones/portal/app`) → all pass, build succeeds.
  Run: `uv run pytest tests/test_portal_app.py tests/test_portal_smoke.py -v` → PASS.

- [ ] **Step 5: Check the build**

  Run: `ls ../app-build ../app-build/assets | grep -i -E "excalidraw|Board"` → no output.
  Run: `grep -rli excalidraw ../app-build` → no output.

- [ ] **Step 6: Commit**

```bash
git add -A .camarones/portal tests/test_portal_app.py
git commit -m "feat(portal): remove the Boards view and the Excalidraw dependency"
```

### Task 3: User docs and version

**Files:**
- Modify: `README.md` (badge line 11; delete the **Pizarras** bullet ≈ line 476), `AGENTS.md` (repo map, portal row:
  "Pipeline, Boards, Ask" → "Pipeline, Ask"), `.camarones/lib/common.py` (`"kit": "4.49.0"`),
  `.camarones/lib/tutorial.py` (es ≈ line 201: "… Librerías con las vulnerabilidades en rojo)"; en ≈ line 530:
  "… vulnerabilities in red)"), `.camarones/TUTORIAL.md` (regenerated),
  `.camarones/templates/docs/guides/tutorial.md` (drop the `**Boards** (…)` item ≈ lines 170–171),
  `.camarones/templates/docs/i18n/es/guides/tutorial.md` (drop the `**Pizarras** (…)` item ≈ lines 180–181)

**Interfaces:** none.

- [ ] **Step 1: Edit the files above.** Keep the surrounding lists grammatical (commas, "and"/"y").

- [ ] **Step 2: Regenerate the tutorial** (from `.camarones/`)

  Run: `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 3: Verify no mention is left**

  Run: `grep -rn -i -E "excalidraw|pizarra|\bboards?\b" README.md AGENTS.md .camarones --include=*.md --include=*.py --include=*.js --include=*.jsx --include=*.json --include=*.css --include=*.html | grep -v -E "node_modules|app-build|package-lock|board\.js|board\.test|Pipeline\.jsx|#native \.board|boards were removed"`
  Expected: no output.
  Run: `uv run pytest tests/test_wizard.py -v` → PASS (TUTORIAL.md matches `tutorial.py`).

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md .camarones/lib/common.py .camarones/lib/tutorial.py .camarones/TUTORIAL.md .camarones/templates/docs
git commit -m "docs: boards removed from README and tutorial; kit 4.49.0"
```

### Task 4: Full verification and one commit

- [ ] **Step 1: Whole suite**

  Run: `uv run pytest` → all pass. Run: `cd .camarones/portal/app && npm test` → pass.
  Run: `cd .camarones/desktop && node --test` → pass.

- [ ] **Step 2: Sandbox end to end**

  Run: `uv run scripts/sandbox.py cli up` in the background; when it prints its URL, `curl -s -o /dev/null -w "%{http_code}" <url>/api/boards`
  → `404`, and `<url>/` loads; stop the server. If the sandbox is missing, `reset` creates it (clones from GitHub):
  say so in the report.

- [ ] **Step 3: Squash the implementation into one commit** (spec and plan commits stay as they are)

```bash
git reset --soft "$(git log --format=%H -1 -- docs/superpowers/plans/2026-10-25-remove-boards.md)"
git commit -m "feat(portal): remove Excalidraw boards; existing board files are kept

Boards were Excalidraw scenes nothing else read; diagrams that stay true live in
Mermaid and LikeC4. Removes lib/boards.py, the boards/board/sketch API, the Boards
view and the @excalidraw/excalidraw dependency. Existing docs/boards/*.excalidraw
files are never touched; #/boards addresses redirect to the Architecture zone.

Projects keep their copy of the tutorial guide (templates are copied once).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Report** the suite output and the sandbox result; the branch is not merged or pushed until the user says
  so (the main checkout's `common.py` has another session's uncommitted edits: expect a `VERSIONS` conflict).
