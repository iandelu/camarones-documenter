"""🦐 Camarón — project documentation wizard + CLI. No arguments opens the wizard.

  setup [--ci]              install tools, sync repos, wire Claude Code/Codex + git hooks (idempotent)
  sync                      clone/pull repos from workspace.yaml
  detect                    add repos found in this folder to workspace.yaml
  changes                   files changed per repo since docs were last updated
  mark-documented [repo..]  record current commits as documented
  status [--json]           trust report: confirmed / draft / needs-reconfirm / orphans / translations
  check [--strict]          CI gate for docs
  confirm FILE.. --by NAME  mark pages as human-confirmed
  translated FILE..         stamp docs/i18n/<lang>/… pages as translations of the current canonical page
  llms                      regenerate docs/llms.txt
  graph                     rebuild the cross-repo code graph (.camarones/.cache/graph/graph.html)
  arch | arch-validate      live C4 editor | validate the C4 model
  portal                    export the read-only portal (docs, C4, code graphs, wikis) to .camarones/.cache/site for CI / hosting
  up [--port] [--docker|--static]   serve the portal: live editable server (default), or the export in Docker / without it
  wiki REPO.. [--init|--update] [--engine openwiki|claude|codex] [--force]   generate / refresh the OpenWiki of repos,
                            one at a time (a first wiki needs the repo's brief; --force skips that check)
  wiki REPO --open | --close    around a manual OpenWiki MCP session (real openwiki/ folder, then back to cam-docs)
  down                      stop the portal
  migrate [--yes] [--dry-run]   move an older layout into <workspace>/cam-docs and clean kit files out of the repos
  uninstall [--dry-run] [--yes] [--global] [--no-backup] [--backup-dir DIR] [--keep-board|--drop-board]
                            undo the project: back up and delete cam-docs, remove every kit trace from the repos
                            and the workspace folder (--global: also ~/.camarones*, saved tokens)
  docs reset --redo|--wipe [--templates] [--dry-run] [--yes]   start an older project's docs again: --redo reopens
                            every finished unit (nothing deleted); --wipe tags cam-docs in git, deletes the generated
                            docs and starts the plan over, keeping the interviews and the pages a person wrote or
                            confirmed; --templates: PLAYBOOK, CONVENTIONS and skeletons follow the kit again
  mcp [--http [--port N]]   MCP server: agents search/read the docs and the code graph, propose draft edits and
                            feedback; --http serves it on 127.0.0.1 with this machine's token (~/.camarones/mcp-token)
  ci [gitlab|github]        install the umbrella CI pipeline
  plan [sync|next|start|note|done|block|drop|add|redo] …   session work plan (docs/.work/plan.yaml)
  plan note UNIT "text"     save a progress checkpoint of a unit (a closed session resumes from it)
  plan redo UNIT [--also U…]  reopen a finished unit (e.g. an interview) to review and update it
  plan approve UNIT          close a unit that waits for a person (`approval: true` in pipeline.yaml); its
                            dependents start after this
  checkpoint ["message"]    commit docs progress locally in the umbrella repo (never pushes)
  remote [URL]              show / set the team's cam-docs repo (origin)
  share [--auto on|off]     checkpoint, pull the team's work (rebase) and push cam-docs; --auto: after every checkpoint
  feedback FILE "text" --by NAME   record a human review comment (applied by the review-fixes unit)
  stats [--json] [--months N] [--record on|off]   team usage KPIs (who consults the docs, what they find, what
                            is read most); --record: whether this machine adds its counts
  version                   kit and pinned tool versions
  config [get|set] [KEY] [VALUE] [--json]   this machine's settings the wizard keeps: lang (es|en), model (Claude
                            Code: sonnet|opus|haiku), codex_model, sessions (canvas|window: where the desktop app
                            opens a session, a terminal on its canvas or a window)
  projects [--json] [--add FOLDER]   the projects registered on this machine, most recent first; --add registers one
  projects --inspect FOLDER [--json]   what a folder is (project, repo, umbrella, code, empty); reads, never writes
  projects --adopt FOLDER [--name NAME] [--json]   make FOLDER a project (docs in a cam-docs/ next to its repos) and register it
                            (--json: a cam-docs that belongs to something else prints {"error": "taken", "detail"};
                            home or a drive root: "home"; code without git: "no-git")
  projects --git-init FOLDER [--json]   git init the code in FOLDER (or in each subfolder with code); prints
                            {"initialised": [paths]}, a failure {"error": "git-init", "detail"}
  app                       the desktop app: run the plan, wikis, scans and checks, and read the portal, in one window
                            (installs its pinned Electron into ~/.camarones/desktop once; needs Node.js)
  new NAME | join URL … --no-open   create or join, print {"path": …} and stop (the desktop app opens it itself);
                            access refused: {"error": auth|denied|not-found|network|unknown, "host", "detail"}, exit 1
                            (join: a cam-docs there that belongs to something else: {"error": "taken", "detail"})
                            (a token for a private repo comes from CAMARONES_JOIN_TOKEN, never from the command line)
  catalog [--json|--markdown|--check]   every command with where it lives (portal / desktop app / CLI) and its
                            arguments, read from this parser; --check exits 1 when lib/catalog.py is out of sync
  prompt UNIT [--lang es|en] [--unattended]      prompt for an agent session (UNIT may be 'update')
  autopilot [--lang es|en] [--max-units N] [--poll-seconds N] [--include-interviews]
                            run ready units back to back unattended (Claude Code / Codex, waits out usage limits)
  arch-draft [--save]       quick static architecture scan → C4 draft (first look, no AI)
  radar [--json]            stack + tools the repos already use (Backstage, Sonar, linters…) → docs/overview/tooling.md
  schemas [--json]          each repo's tables and collections from migrations, schema files, entity classes, Mongo and
                          Firestore (no AI) → an ER diagram the kit keeps in sync with the code: in the repo page
                          (docs/data/<repo>.md is for projects from before 4.52; new projects: the repo page)
  inventory [--cves] [--latest] [--json] [--fail-on high|critical]   every repo's direct dependencies by category
                          (framework, data, cache, security…) → docs/overview/libraries.md, no AI; --cves adds known
                          vulnerabilities (OSV-Scanner with its offline database, so no package name leaves the machine);
                          --latest asks public registries for each library's latest stable version (library names leave
                          the machine, your own never); --fail-on exits 1 when a known vulnerability is that serious
                          (for CI; finding one is not a failure otherwise)
  bump <repo> <library> <version> [--ecosystem E] [--json] [--yes]   update one library of a service repo on a new
                          branch camaron/bump-<name>-<version> with its package manager (or the version rewritten in
                          the manifest, or in the repo's parent pom or BOM a Maven module inherits it from); without
                          --yes it only says what it would do; never commits or pushes
  health [--json] [--refresh]   project health at a glance: the machine, the docs and the code, each ok / warn / bad
                          with its reasons, and per repo Sonar, coverage, vulnerabilities and debt; read from the last
                          snapshot (cam-docs/.cache/health.json), built when there is none; --refresh builds it again
  stack REPO [TEXT|--reset] fix a repo's stack in workspace.yaml (--reset: back to the detected one)
  interview mode [team|live]   how interviews run: team questionnaire answered offline, or live with the agent
  interview export [--lang es|en]   questionnaire → offline HTML form + Markdown copy to share with the team
  interview import FILE|DIR…   import the team's answers (form JSON or filled Markdown)
  interview status [--json]    who answered, unanswered questions, disagreements
  doctor [--json] [--install NAME] [--local|--context [--json]]
                            check prerequisites and tool versions (--json: with the command that fixes each;
                            --install git|node|docker|java|claude|codex: with the OS package manager or npm);
                            --context: the tokens every agent session loads
                            before reading a page (AGENTS.md, skills, MCP schemas) against context.budget;
                            --local: propose a free local model for this machine (bounded/judge work, through
                            OpenCode) without installing anything
  run [--parallel N] [--per-runner claude=2,codex=1] [--max-units N] [--lang es|en] [--include-interviews]
      [--policy on-conflict|never] [--poll-seconds N] [--only UNIT…]
                            run ready units in parallel, up to N at once (one agent may take all N unless
                            --per-runner caps it): discovery, repo briefs, domain, decisions, the flows catalog and
                            flows each in their own copy of cam-docs (merged back when done), other units one at a
                            time. autopilot stays sequential
  runs [RUN] [--json]       what past runs did: units, outcome, merges, time, tokens and cost
  eval [list|run|draft|confirm ID…] [--runner T] [--judge T] [--all] [--json] [--by NAME]
                            golden questions (evals/questions.yaml): run asks the confirmed ones to an agent that may
                            only read the docs and scores cited pages + exact identifiers; draft adds a unit that
                            proposes questions; confirm approves them
  eval comply UNIT [--runner T] [--json]
                            run one ready unit for real and score what it wrote against the method (structure, links,
                            sources), without AI: compare playbook or prompt changes. Use the sandbox, not CI
  export pdf | print | tour FLOW | codetour FLOW | confluence | notion
                            the docs agents may read as one print-ready page (PDF with a headless Chrome), a guided
                            tour of a business flow (HTML slides, or a VS Code CodeTour in .tours/ opened at each
                            step's code), or published to Confluence/Notion (plugins: `plugins enable` first)
  history [--months 12]     docs/overview/history.md from git, no AI: hotspots, who to ask per repo, files that
                            change together, tickets that span repos, commit conventions
  repair                    put back what the kit owns in this project: its skills and agent config, the agent tools'
                            skills, the workspace and wiki links (never the team's pages); your own .claude/ or
                            CLAUDE.md in the workspace gets the kit's entries linked in, its rules imported
  removed add WHAT --why WHY [--decision decisions/NNNN-x.md]
                            record something removed on purpose (docs/overview/removed.md) so agents do not recreate it
  skills list | fork NAME | diff NAME [--kit] | reset NAME | note SKILL TEXT --source retro|review|board
         [--step S] [--change ID] [--ref URL] | notes [SKILL]   [--json]
                            the agents' skills: a team copy in .camarones/skills wins over the kit's; notes say
                            where a skill got in the way (docs/.work/skill-notes)
  review request PAGE [--note T] | wait ID [--timeout S] | list
                            an agent asks a person to review a page and waits for the answer (approve / changes, as
                            JSON); people answer in the portal's Review tab
  board ACTION [ARGS] [--json]   the board (cam-docs/backlog, Backlog.md-compatible): init | add TYPE TITLE | list |
                            show ID | move ID STATUS | assign ID WHO | link ID REF | archive ID | repair
                            (list: --status --epic --repo --label --docs suspect|unconfirmed; add: --epic --repo
                            --label --priority --doc; move: --before/--after ID); merge-driver is git's, not yours
  adr ACTION [ARGS] [--json]   the decisions (docs/decisions): list | new TITLE --kind new|retro [--problem T]
                            [--touch REPO:PATH] [--supersedes N] | show ID | pack ID (the evidence) | candidates |
                            write ID (the proposed file, no AI) | accept ID [--attendee NAME] | reject ID --why T
  hooks [on|off] [--json]   method hooks for Claude Code in cam-docs: the plan state at session start, a check of each
                            docs page right after it is edited, a reminder to update the docs before stopping
  ab --qa "QUESTION" | --golden [--runner T] [--judge T] [--json]
                            the same question with cam-docs and without it (only the code, in a throwaway folder that
                            links the repos): tokens, time, tool calls and identifiers named, side by side
  ab --task "TASK" [--check "CMD"] | --replay [--max N]
                            a coding task twice, in throwaway worktrees of the repos (with cam-docs and without):
                            tokens, time, files changed, the diff, and whether CMD (e.g. the tests) passes in each
  ab sampling on|off        opt in on this machine to keep a sample of real prompts (needs ab.sampling.enabled in
                            workspace.yaml; stored in ~/.camarones/ab-samples/, never in the repo); --replay runs them
  fresh [--json] [--ack PAGE… --by NAME] [--plan]
                            pages whose cited code changed (suspect) or is gone (stale); agents are kept off them.
                            --ack: the page still holds for today's code; --plan: add a unit that refreshes them
  blocks [--force] [--json]  facts read from the repos, no AI: every <!-- generated:… --> block in the docs (new
                            projects: in the repo page; projects from before 4.52 also docs/repos/<repo>/reference.md,
                            until `pages --adopt`). A block edited by hand is kept and flagged by check; --force takes
                            the code's version. `sync` refreshes them too
  pages [--adopt] [--json]  the docs from the code, no AI: docs/index.md (what the project is, a card per repo, the
                            context map) and docs/repos/<repo>/index.md (what each repo exposes, stores and needs to
                            run). Projects from before 4.52 keep their pages; --adopt moves them to this layout
  diagrams [--json]         alias of pages
  pr fresh REPO [--base REF | --files F…] [--json] [--post] [--lang en|es]
                            what a pull request does to the docs, no AI: the pages whose cited code it changes (left
                            out of date by it, or already before). --post writes or updates one comment on the PR/MR
                            (GitHub Actions or GitLab CI); it never fails the pipeline. --head REF: the PR's commit
                            when it is not checked out
  pr propose PR_URL [--ref REF] [--base REF] [--runner R] [--dry-run [--json]] [--comment]
                            AI: an agent updates the pages the PR leaves out of date on cam-docs branch
                            docs/pr-<repo>-<n> (its own worktree); the kit commits, pushes and opens the docs PR.
                            The PR is fetched into refs/camaron/pr/<n> (your checkout is not touched); --dry-run shows
                            the plan; --comment links the docs PR on the service PR; --preview exports the docs
                            branch as a static portal in .camarones/.cache/previews/
  kpis [--json] [--months N] [--no-check] [--compare RUN_A RUN_B]
                            is it working? cost and speed of runs (the team's, per month), coverage, trust, usage;
                            --compare puts two runs side by side
  pipeline show|validate [--json]   the project's plan as units (kit pipeline + .camarones/pipeline.yaml);
                            validate exits 1 when pipeline.yaml has problems (for CI)
  plugins [--json]          plugins of the kit and of this project (.camarones/plugins/): what they provide, whether
                            they run code, and whether they are loaded (code and prompts need approval: `trust`)
  plugins add SOURCE        vendor a team plugin from a folder or git:<url>@<tag>[#subfolder]; pinned in plugins.lock
  plugins update [NAME] [--to TAG] | outdated | remove NAME | enable NAME | disable NAME
                            re-fetch (shows what changed; changed code asks trust again), newer versions, drop one
  install DEST --profile quick|full [--dry-run]   copy kit into an explicit project folder
  upgrade SOURCE [--dry-run]  update kit files with backups; preserve project configuration
  profile quick|full        change the work plan without losing checkpoints
  new NAME [--from URL]     create ./NAME/cam-docs/, register it, open it (global install); --from joins the team's repo
  join URL [FOLDER]         use the team's cam-docs repo: clone it into FOLDER/cam-docs (default: here) or reuse the
                            copy already on this machine; the wizard then only sets up this machine
  trust [--yes] [--json]    list the agent config (hooks, MCP servers, settings, skills) this machine has not approved;
                            approve it and link it into the workspace (unapproved config is never linked)
  switch                    pick a registered project to open (global install)
  self-update               git pull the central kit in place (global install only)
  unlink                    remove this project's local kit copy, keep config (moves to global install)
"""
# The help is this module's docstring, not a string literal: Python 3.13+ dedents docstrings when it compiles
# them, so `__doc__` prints exactly what the old camarones.py docstring printed on every Python version.
TEXT = __doc__
