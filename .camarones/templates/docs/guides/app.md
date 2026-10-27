---
type: guide
title: The desktop app
description: Every screen of Camarón's desktop app — the window, the start screen, the first-run wizard and each section — with what each button runs and when it is off.
tags: [onboarding, tooling, desktop]
x-owner: human
---
# The desktop app

> **TL;DR:** `camaron app` opens one window per project. The rail on the left switches projects, the sections run
> what happens on your machine (plan, interviews, team, quality, libraries, wikis, setup), and the portal opens in your
> browser to read. Every button runs a `camaron` command you could type yourself, and its output lands in the jobs
> panel at the bottom.

The app is where you **operate** a project; the [portal](portal.md) is where you **read** it. The app never shows the
portal inside its window: **View portal**, the Docs section and every "Open in the portal" button open it in your
system browser. What the browser portal cannot do (start runs, build the C4 explorer, generate wikis, scan for
vulnerabilities, answer with AI) is here.

<!-- tour:app -->

## The window

Each project has its own window, served by that project's own local server (see
[how it works](internals.md#the-project-server)). The window has five parts:

| Part | What it does |
|---|---|
| Header | The brand (back to Summary), where you are (`project › section`), **View portal**, **Search or go to…** (<kbd>Ctrl</kbd> <kbd>K</kbd> / <kbd>⌘</kbd> <kbd>K</kbd>) and **⋯**. The header is the window's title bar: drag it to move the window |
| Rail | One button per project of this machine, with its initials. Another project opens **in this window**: the app starts that project's server, moves the window to it and stops the old one. A project that is not on disk is greyed out. **+** opens the start screen |
| Sections | Summary, Board, Plan, Interviews, Team, Quality, Libraries and Docs; then, under **This app**, Machine, Guide and (only in a checkout of the kit) Kit dev. Hover one to see its shortcut |
| Main area | The section you are in |
| Jobs panel and status bar | What runs now and the last jobs, with their output; the status bar shows the first running job and the kit's version |

The **⋯** button opens the app menu under itself: **Projects…** (the start screen, also <kbd>Ctrl</kbd>/<kbd>⌘</kbd>
<kbd>Shift</kbd> <kbd>O</kbd>), **Open in the browser** (this project's portal) and Quit. The window remembers its size
and place when you close it and comes back there if that place is still on a screen.

Opening the window at `/desktop/` from a browser shows "This is the desktop app" and a button to the portal: the app's
sections only work inside the app, with its token.

### The jobs panel

Every command a button starts is a **job**. The panel at the bottom shows one line — the first running job, or the
most recent one — with its state (**Running**, **Done**, **Failed**, **Stopped**), its label and its age, and "+N" when
more are running. **History** unfolds the last six; pick one to read its output, live while it runs. **Stop** appears on
jobs that are processes the app started (a command, a Kit dev task) and stops the command with everything it started
(agents, npm, git). Work the server does itself (a documentation run, a build, a wiki, the first-run setup) has no
Stop there: a run is cancelled from Plan and the first-run setup from its own **Cancel**.

Inside a section, a command's card shows the same thing: a state chip, the error in words when it failed, and a folded
**Output** that opens by itself on a failure.

### Moving around with the keyboard

| Keys | Goes to |
|---|---|
| <kbd>Ctrl</kbd> <kbd>K</kbd> / <kbd>⌘</kbd> <kbd>K</kbd> | The palette: a section, another project, an action or, once you type, any command and any chapter of this guide |
| <kbd>g</kbd> then <kbd>s</kbd> <kbd>b</kbd> <kbd>p</kbd> <kbd>i</kbd> <kbd>t</kbd> <kbd>q</kbd> <kbd>l</kbd> <kbd>d</kbd> | Summary, Board, Plan, Interviews, Team, Quality, Libraries, Docs |
| <kbd>g</kbd> then <kbd>m</kbd> <kbd>h</kbd> <kbd>k</kbd> | Machine, Guide, Kit dev (in a checkout of the kit) |

The second letter has to come within a second and a half of the <kbd>g</kbd>. Shortcuts are ignored while you type in a
field or a dialog. In the palette, <kbd>↑</kbd> <kbd>↓</kbd> move, <kbd>Enter</kbd> goes and <kbd>Esc</kbd> closes;
the search ignores accents and case, and every word must match. A command picked there opens in its section with its
form ready.

### Light, dark and language

The app follows your system's light or dark theme and changes with it. Its language is the one in Machine ›
Language and models (Spanish or English), the same setting the terminal wizard uses.

## The start screen

Outside a project — `camaron app` in any other folder, the rail's **+**, or **Projects…** in the menu — the app asks
one thing: **What do you want to document?**

### Pick a folder

**Choose…** opens a folder dialog. The app then looks at the folder (`camaron projects --inspect`, which only reads)
and tells you what it found before it touches anything:

| It found | Badge | What Continue does |
|---|---|---|
| A project that already has `cam-docs` (or you picked `cam-docs` itself) | Already documented | Registers it and opens it |
| One git repo, or a folder inside one | Existing code | Creates `cam-docs` next to the repo, in its parent folder, and names the sibling repos you can add next |
| A folder that holds repos | Existing code | Lists them and creates `cam-docs` in that folder |
| Code that is not in git | Existing code | Nothing: it says the code is not in a repository and offers **Initialise git here** (`git init` in the folder, or in each first-level folder with code; no commit, no push), then looks again |
| An empty folder | New project | Creates a project with no code yet: you document the design first |
| Your home folder or a disk root | — | Refuses, and says why: `cam-docs` and the repo analysis would land there |

You can change the **Project name** (it starts as the folder's name) and press **Continue**, which runs
`camaron projects --adopt` and opens the project's window.

### Join my team's documentation

Paste the URL of the team's **cam-docs** repo — the documentation's, not the code's — and pick where to put it.
The app runs `camaron join … --no-open` with your own git credentials first. If the host asks for credentials git
does not have, an https URL gets a token field ("GitLab: read_repository + write_repository · GitHub: repo"); the
token travels only in an environment variable, and is saved in the system keychain once git gets in with it. An SSH
URL asks you to set up your SSH key instead. Other refusals are said in words: no access, not found, no network, or a
folder that already has another `cam-docs`.

### Recent

Every project registered on this machine, with **Open**, or "not on disk" when its folder is gone.

## The first-run wizard

A project that is not set up yet opens on the first-run wizard (`#/start`), full width, with no rail. Its place is
saved in the project (`firstrun.json`), shared with the terminal wizard: close the app halfway and you come back to the
same step, in either of them. Until it is finished, the Summary offers **Continue setting it up**.

| Step | What happens |
|---|---|
| Repos | The repos to document: the ones already in the project are ticked, the ones found in the folder are not. Add a code repo by URL (its name and branch fill in). At least one is needed, except in an empty folder |
| Tools | What this machine has and lacks: required tools ticked and locked, the recommended ones picked when missing (one agent CLI is enough), plus the kit's pinned tools |
| Install | Starts by itself: installs what you picked, saves the components, writes the templates, sets the project up and syncs the plan, with a progress bar and the live log. **Cancel** stops between steps. Repos that could not be cloned show the Tokens card right there, with their host filled in |
| Stack | Each repo's stack as read from its manifests; the pencil fixes a wrong one. Never blocks |
| Architecture | A first C4 draft from static analysis, no AI: repos, databases and brokers, relations. **Save draft**, **View diagram ↗**, **Save and improve with AI** (opens your agent in a terminal on the C4 model) or **Skip** |
| Ready | Closes the first run with a checkpoint commit. **Go to the next step** lands on the Summary |

A new project in an **empty folder** goes Repos → Tools → Install → Ready (nothing to read yet). A project you
**joined** goes Tools → Install → Ready, since the team already decided the rest — and skips the wizard entirely when
this machine already has every repo and tool.

## Summary

The project at a glance and the one thing to do next (`#/summary`, <kbd>g</kbd> <kbd>s</kbd>).

<!-- go:summary -->
<!-- tour:summary -->

**Next step** is the same next step the terminal wizard suggests: a unit left half done first, then the next ready
unit, then pages waiting for review, then nothing ("All caught up"). Its button depends on what the step is:

| The step is | The button |
|---|---|
| A unit an agent does | **Start with {agent}** or **Continue with {agent}** (pick the agent when you have two or more): it opens the agent in its own terminal on that unit |
| An interview, before anyone chose how interviews run | **Choose how the interviews run** → Interviews |
| Setting the machine up (`setup`) | **Prepare the machine** → Machine |
| The team's answers (`answers`) | **Collect the answers** → Interviews |
| CI (`ci`) | **Set up CI** → Team |
| Human review (`confirm`) or pages waiting | **Review in the portal** |
| Building the portal (`portal`), or nothing left | **Read the docs** |
| Anything else | **See the plan** |

With no agent installed, the card says so and offers **Prepare the machine**. Below it: a warning when the last check
found something missing on this machine or a kit file out of place (**See it in Quality**), and three figures: the
plan (done of total), pages to review (linked to the portal's Review) and jobs running.

## Board

The project's Kanban, stored in `cam-docs/backlog/` and versioned with the docs (`#/board`, <kbd>g</kbd> <kbd>b</kbd>).
The app writes to it with its own token. The [portal's Board](portal.md#board) shows the same cards, with filters.

<!-- go:board -->
<!-- tour:board -->

A project without a board shows **Turn the board on** (`camaron board init`). With a board:

- **Six columns**: Backlog, Ready, In Progress, In Review, Done, Blocked. A card shows its id, type (Epic, Story, Bug,
  Spike, Task), priority, title, its parent (`↳ WI-3`) and who it is assigned to.
- **Move a card** by dragging it, or with the keyboard: arrows pick a card, <kbd>Space</kbd> grabs it, arrows move it,
  <kbd>Enter</kbd> or <kbd>Space</kbd> drops it, <kbd>Esc</kbd> puts it back. <kbd>Enter</kbd> on a card you did not
  grab opens it.
- **The start gate.** Moving a card into In Progress checks that its dependencies are done and that the files it
  touches do not collide with work already in progress. If something blocks it, the app names the blockers and asks
  whether to move it anyway; yes forces the move (and the forced move is counted).
- **Open a card** to read its description, its acceptance criteria and its definition of done. A story lists its tasks
  and has **Add a task**. **Delete** takes the card off the board after asking: its file moves to
  `backlog/archive/tasks` (its tasks stay).
- **Add** (top) creates an item: type, title, what it goes under (a task under an epic or a story; a story, bug or
  spike under an epic) and priority.

Writing stories with their subtasks and waves happens in the [portal's Stories](portal.md#stories).

## Plan

Run the documentation plan and see every unit (`#/plan`, <kbd>g</kbd> <kbd>p</kbd>). See
[the plan and the harness](internals.md#the-plan-and-the-harness) for what a unit is.

<!-- go:plan -->
<!-- tour:plan -->

A project with no plan offers **Create the plan** (`camaron plan sync`). Otherwise, from the top:

**Run the plan.** **Run the ready ones** starts a documentation run: several units at once (**At once**, 1–4,
default 2), each discovery, repo brief and flow in its own copy of `cam-docs`, merged back when it ends. **Options**
holds sessions per agent (`claude=2,codex=1`), a maximum number of units and whether to include the interviews.
**Autopilot** does one unit after another instead, unattended. Both are off while no unit is ready. While a run is on,
the card shows its progress and **Cancel the run** (agents stop, their units go back to the queue, their work is kept);
while the autopilot is on, **Stop the autopilot**. Only one run exists at a time, from the app or the terminal.

**Keep it current.** **Start with {agent}** opens a session that updates the docs with what changed in the code since
they were written.

**The units.** Done of total, and every unit as a card on a **Board** (Ready to start, Running, Need you, Waiting for
others, Done), by **Phases** or on the **Canvas** (below). Colours: running amber, paused dimmed amber, done green, blocked red, awaiting your
approval violet, waiting for others dashed. Pick a card to open its detail: phase, who does it, its repo, what it
depends on, its notes and, when its terminal is open, what the agent is doing now (the tool and file of its last step,
or that it is waiting for you). The detail's button moves it:

| The unit | Button |
|---|---|
| Awaits approval | **Approve**: the units after it may start |
| Blocked | **Retry**: back to the queue |
| Done | **Redo**: reopened for its agent (`camaron plan redo`) |
| Started, terminal closed (paused) | **Continue** its conversation, or **Start over** |
| Ready | **Start** with the agent you pick |
| An interview before the mode is chosen | **Team questionnaire** or **Live, with an agent** |

**See its log in the portal** opens the unit in the portal's Pipeline.

**The canvas.** The third view, beside Board and Phases: the units as a graph with their dependencies. While a run is
on (the autopilot or **Run the ready ones**), each unit an agent works on opens in its node as a **read-only terminal**
with what it does, line by line (✎ edits, ⌕ reads or searches, ▶ runs, » says, ✕ fails), its agent, the time it has
taken and its cost. About 4 seconds after it ends it folds back into a compact card with its time and cost (**View
terminal** opens it again); a failed unit keeps its terminal. Scroll up inside a terminal and it stops following the
end until you press **Jump to the end**; **⤢** maximises it and Escape goes back to the canvas. **Fit** frames every
open terminal (every unit when none is open), **Re-layout** puts the whole canvas back in its automatic layout, and the
positions you drag are kept while that project's window stays open. Tab and the arrows move between nodes and Enter
opens the unit's detail. With no view picked, the Plan turns to the canvas as soon as something runs (when you arrive,
or started from the Plan itself) and stays there, also when it ends, until you pick another view. The canvas reads the
run's log (the same one the portal reads) and follows the app's light or dark theme; stopping stays on the **Run the
plan** card.

**Plan from zero**, under the units. What the plan has cost since it started (or since the last wipe), for the whole team: agent time
unattended, time with a person, calendar time, tokens and API-equivalent dollars, the most expensive units and a table
by phase. **Update** first collects this machine's agent sessions. What could not be measured or priced is named, never
counted as 0.

**All commands** holds the rest of the plan's commands (`plan`, `wiki`, `pr`, `runs`), each with a form.

**Start the docs again.** For docs written by an older kit: **Redo** reopens every finished unit for its agent to review
with today's playbook (nothing is deleted); **Wipe and start over** tags `cam-docs` in git, deletes the generated pages,
the C4 model, the wikis and the runs' state and starts the plan over, keeping the interviews, the pages a person wrote or
confirmed, the board and the review comments. **See what it would do** comes first; then a dialog repeats the list.

<!-- cmd:docs -->

## Interviews

How the interviews run and how the team's answers come in (`#/interviews`, <kbd>g</kbd> <kbd>i</kbd>).

<!-- go:interviews -->
<!-- tour:interviews -->

Until someone chooses, the section asks **How do you run the interviews?**: a **Team questionnaire** (the team answers,
then an agent consolidates) or **Live, with an agent**. Once chosen you can switch. In questionnaire mode:

- the questionnaire's state: questions, people who answered, and how many questions have no agreement;
- **Answer in the portal** opens the portal's Interview, where each person answers;
- **Export the form** writes an offline HTML form (`camaron interview export`) and shows it in your file manager;
- **Import answers** picks the answer files people sent back (`camaron interview import`);
- **Close the round** marks the answers unit done once someone has answered.

Below, **Interviews with an agent** lists the interview units with the same buttons as in Plan.

## Team

The team's `cam-docs` repo and what came with it (`#/team`, <kbd>g</kbd> <kbd>t</kbd>).

<!-- go:team -->
<!-- tour:team -->

**The team's repo.** Paste its URL and **Save** (`camaron remote`). With a remote, three figures — to send, to bring
in, not saved yet — and **Share now** (a checkpoint, then your work rebased on the team's and pushed), **Check** (asks
the remote what is new) and **Share every time progress is saved** (`camaron share --auto on|off`, this machine only).
A conflict is undone and nothing is touched; something that looks like a secret is not published.

**What came with the team's repo.** Hooks, MCP servers, settings, skills, files and plugins in `cam-docs` that the kit
did not write wait here until you approve them on this machine: **Approve (n)** lists them and runs
`camaron trust --yes`. Approvals live in `~/.camarones/trust/`, never in the repo. **Method hooks in Claude Code**
turns the kit's three hooks on or off (`camaron hooks`).

**Plugins.** The kit's (Gemini, Confluence, Notion) and the team's (`.camarones/plugins/`), with what each brings,
whether it runs code or sends the docs out, and its state here. **Enable**/**Disable** only affect this machine.

**All commands** has board, checkpoint, ci, export, portal, removed and translated.

## Quality

The project's health in one board: this machine, the docs and the code (`#/quality`, <kbd>g</kbd> <kbd>q</kbd>). It
reads `camaron health`, which needs no AI.

<!-- go:quality -->
<!-- tour:quality -->

At the top, a verdict ("Outdated pages: 3 · Critical or high vulnerabilities: 2", or "Everything checked is in order")
and **Check everything** (`camaron health --refresh`). Then three areas, each with a state, two figures and **Open**:

| Area | States | Figures | What Open reveals |
|---|---|---|---|
| Machine | Ready · Review · At risk | tools, missing | **Requirements and tools**: what is missing first, each with **Install** (`camaron doctor --install …`), **Install the pinned ones** (`camaron setup`), **Check again**, and kit files out of place with **Repair**. **Kit files**: **Repair** |
| Documentation | Up to date · Review · At risk | outdated pages, to review | **Outdated pages** (each with **Still holds**, or **Add a unit that refreshes them**), **Control questions (AI)** (confirm golden questions, ask them, or **Propose questions with {agent}**), **Context of each session** (the tokens every agent session loads against the budget), **Pages to review** (portal), **Generated blocks** (refresh them) and **With and without cam-docs (AI)** (the same question asked twice) |
| Code | Healthy · Review · At risk | libraries, critical or high | **Repos**: per repo its SonarQube quality gate (Passed, Warning, Failed) or whether it uses Sonar, coverage (Sonar's, else its local reports) with its date, vulnerabilities by severity and technical debt, and **See full →** (the portal's page for the repo). **Libraries** → the Libraries section |

A repo that uses SonarQube but has no token saved shows **Connect SonarQube**, which opens Machine › Tokens with the
server filled in. A figure that could not be read shows "—", never 0. Below the board: **See the KPIs** (portal) and
**All commands** (the analysis and check commands: check, graph, pages, schemas, radar, history, kpis, stats…).

<!-- cmd:health -->
<!-- cmd:check -->

## Libraries

Every repo's dependencies, read from its manifests and lockfiles without AI (`#/libs`, <kbd>g</kbd> <kbd>l</kbd>).

<!-- go:libs -->
<!-- tour:libs -->

- **Scan for vulnerabilities** runs `camaron inventory --cves` (OSV-Scanner with its offline database, downloaded once);
  **Reread from the code** runs `camaron inventory`. The scan goes repo by repo — the one it is diving into, how many
  are done, a bar and **Stop** — and ends on a tick with what it found ("5 repos checked · 3 libraries with known
  advisories", and the repos it could not scan). Leave Libraries and come back while it runs: it picks its progress up.
  Without OSV-Scanner on the machine the libraries are reread, without vulnerabilities, and it says so.
- Filters: search, category, service, scope and **Vulnerable only**. The table is library × service, the worst first,
  with a chip when two repos use different versions.
- Open a library: **Why it is here** (which repo declares it, in which manifest, with which range and scope) and **Why
  it is flagged** (each advisory with its severity, affected versions, dates, CWE, full text and links).
- **Update** proposes the version that fixes every advisory, asks once and runs `camaron bump`: a new branch
  `camaron/bump-<library>-<version>` in that repo, with no commit and no push. A repo with uncommitted changes is
  left alone.

## Docs

Reading is the portal's; this section opens it and does the work it cannot (`#/docs`, <kbd>g</kbd> <kbd>d</kbd>).

<!-- go:docs -->
<!-- tour:docs -->

- **Read the docs**, **Review drafts** and **Search or ask** open the portal in your browser.
- **Build the C4 explorer** builds the interactive LikeC4 map the portal shows under Architecture; **View** opens it.
- **One block per repo**: **Generate the wiki** writes that repo's OpenWiki. When the repo was not chosen for a wiki,
  it chooses it; when it has no brief yet, it writes a starter brief without AI first. It is off, with the reason,
  when the repo is not cloned, no wiki engine is installed, or another repo's wiki is being generated (one at a time).
  Once the wiki has pages: **View** and **Wiki graph · {repo}** (build its graph).
- **Ask with AI** answers a question only from the docs, through this machine's agent, and lists its sources as
  buttons to the portal. It waits up to 90 seconds; `ask.ai: false` in `workspace.yaml` turns it off and `ask.model`
  picks the model.

<!-- portal:#/docs -->

## Machine

This machine and this project's setup (`#/machine`, <kbd>g</kbd> <kbd>m</kbd>).

<!-- go:machine -->
<!-- tour:machine -->

| Card | What it does |
|---|---|
| Guide and tour | Opens this guide, or the tour of the app |
| Prepare this machine | **Run setup** (`camaron setup`): tools, repos, agent wiring, with a progress bar |
| Language and models | The language of the AI sessions, the Claude Code model and the Codex model (Codex's own list, or **Other…** to type one). Each change is `camaron config set` |
| GitLab, GitHub and SonarQube tokens | Saved hosts with **Test** and **Delete**; a form (host, kind, token) whose **Check and save** checks the token against the server first (**Save it anyway** if you insist). Tokens live in the system keychain, never in the project and never on a command line. SonarQube only over https (http only on localhost) |
| Repos and plan | Each repo, cloned or not, with its stack (edit it, or **Back to detected**); **Clone or pull the repos** (`sync`), **Detect repos in the folder** (`detect`) and the plan's profile, quick or full |
| The kit | **Update the kit** (`self-update`, global install only) and then **Restart the app on the new version**; **Repair the kit's files** (`repair`) |
| All commands | down, upgrade, version; with care: migrate, unlink |
| Uninstall this project | **See what it would remove** first; then **Uninstall** opens a dialog that repeats the list. Optional: also this machine's settings, tokens and caches, and without a backup. By default a `.zip` backup of `cam-docs` goes to the system's temporary folder, and an existing board is kept (copied next to the repos) |

The address `#/machine?host=<host>&kind=sonarqube` (or `gitlab`, `github`) opens the Tokens form filled in.

<!-- cmd:setup -->

## Guide

This guide (`#/guide`, <kbd>g</kbd> <kbd>h</kbd>): how to use Camarón, this app, the portal, how it works inside and
the command reference, in the machine's language, from the kit installed on this machine. The search looks in every
guide; buttons under a paragraph take you to what it describes, and **Show me** starts a tour that points at the real
controls. The same guides are copied into each project's `docs/guides/`, so the portal and the agents read them too.

## All commands

Plan, Team, Quality and Machine end with **All commands**, folded: the commands of that area that no card already runs,
each with a form built from the CLI's own parser (`camaron catalog`). A flag becomes a checkbox, a choice a dropdown, a
number a number field; `--yes` and `--json` are never fields. Commands that delete or move data come last, under
**Careful: these delete or move data**, with a red **Run**; they and any command with `--yes` ask first in a dialog — unless the form asks only for a
dry run. The result is the command's own output, in the card and in the jobs panel.

The palette reaches every one of them: a command with a card opens its section; the rest open their card in **All
commands**, scrolled into view.

## Kit dev

Only in a checkout of the kit (`uv run --script .camarones/camarones.py app` from the kit's repository), not in the
global install. It is the bench for changing the kit:

- **Sandbox**: the Spring PetClinic project in `$CAMARONES_SANDBOX` (default `~/projects/camarones-sandbox`). **What
  the kit left** lists the traces after an uninstall, **Open the wizard on it**, **Reset the sandbox** (asks first) and
  a line to run any catalog command on it.
- **Tests**: `pytest` with a `-k` filter and paths under `tests/`, with a tally.
- **Builds**: `npm ci`, `npm test` and `npm run build` for the portal and this app, **Do the builds match?** (the
  committed builds against the repo) and the main process tests (`node --test`).

## When something fails

| You see | What to do |
|---|---|
| `the desktop app needs Node.js >= 22` | Install Node 22 (`camaron doctor --install node`) and run `camaron app` again |
| The start screen instead of your project | You were outside the project's folder: open it from **Recent** or **Pick a folder** |
| "This code isn't in a git repository" | **Initialise git here**, then Continue |
| "I can't create the project here" | You picked your home folder or a disk root: pick the folder that holds your repos, or an empty one |
| "I could not start the project's server" | The box shows the server's error; `camaron doctor` in that folder usually says what is missing |
| A button you expected is not in the browser portal | On purpose: the browser portal runs nothing on your machine. Do it here |
| You want Electron downloaded again | Delete `~/.camarones/desktop` and run `camaron app` |

On Linux with restricted user namespaces (Ubuntu 24.04 and later) the kit starts the app with `--no-sandbox`; its
windows only ever load your project's local server.
