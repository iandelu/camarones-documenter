---
type: guide
title: How Camarón works
description: Camarón from the inside — its pieces, where every file lives, the project server and its tokens, the CLI and HTTP APIs, the plan and the harness, agent routing, trust and freshness, the MCP servers and plugins.
tags: [architecture, tooling, mcp, api]
x-owner: human
---
# How Camarón works

> **TL;DR:** One Python CLI (`camaron`) does all the work. The terminal wizard, the desktop app and the portal are
> three faces of it: the app runs catalog commands through a per-project local server, the portal reads and edits
> through the same server, and agents read the docs through the `camarones` MCP server. Everything the kit writes for
> a project lives in `cam-docs/`, a git repo next to the code.

## The pieces

```text
  your repos (never get kit files)                      cam-docs/ (its own git repo)
  orders-api/  payments-api/  web/                       docs/  wikis/  backlog/  .camarones/
        |  read                                                ^  write          |  read
        v                                                      |                 v
  +------------------------------- camaron (Python CLI) ------------------------------+
  |  wizard (terminal)    catalog of commands    harness: plan, runs, routing, KPIs     |
  +-----------+--------------------+--------------------------+-----------------------+
              |                    |                          |
     project server (local)   agent runners             MCP server "camarones"
     /  portal   /desktop/    Claude Code, Codex,        search_docs, read_doc, ask,
     /api/...                 OpenCode, commands         propose_edit, board_next…
        |          |                                          |
   browser      desktop app (Electron)                 Claude Code / Codex sessions
   (portal)     one window per project                 (also inside a single repo)
```

| Piece | What it is | Where |
|---|---|---|
| CLI | `camaron <command>`, a `uv` inline script; every behaviour of the kit | `.camarones/camarones.py`, `.camarones/lib/` |
| Wizard | The terminal menus over the same commands | `camaron` (no arguments) |
| Project server | Serves the portal, the app's UI and the HTTP API for one project | `camaron up`; the app starts one per window |
| Portal | React app that reads and edits the docs | `/` of the server, or a static export |
| Desktop app | Electron windows on the project servers, plus the start screen | `camaron app`; Electron pinned in `~/.camarones/desktop` |
| Harness | The plan as data, parallel runs in worktrees, agent routing, run logs, KPIs | `lib/harness/`, `lib/pipelines/` |
| MCP servers | `camarones` (the docs, the plan, the board) and `likec4` (the architecture model) for agents | `.mcp.json`, `.codex/` |

## Where things live

**In the workspace folder** (the folder that holds the repos):

```text
my-project/
├── cam-docs/                 the project's own git repo: share it with the team
│   ├── .camarones/           workspace.yaml (repos, stack, settings), PLAYBOOK.md, CONVENTIONS.md, skeletons/,
│   │                         pipeline.yaml (your plan changes), plugins/ + plugins.lock, .cache/ (ignored)
│   ├── docs/                 the documentation; docs/i18n/es/ the Spanish translations
│   │   └── .work/            plan.yaml, handoff.md, units/ (checkpoints), kpis/, usage/, proposals/
│   ├── wikis/<repo>/         each repo's OpenWiki
│   ├── backlog/              the board: tasks/*.md (Backlog.md format) and board.yaml
│   ├── graph/<repo>/         the code graph (ignored)
│   ├── .claude/ .codex/ .agents/ .mcp.json AGENTS.md CLAUDE.md     the agents' setup
├── .claude → cam-docs/.claude   .mcp.json → …   AGENTS.md → …       links, so agents opened here see it all
├── .cw/<n>/                  a unit's own copy of cam-docs while a parallel run lasts
└── orders-api/  payments-api/  …   the service repos, untouched
```

`.camarones/.cache/` holds what can be rebuilt: run logs (`runs/<run>/events.jsonl`), the exported site (`site/`), the
board's index (`board.db`), the health snapshot and backups of replaced kit files.

**On this machine:**

| Path | Holds |
|---|---|
| `~/.camarones.json` | This machine's choices: language, Claude Code and Codex models, extra runners, routing overrides, OSV online mode |
| `~/.camarones/kit` (Windows: `%LOCALAPPDATA%\camarones-documenter\kit`) | The global install of the kit, shared by every project |
| `~/.camarones/desktop` | The pinned Electron for `camaron app` |
| `~/.camarones/bin`, `~/.camarones/osv-db` | Pinned binaries (gitleaks, OSV-Scanner) and OSV's offline database |
| `~/.camarones/trust/` | What you approved of each team's agent config — never in a repo |
| `~/.camarones/install/` | What the kit installed here (its skills, graphify's, OpenWiki's), so they need no approval |
| `~/.camarones/mcp-token` | The token of `camaron mcp --http` |
| `~/.camarones/hosts.json` | Which host is GitLab, GitHub or SonarQube, and its user (no secrets) |
| System keychain | The tokens themselves (`credentials.json` only where there is no keychain) |

## The project server

`camaron up` starts the server of the current project (port 8080 by default). It serves the portal at `/`, the desktop
app's UI at `/desktop/` and the API at `/api/`. The desktop app starts its own server per window
(`camaron up --foreground --port 0`) and stops it when the window closes.

Who may do what depends on what the request carries:

| Caller | Header or token | May |
|---|---|---|
| Any page of the live portal | `X-Camarones: 1` on writes (a browser on another site cannot send it) | Read everything; edit and create pages, commit, confirm, request changes, decide reviews, edit the C4 model, answer the interview, share, approve or retry units, file KPI misses |
| The portal with the **portal token** (`#cam-token=…` from `camaron up`, or the session token the app hands the browser) | `X-Camaron-Token` | The above, plus writing to the Board and saving or suggesting stories |
| The desktop app (**app token**, a random one per server start) | `X-Camaron-Token` | Everything, including what runs on the machine: runs, wikis, builds, scans, CI files, the AI answer, the plan's cost harvest and all of `/api/app/` |

With either token set, the server refuses requests whose `Host` is not `localhost` or `127.0.0.1` on its port (no DNS
rebinding). The app's window cannot navigate away from `/desktop/`: links to the portal and the web open in the system
browser. Tokens are never passed to the commands the server runs.

## The CLI is the API

Every feature is a `camaron` command; the wizard, the app and CI only call commands.

- `camaron catalog --json` lists every command with its zone, where it lives (portal, app, CLI), its labels in Spanish
  and English, whether it uses AI or deletes data, and its arguments as the parser defines them. `camaron catalog
  --check` fails when a command has no place.
- Most commands take `--json` and then print JSON on stdout for scripts and the app instead of text for people.
- Exit codes: `0` done, `1` refused or failed, `2` a usage error. A refusal with `--json` prints
  `{"error": "<code>", "detail": "…"}` — scripts read `error`; `detail` is for people and may be in Spanish.
- A command that changes data asks first; `--yes` answers for you, `--dry-run` shows the list without touching
  anything.

The app runs commands through `POST /api/app/cmd`: the arguments are checked against the parser (unknown ones, or values
starting with `-`, are refused), there is no shell, and a destructive command or one with `--yes` answers 409 until the
app confirms — then the server adds `--yes` itself.

<!-- cmd:check -->

## The HTTP API

The API serves the portal and the app; it is not a stable public interface (the CLI is). By group:

| Group | Endpoints |
|---|---|
| Docs | `GET tree`, `doc?path&lang`, `search?q`, `ask?q`, `status`, `reviews`, `viewers`, `wikis`, `codemap?repo`; `POST doc`, `commit`, `new`, `confirm`, `feedback`, `review/decide` |
| Architecture | `GET c4/view?id`; `POST c4/element`, `c4/confirm`, `c4/relation`, `c4/remove` |
| Board and stories | `GET kanban`, `kanban/item?id`, `kanban/waves`, `stories`, `stories/item`, `stories/files`; `POST stories/analyze`; with a token: `POST kanban/init`, `add`, `move`, `assign`, `link`, `archive`, `stories/save`, `stories/suggest` |
| Plan | `GET pipeline?lang`, `runs/<id>`, `runs/<id>/events` (server-sent events), `plan/cost`, `interview`, `sync`; `POST units/approve`, `units/retry`, `interview/answer`, `sync/share` |
| Quality | `GET health`, `kpis`, `inventory`, `schemas`, `ci`; `POST kpis/miss` |
| Machine work (app token) | `POST runs`, `runs/<id>/cancel`, `wiki`, `build`, `inventory`, `schemas`, `ci`, `ask/answer`, `plan/cost` |
| The app (app token) | `GET app/info`, `catalog`, `summary`, `machine`, `guide`, `creds`, `agents`, `doctor`, `kitdev`, `onboard/*`, `jobs/<id>/events`; `POST app/cmd`, `agent`, `creds`, `doctor`, `kitdev`, `onboard/*`, `jobs/<id>/cancel` |

Long work is a **job**: `GET jobs` lists them, `GET jobs/<id>?since=n` reads its lines from line `n`.

## The plan and the harness

The documentation of a project is too big for one agent session, so it is split into **units**. The plan
(`docs/.work/plan.yaml`) holds them with their state: to do, in progress, done, blocked, dropped, or waiting for a
person's approval.

**Unit types** (`lib/pipelines/units.yaml`): each has a phase, who does it (an agent, or a wizard step such as
`setup` or `confirm`), the section of `PLAYBOOK.md` it follows, a tier (see [routing](#agents-and-routing)) and
whether it runs in its own copy of `cam-docs` during a parallel run. In phase order: setup; discovery of each repo and
the cross-repo correlation; the questionnaire, the answers and three interviews; each repo's brief and wiki; the C4
system, domain, data, deployment, decisions and quality; the flows catalog and one unit per flow, diagrams, reviews;
the Spanish translation; the portal, CI, human confirmation and the handover.

**Pipelines** (`lib/pipelines/full.yaml`, `quick.yaml`) say which units exist and what each `needs`. `soft` needs do
not block: a repo brief can start before the interviews, as a draft, and finishing the interview reopens it to refine.
A project changes its plan in `cam-docs/.camarones/pipeline.yaml` — drop units, change what they need, add units, set
their agent or tier, or mark one `approval: true` so the units after it wait for a person — and applies it with
`camaron plan sync`. A broken file leaves the plan as it was and says where.

**A session** works on one unit: it reads `handoff.md` and the unit's checkpoints, writes its pages, saves notes
(`camaron plan note`), and closing or blocking the unit makes a local commit in `cam-docs`. An interrupted unit resumes
from its last checkpoint.

**Runs.** `camaron run` (the app's **Run the ready ones**) does several units at once. Units marked for isolation work in
`<workspace>/.cw/<n>/`, a git worktree of `cam-docs` on its own branch. When one ends, the kit brings the latest
`cam-docs` into the copy, checks that no new errors appear (`check`, `arch-validate`) and merges it. A copy that
collides with another unit's work blocks its unit, leaves `cam-docs` untouched and adds an `integrate:<unit>` unit.
Other units run one at a time, and a unit never starts before what it needs is merged. `camaron autopilot` runs units
one after another without worktrees. While either runs, the machine is kept awake, and a session cut by something
passing (sleep, network, an overloaded API) goes back to the queue once.

**What it cost.** Each run writes `.camarones/.cache/runs/<run>/events.jsonl` (`camaron runs`). Each machine adds its
share — runs, wikis written by an agent and the interactive sessions read from Claude Code's transcripts — to
`docs/.work/kpis/<person-machine>.json`, which `share` brings to the team. `camaron plan cost` and `camaron kpis` add
them up; dollars are the API equivalent (the agent's own figure, else tokens × `lib/pricing.yaml`, which `pricing:` in
`workspace.yaml` can override).

<!-- go:plan -->

## Agents and routing

Agents are launched through one adapter (`lib/adapters/runners/`): Claude Code, Codex, OpenCode (the way to local
models such as Qwen on Ollama) and command templates (Gemini CLI comes as a kit plugin; any other CLI can be declared
in `~/.camarones.json` under `runners`). The team's repo may choose agents but never define commands.

Each unit has a **tier**: `agentic-heavy` (long units such as discovery or flows), `bounded` (translating, drafting
golden questions) or `judge` (scoring). Each tier has an ordered list and the first installed agent wins;
`runner:model` also picks the model. The team sets it in `workspace.yaml`, and `~/.camarones.json` overrides it on one
machine:

```yaml
agents:
  routing:
    agentic-heavy: [claude, codex:gpt-5.6-terra]
    bounded: [opencode:ollama/qwen3-coder:30b, claude]
```

Local models never get `agentic-heavy` work. `camaron doctor --local` proposes one that fits this machine's memory.

An **interactive session** (Start, Continue in the app; the wizard's Next step) opens the agent in its own terminal
window, in the workspace, with the unit's prompt. While its window is open the app does not open another one for the
same unit, and it shows what the agent is doing from its transcript.

## Trust in pages: review and freshness

**Review.** Every page is a `draft` (AI wrote it, nobody checked), `confirmed` (a person confirmed this exact
content: the confirmation is tied to the page's hash) or `needs-reconfirm` (it changed after it was confirmed). Agents
never rewrite a confirmed page or one with `x-owner: human` silently, and never touch `<!-- human -->` blocks. When a
page is confirmed, the kit measures how much of the AI's words the person changed — a cheap signal of draft quality.

**Freshness.** When a page is written, the kit fingerprints the code it cites in `x-sources` (lines, or a symbol such as
`orders:src/OrderService.java#OrderService.place` that is found again even if it moves). Code that changed makes the
page **suspect**; code that is gone makes it **stale**; code that only moved keeps it fresh. A page that cites other
pages or C4 elements (`c4:shop.orders`) is suspect when one of them is. Agents do not get suspect or stale pages, nor
unreviewed pages without sources: the MCP and `llms.txt` hold them back and say which code to read instead
(`freshness: {ai_policy: warn}` hands them over with a warning). People still see them, with a notice. `camaron fresh`
lists them, `--plan` adds a unit to refresh them, `--ack <page> --by <name>` says one still holds.

**The quality gate.** `camaron check` runs when every unit closes and in CI: missing front matter or sources, broken
links and anchors, Mermaid that does not render (mermaid-cli), possible secrets (gitleaks; they block the checkpoint and
the export), words the glossary says to avoid, generated blocks edited by hand, `:::rule` blocks whose code is gone,
and each page's structure (TL;DR, the sections its skeleton asks for, a size budget). `--strict` turns warnings into
errors.

## The MCP servers

**`camarones`** is registered for Claude Code and Codex in `cam-docs` and, by `setup`, in each repo's local Claude Code
scope (in `~/.claude.json`, never in the repo), so it also works with an agent opened inside one repo. `camaron doctor`
warns when it is missing and `camaron repair` puts it back. It speaks JSON-RPC over stdio; `camaron mcp --http` serves
it at `http://127.0.0.1:8765/mcp` (Streamable HTTP) with the token in `~/.camarones/mcp-token`.

| Tool | Does |
|---|---|
| `search_docs` | Ranked search; each hit names its section, trust and freshness |
| `read_doc` | A page, or with `section` only its TL;DR and that section |
| `list_docs`, `doc_status` | The index with trust; the documentation's health |
| `ask` | The best sections for a question, each with its citation `[path#section]`; no model is called |
| `propose_edit` | Changes an AI draft in place; for a confirmed or human page, saves a proposal for review instead. Never confirms |
| `add_feedback`, `mark_suspect` | Leave a review comment; hold back a page that no longer matches the code |
| `pipeline_status`, `run_events`, `kpis` | The plan, a run's events, the KPIs |
| `run_node` | Starts a ready unit, only with `mcp: {pipeline_control: true}` in `workspace.yaml` |
| `repo_graph` | Asks the graphify code graph of one repo or all |
| `board_next`, `board_waves` | What may start now without collisions; the open work in waves. Agents read the board; they never move cards |

It also offers every page as a resource (`camdocs://<path>`, plus `camdocs://llms.txt`) and two prompts,
`implement-feature` and `update-docs`. Everything goes through the same freshness gate.

**`likec4`** answers questions about the architecture model (who calls this service, what sits between A and B). The
skills `cam-docs-lookup`, `cam-docs-update` and `cam-docs-diagrams` teach agents when to use them.

## Plugins and trust

A plugin is a folder with a `plugin.yaml` that brings agents, checks, prompts, skills, hooks, MCP servers or unit types.
The kit ships Gemini, Confluence and Notion; a team adds its own with `camaron plugins add <folder | git:<url>@<tag>>`,
which copies it into `cam-docs/.camarones/plugins/` and pins version, origin and fingerprint in `plugins.lock`.
`plugins outdated`, `update` and `remove` manage them; `check` warns when someone edits one by hand.

The kit works out whether a plugin runs code instead of trusting its manifest. Anything that runs code or steers agents
and arrived with the team's repo — plugins, hooks, MCP servers, settings, skills — is not loaded until you approve it on
your machine (`camaron trust`, or Team in the app). The approval covers every file, so any change asks again. What the
kit itself installed is recognised without asking, and `camaron repair` restores it if someone edits or deletes it.

<!-- go:team -->

## Pages written without AI

A fresh install already documents a lot from static analysis, with sources on every row:

| Command | Writes |
|---|---|
| `camaron pages` (alias `diagrams`) | `docs/index.md` (what the project is, a card per repo, the context map), `docs/repos/<repo>/index.md` (endpoints, data as an ER diagram, state diagrams per status enum, messages, env vars and commands) and `docs/architecture/messaging.md` |
| `camaron radar`, `camaron stack` | `docs/overview/tooling.md`: each repo's stack and the tools it uses |
| `camaron inventory [--cves]` | `docs/overview/libraries.md`: direct dependencies by category, versions that differ, known vulnerabilities |
| `camaron schemas` | Tables and collections from migrations, entities, Mongo and Firestore |
| `camaron history` | `docs/overview/history.md`: hotspots, who works where, files that change together |
| `camaron arch-draft` | A first C4 model to verify |
| `camaron llms` | `llms.txt` and `llms-full.txt` for agents |

These are **generated blocks** (`<!-- generated:… sha=… -->`) that `pages`, `blocks` and `sync` keep current. A person
confirms one by copying its `sha=` into `confirmed=` with `by=<name>`; from then on a refresh leaves it alone and
`check` says when the code moved since.

<!-- cmd:pages -->

## Versions and compatibility

The kit's version and every tool it installs (Electron, LikeC4, graphify, OpenWiki, mermaid-cli, gitleaks,
OSV-Scanner…) are pinned in `lib/common.py` (`VERSIONS`); `camaron version` shows them and `camaron doctor` checks them.
A project made by any 3.x or 4.x kit opens with a newer kit without manual steps; older layouts go through
`camaron migrate`. The global install updates with `camaron self-update` (every project at once); a copy of the kit
inside a project updates with `camaron upgrade <new-kit-folder>`. Templates such as these guides are copied into a
project once and never overwritten, so a new guide arrives with the next `camaron setup` while a guide the team edited
stays theirs.
