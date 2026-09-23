---
type: guide
title: Tutorial — Camarones Documenter, the project docs wizard
description: How to install Camarones Documenter on macOS or Windows, run the guided documentation sessions with Claude Code or Codex, confirm AI drafts, run the portal and wire CI.
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

**New project from the zip:** put `camarones-documenter.zip` in the folder where the project's repos live, extract it there and
open the launcher. If extraction created a `camarones-documenter/` subfolder, the wizard offers to move itself one level up.
Repos already in the folder are detected; you can add more by URL.

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

Every page starts as **🤖 draft** (banner in the portal). **✅ Review & confirm pages** in the wizard lets you tick the
pages you checked; the confirmation is locked to the content — if anyone edits the page later it becomes
**⚠️ needs re-confirmation**. Agents treat confirmed pages as the source of truth. To protect a paragraph from agents:

```markdown
<!-- human -->
Only humans edit this paragraph.
<!-- /human -->
```

## 4. After the first pass

**🔄 Update docs after changes** runs an incremental session: only what changed in the code is regenerated, stale pages
are cleaned up, confirmed pages are never silently rewritten. CI can run the same thing automatically (section 6).

## 5. Portal

Wizard → **🌐 Portal** → build / run with Docker / open. It serves: docs in EN/ES, the interactive C4 explorer
(`/architecture/`), the code graph (`/code-graph/`), per-repo wiki graphs (`/wiki-graph/<repo>/`) and `/llms.txt`.
It is plain nginx with static files and works without internet. On a server:
`DOCS_IMAGE=<registry>/<group>/<umbrella>/portal:latest docker compose -f .camarones/portal/compose.yml up -d --no-build`.

## 6. CI

Wizard → **⚙️ CI** installs the umbrella pipeline (GitLab or GitHub). Per-repo snippets: `.camarones/ci/repo.*`.
Variables: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, a bot token to open MRs/PRs; on GitLab allow the umbrella project's
job token to clone each service repo (repo → Settings → CI/CD → Job token permissions).

## 7. Commands (for scripts and agents)

`./camarones.command help` (Windows: `camarones.cmd help`): `setup`, `sync`, `detect`, `plan`, `plan next`, `status`, `check`,
`confirm`, `graph`, `arch` (live C4 editor), `arch-validate`, `portal`, `up`, `down`, `ci`, `prompt <unit>`, `doctor`.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| macOS blocks `camarones.command` ("cannot be opened" / "Apple could not verify…") | open Terminal in the folder and run `sh camarones.command` (once: the launcher clears the quarantine flag, then double-click works). Or: System Settings → Privacy & Security → "Open Anyway" |
| Windows: SmartScreen warning | "More info" → "Run anyway" |
| Windows blocks the file or the antivirus removes it | before extracting: right-click the zip → Properties → tick **Unblock** → OK. Already extracted: in PowerShell inside the folder `Get-ChildItem -Recurse | Unblock-File`. Company PC that forbids `.cmd`: `winget install astral-sh.uv`, then `uv run --script .camarones\camarones.py` |
| Something installed but not detected | close and reopen the wizard (PATH refresh) |
| `doctor` shows a tool missing | wizard → 🛠 Install / repair |
| Repo "skip … local changes" on sync | commit or stash in that repo, sync again |
| C4 errors | `camarones arch-validate` shows file + line |
| OpenWiki tools missing in the agent | restart Claude Code / Codex inside the project folder |
