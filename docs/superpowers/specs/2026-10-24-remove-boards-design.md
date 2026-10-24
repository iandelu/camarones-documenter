# Remove the Excalidraw boards — design

Part 1 of 3 of "simpler start, Mermaid diagrams, less noise" (2: diagrams generated without AI, improved by AI and
reviewed by a person, plus Mermaid in the doc skills; 3: a shorter, simpler first run and plan).

## Why

Boards (R34, H24) are free-form Excalidraw scenes in `cam-docs/docs/boards/`. Nothing else in the kit reads them: no
agent, no `check`, no search, no MCP tool. They pull the heaviest dependency in the portal (`@excalidraw/excalidraw`
with its locales and fonts) and a C4-to-sketch layout engine, for a picture that drifts from the model the moment it is
saved. Diagrams that stay true belong in Markdown (Mermaid) and LikeC4, where agents and `check` can read them — that
is part 2.

## Scope

Removed:

| Area | What goes |
|---|---|
| Python | `lib/boards.py`; the `boards`, `board`, `sketch` GET routes and `POST /api/board` in `lib/serve.py` |
| Portal (React) | `Boards.jsx`, `BoardCanvas.jsx`, `boardName.js` + `boardName.test.js`, `stubs/mermaid-to-excalidraw.js`; the `boards` entry in `Native.jsx`, `zones.js`, `main.jsx` (`wide` class); `boards*` strings in `i18n.js`; `.boards-*` rules in `styles.css` |
| Portal (legacy) | `boards` in the native-view list of `public/legacy/app.js`; `boards`, `view.boards`, `viewd.boards` strings and "boards" in `zoned.arch` in `core.js` |
| Build | `@excalidraw/excalidraw` in `package.json` (+ lock), the `offlineExcalidraw` plugin and the alias in `vite.config.js`, `public/excalidraw/`; `app-build/` rebuilt |
| Tests | the board tests in `test_boards_review.py` (file renamed `test_ask_review.py`, its C4 fixture dropped), `test_board_layout.py`, the board lines in `test_portal_smoke.py` and `test_portal_app.py` |
| Docs | Boards in `README.md`, `lib/tutorial.py` (+ regenerated `TUTORIAL.md`), both tutorial templates, `AGENTS.md` repo map |

Kept: the Pipeline's "Board" mode (kanban of plan units: `board.js`, `Board` in `Pipeline.jsx`). Same word, different
feature.

## Backward compatibility (AGENTS.md 2.3)

- Existing `cam-docs/docs/boards/*.excalidraw` files are **never touched**: people made them; they stay in git and open
  in excalidraw.com. No migration deletes or moves them. Nothing in the kit reads them, so nothing breaks.
- A bookmarked `#/boards` or `#/boards/<name>` falls back like any unknown portal route (no blank page, no error).
- `/api/boards`, `/api/board`, `/api/sketch` answer 404 like any unknown route. No CLI command, flag, workspace key or
  frontmatter field changes.
- Projects keep their copy of the tutorial (templates are copied once); the commit body says so.
- `VERSIONS["kit"]` minor bump and the README badge.

## Tests first

1. `test_portal_app.py`: the Architecture zone links no `#/boards`.
2. `zones.test.js`: Architecture views are `['c4', 'data', 'libs']`; `crumbs('#/boards/x')` does not throw and returns
   no boards crumb.
3. New Python test: `/api/boards` and `/api/sketch` → 404; a workspace with `docs/boards/old.excalidraw` still serves
   the portal and `check` passes without mentioning it; the file is unchanged afterwards.
4. Then delete the code and the board tests; the suite (`uv run pytest`, `npm test`, `node --test` in desktop) is
   green on the three OSes, and CI's app-build check matches the rebuilt bundle.

## Done when

- No `excalidraw`/`boards` reference left outside history, research notes and the Pipeline kanban.
- Suite green; sandbox: `uv run scripts/sandbox.py cli up` serves the portal with no Boards entry.
- One conventional commit: `feat(portal)!`-free — `refactor(portal): drop Excalidraw boards` is wrong because users
  notice it; use `feat(portal): remove Excalidraw boards; existing board files are kept`.
