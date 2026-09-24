---
type: guide
title: Tutorial — Camarones Documenter, the project docs wizard
description: How to install Camarones Documenter on macOS or Windows, run the guided documentation sessions with Claude Code or Codex, confirm AI drafts, use the portal (read, edit, review), generate the OpenWiki wikis and wire CI.
tags: [onboarding, tooling]
x-owner: human
---
# Tutorial — Camarones Documenter 🦐

*Camarón que se duerme, se lo lleva la corriente.* Camarones Documenter documents a whole project (all its repos) in short AI
sessions, saves progress after each one and always tells you what comes next.

## 1. Install (once per computer)

Requirements: **git** and **Node.js ≥ 22**; Java only for JVM repos (SDKMAN, brew or winget installs are detected) (the wizard offers to install them with Homebrew / winget),
**Docker Desktop** only to serve the portal, and **Claude Code** and/or **Codex** for the AI sessions.
Python is *not* required: the launcher installs `uv`, which brings its own Python.

| | Open the wizard |
|---|---|
| macOS | double-click `camarones.command` (if macOS blocks it the first time: Terminal in the folder → `sh camarones.command`) — or `./camarones.command` |
| Windows | double-click `camarones.cmd` — or `camarones.cmd` in a terminal |
| Linux / CI | `./camarones.command` (it is a plain shell script) |

**Global install (several projects):** `sh install-global.sh` (Windows: `install-global.cmd`) from the kit repo leaves a
`camarones` command on your PATH; run `camarones` in the folder that groups the repos and it creates `./cam-docs/`.

**New project from the zip:** put `camarones-documenter.zip` in the folder where the project's repos live, extract it there and
open the launcher. If extraction created a `camarones-documenter/` subfolder, the wizard offers to move itself one level up.
Repos already in the folder are detected; you can add more by URL.

Everything the kit writes lives in **`cam-docs/`**, next to the repos: its own git repo with `docs/`, `wikis/<repo>/`, the
tool configuration (`.camarones/`) and the agents' setup (`.claude/`, `.codex/`, `.agents/`, `.mcp.json`). Service repos
get no kit files; paths below are relative to `cam-docs/`.

## 2. The guided flow

The first run walks you through: workspace (project name) → repos → tools (install everything — recommended — or pick
what to install) → setup (repos, Claude/Codex wiring, git hooks) → how sessions work. Esc always goes one step back; long
tasks show what they are doing, a progress bar and crustacean facts. After that the main menu shows the plan progress and the next step.

**🦐 Next step** lists the plan units that are ready (their dependencies are done). Pick one and choose Claude Code, Codex
or "copy prompt". The agent opens with instructions to do *only that unit*, deeply, then:
- marks it done in `docs/.work/plan.yaml`,
- writes what it did and what is pending in `docs/.work/handoff.md`,
- asks you what to do next.

Close the agent and come back to the wizard for the next unit (a fresh session = a fresh context window). The plan:

| Phase | Units |
|---|---|
| 0 | setup |
| 1 | discovery of each repo → cross-repo correlation |
| 2 | 3 short interviews: context/actors/environments · glossary/SLAs · decisions/debt/validation |
| 3 | per repo: README + AGENTS.md/CLAUDE.md + C4 components (brief) · OpenWiki (wiki) |
| 4 | C4 system · domain · data · deployment · ADRs & quality |
| 5 | flows catalog → one unit per business flow |
| 6 | Spanish translations |
| 7 | portal · CI · human confirmation · handover |

Big unit? The agent splits it and adds the remainder to the plan. Everything survives between sessions and computers
(the plan is committed with the docs).

## 3. Trust: AI drafts vs confirmed

Every page starts as **🤖 draft** (banner in the portal). Confirm pages in the portal (**Confirm** on each page, the
**Review** tab lists what is pending) or with **✅ Review & confirm pages** in the wizard; the confirmation is locked to the content — if anyone edits the page later it becomes
**⚠️ needs re-confirmation**. Agents treat confirmed pages as the source of truth. To protect a paragraph from agents:

```markdown
<!-- human -->
Only humans edit this paragraph.
<!-- /human -->
```

## 4. After the first pass

**🔄 Update docs after changes** runs an incremental session: only what changed in the code is regenerated, stale pages
are cleaned up, confirmed pages are never silently rewritten. CI can run the same thing automatically (section 8).

## 5. Portal

One portal, two modes, the same interface. Tabs: **Docs** (tree, search, trust badges), **Architecture (C4)**,
**Code graph** (all repos or one), **Wikis** (OpenWiki per repo, its pages and graph) and **Review** (pending pages,
change requests, code changed since the docs, `check`). The language switch changes the interface and the docs; a page
not translated yet is shown in English with a notice.

| | Command | What it is |
|---|---|---|
| Local, editable | `camarones up` (wizard → 🌐 Portal → 📝 Open the portal) | `http://127.0.0.1:8080`, only on your machine |
| Export for deployment | `camarones portal` (wizard → 📦 Export) | read-only HTML + JSON in `.camarones/.cache/site`, no npm build |
| See the export | `camarones up --static` or `camarones up --docker` | exactly what the server will serve |

The export is plain static files (nginx image, GitLab/GitHub Pages) and works without internet. On a server, run the image
CI pushed: `docker run -d -p 8080:80 <registry>/<group>/cam-docs/portal:latest`.

## 6. Editing: where and when

| Where | What you can do | Where the change goes |
|---|---|---|
| Local portal (`camarones up`) | edit (markdown + live preview), **+ New page**, **Confirm**, **Request changes**, generate wikis, rebuild C4 / code graph | `cam-docs/docs` + a local commit if "commit to cam-docs" is ticked — you push |
| Deployed portal (export) | read and search; **Edit** opens the file in GitLab / GitHub (when `cam-docs` has a remote) | a merge request in `cam-docs`; CI publishes it again |
| Your editor / IDE | any `.md` under `cam-docs/docs` | plain git in `cam-docs` |
| The AI (🦐 Next step) | only its unit; never rewrites confirmed pages silently | a local commit per unit |

- **Confirm** signs with your `git config user.name`. **Request changes** saves the comment and adds a `review-fixes`
  unit that the AI applies in the next session.
- With Spanish selected, **Edit** edits the translation (`docs/i18n/es/…`).
- Editing a ✅ page turns it **⚠️ needs re-confirmation** until someone checks it again.
- Don't hand-edit generated files (`llms.txt`, `docs/.status.json`, the viewers). Wikis are better regenerated from the
  **Wikis** tab: an OpenWiki update can rewrite what you change.

## 7. OpenWiki: one wiki per repo

Portal → **Wikis** → **Generate / update wiki** (live log), wizard → **📚 Wikis**, or `camarones wiki <repo>`. The wiki
is stored in `cam-docs/wikis/<repo>/` (the repo sees an unversioned `openwiki/` link) and its pages show under **Docs** as
`repos/<repo>/…`. It uses the OpenWiki provider if one is configured (`openwiki auth configure <provider>`), otherwise
Claude Code or Codex. The files OpenWiki adds to the repo itself (`AGENTS.md`, `CLAUDE.md`, `.github/`) are removed when
the run ends.

Each wiki is a full agent run, so only the repos you choose get one: wizard → **📚 Wikis** → **Choose which repos get a
wiki** (stored as `wiki: true` in `.camarones/workspace.yaml`). Pick the services with logic, not libraries or CI repos.
A first wiki waits for the repo's brief (`wikis/<repo>/INSTRUCTIONS.md`, written by the repo-brief unit) so it uses your
glossary; `camarones wiki <repo> --force` skips that check. Runs go one at a time, and a batch stops as soon as the
engine is out of quota or logged out instead of failing every remaining repo.

## 8. CI

Wizard → **⚙️ CI** installs the pipeline in `cam-docs` (GitLab or GitHub): update the affected docs, `check`, export the portal and publish it. Per-repo snippets: `.camarones/ci/repo.*`.
Variables: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, a bot token to open MRs/PRs; on GitLab allow the `cam-docs` project's
job token to clone each service repo (repo → Settings → CI/CD → Job token permissions).

## 9. Commands (for scripts and agents)

`camarones help` (per-project copy: `./camarones.command help`, Windows `camarones.cmd help`): `setup`, `sync`, `detect`,
`plan`, `plan next`, `status`, `check`, `confirm`, `feedback`, `checkpoint`, `graph`, `arch` (live C4 editor), `arch-validate`,
`wiki <repo>`, `portal` (export), `up [--static|--docker]`, `down`, `ci`, `prompt <unit>`, `migrate`, `doctor`.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| macOS blocks `camarones.command` ("cannot be opened" / "Apple could not verify…") | open Terminal in the folder and run `sh camarones.command` (once: the launcher clears the quarantine flag, then double-click works). Or: System Settings → Privacy & Security → "Open Anyway" |
| Windows: SmartScreen warning | "More info" → "Run anyway" |
| Windows blocks the file or the antivirus removes it | before extracting: right-click the zip → Properties → tick **Unblock** → OK. Already extracted: in PowerShell inside the folder `Get-ChildItem -Recurse | Unblock-File`. Company PC that forbids `.cmd`: `winget install astral-sh.uv`, then `uv run --script .camarones\camarones.py` |
| Something installed but not detected | close and reopen the wizard (PATH refresh) |
| `doctor` shows a tool missing | wizard → 🛠 Install / repair |
| Repo "skip … local changes" on sync | commit or stash in that repo, sync again |
| C4 errors | `camarones arch-validate` shows file + line |
| OpenWiki tools missing in the agent | restart Claude Code / Codex in the workspace folder (the one that holds `cam-docs/`) |
| The deployed portal has no **Edit** button | `cam-docs` has no git remote: add one and export again |
| A wiki run failed | the ⚠ line says why (quota or login → wait or log in again); run `camarones wiki <repo>` again — an interrupted run resumes |
