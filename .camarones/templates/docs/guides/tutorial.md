---
type: guide
title: Tutorial — Camarón, the project docs wizard
description: How to install Camarón on macOS or Windows, run the guided documentation sessions with Claude Code or Codex, confirm AI drafts, use the portal (read, edit, review), generate the OpenWiki wikis and wire CI.
tags: [onboarding, tooling]
x-owner: human
---
# Tutorial — Camarón 🦐

*Camarón que se duerme, se lo lleva la corriente.* Camarón documents a whole project (all its repos) in short AI
sessions, saves progress after each one and always tells you what comes next.

## 1. Install (once per computer)

Requirements: **git** and **Node.js ≥ 22**; Java only for JVM repos (SDKMAN, brew or winget installs are detected) (the wizard offers to install them with Homebrew / winget),
**Docker Desktop** only to serve the portal, and **Claude Code** and/or **Codex** for the AI sessions (OpenCode and
Gemini CLI work too; OpenCode is the way to local models).
Python is *not* required: the launcher installs `uv`, which brings its own Python.

| | Open the wizard |
|---|---|
| macOS | double-click `camaron.command` (if macOS blocks it the first time: Terminal in the folder → `sh camaron.command`) — or `./camaron.command` |
| Windows | double-click `camaron.cmd` — or `camaron.cmd` in a terminal |
| Linux / CI | `./camaron.command` (it is a plain shell script) |

**Global install (several projects):** `sh install-global.sh` (Windows: `install-global.cmd`) from the kit repo leaves a
`camarones` command on your PATH; run `camarones` in the folder that groups the repos and it creates `./cam-docs/`.

**New project from the zip:** put `camarones-documenter.zip` in the folder where the project's repos live, extract it there and
open the launcher. If extraction created a `camarones-documenter/` subfolder, the wizard offers to move itself one level up.
Repos already in the folder are detected; you can add more by URL.

Everything the kit writes lives in **`cam-docs/`**, next to the repos: its own git repo with `docs/`, `wikis/<repo>/`, the
tool configuration (`.camarones/`) and the agents' setup (`.claude/`, `.codex/`, `.agents/`, `.mcp.json`). Service repos
get no kit files; paths below are relative to `cam-docs/`.

The agents' setup is shared with the team, so it is never loaded blindly: hooks, MCP servers, settings and skills the
kit did not write are listed when you open the wizard, and the workspace only links them once you approve them on this
machine (`camaron trust`). Approvals live in `~/.camarones/trust/`, never in the repo. What the kit installed on this
machine (its skills, graphify's and OpenWiki's, recorded in `~/.camarones/install/`) is recognised without asking;
`camaron doctor` shows a kit file edited or a link gone, and `camaron repair` puts them back.

## 2. The guided flow

The first run walks you through: workspace (project name) → repos → tools (install everything — recommended — or pick
what to install) → setup (repos, Claude/Codex wiring, git hooks) → stack & tools (each repo's stack and the tools you
already use — Backstage, Sonar, component library, linters, contracts, CI — found without AI; fix a wrong stack there
or later with `camaron stack`; saved in `docs/overview/tooling.md`, with every direct dependency by category in
`docs/overview/libraries.md`, also `camaron inventory`; `--cves` adds known vulnerabilities from OSV-Scanner's offline
database; and each repo's tables and collections in `docs/data/<repo>.md`, also `camaron schemas`) → quick C4 draft → how sessions work. Esc always goes one step back; long
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

The interviews do not block drafting: repo briefs, domain, data, decisions and the flows catalog start from the code as
provisional drafts (`✎ draft` in `plan`), leave their questions in `docs/interview/open-questions.md`, and are reopened
to refine when the interview is done. Translations and confirmation still wait for the interviews.
As a team questionnaire, each person answers it in the portal (Plan › Interview) or in the offline form
(`camaron interview export`, then `interview import`); both write the same `responses/<name>.yaml`.

Big unit? The agent splits it and adds the remainder to the plan. Everything survives between sessions and computers
(the plan is committed with the docs).

**Your own plan.** The plan comes from the kit's pipeline (`full` or `quick`). To change it for this project, create
`.camarones/pipeline.yaml` and run `camaron plan sync`:

```yaml
extends: kit:full
nodes:                                   # extra units
  - {id: security-review, type: security-review, needs: [arch-system]}
patch:
  - {op: disable, node: ci}              # the unit is dropped; remove the line and it comes back
  - {op: needs, node: domain, add: [data]}
  - {op: set, node: i18n, runner: "opencode:ollama/qwen3-coder:30b"}   # or tier: bounded / judge
  - {op: set, node: "repo-brief:*", approval: true}   # a person approves each brief before anything builds on it
```

A unit with `approval: true` waits as "awaiting approval" when its agent finishes; its dependents start after
`camaron plan approve <unit>` or the Approve button in the portal's Pipeline (Plan zone).

`node` is the id as the kit writes it (`discovery:{repo}`) or a prefix with `*` (`repo-wiki:*`). If the file has a
mistake, the plan stays as it was and `camaron plan` says where (`patch[1].node: unknown node 'cii'`).

**Plugins.** A plugin is a folder in `.camarones/plugins/<name>/` with a `plugin.yaml` (`name`, `version`, `kit`
range, `provides`). `camaron plugins` lists the kit's and the project's, what they provide and whether they run code.
A plugin that runs code (agent commands, hooks, MCP servers, scripts) or steers agents (prompts, skills) is shared
with the whole team through the repo, so it is not loaded until it is approved on each machine: the wizard asks along
with the rest of the agent config, or `camaron trust` (`--yes` to approve). The approval covers every file of the
plugin folder: any change asks again. An approved plugin's agent runners are then available like the built-in ones.

Team plugins are vendored and pinned: `camaron plugins add <folder | git:<url>@<tag>[#subfolder]>` copies one into
`.camarones/plugins/` and records its version, source and fingerprint in `.camarones/plugins.lock`; a plugin whose
`kit` range does not include this kit is refused. `plugins outdated` lists newer versions, `plugins update [name]
[--to <tag>]` re-fetches and lists the files that changed, `plugins remove <name>` drops one. `check` warns when a
folder no longer matches the lock. A pipeline node can follow a plugin, pinned to a major version: in
`.camarones/pipeline.yaml`, `patch: [{op: set, node: decisions-quality, uses: adr-style@1}]`. That unit's prompt then
carries the plugin's prompts and points to its skills; a wrong major or an unapproved plugin is a pipeline error.

## 3. Trust: AI drafts vs confirmed

Every page starts as **✨ draft** (banner in the portal). Confirm pages in the portal (**Confirm** on each page, the
**Review** zone lists what is pending) or with **✅ Review & confirm pages** in the wizard; the confirmation is locked to the content — if anyone edits the page later it becomes
**⚠️ needs re-confirmation**. Agents treat confirmed pages as the source of truth.

**Freshness.** When a page is written, the code it cites (`x-sources`) is fingerprinted. If that code changes the page
is **suspect**; if it is gone, **stale** (moved code does not count). Agents are not given suspect or stale pages, nor
unreviewed pages without sources: the MCP, `llms.txt` and `llms-full.txt` withhold them and point to the code. People still see them,
with a banner. `camaron fresh` lists them, `fresh --plan` adds a unit to refresh them, `fresh --ack <page> --by <name>`
says one still holds. `freshness: {ai_policy: warn}` in `workspace.yaml` serves them with a warning instead.
Cite a symbol rather than lines when you can (`orders:src/…/OrderService.java#OrderService.place`): it is found again
wherever it moves, so only a change to its own body counts. A page built on other pages or C4 elements cites them
(`docs/flows/checkout.md`, `c4:shop.orders`) and becomes suspect when one of them does.

To protect a paragraph from agents:

```markdown
<!-- human -->
Only humans edit this paragraph.
<!-- /human -->
```

## 4. After the first pass

**🔄 Update docs after changes** runs an incremental session: only what changed in the code is regenerated, stale pages
are cleaned up, confirmed pages are never silently rewritten. CI can run the same thing automatically (section 8).

**Quality gate.** `camaron check` runs after every unit and in CI. Besides frontmatter, sources, trust and
translations it reports:

| Check | Severity | Needs |
|---|---|---|
| Broken link to another page (external URLs are not checked) | ERROR | — |
| A `#anchor` with no matching heading in the target page | warning (ERROR with `--strict`) | — |
| Mermaid diagram that doesn't render | ERROR | mermaid-cli |
| Possible secret in `docs/` or a wiki (file and line only, never the value) | ERROR; also blocks checkpoint commits and `camaron portal` | gitleaks |
| A word from the glossary's **Avoid** column | warning (ERROR with `--strict`) | an Avoid column in `docs/domain/glossary.md` |
| Generated block edited by hand or behind the code (`camaron blocks`) | warning (ERROR with `--strict`) | — |
| Page structure: TL;DR under the title, the sections of its skeleton in `.camarones/skeletons/`, size budget, vague references | warning (ERROR with `--strict`) | — |

mermaid-cli and gitleaks come with the full install (the `quality` component; mermaid-cli downloads a headless Chromium
once). Without them `check` prints one warning and skips that check.

## 5. Portal

A fresh project never shows blank views: Home, Docs and Architecture offer a **first look from the code (no AI)** — the C4
draft and its page, the stack and tools — and Code offers to build the code graph.

One portal, two modes, the same interface, in Cofundo's visual language with the Camarón brand (light or dark, fonts served by the portal itself). There is no tab bar: **Home** asks first (Ask live, search in the export), shows the project's state (confirmed, to reconfirm, drafts, pending feedback); the sidebar keeps five zones — Docs, Architecture, Plan, Quality and Review — on every view; the top bar shows where you are and Ctrl K / ⌘K jumps to any page, zone or view, or (live) takes the question to Ask. Old addresses (`#/c4`, `#/docs/…`) still work. The views: **Docs** (tree, search, trust badges), **Architecture (C4)** (under each view, its elements: edit title,
technology, description and relations, and confirm what the AI drafted, one by one or the whole view),
**Code graph** (all repos or one), **Wikis** (OpenWiki per repo, its pages and graph), **Review** (pending pages with their sources, confirmed several at once; reviews
an agent is waiting for, change requests, code changed since the docs, `check`), **Ask** (the sections that best answer
a question, with citations, no AI; "database" also finds PostgreSQL and Spanish questions find English pages; with an agent set up, "Answer with AI" writes the answer from them
alone), **Libraries** (every repo's dependencies as a library × service matrix, filtered by category,
language, repo or scope, with known vulnerabilities in red), **Data** (each repo's tables and collections from the code,
as an ER diagram), **Pipeline** and **KPIs** (pages and C4 elements confirmed, pages out of date, AI cost by month and
the questions nobody found, which one click turns into an open question). The language switch changes the interface and the docs; a page not translated yet is shown in
English with a notice. Tables sort by column (long ones filter), `:::tabs`/`:::steps`/`:::details`/`:::cards` render
as tabs, steps, folds and cards, an "All / Business" switch (on each page and above the menu) hides `:::tech` blocks and, in Business, keeps
only the overview, domain, glossary, flow and decision pages in the menu and on the home page, which also has a "How
does … work?" box that sends the question to Ask, and Mermaid names that match a page
or a repo are links. A `:::rule ORD-1 Title` block states a business rule with `enforced:`/`test:` anchors
(`repo:path#Symbol`); `check` fails when that code is gone.

The **Pipeline** view (Plan zone; it ships already built
with the kit, no Node needed) shows the plan live: a graph of the units by phase, a board by
status, and per unit its agent, outcome, time, tokens, cost and the agent's log line by line. Start `camaron run` with
the page open and it picks the run up by itself. From the view you can also start a run, cancel it (the agents stop and
their units go back to the queue, keeping their work) and retry a blocked unit. One run at a time, CLI or portal.

| | Command | What it is |
|---|---|---|
| Local, editable | `camaron up` (wizard → 🌐 Portal → 📝 Open the portal) | `http://127.0.0.1:8080`, only on your machine |
| Export for deployment | `camaron portal` (wizard → 📦 Export) | read-only HTML + JSON in `.camarones/.cache/site`, no npm build |
| See the export | `camaron up --static` or `camaron up --docker` | exactly what the server will serve |

The export is plain static files (nginx image, GitLab/GitHub Pages) and works without internet. On a server, run the image
CI pushed: `docker run -d -p 8080:80 <registry>/<group>/cam-docs/portal:latest`.

### 🖥️ The desktop app

Where you operate a project; the portal is where you read it. Each project opens in its window: at the left the rail
with your projects and the sections, below the jobs panel (what runs and the last ones, their output and **Stop**). The
browser portal stays the team's viewer (read, edit, review, pipeline status, the interview) and does not show what it
cannot do. From the keyboard, Ctrl K / ⌘K goes to a section, another project or any command, and `g` then a letter jumps
between sections (`g s` Summary, `g p` Plan, `g q` Quality…).

| Section | What you do there |
|---|---|
| 🏠 Summary | the next step with one button (the one the wizard suggests), what this machine is missing, where the plan, the review and the jobs stand |
| 🗺️ Plan | run the ready units in parallel or the autopilot, and stop them; the units grouped by what they ask of you (approve, retry, continue, start) with the agent you pick; the docs update |
| 🎙️ Interviews | team questionnaire or live, export the offline form, import answers, close the round, each interview with its agent |
| 🤝 Team | the team's repo and sharing, approving the agent config that came with it, hooks, plugins |
| ✅ Quality | prerequisites and tools (kept between visits, "Check again"), the context every agent session loads, golden questions, with vs without cam-docs; without AI, known vulnerabilities, pages out of date, generated blocks |
| 📖 Docs | opens the portal: read, review drafts, search or ask |
| 🧰 Machine | setup with progress, language and models, GitLab / GitHub tokens, repos and their stack, the plan profile, kit updates, repair and, apart and previewed first, uninstall |

Every section ends with **All commands**, folded: the rest of its catalog zone, each with its form.

**Install and open it**

1. The kit installed (global install: the `camaron` command on your PATH).
2. Node.js 22 or newer: `node --version`. Missing? `camaron doctor --install node` (winget on Windows, Homebrew on macOS).
3. `camaron app`. The first time it downloads Electron (pinned, about 100 MB) into `~/.camarones/desktop`, with no admin
   rights and nothing in your projects; then it opens at once.

From a project's folder it opens that project; from anywhere else, the picker: open a project, create one, join the
team's `cam-docs` with its URL or add a folder that already has one. The wizard has the same entry (🖥️ Desktop app).
Inside, your projects sit on the rail: another one opens in the same window, which comes back where you left it.
<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>O</kbd> goes back to the projects and **camarón › Open in
the browser** opens the same portal outside. On Linux with restricted user namespaces (Ubuntu 24.04+) the kit starts
it with `--no-sandbox`: its windows only load your project's local server.

### 📋 The board

A Kanban stored in `cam-docs/backlog/` and versioned with the docs. Each card is a Markdown file compatible with
Backlog.md (it reads and edits them without breaking anything); the kit's own state (column and order of each card)
is in `backlog/board.yaml`, one line per card so git merges per card. Turn it on with `camaron board init`;
projects without `backlog/` behave as before.

```sh
camaron board add story "Idempotent retries" --epic WI-3 --repo payments --doc FLOW-k3f9#retries
camaron board list --status Ready --repo payments     # also --epic, --label, --docs suspect|unconfirmed
camaron board show WI-42                              # the card and the trust state of its pages
camaron board move WI-42 "In Progress"                # Backlog, Ready, In Progress, In Review, Done, Blocked
camaron board assign WI-42 ana
camaron board link WI-42 flows/payments.md#retries
camaron board archive WI-42
camaron board repair                                  # also runs before every checkpoint and share
```

All of them take `--json`. Links to pages go by `x-id`, so they survive a move or rename, and the board knows whether
a linked page changed since it was linked. In the portal, the **Board** zone (`#/kanban`) has the Kanban
with filters by repo, epic, label and docs state, and the card detail; writing needs the machine token (the desktop app sends it; `camaron up` prints it in the
URL as `#cam-token=…`), without it the board is read-only. On uninstall, the CLI's
`camaron uninstall` asks whether to keep `backlog/` (`--keep-board` / `--drop-board` choose without asking); the
wizard and the desktop app always keep it.

## 6. Editing: where and when

| Where | What you can do | Where the change goes |
|---|---|---|
| Local portal (`camaron up`) | edit (markdown + live preview), **+ New page**, **Confirm**, **Request changes**, generate wikis, rebuild C4 / code graph | `cam-docs/docs` + a local commit if "commit to cam-docs" is ticked — you push |
| Deployed portal (export) | read and search; **Edit** opens the file in GitLab / GitHub (when `cam-docs` has a remote) | a merge request in `cam-docs`; CI publishes it again |
| Your editor / IDE | any `.md` under `cam-docs/docs` | plain git in `cam-docs` |
| The AI (🦐 Next step) | only its unit; never rewrites confirmed pages silently | a local commit per unit |

- **Confirm** signs with your `git config user.name`. **Request changes** saves the comment and adds a `review-fixes`
  unit that the AI applies in the next session.
- With Spanish selected, **Edit** edits the translation (`docs/i18n/es/…`).
- Editing a ✅ page turns it **⚠️ needs re-confirmation** until someone checks it again.
- Don't hand-edit generated files (`llms.txt`, `llms-full.txt`, `docs/.status.json`, the viewers). Wikis are better regenerated from the
  **Wikis** view: an OpenWiki update can rewrite what you change.

## 7. OpenWiki: one wiki per repo

Portal → **Wikis** → **Generate / update wiki** (live log), wizard → **📚 Wikis**, or `camaron wiki <repo>`. The wiki
is stored in `cam-docs/wikis/<repo>/` (the repo sees an unversioned `openwiki/` link) and its pages show under **Docs** as
`repos/<repo>/…`. It uses the OpenWiki provider if one is configured (`openwiki auth configure <provider>`), otherwise
Claude Code or Codex. The files OpenWiki adds to the repo itself (`AGENTS.md`, `CLAUDE.md`, `.github/`) are removed when
the run ends.

Each wiki is a full agent run, so only the repos you choose get one: wizard → **📚 Wikis** → **Choose which repos get a
wiki** (stored as `wiki: true` in `.camarones/workspace.yaml`). Pick the services with logic, not libraries or CI repos.
A first wiki waits for the repo's brief (`wikis/<repo>/INSTRUCTIONS.md`, written by the repo-brief unit) so it uses your
glossary; `camaron wiki <repo> --force` skips that check. In the portal's Wikis view every repo has the button: for a
repo not chosen yet it chooses it, and without a brief it first writes a starter one from the static scan (no AI), which
the repo-brief unit replaces later. When no engine can run, the view says what is missing. Runs go one at a time, and a batch stops as soon as the
engine is out of quota or logged out instead of failing every remaining repo.

## 8. CI

Wizard → **⚙️ CI** installs the pipeline in `cam-docs` (GitLab or GitHub): update the affected docs, `check`, export the portal and publish it. Per-repo snippets: `.camarones/ci/repo.*`.
The portal's **CI** view (Quality zone) shows the same: which pipeline files exist and whether they still match the kit's definition,
a button to generate them for GitHub or GitLab, the current `check` and freshness, the per-repo files to copy, and the last
pipeline run when `gh` or `glab` is installed and logged in.
Before the update branch is pushed, `camaron check --secrets` runs: a possible secret fails the job, so no MR/PR is opened.
Variables: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, a bot token to open MRs/PRs; on GitLab allow the `cam-docs` project's
job token to clone each service repo (repo → Settings → CI/CD → Job token permissions).

**Every pull request, no AI.** `camaron ci` also writes `.camarones/ci/docs-fresh.github.yml` (or `.gitlab-ci.yml`) for
each service repo. On every PR/MR it comments which pages the change leaves out of date, and which were already out of
date before; one comment per PR, updated on each push. It needs no API key and never blocks the merge. It needs
`DOCS_REPO_URL` and a `DOCS_READ_TOKEN` that can read `cam-docs` (on GitLab also `DOCS_BOT_TOKEN` to comment). Locally:
`camaron pr fresh <repo> --base main`. It runs on hosted runners by default; to keep it on your own runners, set
`ci: {target: self-hosted, runner_labels: [self-hosted, docs], runner_tags: [docs]}` in `workspace.yaml` and run
`camaron ci` again. Pull requests on `cam-docs` itself only run `check`.

**An AI proposal for a PR.** `camaron pr propose <PR url>` fetches the PR into `refs/camaron/pr/<n>` of the service
repo (your checkout is not touched), and an agent updates the pages it leaves out of date on the cam-docs branch
`docs/pr-<repo>-<n>`, in its own worktree. The kit commits, pushes and opens the docs PR (`--comment` links it on the
service PR, `--preview` exports that branch as a static portal); `--dry-run` shows the plan first. With `ci.target: self-hosted`, `camaron ci` also writes `docs-propose`:
the same command on your runner when a member labels a PR `docs:update` (another label: `ci: {propose_label: …}` in
`workspace.yaml`), never for forks. Setting up the runner:
[self-hosted runner guide](self-hosted-runner.md).

**The MCP server.** Agents reach the docs through the `camarones` MCP server: `search_docs`, `read_doc(path, section)`,
`ask` (the best sections for a question, with citations), resources `camdocs://<page>` and two prompts. It can also
write, but only drafts: `propose_edit` changes an AI draft in place and never touches a page a person confirmed or
owns (the proposal is saved in `docs/.work/proposals/` and listed in Review), `add_feedback` leaves a review comment,
`mark_suspect` withholds a page from agents until it is refreshed or acknowledged. Nothing it does confirms a page.
`pipeline_status`, `run_events` and `kpis` report on the plan; `run_node` starts a unit only with
`mcp: {pipeline_control: true}` in `workspace.yaml`. `camaron mcp --http` serves the same tools on
`http://127.0.0.1:8765/mcp` for clients that speak Streamable HTTP; they need `Authorization: Bearer <token>`, with the
token in `~/.camarones/mcp-token`, and requests from other origins are refused.

**Claude Code inside one repo.** `setup` (and `repair`) registers the `camarones` MCP server in Claude Code's local
scope for each repo folder, so a session opened in `<repo>/` searches and reads the docs too. It lives in your own
Claude Code config (`~/.claude.json`), never in the repo; `doctor` says when a repo lacks it and `uninstall` removes it.

**Method hooks (opt-in).** `camaron hooks on` adds three Claude Code hooks to `cam-docs/.claude/settings.json`, which
the kit owns (`trust` does not ask about them): at session start the agent gets the plan state, the last handoff and
pending reviews; right after it edits a docs page, that page is checked and the problems go back to the agent; before
it stops, if the repos moved on since the docs, it is reminded once to update them. `camaron hooks off` removes them.

**Does the method hold?** `camaron eval comply <unit>` runs one ready unit for real and scores what it wrote (structure,
links, sources), without AI. Use it on the sandbox to compare a playbook or prompt change before and after.

**Export.** `camaron export pdf` writes every page agents may read into one print-ready page and turns it into a PDF
with a headless Chrome, Chromium or Edge when there is one (otherwise print the page to PDF from a browser).
`camaron export tour flows/<flow>.md` makes a guided tour of a business flow, one slide per row of its Steps table;
`export codetour flows/<flow>.md` writes it as a VS Code CodeTour (`.tours/<flow>.tour`) that opens each step's code.
`camaron export confluence` and `export notion` publish the docs to those tools; they send the docs outside your
machine, so they are off until you run `camaron plugins enable confluence` (or `notion`) and set their URL and token
(`CONFLUENCE_URL`, `CONFLUENCE_USER`, `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE`; `NOTION_TOKEN`, `NOTION_PARENT_PAGE`).

**Ask a person and wait.** An agent that needs a human answer on a page runs `camaron review request <page>` and then
`camaron review wait <id>`: it blocks until someone approves or asks for changes in the portal's Review zone, and gets
the decision as JSON. Review comments can point at a section: they keep the section's slug and a short quote, so they
are found again after a heading is renamed.

**What was removed on purpose.** `camaron removed add "SOAP billing endpoint" --why "replaced by the REST API"
--decision decisions/0007-drop-soap.md` adds a row to `docs/overview/removed.md` (what, when, why, the decision).
Agents read it before recreating something; the project's `AGENTS.md` also has a "Where to look" table for each task.
Each session ends with a handoff that keeps what was verified (with evidence), what was not, the commands run and the
next action apart.

## 9. Commands (for scripts and agents)

`camaron help` (per-project copy: `./camaron.command help`, Windows `camaron.cmd help`): `setup`, `sync`, `detect`,
`plan`, `plan next`, `status`, `check [--strict|--secrets]`, `confirm`, `feedback`, `checkpoint`, `graph`, `arch` (live C4 editor), `arch-validate`,
`wiki <repo>`, `portal` (export), `up [--static|--docker]`, `down`, `ci`, `prompt <unit>`, `migrate`, `doctor`,
`doctor --json` (each check with the command that fixes it), `doctor --install git|node|docker|java|claude|codex`,
`doctor --local` (proposes a free local model for this computer, installs nothing), `doctor --context` (the tokens
every agent session loads before reading a page, against `context.budget`), `autopilot`, `plugins [--json]`,
`run`, `runs`, `kpis`, `eval`, `ab`, `pipeline show|validate`, `blocks [--force]`, `diagrams [--json]`, `pr fresh <repo>`,
`plugins add|update|outdated|remove`, `pr propose <url>`, `removed add`, `repair`, `export codetour <flow>`, `history [--months 12]`
(hotspots, who to ask per repo, files that change together, read from git without AI into `docs/overview/history.md`),
`catalog [--json|--check]` (every command with where it lives: portal, desktop app or CLI only, and its arguments),
`projects [--json]` (the projects registered on this machine), `config [get|set KEY VALUE]` (lang, model, codex_model: the wizard's settings), `trust --json` and `hooks --json` (what is pending
approval, whether the method hooks are on), the portal's **Plan › Sync** (the same as `share`, with where you stand), `app` (the desktop app: the project's sections by task, the portal to read,
where runs, wikis, scans and checks start; the browser portal only shows them).

**Facts from the code, no AI.** `camaron blocks` writes `docs/repos/<repo>/reference.md` for each repo: commands
(Maven, Gradle, `package.json`, Makefile, Docker Compose), env vars (Spring `${VAR:default}` placeholders,
`.env.example`, Angular `environment.ts`; secret-looking defaults hidden), HTTP endpoints (OpenAPI, else Spring
annotations) and message topics, each row with its file and line. They are `<!-- generated:<kind> repo=<repo> -->`
blocks you can put in any page; `blocks` and `sync` refresh them. A block edited by hand is kept and `check` flags it;
`blocks --force` takes the code's version.

**Diagrams from the code, no AI.** `camaron diagrams [--json]` (also run by the first scan and the first look) draws
what the code states, in Mermaid, and never guesses: `docs/architecture/system-map.md` has the context map (repos,
datastores, brokers, identity providers) and one sequence per message topic (who publishes, who consumes);
`docs/repos/<repo>/diagrams.md` has the repo's endpoints map and one state diagram per status enum, with the states
only (transitions are not guessed). They are ordinary Docs pages made of generated blocks like the ones above. A
person can confirm one by hand: copy the block's `sha=` value into `confirmed=` and put a name in `by=` (one word, or
quoted when it has spaces: `by="Ana López"`), e.g.
`<!-- generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`. A refresh then
never rewrites it, and `check` warns "the code changed since this diagram was confirmed" (or that the code no longer
has the diagram's source). To take the code's version, remove `confirmed=` and `by=` from the marker, run
`camaron diagrams` (or `blocks`), then confirm it again. The portal labels each diagram "From the code", "Edited by
hand", "Confirmed by <name>" or "The code changed".
Agents follow the `cam-docs-diagrams` skill: pick the right diagram, write Mermaid that renders, never edit a generated block.

**Parallel runs.** `camaron run --parallel 3 --per-runner claude=2,codex=1` does several units at once. Discovery, repo
briefs and flows each work in their own copy of `cam-docs/` (a git worktree in `.cw/<n>/`) and are merged back when
they finish, after `check` and `arch-validate` show no new errors; other units run one at a time, and a unit waits for
what it needs to be merged. A clash blocks the unit, leaves `cam-docs/` untouched and adds an `integrate:<unit>` unit.
`camaron runs` shows what each run did and cost; `camaron pipeline show` lists the units and where each one works.
`autopilot` stays sequential. Runs keep the computer awake (a laptop that sleeps breaks the agent's session); a
session cut by something passing (sleep, network, an overloaded API) is retried once. One session per agent by default:
with a single agent installed, `--per-runner claude=2` lets it take more.

**Is it working?** `camaron kpis` shows the team's runs per month (time, tokens, cost per unit, parallelism, limits,
failures), coverage (repos with a brief, flows, C4 files, `check` errors), trust (confirmed, drafts, re-confirmations,
repos changed since documented, and how much of the AI's words people change before confirming a page) and usage (agent and portal queries, searches with no result). Runs add up through
`docs/.work/kpis/` (committed, one file per person and machine). `camaron kpis --compare <run-a> <run-b>` shows whether
a prompt, model or kit change helped.

**Golden questions.** An exam with an answer key for the docs: `evals/questions.yaml` lists real questions, the pages
that should be cited (`expect`, as `read_doc` takes them) and the exact identifiers a right answer names (`mention`).
`camaron eval draft` adds a unit where an agent proposes them; `camaron eval confirm <id> --by <name>` approves them
(only confirmed ones count); `camaron eval run` asks them to an agent that can only read the docs and scores the cited
pages and identifiers, without AI (`--judge` adds a model's grade). `kpis` shows the latest score.

**Does cam-docs help?** `camaron ab --qa "<question>"` asks the same question twice: through the docs, and with only
the code, in a temporary folder outside the project that links the repos and nothing else (no `cam-docs/`, no
`AGENTS.md`, no MCP). It compares the context read (input plus cached tokens), time, cost, tool calls and the exact
identifiers each answer names; `--golden`
does it for the golden questions. The repos are never touched. `ab: {enabled: false}` in `workspace.yaml` turns it off.
`camaron ab --task "<task>" [--check "<test command>"]` does a coding task twice, each time in throwaway git worktrees
of the repos (with a worktree of cam-docs and the agent config, and without): it compares tokens, time, tool calls,
files changed and the diff, and whether the check passes in each. Your checkouts are not touched. `camaron ab sampling
on` keeps a sample of real prompts on this machine (only if `ab: {sampling: {enabled: true, rate: 0.05}}` is set too;
stored in `~/.camarones/ab-samples/`, never in the repo) and `ab --replay` runs them as tasks.

**Which agent runs what.** Each kind of work has an ordered list and the first installed agent runs it:
`agentic-heavy` (long units), `bounded` (translations, summaries) and `judge` (eval scoring). `runner:model` also picks
the model. The team sets it in `.camarones/workspace.yaml` (`agents: routing:`); `~/.camarones.json` (`routing`) wins on
this machine. Local models go only through OpenCode (`opencode:ollama/qwen3-coder:30b`) and never do `agentic-heavy`
work. `autopilot` and `run` read it unit by unit. Each run is logged in `.camarones/.cache/runs/` (`camaron runs`).

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| macOS blocks `camaron.command` ("cannot be opened" / "Apple could not verify…") | open Terminal in the folder and run `sh camaron.command` (once: the launcher clears the quarantine flag, then double-click works). Or: System Settings → Privacy & Security → "Open Anyway" |
| Windows: SmartScreen warning | "More info" → "Run anyway" |
| Windows blocks the file or the antivirus removes it | before extracting: right-click the zip → Properties → tick **Unblock** → OK. Already extracted: in PowerShell inside the folder `Get-ChildItem -Recurse | Unblock-File`. Company PC that forbids `.cmd`: `winget install astral-sh.uv`, then `uv run --script .camarones\camarones.py` |
| Something installed but not detected | close and reopen the wizard (PATH refresh) |
| `doctor` shows a tool missing | wizard → 🛠 Install / repair |
| Repo "skip … local changes" on sync | commit or stash in that repo, sync again |
| C4 errors | `camaron arch-validate` shows file + line |
| `checkpoint` / `portal` refuse: "possible secret" | replace the value at that file and line with a placeholder (`<your token>`), then run it again |
| `check`: "mermaid-cli could not start its browser" | Chromium is missing system libraries (usually in CI containers); diagrams are skipped, the rest of the check still runs |
| OpenWiki tools missing in the agent | restart Claude Code / Codex in the workspace folder (the one that holds `cam-docs/`) |
| The deployed portal has no **Edit** button | `cam-docs` has no git remote: add one and export again |
| A wiki run failed | the ⚠ line says why (quota or login → wait or log in again); run `camaron wiki <repo>` again — an interrupted run resumes |
| `camaron app`: "needs Node.js >= 22" | install Node 22 (`camaron doctor --install node`) and run `camaron app` again |
| The app opens the project picker, not your project | you ran it outside the project's folder: open it from the list or **Add folder** |
| The browser portal lacks a button you expected | on purpose: the browser portal does not start processes; use `camaron app` |
