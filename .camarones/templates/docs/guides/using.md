---
type: guide
title: Using Camarón
description: How to use Camarón day to day — install, the first run, joining a team, documenting unit by unit, reviewing, sharing, the board, health, keeping the docs current and starting over — first in the desktop app, then the command that does the same.
tags: [onboarding, workflow]
x-owner: human
---
# Using Camarón

> **TL;DR:** Install the kit, run `camaron app`, pick the folder with your repos. A first pass needs no AI. Then let
> your agent document one unit at a time (or several at once), review in the portal what it wrote, confirm what is
> right and share with the team. When the code changes, the kit tells you which pages fell behind.

## The idea in one minute

Camarón is a **project brain**: one versioned place, `cam-docs/`, where the code, the architecture, the domain and the
decisions of a multi-repo project are explained for people and for AI agents.

1. **Installing already gives value, without AI.** The kit detects your repos and writes, from static analysis, the
   project's home page, a page per repo (endpoints, data, states, messages, env vars), the libraries and their known
   vulnerabilities, a first C4 draft and the plan.
2. **Then the AI completes it**, one **unit** of work per session: discovery of each repo, interviews, architecture,
   domain, data, flows, decisions, translations.
3. **Everything the AI writes stays reviewable**: a draft until a person confirms it, with the code it comes from
   (`x-sources`), and suspect as soon as that code changes.

Three ways in, the same commands underneath: the **desktop app** (`camaron app`) to operate, the **portal** to read
and review, and the **terminal** (`camaron`, the wizard, or any command) for everything, scripts and CI included.

<!-- tour:app -->

## First run

**Requirements:** git and Node.js 22 or newer; `uv` (the launcher installs it); Claude Code or Codex signed in for the
AI sessions (OpenCode and Gemini CLI work too). Docker is optional.

**Install the kit once per machine** — one line, no clone:

```sh
curl -fsSL https://raw.githubusercontent.com/iandelu/camarones-documenter/main/install-global.sh | sh
```

On Windows, the PowerShell line in the README does the same. The `camaron` command lands on your PATH.

**Open the app** in the folder that holds your repos, or anywhere:

```sh
camaron app
```

The first time it downloads Electron (about 100 MB) into `~/.camarones/desktop`. **Pick a folder**, check what it
found, **Continue**, and follow the first-run wizard: repos, tools, install, stack, a first architecture draft, ready.
It lands on the **Summary** with the next step. Prefer the terminal? `camaron` in that folder opens the same steps in
the wizard; you can switch between them halfway.

<!-- go:summary -->

## Joining your team

When your team already has a `cam-docs` repo: in the app's start screen, **Join my team's documentation** and paste
its URL (the docs repo, not the code's). From a terminal: `camaron join <url>`. The kit clones it, or reuses the copy you
already have, and only prepares your machine — the team already chose the repos, the stack, the architecture and the
plan, and the sessions go on where they were.

What came with the team's repo and runs code or steers agents (hooks, MCP servers, settings, skills, plugins) waits
until you approve it on your machine: **Team › What came with the team's repo**, or `camaron trust`.

<!-- go:team -->

## A normal day

1. **See the next step** — the app's **Summary**, or `camaron plan next`.
2. **Do a unit with your agent** — **Start with Claude Code** (or Codex) opens it as a terminal on the Plan's canvas,
   on that unit only, where you type to the agent. Close it whenever you like: the unit pauses and **Continue** picks
   the conversation up.
3. **Or do several at once** — **Plan › Run the ready ones** (`camaron run --parallel 2`): each unit in its own copy of
   `cam-docs`, merged when it ends. **Autopilot** (`camaron autopilot`) goes one by one, unattended.
4. **Read and review** what it wrote — **View portal**, then Review.
5. **Share** — **Team › Share now** or `camaron share`.

Each unit ends with a local commit in `cam-docs` and a handoff note, so the next session — yours or a colleague's —
knows what was checked, what was not and what comes next.

<!-- go:plan -->
<!-- tour:plan -->

## Reviewing and confirming

AI drafts are useful but unverified. In the portal:

- **Review** lists what waits for a person: drafts, pages to reconfirm, reviews an agent is waiting for. Tick several
  and **Confirm the n**.
- On a page, **Confirm as correct** signs it with your name: agents treat it as the truth from then on.
- **Request a change** leaves a comment for the next AI session (or creates a board item with the page linked).
- **Edit** changes it yourself; a confirmed page you edit needs re-confirmation.

From a terminal: `camaron confirm <page> --by <name>`, `camaron feedback <page> "<what is wrong>" --by <name>`,
`camaron status`.

<!-- portal:#/review -->

## Sharing with the team

`cam-docs` is a normal git repo. By default checkpoints stay local and publishing is a step you take: **Team › Share
now**, **Plan › Sync** in the portal, or `camaron share` — a checkpoint, the team's work rebased in, yours pushed. **Share
every time progress is saved** (`camaron share --auto on`) does it after every checkpoint, on this machine only. A
conflict is undone and nothing is touched; something that looks like a secret is never pushed.

No team repo yet? Paste its URL in **Team › The team's repo** (`camaron remote <url>`); your first share publishes it.

## The board and stories

The board lives in `cam-docs/backlog/`, next to the docs, and Backlog.md can read it. Turn it on with **Board › Turn
the board on** (`camaron board init`).

- **Write a story** in the portal's **Stories**: *As / I want / so that*, the files and pages it touches, an INVEST
  verdict, and subtasks in **waves** that never touch the same files. Nothing is saved until you approve.
- **Move cards** in the app's Board or the portal's. Moving into In Progress checks dependencies and collisions first.
- **What can start now** for an agent or a person: `camaron board next --n 3`; the open work in waves:
  `camaron board waves`.

<!-- go:board -->
<!-- portal:#/stories -->

## Health, libraries and vulnerabilities

**Quality** in the app is the project's health without AI — machine, docs and code — with a verdict, a state per area
and a row per repo (SonarQube gate, coverage, vulnerabilities, debt). **Check everything** refreshes it
(`camaron health --refresh`). A missing tool has its **Install** button there.

**Libraries** lists every dependency by repo. **Scan for vulnerabilities** checks them against OSV's offline database
(`camaron inventory --cves`; nothing leaves your machine). A flagged library's **Update** proposes the version that
fixes it and makes a branch in that repo (`camaron bump`), without committing or pushing; in a Maven module it changes
the parent pom of the same repo, where the version is set.

SonarQube: save a token in **Machine › Tokens** and the health check reads each repo's gate, coverage and issues.

<!-- go:quality -->
<!-- go:libs -->

## Keeping the docs current

When the code moves, the docs follow:

- `camaron changes` lists what changed in the repos since the docs were written; **Plan › Keep it current** opens a
  session that updates the affected pages.
- **Quality › Outdated pages** (`camaron fresh`) lists pages whose cited code changed or disappeared; **Still holds**
  acknowledges one, **Add a unit that refreshes them** queues the work.
- In CI, `camaron ci` writes a job per service repo that comments on each pull request which pages it leaves out of
  date, without AI; `camaron pr propose <url>` lets an agent propose the doc changes in a PR of `cam-docs`.
- `camaron check` is the gate: broken links, diagrams that do not render, secrets, structure.

## Costs and KPIs

- **Plan › Plan from zero** (`camaron plan cost`): tokens, hours and API-equivalent dollars the plan took, for the
  whole team, by phase and by unit.
- The portal's **Quality › KPIs** (`camaron kpis`): confirmed share, pages out of date, searches with no answer, AI
  cost by month, and the questions nobody found — one click turns each into an open question for the next interview.
- **Golden questions** (`camaron eval`): questions the docs must answer, approved by a person, asked to an agent that
  can only read the docs. **With and without cam-docs** (`camaron ab`) asks the same question twice to show what the
  docs save.

<!-- portal:#/kpis -->

## Starting over and uninstalling

- **Docs written by an older kit:** **Plan › Start the docs again** — **Redo** reopens every finished unit for review
  (nothing deleted); **Wipe and start over** tags `cam-docs` in git, deletes what was generated and restarts the plan,
  keeping interviews, confirmed pages and the board (`camaron docs reset --redo | --wipe`).
- **Uninstall a project:** **Machine › Uninstall this project** — **See what it would remove** first. It stops the
  portal, zips `cam-docs` into the system's temporary folder, removes what the kit added to each repo and the workspace
  folder, and deletes `cam-docs`. The repos end exactly as in their last commit (`camaron uninstall`).
- **Update the kit:** **Machine › Update the kit** (`camaron self-update`) updates every project on this machine at
  once and restarts the app.

<!-- go:machine -->

## When something fails

| Symptom | First thing to try |
|---|---|
| A tool is missing or the wrong version | **Quality › Requirements and tools**, or `camaron doctor` |
| A kit file or link was edited or deleted | **Machine › Repair the kit's files**, or `camaron repair` |
| A private repo will not clone | Save a token in **Machine › Tokens** and **Clone or pull the repos** |
| An agent session left a unit half done | **Plan**, open the unit, **Continue** (or **Start over**) |
| A run's unit is blocked after merging | Its `integrate:<unit>` unit resolves it; or **Retry** |
| The portal will not show a button you expect | It runs nothing on your machine: do it in the app |

The [app guide](app.md#when-something-fails) has the app's own messages.
