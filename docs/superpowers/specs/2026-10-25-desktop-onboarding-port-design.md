# Desktop onboarding, ported onto the new desktop app — design addendum

Addendum to `2026-10-25-desktop-onboarding-design.md` (the original spec). The onboarding was built on branch
`worktree-onboarding` (d2c94ca..248be9b) while `main` replaced the desktop UI. This addendum says what changes so the
work lands on `main` (d190ca7, kit 4.57.0). The original spec stays binding for everything this addendum does not
replace.

## 1. What `main` changed

- The Electron hub (`desktop/hub/`) is gone. The hub is now the **hub mode** of the React app in
  `desktop/renderer` (`App.jsx` → `Hub`), loaded from disk with `window.camaronHub`. It still offers the old
  create / join / add buttons.
- Project windows load the same React app from their server at `/desktop/` (`window.camaronApp`). The app has a
  project rail and sections: Summary (one next step, `plan.next_step`), Plan, Interviews, Team, Quality, Docs,
  Machine and Kit dev. `@camaron/ui` (`.camarones/ui`) holds the shared components and tokens.
- The portal's Taller, its panels and the legacy router's app mode are gone. The portal is the reader. But inside
  a project window it still opens **in the window**: `../#/…` links are same-origin, so the main process's guard
  lets them through.
- The kit is at 4.57.0. `quickarch.save` takes `page=`. `/api/pipeline` units carry `ready`. The test suite runs in
  parallel (`pytest -n auto`, per-process template, `@pytest.mark.serial`).

## 2. What is kept from the branch, unchanged in intent

The original spec's §3 (folder detection), §4 (steps and shared state) and §7 (errors), as built and reviewed in the
branch's Python work:

- `lib/onboard.py`
- `projects --inspect/--adopt`
- the `taken` code
- `join --no-open` with `CAMARONES_JOIN_TOKEN` and its JSON reasons
- `/api/app/onboard/*` with cooperative cancel
- the CLI wizard sharing `onboard.*`

They are ported onto `main`, resolving conflicts with main's own changes: the `pages` layout, `quickarch.save(page=)`,
`plan.title`, `MENU_DEFAULT` and the parallel tests.

## 3. What replaces the original spec's §5 (hub) and §6 (project window)

**Start screen = the renderer's hub mode.** The copy and flow are the approved sketches A and B: "¿Qué quieres
documentar?" · Elegir carpeta · Unirme a la documentación de mi equipo · Recientes, then the "what I found" card.
`Hub` in `App.jsx` is replaced by it.

- The main process's hub IPC becomes `hub:pick`, `hub:inspect`, `hub:adopt`, `hub:join({url, token?})` and
  `hub:gitInit`. `hub:new` and `hub:add` go. The CLI keeps `new` and `projects --add`.

**First-run wizard = a renderer section `#/start`.**

- Same steps and copy as sketch C. It is driven by `/api/app/onboard/*` through the renderer's `server()` and
  `useJob`, and reuses Machine's token form for missing repos.
- While `state.done` is false the project window opens on `#/start`. The wizard is full width, with no section nav.
- When it finishes, the window lands on **Summary**. Main's Summary *is* the "next step" home, so the branch's
  portal Next view and app nav are dropped.

**Reading happens in the browser.**

- In a project window, any same-origin address outside `/desktop/` (the portal: `../#/…`, Docs, review links,
  `next.read`) opens in the system browser through `shell.openExternal`, and the window stays. One rule in the main
  process's guard: `renderer.cjs` decides it and `node --test` covers it.
- The header gets a **Ver portal** button (`app.openExternal(origin + '/#/')`).
- The portal in the browser has no token. The machine work it used to offer in the window now has a place in the
  app (see I3).

## 4. Findings from the branch's final review, now part of the design

- **I1 — code folder without git.**
  - `inspect` keeps `case: code`. The found card does not offer Continue. It explains (es/en) that the code is
    not in a git repository and offers **"Inicializar git aquí"**.
  - That action runs `git init` (after the person clicks it) in each folder that holds a manifest: the picked folder
    itself when it has one at its top, else each first-level subfolder with one. It then inspects again, so the
    case becomes `repo` or `umbrella`. "Cambiar carpeta" stays.
  - New CLI: `projects --git-init DIR --json` → `{"initialised": [paths]}`. It never runs on its own.
  - `onboard.start` refuses a `code` case with `ValueError` / `{"error":"no-git"}`.
- **I2 — home or a filesystem root as the workspace.**
  - `inspect` adds `warning: "home"` when the workspace it resolves is `Path.home()` or a filesystem root (a path
    equal to its anchor).
  - `onboard.start` refuses it with `{"error":"home"}`. The card explains it and offers only "Cambiar carpeta", in
    es/en.
  - This covers picking `~`, a repo directly under `~`, or `C:\` / `/`.
- **I3 — C4 explorer and wiki graph builds.**
  - The app's Docs section gets "Construir el explorador C4" and, per repo with a wiki, "Construir el grafo de la
    wiki". These are jobs through the existing token-gated `POST /api/build` (`what: c4 | wiki-graph`).
  - Each has a "Ver" button that opens the result in the browser.
- **Must-fix minors.**
  - The arch step's no-agent warning no longer promises a picker that is disabled. The copy says to improve it later
    from the Plan.
  - The branch's FirstLook card does not come over, because the Summary replaces the Next view.
- **Small fixes ported along.**
  - A picked folder named `cam-docs` maps to its parent.
  - Repo names reject `:` and Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`).
  - `wizard.retry_missing` uses `onboard.missing_repos()`.
  - The unused `ws_rel` import goes.

## 5. Docs, version, verification

- README, the tutorial (es/en) and the guide templates describe main's new app sections plus this flow.
- The kit version is the next minor above main's at merge time (4.58.0 against 4.57.0).
- End to end on the sandbox: CLI, the HTTP onboarding flow with a token, and the browser portal. Then a person's
  pass in the Electron window, with the list from the branch's Task 10 report adapted to the renderer.
