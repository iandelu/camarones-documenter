# 🦐 Camarón — Tutorial
Español abajo · English first.

## English

### 1. 🦐 Camarón: the big picture

```text
   your repos            the wizard              your AI               result
  +---------+          +-------------+       +------------+       +--------------+
  | repo-a  |--+       |             |       |  Claude    |       |  cam-docs/   |
  | repo-b  |--+-----> |  CAMARONES  | ----> |  Code  or  | ----> |  docs, C4    |
  | repo-c  |--+       |  (wizard)   |       |  Codex     |       |  wikis, ADRs |
  +---------+          +-------------+       +------------+       |  flows       |
                        installs, plans       reads the code       +------+-------+
                        and saves progress    and writes docs             |
                                                                          v
                                                                   +--------------+
                                                                   |  web portal  |
                                                                   +--------------+
```

Camarón turns several repos into living documentation that serves both people and AIs. You don't write the docs: the wizard prepares everything, your AI (Claude Code or Codex) analyses the code and writes, and you review and confirm. Everything lives in the cam-docs/ folder next to your repos: its own git repo with the docs and the tool configuration, meant to be shared with the team. Your service repos get no kit files.

### 2. 🧭 The wizard and the work plan

```text
   PLAN  (cam-docs/docs/.work/plan.yaml)
   [x] setup                       <- done by the wizard
   [x] discovery:repo-a            <- 1 AI session = 1 unit
   [>] discovery:repo-b   ...      <- half done: resumes by itself
   [ ] interview-context           <- the AI asks you questions
   [ ] arch-system
   [ ] flows-catalog  ...

   session 1 --> [x]   session 2 --> [x]   session 3 --> [>] (closed)  --> session 4 resumes
```

Documenting a project in depth doesn't fit in one AI conversation, so the work is split into small units. Every “🦐 Next step” opens a session that does ONE unit. The AI saves checkpoints while it works: if you close the terminal or the laptop, next time you get “▶ Continue” and it resumes from the last checkpoint. Each finished unit is committed locally in cam-docs so nothing is lost; “🤝 Share with the team” (or `camaron share`) pulls the team's work and publishes yours when you decide. Want a different plan? `.camarones/pipeline.yaml` lets you drop, add or rewire units without touching the kit (the command guide has examples). The interviews don't hold you up: what depends on them is drafted first and refined once you have them. In a hurry? `camaron run` does several units at once, each in its own copy of cam-docs, and `camaron kpis` tells you what it cost and whether it was worth it; `camaron plan cost` adds up what the plan took from zero (tokens, hours and dollars, for the whole team). `camaron eval` tests the docs with golden questions the team approves, and `camaron ab` compares the same question with and without cam-docs.

### 3. 🗂 The menu: daily work on top, the rest in sections

```text
   What shall we do?
   > Next step (AI session)           <- the cursor is already on the recommended one
     Review & verify pages (3)
     Portal  /  Wikis  /  Update  /  Share

     Plan & docs           >   plan, status, redo, diagram, stack
     Team                  >   questionnaire, stats, CI
     Settings              >   repos, tokens, environment, AI model, language, update, undo

     Tutorial  /  Exit                  Esc = one level back
```

On top there is only what you use every day, and the cursor already points at the recommended action (continue what was left half done, the next step, or review), so often Enter is all it takes. The rest lives in three sections: “Plan & docs” (the plan, status, redo a step, the quick diagram and each repo's stack), “Team” (questionnaire, usage stats and CI) and “Settings” (repos, tokens, install or repair the environment, AI model, language, update Camarón and undo everything). Next to each section you see what is inside. Esc goes one level back; on the main menu it asks before leaving.

### 4. 🤖 Claude Code / Codex: your AI

```text
        +-----------------------------+
        |  > Follow docs/.work/       |      reads:  code, config, OpenAPI,
        |    next-prompt.md           |              graph, wiki, your answers
        |                             |
        |  * reading repo-a ...       |      writes: cam-docs/docs/*.md,
        |  * question: who calls      |              C4 diagrams, repo pages
        |    this endpoint?           |
        +-----------------------------+      you only need ONE of them
```

Claude Code (Anthropic) and Codex (OpenAI) are agents that work in your terminal: they read code, run commands and write files. Camarones gives them the instructions for each unit (PLAYBOOK) and the format rules (CONVENTIONS). One of them is enough. With none, you can copy the prompt and paste it anywhere. OpenCode (the way to local models, such as Qwen on Ollama) and Gemini CLI work too; `camaron doctor --local` proposes a local model that fits your computer's memory. Later, when you implement features, the AI looks the docs up through the “camarones” MCP server (ask with citations, search, read a page or just the section it needs, repo graph), also with Claude Code opened inside a single repo.

### 5. 📖 OpenWiki: each repo's wiki

```text
   cam-docs/wikis/repo-a/     <- the wiki lives here, versioned with the rest of the docs
   +-- overview.md        "The service exposes /orders"  [evidence: OrderController.java:42]
   +-- modules/...        "Publishes OrderCreated"       [evidence: OrderEvents.java:17]
   +-- .claims/*.json     <- every claim points at the code

   repo-a/openwiki  -->  link to cam-docs/wikis/repo-a (not versioned in the repo)

   generate or update:  app > Docs > Generate the wiki  |  wizard > Wikis  |  camaron wiki repo-a
   read it:  portal (browser) > Docs > Wikis
```

OpenWiki writes a standard wiki for each repo where every claim is anchored to a file and line of code, so the AI can't make things up and anyone can check. The wiki is stored in cam-docs/wikis/<repo>, so the service repo stays clean. Generate or update it from the app (Docs › “Generate the wiki”, with a live log), from the wizard (📚 Wikis) or with “camaron wiki <repo>” in a terminal; you read it in the browser portal (Docs › Wikis), where its pages show up as repos/<repo>/. Each wiki is a full agent run, so only the repos you choose get one (wizard > Wikis > choose), and the first one waits for the repo-brief, which gives it the repo's role and glossary. “Generate the wiki” in the app starts one anyway: it chooses the repo and writes a starter brief without AI when they are missing, and it stays closed, with the reason, if the repo is not cloned or no wiki engine is installed. `camaron wiki <repo>` does neither: it needs the repo cloned, an engine and, for the first run, the brief (or `--force`). They run one at a time. Camarones fills what OpenWiki doesn't cover: the whole-project view, domain, business flows, deployment and decisions.

### 6. 🕸 graphify: the code graph

```text
          (OrderController)
                 |
                 v
          (OrderService) -----> (PaymentClient) ----> repo-b
                 |
                 v
          (OrderRepository) --> [orders table]

   graphify query "who calls PaymentClient?"

```

graphify walks the code and builds a graph: classes, functions, calls and cross-repo dependencies. The AI uses it to answer questions without reading thousands of files, and you explore it in the portal's “Code graph” view, in the Architecture zone (all repos together or one at a time). A git hook keeps it up to date, or run `camaron graph` (in the app: Quality › All commands).

### 7. 🏗 LikeC4: architecture diagrams (C4 model)

```text
   Level 1 CONTEXT       [Customer] --> ( Your system ) --> [Payment gateway]
                                           |  zoom
   Level 2 CONTAINERS     +----------------v------------------+
                          | [web] -> [api] -> [orders] -> DB  |
                          |                    |  Kafka        |
                          +--------------------|---------------+
                                               |  zoom
   Level 3 COMPONENTS               [Controller] -> [Service] -> [Repository]
```

C4 draws architecture at zoom levels: the system and who uses it (context), the applications and databases (containers) and the parts of each application (components). LikeC4 keeps it as code in docs/architecture/*.c4: one model generates every diagram, so they never contradict each other. You browse it in the portal under Architecture › C4 model. After installing you'll see an automatic first draft (“Does it look right? Shall I save it?”). The AI also queries the model while it writes, through the “likec4” MCP server (who calls this service? what sits between A and B?).

### 8. ✅ Review & verify: how much to trust each page

```text
    AI writes          you review              confirmed              someone edits it
   +----------+      +------------+         +-------------+         +----------------+
   |  draft   | ---> |  I read it | --ok--> | source of   | ------> | re-confirm     |
   |   (AI)   |      |            |         | truth       |         | (change seen)  |
   +----------+      +-----+------+         +-------------+         +----------------+
                           | something wrong
                           v
                   "request changes" --> the AI fixes it in the next session
```

Every page has a trust mark. ✨ Draft: written by the AI, nobody reviewed it. ✅ Confirmed: a person read it and said “looks right”; from then on AIs treat it as the truth and don't rewrite it silently. ⚠️ Re-confirm: a confirmed page changed (by hand, in the portal or by the AI) and needs another look. Review in the portal (Confirm and Request changes buttons on every page; the Review zone lists what's pending) or in the wizard's “✅ Review”. If the code a page cites changes, the page turns suspect and AIs stop reading it until it is refreshed (`camaron fresh`): no information beats wrong information.

### 9. 🧪 Quality gate: what check looks at

```text
   camaron check
     |-- broken links between pages           ERROR
     |-- Mermaid diagrams that don't render   ERROR   (mermaid-cli)
     |-- secrets copied into the docs         ERROR   (gitleaks: blocks commit and portal)
     |-- glossary words to avoid              warning (ERROR with --strict)
     |-- structure: TL;DR, sections, size     warning (ERROR with --strict)
     |-- :::rule blocks whose code is gone    ERROR
     +-- sources, frontmatter, translations   ERROR / warning
```

The AI writes fast and sometimes slips on small things: a link to a page that doesn't exist, a diagram that doesn't render or a token copied from a config file. “camaron check” looks for them when each unit closes and in CI. Secrets are special: while gitleaks finds one, the checkpoint commit and the portal export don't happen (the value is never shown, only file and line). Fill the glossary's “Avoid” column (say “purchase, request” for Order) and check warns wherever those words appear. Pages are written for agents first: a TL;DR under the title, sections that read alone, the ones their skeleton asks for (.camarones/skeletons/) and a size budget; check warns about what is missing. mermaid-cli and gitleaks come with the full install; without them, check says so once and skips that check. Business rules can go in `:::rule` blocks anchored to the method that applies them: if that code disappears, check fails.

### 10. 🌍 Bilingual: English + Spanish

```text
   docs/domain/glossary.md              (English, the official version)
          |  translation
          v
   docs/i18n/es/domain/glossary.md      (Spanish)   status: current | outdated | missing
```

Docs are written in English (best for AIs and mixed teams) and translated to Spanish. Camarones knows which translations are current and which fell behind when the original changed. The portal's language switch changes both the interface and the docs; a page with no translation yet is shown in English with a notice.

### 11. 🌐 The portal: docs as a website

```text
   +----------------------------------------------------------------------------+
   | camarón  / Architecture / C4 model            [ Search  Ctrl K ]  En v     |
   |                                                                            |
   | Ask anything about the project.                                            |
   | I answer with the page it comes from.   [ Where is a date checked?  → ]    |
   |                                                                            |
   | STATE    Confirmed 41/57 · To reconfirm 6 · Drafts 9                       |
   | EXPLORE  [Docs] [Architecture] [Plan] [Quality] [Review]                   |
   +----------------------------------------------------------------------------+
```

The 🦐 portal brings the docs (with search, editing and review), the C4 explorer (under each view, its elements to fix and confirm what the AI drafted), the code graph and the OpenWiki wikis together in one site, in English or Spanish. It has two modes with the same interface: the local portal (`camaron up`, or wizard → 🌐 Portal → 📝 Open the portal), where you can edit, and the read-only export (`camaron portal`) that is deployed with Docker or on any static host. `camaron up --static` shows you the export as is. Everything works offline (on-premise), its fonts too. It follows Cofundo's design system with the Camarón brand, light or dark. Home asks first and shows the project's state; the sidebar always has five zones: Docs (pages and wikis), Architecture (C4, code graph, Data as an ER diagram, and Libraries with known vulnerabilities in red), Plan (the live Pipeline: retry and approve here; run and cancel in the desktop app's Plan, which also shows what the plan has cost so far; the Interview, where each person answers the team questionnaire, and Sync, which shares with the team and brings in their work), Quality (Health, read-only: machine, docs and code, and each repo with its coverage (SonarQube's when a token is saved), vulnerabilities, tech debt and Sonar quality gate; KPIs: confirmed share, pages out of date, AI cost, what the plan took from zero and the questions nobody found; and CI) and Review. The top bar says where you are and Ctrl K jumps to any page, zone or view, or takes the question to Ask. A fresh project offers a first look from the code, no AI, from the app. Ask gives the sections that answer, with citations (it goes by meaning: “database” finds PostgreSQL), and with an agent set up it can also write the answer from them. The “All / Business” switch keeps only the pages about what the system does and why.

### 12. 🖥 The desktop app, by task

```text
   +----------------------------------------------------------------------------+
   | camarón  bench > Summary                    [ Search or go to…  Ctrl K ]   |
   | [BE] Summary      NEXT STEP                                                |
   | [CL] Plan         Discovery of api                                         |
   | [+ ] Interviews   [Claude Code v]  ( Start with Claude Code )              |
   |      Team                                                                  |
   |      Quality      This machine is missing something: gitleaks  ( See )     |
   |      Docs                                                                  |
   |      Machine      JOBS  Done  doctor  just now                 History     |
   +----------------------------------------------------------------------------+
```

`camaron app` (or wizard → 🖥️ Desktop app) opens the app where you operate the project: at the left, the rail with your projects and its sections, by task. Summary (the next step with one button, the one this wizard suggests), Board (the columns from Backlog to Done: move a card by dragging it or with the keyboard, open its description and criteria, and on a story its tasks with Add a task; Delete archives it; Add creates a story, a task…; if the board is not on, the section offers to turn it on), Decisions (the ADRs: frame a decision, gather its evidence without AI, review it part by part and accept it; see “Decisions: the ADRs”), Plan (run the ready units or the autopilot, and the units on a board coloured by state or by phase; a started unit whose terminal is closed stays paused until you continue it, and an open one says what its agent is doing; under the board, what the plan has cost so far), Interviews, Team (the team's repo and sharing, what is left to approve, plugins), Quality (the project's health at a glance: verdict, machine, docs and code, and each repo with its coverage (SonarQube's when a token is saved), vulnerabilities, tech debt and Sonar quality gate; prerequisites and tools kept between visits, context, golden questions, with and without cam-docs, libraries and vulnerabilities, pages out of date), Libraries (scan for vulnerabilities repo by repo, with its bar, Stop and a tick when it ends; why each one is there, its security advisories in full, and Update on a new branch of the repo, not committed) and Docs, which opens the portal in your browser and builds the C4 explorer, generates each repo's wiki and its graph, and answers your questions with AI; below, Machine (setup, language and models, tokens, repos, the kit and uninstall previewed first). Every CLI command is there, with its form under "All commands", its output in the jobs panel and its result; what deletes or moves data sits apart and asks first. Ctrl K / ⌘K goes to a section, another project or a command, and g then a letter (g b, g a, g p, g q…) jumps between sections. Outside a project it opens on the start screen, "What do you want to document?" (see "First run in the app"). "View portal", at the top, opens the portal in your browser: there you read, edit and review, and it is the team's viewer; without the app's token it does not show the buttons for what it cannot do. The first time it installs Electron into ~/.camarones/desktop (needs Node.js); without it the CLI and this wizard work the same.

### 13. 📦 Installing and opening the desktop app

```text
   +----------------------------------------------------------------------------+
   | 1  the kit installed           camaron  (global install, one line)         |
   | 2  Node.js 22 or newer         node --version                              |
   |                                if missing: camaron doctor --install node   |
   | 3  open the app                camaron app                                 |
   |                                (the first time it downloads Electron, ~100 MB) |
   |                                                                            |
   |    inside a project       ->  opens that project                           |
   |    in any other folder    ->  start: pick a folder · join · recent         |
   |    in the wizard          ->  menu › Desktop app                           |
   +----------------------------------------------------------------------------+
```

The app is not installed separately: it comes with the kit. It only needs Node.js 22 or newer (`camaron doctor --install node` installs it with winget on Windows or Homebrew on macOS). Run `camaron app`: the first time it downloads Electron, pinned to one version, into ~/.camarones/desktop, with no admin rights and nothing in your projects. From a project's folder it opens that project; from anywhere else, the start screen (next page). Inside, the header is the window's title bar (drag it to move the window) and your projects sit on the rail at the left: another one opens in the same window, which comes back where you left it. Ctrl or Cmd + Shift + O (or the rail's +) goes back to the start screen, "View portal" opens the portal in your browser and the bar's ⋯ button opens the app menu, with "Open in the browser". It opens on the Summary, or on the first-run wizard if the project is not set up yet; what each section holds is on the page before. A good first step: Quality › Prerequisites and tools to see what is missing. If something fails, the notice says what; deleting ~/.camarones/desktop makes it download Electron again.

### 14. 🚀 First run in the app

```text
   +----------------------------------------------------------------------------+
   |  What do you want to document?                                             |
   |  [ Pick a folder ]  repo · repos · code · empty · has cam-docs             |
   |  [ Join my team's documentation ]  cam-docs URL                            |
   |  Recent: shop  ~/shop/cam-docs  [Open]                                     |
   |                                                                            |
   |  1 Repos > 2 Tools > 3 Install > 4 Stack > 5 Architecture > 6 Ready        |
   |                                           [ Go to the next step ]          |
   +----------------------------------------------------------------------------+
```

The start screen asks one thing: "What do you want to document?". "Pick a folder" takes any folder and tells you what it found before touching anything: several repos (it documents them), a single repo or a folder inside one (it creates cam-docs next to the repo, in its parent folder, and lets you add the sibling repos), an empty folder (a new project: you document the design before coding), a project that already has cam-docs (it opens as is) or code that is not in git (it will not continue and offers "Initialise git here", which runs git init without commits or pushes). Your home folder or a disk root is refused, and it says why. You confirm the name and press Continue. "Join my team's documentation" asks for the cam-docs repo's URL (the documentation's, not the code's); if git has no access it asks for a token, kept in the system keychain and never in the project. "Create project", "Join" and "Add folder" are gone from the app; the CLI keeps `camaron new` and `camaron projects --add`. A project not set up yet opens the first-run wizard in its window, full screen (#/start): Repos (add a code repo with its URL, name and branch), Tools, Install (with progress and Cancel), Stack (editable), Architecture (a no-AI draft you save, view with "View diagram" or improve with AI) and Ready, which takes you to the Summary. If you close the app halfway, reopening resumes where you left off, and the terminal wizard sees the same step; if you go to another section before finishing, the Summary offers “Continue setting it up”. In an empty folder the wizard allows zero repos and skips Stack and Architecture. On the CLI: `camaron projects --inspect FOLDER` says what a folder is, `--adopt FOLDER` turns it into a project and `--git-init FOLDER` puts its code under git; all three accept `--json`, and a refusal comes out as {"error": taken | home | no-git | git-init}.

### 15. ✏️ Where and when you can edit

```text
   WHERE                        WHAT YOU CAN DO                      WHERE IT GOES
   ---------------------------  -----------------------------------  ------------------------
   local portal                 edit, new page, confirm,             cam-docs + local commit
   (camaron up)                 request changes                      (you push it)
   desktop app (Docs)           build the C4 explorer, generate      read in the portal
                                each repo's wiki and its graph,
                                ask with AI
   deployed portal              read and search; "Edit" opens the    merge request in the
   (export)                     file in GitLab / GitHub              cam-docs repo
   your editor / IDE            any .md in cam-docs/docs             cam-docs (plain git)
   the AI (Next step)           only its unit; never overwrites      local commit per unit
                                confirmed pages silently
```

In the local portal, “Edit” opens the markdown with a live preview; saving writes to cam-docs/docs and, with “commit to cam-docs” ticked, makes a local commit (sharing it with git push is up to you). “+ New page” creates a page of your own and “Confirm” signs with your git user name. With Spanish selected you edit the translation. The deployed portal doesn't edit: it's a snapshot of the last export; its “Edit” button takes you to the file in GitLab/GitHub (when cam-docs has a remote), the change goes in as a merge request and CI publishes it again. Editing a ✅ page turns it ⚠️ until someone checks it. Don't hand-edit generated files (llms.txt, llms-full.txt, .status.json, viewers); wikis are better regenerated with “Generate the wiki” (Docs, in the app), since an update can rewrite what you change.

### 16. 🔑 GitLab / GitHub tokens

```text
   OS keychain          --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        list projects       (OK)

   Claude / Codex  ---X--->  token             (never passed to them)
   project folder  ---X--->  token             (never written there)
```

If your repos are private, Camarones needs a token to clone and update them. It is stored in your OS keychain and used only by Camarones' own git commands: never written to the project or git config, never shared with Claude, Codex or other third parties. When you join a team's cam-docs repo, Camarones first tries your own git (keychain, credential manager, SSH keys) and asks for a token only if that is refused. Manage them in “Settings › Tokens”. The agent config that comes with the team's cam-docs gets the same care: hooks, MCP servers, settings and skills the kit did not write are listed when you open the wizard, and Claude Code / Codex only load them once you approve them on this machine (or with `camaron trust`). Approvals live in ~/.camarones/trust/, never in the repo, so nobody can approve them for you with a push. What the kit installed on this machine (its skills, graphify's and OpenWiki's) is recognised without asking, and `camaron repair` puts it back if someone edits or deletes it.

### 17. ⚙️ CI: docs that update themselves

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- what changed in the code?
                  |-- AI updates only the affected pages
                  |-- check --secrets  (a secret stops here: no MR)
                  |-- check (links, diagrams, sources, trust)
                  +-- exports the portal (camaron portal) --> nginx image / Pages
   PR in a repo --> comment, no AI: which pages it leaves out of date
                --> camaron pr propose: an agent proposes the docs in a PR
```

Optional: a pipeline that, after each change in the repos or in cam-docs, updates the affected docs and publishes the read-only portal. So a merge request opened from the deployed portal's “Edit” shows up once merged. Set it up in “Team › CI”. You can also do it by hand with “🔄 Update docs after changes” and “🌐 Portal › 📦 Export the portal”. And on every pull request in a repo, a job without AI comments which pages the change leaves out of date (`camaron pr fresh`).

### 18. 📋 The Board: the work next to the docs

```text
   cam-docs/backlog/
     tasks/wi-42 - Title.md    -> one card (Markdown, Backlog.md reads it)
     board.yaml                -> each card's column and order
   camaron board add story "..." --repo api --doc flows/payment.md
   camaron board move WI-42 Ready
   camaron board story split WI-42 --accept   -> subtasks that do not collide
   camaron board next                         -> what can start now
```

A Kanban versioned with the docs: epics, stories, bugs and tasks with repos, acceptance criteria and linked pages. Turn it on with `camaron board init` (projects without it stay as they were) and use `camaron board add|list|show|move|assign|link|archive|repair`, all with `--json`.

Each card is a Markdown file compatible with Backlog.md, so that tool reads and edits it too. What you link from the docs is watched: the Board tells you whether the page changed since you linked it or is still unconfirmed. In the portal, the “Board” zone (`#/kanban`) has the Kanban, with filters by repo, epic, label and docs state, and the card detail; writing needs the token, which the portal the desktop app opens in your browser carries while the app is open, and `camaron up` prints in the URL (`#cam-token=…`). Without it, read-only.

Stories. The “Stories” zone (`#/stories`) helps you write a story (As / I want / so that) with instant hints, no AI; works out an INVEST verdict by rules; in “Touches” you pick the files and pages it changes (its footprint); proposes subtasks by template with their dependencies and spreads them into waves of tasks that do not collide; and writes nothing to `backlog/` until you approve and save it. In the terminal: `camaron board story lint|invest|split ID [--touch repo:path] [--accept]`, `camaron board next [--n 3] [--story ID|--epic ID]` (what can start now: one wave of tasks that collide neither with each other nor with work in progress) and `camaron board waves`. `--accept` never splits a story that already has subtasks.

The start gate. Moving a card into “In Progress” checks that its dependencies are done and that its footprint collides with nothing already in progress. A person is warned and can go on with `--force` (in the portal and the app, “Move anyway”; it is counted in the usage statistics); an agent (MCP `board_next` and `board_waves`, or the harness) is always refused. A card with children is a container and never blocks its own tasks.

“✨ Suggest with AI” is in all three steps (rewriting the story, the criteria and the subtasks) and only spends when you press it: it only suggests and never decides footprints, dependencies, waves or the verdict. While it thinks the button shimmers and cannot be pressed again (Escape cancels); what it proposes stays in your browser, per story, until you accept or dismiss it, even if you ask for something else, open another story or reload. When it cannot run (no agent installed, no token, or turned off) it shows disabled and says why. Optional settings in `workspace.yaml`: `stories: {ai: false}` turns it off, `stories: {model: …}` picks the model and `stories: {small: {groups, files, repos}}` sets the thresholds of INVEST's “S”. The index `.camarones/.cache/board.db` rebuilds itself and is safe to delete.

Your intern shrimp has pinned the sticky notes up already: all you do is move them.

### 19. 📜 Decisions: the ADRs, with the evidence in front of you

```text
   Decisions (g a)                        docs/decisions/0007-why-jpa.md
   +--------------------------------+     ---
   | 0007  Accepted   Why spring... |     type: decision      x-owner: human
   | 0008  In review  Cache de...   |     ## Status   Accepted (2026-10-28)
   | Candidates: 3                  |     ## Context, Decision, Evidence
   +--------------------------------+     ## Decided by   ana, luis

   problem -> evidence -> review -> accepted
   camaron adr candidates | new | pack | write | accept | reject
```

An ADR writes down why the code is the way it is. The “Decisions” section of the desktop app (`g a`) helps you make the decision with the evidence in front of you and works entirely without AI, with no agent installed. The ADR lives in `docs/decisions/NNNN-title.md` and what the review decides along the way, in `docs/.work/adr/NNNN.yaml`.

Framing. “New ADR” asks for a title and what it is about: new (something the code does not do yet) or retroactive (something the code already does that nobody wrote down). In “Touches” you search the files, code-map groups and doc pages it affects. “Candidates” lists, without AI, the decisions the code already took that no ADR names: data, cache, messaging, security and framework libraries from the inventory, C4 technologies and deployment files (Docker Compose, Helm); “Create a retro ADR” opens one with the title and what it touches already in.

Evidence. The evidence pack gathers what the project already knows about what the ADR touches: neighbouring files in the code graph, the pages that cite them, other ADRs, the last year of commits, C4 elements, libraries and open questions. “Write without AI” writes the proposed ADR from the template with that evidence already in.

Review and decide. The review walks the ADR part by part (approve, edit or defer each section) and each decision point (a question with its options: you pick one, with its reason in one line). You can add points and note the attendees. “Present” (`P`) shows one part per screen in large type to run the meeting while sharing a screen, by keyboard: ←/→ change part, 1–9 pick an option, E edits, D defers, A accepts and Esc leaves. Accepting leaves the file as “Accepted” with the date, owned by a person (`x-owner: human`), confirmed and with “Decided by”, and each point's options, with their pros and cons, go into “Considered options”; rejecting needs a reason and keeps the file; an ADR that supersedes another marks it “Superseded by”. What is not decided cannot be accepted: a deferred point or one with no choice, or no text in “Decision” and no points; sections that still hold a `TODO(question)` do not stop it, but the accept dialog names them.

An ADR written by hand or by another kit (no frontmatter, Spanish headings…) shows in the list with its status and not a byte changes until you accept or reject it in a session; one already accepted, rejected, superseded or deprecated is closed: it opens no session, and changing it takes a new ADR that supersedes it. In the portal each ADR shows its status in the tree and on its page, and the pages an accepted decision cites carry a banner (“pending implementation” for a new decision), also in the static export.

In the terminal: `camaron adr list|new|show|pack|candidates|write|accept|reject`, all with `--json` (`new TITLE --kind new|retro [--problem T] [--touch repo:path] [--supersedes N]`, `accept ID [--attendee NAME]`, `reject ID --why REASON`). The part-by-part review is the app's.

Your intern shrimp has already combed the code for the decisions nobody wrote down: you get the last word.

### 20. 🧰 Supporting pieces

```text
   uv        -> runs Camarones (Python) without installing anything else
   git       -> repos and the docs history
   Node.js   -> OpenWiki, LikeC4 and mermaid-cli (the portal needs no npm)
   gitleaks  -> looks for secrets before every commit and before publishing
   Docker    -> serve the portal like production (optional)
   Java      -> only for Java/Kotlin repos (SDKMAN is detected)
```

The wizard checks all of this and installs it for you (winget on Windows, Homebrew on Mac) when you choose “Install everything recommended”. Only git and Node.js are required. The quality gate (mermaid-cli and gitleaks) comes with the full install; mermaid-cli downloads a headless Chromium the first time. Without AI, the install writes `docs/index.md` (what the project is, a card per repo and the context map) and, for each repo, `docs/repos/<repo>/index.md`: what it exposes (the endpoints map, with the endpoints table folded), what data it stores (ER diagram), its lifecycles (one state diagram per status enum; transitions are never guessed), its messages and what it needs to run (env vars and commands, folded), all read from its files; with topics, also `docs/architecture/messaging.md`. `camaron pages` (`camaron diagrams` is its alias) brings them up to date, and `camaron blocks` and `sync` keep the blocks current. A project from before 4.52 keeps its pages (`reference.md`, `diagrams.md`, `system-map.md`, `first-look.md`, `data/<repo>.md`) until you run `camaron pages --adopt`: it moves the blocks with their confirmations into the new pages, deletes only the kit pages it emptied, never writes a person's page (`x-owner: human` or `x-confirmed`) and lists what it could not touch (pages, links, translations). They are ordinary Docs pages made of generated blocks: a person can confirm one by copying the block's `sha=` value into `confirmed=` and putting their name in `by=` (one word, or quoted when it has spaces: `by="Ana López"`), e.g. `<!-- generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`; the kit then stops rewriting it, and `check` warns when the code has changed since or no longer has the diagram's source. To take the code's version, remove `confirmed=` and `by=` from the marker, run `camaron diagrams` and confirm it again. The portal tells you for each diagram whether it comes from the code, was edited by hand, a person confirmed it, or the code changed. Team extensions go in `.camarones/plugins/` as plugins (`camaron plugins add` brings one in and pins it in plugins.lock); the ones that run code or steer agents are not loaded until you approve them on your machine, and any change asks again. Also without AI: `camaron history` reads the git history (hotspots, who to ask), `camaron doctor --context` counts what every agent session loads and `camaron repair` puts the kit's files back if someone touches them.

### 21. 🗺 Your day to day

```text
   1. camarones              -> opens the project's wizard (cam-docs)
   2. Next step              -> an AI session does the next unit
   3. Portal (camaron up)    -> read, edit, confirm or request changes
   4. Wikis                  -> create or refresh a repo's wiki
   5. Update                 -> when the code changes
   6. Share                  -> pull the team's work and publish yours
```

That's all, and it is all on the top part of the menu. Stop whenever you like: progress saves itself. Esc always goes back.

Is there a new Camarón? “Settings › ⬆️ Update Camarón” (or `camaron self-update`) checks the official kit, tells you what changed and, if you say yes, updates it for every project on this machine and restarts the wizard. Your projects and documentation are not touched. With a local kit copy in the project, `camaron upgrade <new-kit-folder>` brings it up to date and deletes the kit files the new version no longer ships, except the ones your team edited.

Docs from an older kit? `camaron docs reset --redo` reopens the finished units to review them, and `--wipe` deletes what was generated (tagged in git first) and starts the plan over, keeping the interviews and the confirmed pages. In the desktop app, at the bottom of “Plan”.

Want to start over? “Settings › 🧹 Undo everything” (or `camaron uninstall`) zips cam-docs/ as a backup, deletes it, and removes every trace of the kit from the repos and the workspace folder. The repos end up exactly as in their last commit.

## Español

### 1. 🦐 Camarón: la foto completa

```text
   tus repos             el asistente            tu IA                 resultado
  +---------+          +-------------+       +------------+       +--------------+
  | repo-a  |--+       |             |       |  Claude    |       |  cam-docs/   |
  | repo-b  |--+-----> |  CAMARONES  | ----> |  Code  o   | ----> |  docs, C4    |
  | repo-c  |--+       |  (wizard)   |       |  Codex     |       |  wikis, ADR  |
  +---------+          +-------------+       +------------+       |  flujos      |
                        instala, planifica    lee el codigo        +------+-------+
                        y guarda progreso     y escribe docs              |
                                                                          v
                                                                   +--------------+
                                                                   |  portal web  |
                                                                   +--------------+
```

Camarón convierte varios repos en una documentación viva que sirve a personas y a IAs. Tú no escribes la documentación: el asistente prepara todo, tu IA (Claude Code o Codex) analiza el código y escribe, y tú revisas y confirmas. Todo queda en la carpeta cam-docs/, junto a tus repos: es un repo git propio con la documentación y la configuración de las herramientas, pensado para compartirlo con el equipo. Tus repos de servicio no reciben archivos del kit.

### 2. 🧭 El asistente y el plan de trabajo

```text
   PLAN  (cam-docs/docs/.work/plan.yaml)
   [x] setup                       <- lo hace el asistente
   [x] discovery:repo-a            <- 1 sesion de IA = 1 unidad
   [>] discovery:repo-b   ...      <- a medias: se retoma sola
   [ ] interview-context           <- la IA te pregunta
   [ ] arch-system
   [ ] flows-catalog  ...

   sesion 1 --> [x]   sesion 2 --> [x]   sesion 3 --> [>] (cerraste)  --> sesion 4 continua
```

Documentar a fondo un proyecto no cabe en una sola conversación con la IA, así que el trabajo se divide en unidades pequeñas. Cada vez que eliges «🦐 Siguiente paso» se abre una sesión que hace UNA unidad. La IA guarda checkpoints mientras trabaja: si cierras la terminal o el portátil, la próxima vez aparece «▶ Continuar» y retoma desde el último checkpoint. Al terminar cada unidad se hace un commit local en cam-docs para que nada se pierda; «🤝 Compartir con el equipo» (o `camaron share`) trae el trabajo del equipo y publica el tuyo cuando tú decides. ¿Queréis otro plan? En `.camarones/pipeline.yaml` podéis quitar, añadir o reordenar unidades sin tocar el kit (la guía de comandos trae ejemplos). Las entrevistas no te frenan: lo que depende de ellas se escribe antes como borrador y se afina cuando las haces. ¿Con prisa? `camaron run` hace varias unidades a la vez, cada una en su propia copia de cam-docs, y `camaron kpis` te dice cuánto costó y si mereció la pena; `camaron plan cost` suma lo que lleva el plan desde cero (tokens, horas y dólares, de todo el equipo). `camaron eval` examina la documentación con preguntas de oro que el equipo aprueba, y `camaron ab` compara la misma pregunta con y sin cam-docs.

### 3. 🗂 El menú: lo de cada día arriba, lo demás por secciones

```text
   Que hacemos?
   > Siguiente paso (sesion con IA)   <- el cursor ya esta en lo recomendado
     Revisar y verificar paginas (3)
     Portal  /  Wikis  /  Actualizar  /  Compartir

     Plan y documentacion  >   plan, estado, rehacer, diagrama, stack
     Equipo                >   cuestionario, estadisticas, CI
     Ajustes               >   repos, tokens, entorno, modelo IA, idioma, actualizar, deshacer

     Tutorial  /  Salir                 Esc = un nivel atras
```

Arriba está solo lo que usas cada día, y el cursor ya apunta a lo recomendado (continuar lo que quedó a medias, el siguiente paso o revisar), así que muchas veces basta con Enter. Lo demás vive en tres secciones: «Plan y documentación» (ver el plan, el estado, rehacer un paso, el diagrama rápido y el stack de cada repo), «Equipo» (cuestionario, estadísticas de uso y CI) y «Ajustes» (repos, tokens, instalar o reparar el entorno, modelo de IA, idioma, actualizar Camarón y deshacer todo). Al lado de cada sección ves qué hay dentro. Esc vuelve un nivel atrás; en el menú principal te pregunta antes de salir.

### 4. 🤖 Claude Code / Codex: tu IA

```text
        +-----------------------------+
        |  > Sigue docs/.work/        |      lee:  codigo, config, OpenAPI,
        |    next-prompt.md           |            grafo, wiki, tus respuestas
        |                             |
        |  * leyendo repo-a ...       |      escribe: cam-docs/docs/*.md,
        |  * pregunta: ¿quien usa     |               diagramas C4, fichas por repo
        |    este endpoint?           |
        +-----------------------------+      solo necesitas UNO de los dos
```

Claude Code (Anthropic) y Codex (OpenAI) son agentes que trabajan en tu terminal: leen el código, ejecutan comandos y escriben ficheros. Camarones les prepara las instrucciones de cada unidad (PLAYBOOK) y las reglas de formato (CONVENTIONS). Con tener uno instalado basta. Si no tienes ninguno, puedes copiar el prompt y pegarlo donde quieras. También sirven OpenCode (la vía para modelos locales, como Qwen con Ollama) y Gemini CLI; `camaron doctor --local` te propone un modelo local según la memoria de tu equipo. Cuando luego implementéis features, la IA consulta la documentación con el servidor MCP «camarones» (preguntar con citas, buscar, leer una página o solo la sección que hace falta, grafo del repo), también con Claude Code abierto dentro de un solo repo.

### 5. 📖 OpenWiki: la wiki de cada repo

```text
   cam-docs/wikis/repo-a/     <- la wiki vive aqui, versionada con el resto de la doc
   +-- overview.md        "El servicio expone /orders"  [evidencia: OrderController.java:42]
   +-- modules/...        "Publica OrderCreated"        [evidencia: OrderEvents.java:17]
   +-- .claims/*.json     <- cada afirmacion apunta al codigo

   repo-a/openwiki  -->  enlace a cam-docs/wikis/repo-a (sin versionar en el repo)

   generar o actualizar:  app > Docs > Generar la wiki  |  asistente > Wikis  |  camaron wiki repo-a
   leerla:  portal (navegador) > Docs > Wikis
```

OpenWiki escribe una wiki estándar de cada repo donde cada afirmación está anclada a un fichero y línea del código: la IA no se inventa cosas y cualquiera puede comprobarlas. La wiki se guarda en cam-docs/wikis/<repo>, así que el repo de servicio queda limpio. La generas o actualizas desde la app (Docs › «Generar la wiki», con el log en directo), desde el asistente (📚 Wikis) o con «camaron wiki <repo>» en una terminal; la lees en el portal del navegador (Docs › Wikis), donde sus páginas aparecen en repos/<repo>/. Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas (asistente > Wikis > elegir), y la primera espera al repo-brief, que le da el rol y el glosario del repo. «Generar la wiki», en la app, la lanza igual: elige el repo y escribe un brief inicial sin IA si aún no los tiene, y queda cerrado, con el motivo, si el repo no está clonado o no hay motor de wiki instalado. `camaron wiki <repo>` no hace ninguna de las dos cosas: pide el repo clonado, un motor y, en la primera, el brief (o `--force`). Se lanzan de una en una. Camarones rellena lo que OpenWiki no cubre: visión del proyecto entero, dominio, flujos de negocio, despliegue y decisiones.

### 6. 🕸 graphify: el grafo del código

```text
          (OrderController)
                 |
                 v
          (OrderService) -----> (PaymentClient) ----> repo-b
                 |
                 v
          (OrderRepository) --> [tabla orders]

   graphify query "¿quien llama a PaymentClient?"

```

graphify recorre el código y construye un grafo: clases, funciones, llamadas y dependencias entre repos. La IA lo usa para responder preguntas sin leer miles de ficheros, y tú lo exploras en el «Grafo de código» del portal, en la zona Arquitectura (todos los repos juntos o uno a uno). Se actualiza solo con un hook de git, o con `camaron graph` (en la app: Calidad › Todos los comandos).

### 7. 🏗 LikeC4: diagramas de arquitectura (modelo C4)

```text
   Nivel 1 CONTEXTO      [Cliente] --> ( Tu sistema ) --> [Pasarela de pago]
                                           |  zoom
   Nivel 2 CONTENEDORES   +----------------v------------------+
                          | [web] -> [api] -> [orders] -> DB  |
                          |                    |  Kafka        |
                          +--------------------|---------------+
                                               |  zoom
   Nivel 3 COMPONENTES              [Controller] -> [Service] -> [Repository]
```

C4 es una forma de dibujar la arquitectura por niveles de zoom: el sistema y quién lo usa (contexto), las aplicaciones y bases de datos (contenedores) y las piezas de cada aplicación (componentes). LikeC4 guarda todo como código en docs/architecture/*.c4: un solo modelo genera todos los diagramas, así que nunca se contradicen. Lo navegas en Arquitectura › Modelo C4 del portal. Al instalar verás un primer borrador automático («¿Está bien? ¿Lo guardo?»). La IA también consulta el modelo mientras escribe, con el servidor MCP «likec4» (¿quién llama a este servicio?, ¿qué hay entre A y B?).

### 8. ✅ Revisar y verificar: la confianza de cada página

```text
    IA escribe         tu revisas              confirmada             alguien la edita
   +----------+      +------------+         +-------------+         +----------------+
   | borrador | ---> |  lo leo    | --ok--> | fuente de   | ------> | re-confirmar   |
   |   (IA)   |      |            |         | verdad      |         | (cambio visto) |
   +----------+      +-----+------+         +-------------+         +----------------+
                           | algo mal
                           v
                   "pedir cambios" --> la IA lo corrige en la siguiente sesion
```

Cada página lleva una marca de confianza. ✨ Borrador: la escribió la IA y nadie la ha revisado. ✅ Confirmada: una persona la leyó y dijo «está bien»; a partir de ahí las IAs la tratan como verdad y no la reescriben sin avisar. ⚠️ Re-confirmar: alguien cambió una página confirmada (a mano, en el portal o la IA) y hay que volver a mirarla. Puedes revisar en el portal (botones Confirmar y Pedir cambios en cada página; la zona Revisión lista lo pendiente) o en «✅ Revisar» del asistente. Si el código que cita una página cambia, la página queda sospechosa y las IAs dejan de leerla hasta que se actualice (`camaron fresh`): mejor sin información que con información equivocada.

### 9. 🧪 Control de calidad: lo que revisa check

```text
   camaron check
     |-- enlaces rotos entre paginas          ERROR
     |-- diagramas Mermaid que no se dibujan  ERROR   (mermaid-cli)
     |-- secretos copiados en la doc          ERROR   (gitleaks: bloquea commit y portal)
     |-- palabras a evitar del glosario       aviso   (ERROR con --strict)
     |-- estructura: TL;DR, secciones, largo  aviso   (ERROR con --strict)
     |-- reglas :::rule sin su codigo         ERROR
     +-- fuentes, frontmatter, traducciones   ERROR / aviso
```

La IA escribe rápido y a veces falla en lo pequeño: un enlace a una página que no existe, un diagrama que no se dibuja o un token copiado de un fichero de configuración. «camaron check» lo revisa al cerrar cada unidad y en el CI. Los secretos son especiales: mientras gitleaks encuentre uno, no se hace el commit de checkpoint ni se exporta el portal (nunca se muestra el valor, solo fichero y línea). Si en el glosario rellenas la columna «Avoid» (por ejemplo «compra, petición» para Pedido), check avisa donde aparezcan esas palabras. Las páginas se escriben primero para agentes: un TL;DR bajo el título, secciones que se leen solas y las de su plantilla (.camarones/skeletons/), y un tamaño máximo; check avisa de lo que falte. mermaid-cli y gitleaks vienen con la instalación completa; si faltan, check lo avisa una vez y se salta esa comprobación. Las reglas de negocio pueden ir en bloques `:::rule` anclados al método que las aplica: si ese código desaparece, check falla.

### 10. 🌍 Bilingüe: inglés + español

```text
   docs/domain/glossary.md              (ingles, la version oficial)
          |  traduccion
          v
   docs/i18n/es/domain/glossary.md      (espanol)   estado: al dia | desactualizada | falta
```

La documentación se escribe en inglés (lo que mejor entienden las IAs y los equipos mixtos) y se traduce al español. Camarones sabe qué traducciones están al día y cuáles se quedaron atrás cuando cambió el original. El selector de idioma del portal cambia la interfaz y la documentación; si una página aún no tiene traducción, se muestra en inglés con un aviso.

### 11. 🌐 El portal: la documentación como web

```text
   +----------------------------------------------------------------------------+
   | camarón  / Arquitectura / Modelo C4          [ Buscar  Ctrl K ]  Es v      |
   |                                                                            |
   | Pregunta lo que sea del proyecto.                                          |
   | Te contesto con la página de la que sale.  [ ¿Dónde se valida...?  → ]     |
   |                                                                            |
   | ESTADO   Confirmadas 41/57 · Por reconfirmar 6 · Borradores 9              |
   | EXPLORA  [Docs] [Arquitectura] [Plan] [Calidad] [Revisión]                 |
   +----------------------------------------------------------------------------+
```

El portal 🦐 junta en una sola web la documentación (con buscador, edición y revisión), el explorador C4 (bajo cada vista, sus elementos para corregir y confirmar lo que redactó la IA), el grafo de código y las wikis de OpenWiki, en español o inglés. Tiene dos modos con la misma interfaz: el portal local (`camaron up`, o asistente → 🌐 Portal → 📝 Abrir el portal), donde se puede editar, y la exportación de solo lectura (`camaron portal`) que se despliega con Docker o en cualquier hosting estático. `camaron up --static` te enseña la exportación tal cual. Todo funciona sin Internet (on-premise), también sus fuentes. Sigue el sistema de diseño de Cofundo con la marca Camarón, en claro u oscuro. Inicio pregunta primero y enseña el estado del proyecto; el menú lateral tiene siempre cinco zonas: Docs (páginas y wikis), Arquitectura (C4, grafo de código, Datos como diagrama ER y Librerías con las vulnerabilidades en rojo), Plan (el Pipeline en vivo: reintentar y aprobar aquí; lanzar y cancelar, en el Plan de la app de escritorio, que también enseña lo que lleva costado el plan; la Entrevista, donde cada persona responde el cuestionario del equipo, y Sincronizar, que comparte con el equipo y trae su trabajo), Calidad (Salud, de solo lectura: máquina, documentación y código, y cada repo con su cobertura (la de SonarQube si hay token guardado), vulnerabilidades, deuda técnica y la puerta de calidad de Sonar; KPIs: cuánto está confirmado, qué se ha quedado viejo, el coste de IA, lo que lleva el plan desde 0 y las preguntas que nadie encontró; y CI) y Revisión. La barra de arriba dice dónde estás y Ctrl K salta a cualquier página, zona o vista, o lleva la pregunta a Preguntar. Un proyecto nuevo ofrece un primer vistazo desde el código, sin IA, desde la app. Preguntar da las secciones que responden, con su cita (entiende el sentido: «base de datos» encuentra PostgreSQL), y si hay un agente configurado también puede redactar la respuesta con ellas. El interruptor «Todo / Negocio» deja solo las páginas de qué hace el sistema y por qué.

### 12. 🖥 La app de escritorio, por tareas

```text
   +----------------------------------------------------------------------------+
   | camarón  bench > Resumen                    [ Buscar o ir a…  Ctrl K ]     |
   | [BE] Resumen      SIGUIENTE PASO                                           |
   | [CL] Plan         Descubrimiento de api                                    |
   | [+ ] Entrevistas  [Claude Code v]  ( Empezar con Claude Code )             |
   |      Equipo                                                                |
   |      Calidad      A esta máquina le falta algo: gitleaks   ( Verlo )       |
   |      Docs                                                                  |
   |      Máquina      TRABAJOS  Hecho  doctor  ahora              Historial    |
   +----------------------------------------------------------------------------+
```

`camaron app` (o asistente → 🖥️ App de escritorio) abre la app donde se opera el proyecto: a la izquierda el raíl con tus proyectos y sus secciones, por tareas. Resumen (el siguiente paso con un solo botón, el mismo que propone este asistente), Tablero (las columnas de Backlog a Hecho: mueves una tarjeta arrastrándola o con el teclado, abres su descripción y criterios, y en una historia sus tareas con Añadir tarea; Eliminar la archiva; Añadir crea una historia, una tarea…; si el tablero no está activado, la sección ofrece activarlo), Decisiones (los ADR: plantear una decisión, reunir su evidencia sin IA, revisarla por partes y aceptarla; ver «Decisiones: los ADR»), Plan (ejecutar las unidades listas o el piloto automático, y las unidades en un tablero de colores por estado o por fases; una unidad empezada sin su terminal abierta queda en pausa hasta que la sigues, y una abierta dice qué está haciendo su agente; debajo del tablero, lo que lleva costado el plan), Entrevistas, Equipo (repo del equipo y compartir, lo que falta aprobar, plugins), Calidad (la salud del proyecto de un vistazo: veredicto, máquina, documentación y código, y cada repo con su cobertura (la de SonarQube si hay token guardado), vulnerabilidades, deuda técnica y la puerta de calidad de Sonar; requisitos y herramientas guardados entre visitas, contexto, preguntas de control, con y sin cam-docs, librerías y vulnerabilidades, páginas desactualizadas), Librerías (buscar vulnerabilidades repo a repo, con su barra, Parar y un tick al acabar; por qué está cada una, sus avisos de seguridad completos y Actualizar en una rama nueva del repo, sin commit) y Docs, que abre el portal en tu navegador y construye el explorador C4, genera la wiki de cada repo y su grafo, y responde con IA a tus preguntas; debajo, Máquina (setup, idioma y modelos, tokens, repos, el kit y desinstalar con vista previa). Cada comando de la CLI está ahí, con su formulario en «Todos los comandos», su salida en el panel de trabajos y su resultado; lo que borra o mueve datos va aparte y pregunta antes. Ctrl K / ⌘K va a una sección, a otro proyecto o a un comando, y g y una letra (g b, g a, g p, g q…) salta de sección. Fuera de un proyecto abre en la pantalla de inicio, «¿Qué quieres documentar?» (ver «El primer arranque en la app»). «Ver portal», arriba, abre el portal en tu navegador: ahí se lee, edita y revisa, y es el visor del equipo; sin el token de la app no enseña los botones de lo que no puede hacer. La primera vez instala Electron en ~/.camarones/desktop (necesita Node.js); sin él, la CLI y este asistente funcionan igual.

### 13. 📦 Instalar y abrir la app de escritorio

```text
   +----------------------------------------------------------------------------+
   | 1  el kit instalado            camaron  (instalación global, una línea)    |
   | 2  Node.js 22 o superior       node --version                              |
   |                                si falta: camaron doctor --install node     |
   | 3  abrir la app                camaron app                                 |
   |                                (la 1.ª vez descarga Electron, ~100 MB)     |
   |                                                                            |
   |    dentro de un proyecto  ->  abre ese proyecto                            |
   |    en otra carpeta        ->  inicio: elegir carpeta · unirse · recientes  |
   |    en el asistente        ->  menú › App de escritorio                     |
   +----------------------------------------------------------------------------+
```

La app no se instala aparte: viene con el kit. Solo necesita Node.js 22 o superior (`camaron doctor --install node` lo instala con winget en Windows o Homebrew en macOS). Lanza `camaron app`: la primera vez descarga Electron, fijado a una versión, en ~/.camarones/desktop, sin permisos de administrador y sin tocar tus proyectos. Desde la carpeta de un proyecto abre ese proyecto; desde cualquier otra, la pantalla de inicio (la página siguiente). Dentro, la cabecera es la barra de la ventana (arrástrala para moverla) y tus proyectos están en el raíl de la izquierda: otro se abre en la misma ventana, que vuelve a salir donde la dejaste. Ctrl o Cmd + Shift + O (o el + del raíl) vuelve a la pantalla de inicio, «Ver portal» abre el portal en tu navegador y el botón ⋯ de la barra abre el menú de la app, con «Abrir en el navegador». Abre en el Resumen, o en el asistente de primer arranque si el proyecto aún no está preparado; lo que hay en cada sección está en la página anterior. Un buen primer paso: Calidad › Requisitos y herramientas para ver qué falta. Si algo falla, el aviso dice qué; borrar ~/.camarones/desktop fuerza a descargar Electron otra vez.

### 14. 🚀 El primer arranque en la app

```text
   +----------------------------------------------------------------------------+
   |  ¿Qué quieres documentar?                                                  |
   |  [ Elegir carpeta ]  repo · repos · código · vacía · con cam-docs          |
   |  [ Unirme a la documentación de mi equipo ]  URL del cam-docs              |
   |  Recientes: shop  ~/shop/cam-docs  [Abrir]                                 |
   |                                                                            |
   |  1 Repos > 2 Herram. > 3 Instalar > 4 Stack > 5 Arquit. > 6 Listo          |
   |                                           [ Ir al siguiente paso ]         |
   +----------------------------------------------------------------------------+
```

La pantalla de inicio pregunta una sola cosa: «¿Qué quieres documentar?». «Elegir carpeta» acepta cualquier carpeta y te cuenta qué ha encontrado antes de tocar nada: varios repos (los documenta), un repo suelto o una carpeta dentro de uno (crea cam-docs junto al repo, en su carpeta padre, y te deja sumar los repos hermanos), una carpeta vacía (un proyecto nuevo: se documenta el diseño antes de programar), un proyecto que ya tiene cam-docs (se abre tal cual) o código que no está en git (no deja continuar y ofrece «Inicializar git aquí», que hace git init sin commits ni push). Tu carpeta personal o la raíz de un disco se rechazan, y lo explica. Confirmas el nombre y «Continuar». «Unirme a la documentación de mi equipo» pide la URL del repo cam-docs (el de la documentación, no el del código); si git no tiene acceso, pide un token, que se guarda en el llavero del sistema y nunca en el proyecto. «Crear proyecto», «Unirse» y «Añadir carpeta» ya no están en la app; la CLI conserva `camaron new` y `camaron projects --add`. Un proyecto sin preparar abre en su ventana el asistente de primer arranque, a pantalla completa (#/start): Repos (añade un repo de código con su URL, nombre y rama), Herramientas, Instalar (con progreso y «Cancelar»), Stack (editable), Arquitectura (un borrador sin IA que guardas, miras con «Ver diagrama» o mejoras con IA) y Listo, que te lleva al Resumen. Si cierras la app a medias, al reabrir sigue donde lo dejaste, y el asistente de la terminal ve el mismo paso; si te vas a otra sección antes de terminar, el Resumen te ofrece «Seguir con la preparación». En una carpeta vacía el asistente permite cero repos y se salta Stack y Arquitectura. En la CLI: `camaron projects --inspect CARPETA` dice qué es una carpeta, `--adopt CARPETA` la convierte en proyecto y `--git-init CARPETA` pone en git su código; los tres aceptan `--json`, y un rechazo sale como {"error": taken | home | no-git | git-init}.

### 15. ✏️ Dónde y cuándo se puede editar

```text
   DONDE                        QUE PUEDES HACER                     DONDE QUEDA
   ---------------------------  -----------------------------------  ------------------------
   portal local                 editar, pagina nueva, confirmar,     cam-docs + commit local
   (camaron up)                 pedir cambios                        (el push lo haces tu)
   app de escritorio (Docs)     construir el C4, generar la wiki     se lee en el portal
                                de cada repo y su grafo, y
                                preguntar con IA
   portal desplegado            leer y buscar; "Editar" abre el      merge request en el
   (exportacion)                fichero en GitLab / GitHub           repo cam-docs
   tu editor / IDE              cualquier .md de cam-docs/docs       cam-docs (git normal)
   la IA (Siguiente paso)       solo su unidad; no pisa lo           commit local por unidad
                                confirmado sin avisar
```

En el portal local, «Editar» abre el markdown con vista previa; al guardar se escribe en cam-docs/docs y, si marcas «commit en cam-docs», se hace un commit local (compartirlo con git push es cosa tuya). «+ Nueva página» crea una página tuya y «Confirmar» firma con tu usuario de git. Con el idioma en español editas la traducción. El portal desplegado no edita: es una foto de la última exportación; su botón «Editar» te lleva al fichero en GitLab/GitHub (si cam-docs tiene remote) y el cambio entra por merge request, y el CI vuelve a publicar. Editar una página ✅ la pasa a ⚠️ hasta que alguien la mire. No edites a mano lo generado (llms.txt, llms-full.txt, .status.json, visores): las wikis mejor regenerarlas con «Generar la wiki» (Docs, en la app), porque una actualización puede reescribir lo que cambies.

### 16. 🔑 Tokens de GitLab / GitHub

```text
   llavero del sistema  --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        listar proyectos    (OK)

   Claude / Codex  ---X--->  token             (nunca se les pasa)
   carpeta del proyecto ---X---> token         (nunca se escribe)
```

Si tus repos son privados, Camarones necesita un token para clonarlos y actualizarlos. Se guarda en el llavero de tu sistema operativo y solo lo usa Camarones en sus propios comandos git: no se escribe en el proyecto, ni en git config, ni se comparte con Claude, Codex u otros terceros. Al unirte al repo de cam-docs de un equipo, Camarones prueba primero con tu propio git (llavero, gestor de credenciales, claves SSH) y solo te pide un token si eso no entra. Los gestionas en «Ajustes › Tokens». La configuración de agentes que llega con el cam-docs del equipo recibe el mismo cuidado: los hooks, servidores MCP, ajustes y skills que no ha escrito el kit se listan al abrir el asistente, y Claude Code / Codex solo los cargan cuando los apruebas en esta máquina (o con `camaron trust`). Las aprobaciones viven en ~/.camarones/trust/, nunca en el repo, así que nadie puede aprobarlas por ti con un push. Lo que el kit instaló en esta máquina (sus skills y los de graphify y OpenWiki) lo reconoce sin preguntar, y `camaron repair` lo devuelve a su sitio si alguien lo edita o lo borra.

### 17. ⚙️ CI: documentación que se actualiza sola

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- que ha cambiado en el codigo?
                  |-- IA actualiza solo las paginas afectadas
                  |-- check --secrets  (un secreto para aqui: no hay MR)
                  |-- check (enlaces, diagramas, fuentes, confianza)
                  +-- exporta el portal (camaron portal) --> imagen nginx / Pages
   PR en un repo --> comentario sin IA: que paginas deja desactualizadas
                 --> camaron pr propose: un agente propone la doc en otra PR
```

Opcional: un pipeline que, tras cada cambio en los repos o en cam-docs, actualiza la documentación afectada y publica el portal de solo lectura. Así, un merge request hecho desde «Editar» del portal desplegado aparece publicado al fusionarse. Se configura en «Equipo › CI». También se puede hacer a mano con «🔄 Actualizar doc tras cambios» y «🌐 Portal › 📦 Exportar el portal». Y en cada pull request de un repo, un job sin IA comenta qué páginas deja desactualizadas el cambio (`camaron pr fresh`).

### 18. 📋 El Tablero: el trabajo junto a la documentación

```text
   cam-docs/backlog/
     tasks/wi-42 - Titulo.md   -> una tarjeta (Markdown, lo lee Backlog.md)
     board.yaml                -> columna y orden de cada tarjeta
   camaron board add story "..." --repo api --doc flows/pago.md
   camaron board move WI-42 Ready
   camaron board story split WI-42 --accept   -> subtareas sin choques
   camaron board next                         -> lo que puede empezar ya
```

Un Kanban versionado con la documentación: epics, historias, bugs y tareas con repos, criterios de aceptación y páginas enlazadas. Se activa con `camaron board init` (los proyectos sin él siguen igual) y se maneja con `camaron board add|list|show|move|assign|link|archive|repair`, todos con `--json`.

Cada tarjeta es un fichero Markdown compatible con Backlog.md, así que esa herramienta también lo lee y lo edita. Lo que enlazas de la documentación se vigila: el Tablero te dice si la página cambió desde que la enlazaste o si sigue sin confirmar. En el portal, la zona «Tablero» (`#/kanban`) tiene el Kanban, con filtros por repo, epic, etiqueta y estado de la documentación, y el detalle de cada tarjeta; para escribir pide el token, que lleva el portal que la app de escritorio abre en tu navegador mientras la app está abierta, y que `camaron up` imprime en la dirección (`#cam-token=…`). Sin él, solo lectura.

Historias. La zona «Historias» (`#/stories`) te ayuda a escribir una historia (Como / quiero / para) con avisos al instante, sin IA; calcula un veredicto INVEST por reglas; en «Toca» eliges los ficheros y las páginas que cambia (su huella); propone subtareas por plantilla con sus dependencias y las reparte en oleadas de tareas que no chocan; y no escribe nada en `backlog/` hasta que la apruebas y la guardas. En la terminal: `camaron board story lint|invest|split ID [--touch repo:ruta] [--accept]`, `camaron board next [--n 3] [--story ID|--epic ID]` (lo que puede empezar ya: una oleada de tareas que no chocan entre sí ni con lo que está en curso) y `camaron board waves`. `--accept` no vuelve a dividir una historia que ya tiene subtareas.

La puerta de salida. Mover una tarjeta a «In Progress» comprueba que sus dependencias estén hechas y que su huella no choque con lo que ya está en curso. A una persona se le avisa y puede seguir con `--force` (en el portal y en la app, «Mover igualmente»; se cuenta en las estadísticas de uso); a un agente (MCP `board_next` y `board_waves`, o el harness) se le rechaza siempre. Una tarjeta con hijas es un contenedor y no bloquea a sus propias tareas.

«✨ Sugerir con IA» está en los tres pasos (reescribir la historia, los criterios y las subtareas) y solo gasta cuando lo pulsas: solo sugiere, nunca decide huellas, dependencias, oleadas ni el veredicto. Mientras piensa, el botón brilla y no se puede volver a pulsar (Escape cancela); lo que propone se queda en tu navegador, por historia, hasta que lo aceptas o descartas, aunque pidas otra cosa, abras otra historia o recargues. Si no puede usarse (no hay agente instalado, falta el token o está apagada) sale desactivado y dice por qué. Ajustes opcionales en `workspace.yaml`: `stories: {ai: false}` la apaga, `stories: {model: …}` elige el modelo y `stories: {small: {groups, files, repos}}` los umbrales de la «S» de INVEST. El índice `.camarones/.cache/board.db` se reconstruye solo y se puede borrar.

Tu gambita de prácticas ya ha colgado los post-its en su sitio: tú solo los mueves.

### 19. 📜 Decisiones: los ADR, con la evidencia delante

```text
   Decisiones (g a)                       docs/decisions/0007-why-jpa.md
   +--------------------------------+     ---
   | 0007  Aceptada   Why spring... |     type: decision      x-owner: human
   | 0008  En revision  Cache de... |     ## Status   Accepted (2026-10-28)
   | Candidatas: 3                  |     ## Context, Decision, Evidence
   +--------------------------------+     ## Decided by   ana, luis

   problema -> evidencia -> revision -> aceptado
   camaron adr candidates | new | pack | write | accept | reject
```

Un ADR deja por escrito por qué el código es como es. La sección «Decisiones» de la app de escritorio (`g a`) ayuda a tomar la decisión con la evidencia delante y funciona entera sin IA, sin ningún agente instalado. El ADR vive en `docs/decisions/NNNN-titulo.md` y lo que la revisión va decidiendo, en `docs/.work/adr/NNNN.yaml`.

Plantear. «Nuevo ADR» pide un título y de qué va: nuevo (algo que el código aún no hace) o retroactivo (algo que el código ya hace y nadie dejó escrito). En «Toca» buscas los ficheros, los grupos del mapa del código y las páginas de documentación que afecta. «Candidatas» lista, sin IA, las decisiones que el código ya tomó y ningún ADR nombra: librerías de datos, caché, mensajería, seguridad y frameworks del inventario, tecnologías del C4 y ficheros de despliegue (Docker Compose, Helm); «Crear ADR retro» las abre con el título y lo que toca ya puestos.

Evidencia. El paquete de evidencia reúne lo que el proyecto ya sabe de lo que toca el ADR: ficheros vecinos del grafo del código, páginas que los citan, otros ADR, commits del último año, elementos del C4, librerías y preguntas abiertas. «Escribir sin IA» escribe el ADR propuesto con la plantilla y esa evidencia ya puesta.

Revisar y decidir. La revisión recorre el ADR parte por parte (aprobar, editar o aplazar cada sección) y cada punto de decisión (una pregunta con sus opciones: eliges una, con su razón en una línea). Puedes añadir puntos y apuntar a los asistentes. «Presentar» (`P`) pone una parte por pantalla en letra grande para llevar la reunión compartiendo pantalla, con el teclado: ←/→ cambian de parte, 1–9 eligen opción, E edita, D aplaza, A acepta y Esc sale. Aceptar deja el fichero en «Accepted» con la fecha, de una persona (`x-owner: human`), confirmado y con «Decided by», y las opciones de cada punto, con sus a favor y en contra, pasan a «Considered options»; rechazar exige un motivo y deja el fichero; un ADR que sustituye a otro lo marca «Superseded by». No se acepta lo que no está decidido: un punto aplazado o sin elección, o ningún texto en «Decision» ni puntos; las secciones que siguen con un `TODO(question)` no lo impiden, pero el diálogo de aceptar las nombra.

Un ADR escrito a mano o por otro kit (sin frontmatter, con encabezados en español…) sale en la lista con su estado y no cambia ni un byte hasta que lo aceptes o lo rechaces en una sesión; si ya está aceptado, rechazado, sustituido u obsoleto, está cerrado: no abre sesión y, para cambiarlo, un ADR nuevo que lo sustituya. En el portal, cada ADR enseña su estado en el árbol y en su página, y las páginas que cita una decisión aceptada llevan un aviso («pendiente de implementar» si es una decisión nueva), también en la exportación estática.

En la terminal: `camaron adr list|new|show|pack|candidates|write|accept|reject`, todos con `--json` (`new TÍTULO --kind new|retro [--problem T] [--touch repo:ruta] [--supersedes N]`, `accept ID [--attendee NOMBRE]`, `reject ID --why MOTIVO`). La revisión por partes es de la app.

Tu gambita de prácticas ya ha rebuscado en el código las decisiones que nadie escribió: tú pones la última palabra.

### 20. 🧰 Piezas de apoyo

```text
   uv        -> ejecuta Camarones (Python) sin instalar nada mas
   git       -> repos y el historial de la documentacion
   Node.js   -> OpenWiki, LikeC4 y mermaid-cli (el portal no necesita npm)
   gitleaks  -> busca secretos antes de cada commit y de publicar
   Docker    -> servir el portal como en produccion (opcional)
   Java      -> solo si hay repos Java/Kotlin (se detecta SDKMAN)
```

El asistente comprueba todo esto y lo instala por ti (winget en Windows, Homebrew en Mac) si eliges «Instalar todo lo recomendado». Solo git y Node.js son obligatorios. El control de calidad (mermaid-cli y gitleaks) viene con la instalación completa; mermaid-cli descarga un Chromium sin ventana la primera vez. Sin IA, la instalación escribe `docs/index.md` (qué es el proyecto, una tarjeta por repo y el mapa de contexto) y, por cada repo, `docs/repos/<repo>/index.md`: qué expone (el mapa de endpoints, con la tabla de endpoints plegada), qué datos guarda (diagrama ER), sus ciclos de vida (un diagrama de estados por enum de estado; las transiciones no se adivinan), sus mensajes y qué necesita para arrancar (variables de entorno y comandos, plegados), todo leído de sus ficheros; con topics, también `docs/architecture/messaging.md`. `camaron pages` (`camaron diagrams` es su alias) los pone al día, y `camaron blocks` y `sync` mantienen los bloques. Un proyecto anterior a la 4.52 conserva sus páginas (`reference.md`, `diagrams.md`, `system-map.md`, `first-look.md`, `data/<repo>.md`) hasta que ejecutes `camaron pages --adopt`: mueve los bloques con sus confirmaciones a las páginas nuevas, borra solo las páginas del kit que deja vacías, no escribe nunca una página de una persona (`x-owner: human` o `x-confirmed`) y te lista lo que no pudo tocar (páginas, enlaces, traducciones). Son páginas normales de Docs hechas de bloques generados: una persona puede confirmar uno copiando el `sha=` del bloque en `confirmed=` y poniendo su nombre en `by=` (una palabra, o entre comillas si lleva espacios: `by="Ana López"`), p. ej. `<!-- generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`; entonces el kit ya no lo reescribe, y `check` avisa si el código cambió desde entonces o si ya no tiene la fuente del diagrama. Para quedarte con la versión del código, quita `confirmed=` y `by=` del marcador, ejecuta `camaron diagrams` y vuelve a confirmarlo. El portal dice de cada diagrama si viene del código, si se editó a mano, si lo confirmó alguien o si el código cambió. Las extensiones del equipo van como plugins en `.camarones/plugins/` (`camaron plugins add` las trae y las fija en plugins.lock); las que ejecutan código o guían a los agentes no se cargan hasta que las apruebas en tu máquina, y cualquier cambio vuelve a preguntar. También sin IA: `camaron history` lee el historial de git (ficheros más tocados, a quién preguntar), `camaron doctor --context` cuenta lo que carga cada sesión de un agente y `camaron repair` devuelve a su sitio los ficheros del kit si alguien los toca.

### 21. 🗺 Tu día a día

```text
   1. camarones              -> abre el asistente del proyecto (cam-docs)
   2. Siguiente paso         -> una sesion de IA hace la siguiente unidad
   3. Portal (camaron up)    -> leer, editar, confirmar o pedir cambios
   4. Wikis                  -> crear o refrescar la wiki de un repo
   5. Actualizar             -> cuando cambie el codigo
   6. Compartir              -> traer lo del equipo y publicar lo tuyo
```

Con esto basta, y todo está en la parte de arriba del menú. Puedes parar cuando quieras: el progreso se guarda solo. Esc siempre vuelve atrás.

¿Hay un Camarón nuevo? «Ajustes › ⬆️ Actualizar Camarón» (o `camaron self-update`) mira el kit oficial, te dice qué ha cambiado y, si le dices que sí, lo actualiza para todos los proyectos de esta máquina y reinicia el asistente. Tus proyectos y tu documentación no se tocan. Con una copia local del kit en el proyecto, `camaron upgrade <carpeta del kit nuevo>` la pone al día y borra los ficheros del kit que la versión nueva ya no trae, salvo los que hayáis editado.

¿La documentación es de un kit antiguo? `camaron docs reset --redo` reabre las unidades terminadas para revisarlas, y `--wipe` borra lo generado (antes lo etiqueta en git) y el plan vuelve a empezar, sin tocar las entrevistas ni las páginas confirmadas. En la app de escritorio, al final de «Plan».

¿Quieres empezar de cero? «Ajustes › 🧹 Deshacer todo» (o `camaron uninstall`) guarda una copia .zip de cam-docs/, lo borra y quita todo rastro del kit de los repos y de la carpeta del workspace. Los repos quedan exactamente como en su último commit.
