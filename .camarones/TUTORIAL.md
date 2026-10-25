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

Documenting a project in depth doesn't fit in one AI conversation, so the work is split into small units. Every “🦐 Next step” opens a session that does ONE unit. The AI saves checkpoints while it works: if you close the terminal or the laptop, next time you get “▶ Continue” and it resumes from the last checkpoint. Each finished unit is committed locally in cam-docs so nothing is lost; “🤝 Share with the team” (or `camaron share`) pulls the team's work and publishes yours when you decide. Want a different plan? `.camarones/pipeline.yaml` lets you drop, add or rewire units without touching the kit (the command guide has examples). The interviews don't hold you up: what depends on them is drafted first and refined once you have them. In a hurry? `camaron run` does several units at once, each in its own copy of cam-docs, and `camaron kpis` tells you what it cost and whether it was worth it. `camaron eval` tests the docs with golden questions the team approves, and `camaron ab` compares the same question with and without cam-docs.

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

   generate or update:  portal > Wikis  |  wizard > Wikis  |  camaron wiki repo-a
```

OpenWiki writes a standard wiki for each repo where every claim is anchored to a file and line of code, so the AI can't make things up and anyone can check. The wiki is stored in cam-docs/wikis/<repo>, so the service repo stays clean. Generate or update it from the portal (Docs › Wikis, with a live log), from the wizard (📚 Wikis) or with “camaron wiki <repo>”; its pages show up under Docs as repos/<repo>/. Each wiki is a full agent run, so only the repos you choose get one (wizard > Wikis > choose), and the first one waits for the repo-brief, which gives it the repo's role and glossary (from the portal you can start one anyway: it chooses the repo and writes a starter brief without AI). They run one at a time. Camarones fills what OpenWiki doesn't cover: the whole-project view, domain, business flows, deployment and decisions.

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

graphify walks the code and builds a graph: classes, functions, calls and cross-repo dependencies. The AI uses it to answer questions without reading thousands of files, and you explore it in the portal's “Code graph” view, in the Architecture zone (all repos together or one at a time). A git hook keeps it up to date, or press “Rebuild” in the local portal.

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

The 🦐 portal brings the docs (with search, editing and review), the C4 explorer (under each view, its elements to fix and confirm what the AI drafted), the code graph and the OpenWiki wikis together in one site, in English or Spanish. It has two modes with the same interface: the local portal (`camaron up`, or wizard → 🌐 Portal → 📝 Open the portal), where you can edit, and the read-only export (`camaron portal`) that is deployed with Docker or on any static host. `camaron up --static` shows you the export as is. Everything works offline (on-premise), its fonts too. It follows Cofundo's design system with the Camarón brand, light or dark. Home asks first and shows the project's state; the sidebar always has five zones: Docs (pages and wikis), Architecture (C4, code graph, Data as an ER diagram, and Libraries with known vulnerabilities in red), Plan (the live Pipeline: retry and approve here; run and cancel in the desktop app; the Interview, where each person answers the team questionnaire, and Sync, which shares with the team and brings in their work), Quality (KPIs: confirmed share, pages out of date, AI cost and the questions nobody found; and CI) and Review. The top bar says where you are and Ctrl K jumps to any page, zone or view, or takes the question to Ask. A fresh project offers a first look from the code, no AI, from the app. Ask gives the sections that answer, with citations (it goes by meaning: “database” finds PostgreSQL), and with an agent set up it can also write the answer from them. The “All / Business” switch keeps only the pages about what the system does and why.

### 12. 🖥 The desktop app: your workshop

```text
   +----------------------------------------------------------------------------+
   | camarón  / Workshop / Generate                                             |
   |                                                                            |
   | Document the ready units in parallel   camaron run              [AI]       |
   |   --parallel [ 2 ]   [ ] --include-interviews                              |
   |   ( Run run )   Peeling it for you…                                        |
   |   unit.started repo-brief:api …                                            |
   +----------------------------------------------------------------------------+
```

`camaron app` (or wizard → 🖥️ Desktop app) opens a window with the same portal plus one more zone, the Workshop: everything that runs on your machine. Generate (the plan with AI, the autopilot, a unit in a terminal with the agent you pick, wikis, pull requests), Analyze (no AI: C4 draft, stack, dependencies and vulnerabilities, data, history), Check (prerequisites, check, golden questions, KPIs), Interviews, Team (shared repo, agents, plugins, CI) and This machine (setup with progress, language and models, tokens, repos, kit updates and uninstall previewed first). Every CLI command has its form there, its live output and its result; what deletes or moves data sits apart and asks first. When it opens you pick a project, create one or join the team's. The browser portal stays the team's viewer: reading, editing, review and status; whatever starts a process or calls a model says "open it in the app". The first time it installs Electron into ~/.camarones/desktop (needs Node.js); without it the CLI and this wizard work the same.

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
   |    in any other folder    ->  picker: open · create · join · add           |
   |    in the wizard          ->  menu › Desktop app                           |
   +----------------------------------------------------------------------------+
```

The app is not installed separately: it comes with the kit. It only needs Node.js 22 or newer (`camaron doctor --install node` installs it with winget on Windows or Homebrew on macOS). Run `camaron app`: the first time it downloads Electron, pinned to one version, into ~/.camarones/desktop, with no admin rights and nothing in your projects. From a project's folder it opens that project; from anywhere else, the picker, where you open one, create a new one, join the team's cam-docs with its URL or add a folder. Inside, your projects sit on the rail at the left: another one opens in the same window, which comes back where you left it. Ctrl or Cmd + Shift + O goes back to the projects and "camarón › Open in the browser" opens the same portal outside. The sections the app is still rebuilding open their Workshop zone, and "Back to the app" brings you back. A good first step: Workshop › Check to see what is missing, and Analyze for the first look without AI. If something fails, the notice says what; deleting ~/.camarones/desktop makes it download Electron again.

### 14. ✏️ Where and when you can edit

```text
   WHERE                        WHAT YOU CAN DO                      WHERE IT GOES
   ---------------------------  -----------------------------------  ------------------------
   local portal                 edit, new page, confirm,             cam-docs + local commit
   (camaron up)               request changes, generate wikis,     (you push it)
                                rebuild C4 and graph
   deployed portal              read and search; "Edit" opens the    merge request in the
   (export)                     file in GitLab / GitHub              cam-docs repo
   your editor / IDE            any .md in cam-docs/docs             cam-docs (plain git)
   the AI (Next step)           only its unit; never overwrites      local commit per unit
                                confirmed pages silently
```

In the local portal, “Edit” opens the markdown with a live preview; saving writes to cam-docs/docs and, with “commit to cam-docs” ticked, makes a local commit (sharing it with git push is up to you). “+ New page” creates a page of your own and “Confirm” signs with your git user name. With Spanish selected you edit the translation. The deployed portal doesn't edit: it's a snapshot of the last export; its “Edit” button takes you to the file in GitLab/GitHub (when cam-docs has a remote), the change goes in as a merge request and CI publishes it again. Editing a ✅ page turns it ⚠️ until someone checks it. Don't hand-edit generated files (llms.txt, llms-full.txt, .status.json, viewers); wikis are better regenerated from the Wikis view, since an update can rewrite what you change.

### 15. 🔑 GitLab / GitHub tokens

```text
   OS keychain          --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        list projects       (OK)

   Claude / Codex  ---X--->  token             (never passed to them)
   project folder  ---X--->  token             (never written there)
```

If your repos are private, Camarones needs a token to clone and update them. It is stored in your OS keychain and used only by Camarones' own git commands: never written to the project or git config, never shared with Claude, Codex or other third parties. When you join a team's cam-docs repo, Camarones first tries your own git (keychain, credential manager, SSH keys) and asks for a token only if that is refused. Manage them in “Settings › Tokens”. The agent config that comes with the team's cam-docs gets the same care: hooks, MCP servers, settings and skills the kit did not write are listed when you open the wizard, and Claude Code / Codex only load them once you approve them on this machine (or with `camaron trust`). Approvals live in ~/.camarones/trust/, never in the repo, so nobody can approve them for you with a push. What the kit installed on this machine (its skills, graphify's and OpenWiki's) is recognised without asking, and `camaron repair` puts it back if someone edits or deletes it.

### 16. ⚙️ CI: docs that update themselves

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

### 17. 📋 The Board: the work next to the docs

```text
   cam-docs/backlog/
     tasks/wi-42 - Title.md    -> one card (Markdown, Backlog.md reads it)
     board.yaml                -> each card's column and order
   camaron board add story "..." --repo api --doc flows/payment.md
   camaron board move WI-42 Ready
```

A Kanban versioned with the docs: epics, stories, bugs and tasks with repos, acceptance criteria and linked pages. Turn it on with `camaron board init` (projects without it stay as they were) and use `camaron board add|list|show|move|assign|link|archive|repair`, all with `--json`.

Each card is a Markdown file compatible with Backlog.md, so that tool reads and edits it too. What you link from the docs is watched: the Board tells you whether the page changed since you linked it or is still unconfirmed. In the portal, the “Board” zone (`#/kanban`) has the Kanban, with filters by repo, epic, label and docs state, and the card detail; writing needs the token, which the desktop app already sends and `camaron up` prints in the URL (`#cam-token=…`). Without it, read-only.

Your intern shrimp has pinned the sticky notes up already: all you do is move them.

### 18. 🧰 Supporting pieces

```text
   uv        -> runs Camarones (Python) without installing anything else
   git       -> repos and the docs history
   Node.js   -> OpenWiki, LikeC4 and mermaid-cli (the portal needs no npm)
   gitleaks  -> looks for secrets before every commit and before publishing
   Docker    -> serve the portal like production (optional)
   Java      -> only for Java/Kotlin repos (SDKMAN is detected)
```

The wizard checks all of this and installs it for you (winget on Windows, Homebrew on Mac) when you choose “Install everything recommended”. Only git and Node.js are required. The quality gate (mermaid-cli and gitleaks) comes with the full install; mermaid-cli downloads a headless Chromium the first time. Without AI, each repo also gets `docs/repos/<repo>/reference.md`: commands, env vars, endpoints and topics read from its files, kept current by `camaron blocks` and `sync`. Also without AI, `camaron diagrams` draws the system map (`docs/architecture/system-map.md`: who talks to whom, and who publishes or consumes each topic) and, per repo, `docs/repos/<repo>/diagrams.md` (endpoints and the states of each status enum; transitions are never guessed). They are ordinary Docs pages (under architecture and each repo) made of generated blocks: a person can confirm one by copying the block's `sha=` value into `confirmed=` and putting their name in `by=` (one word, or quoted when it has spaces: `by="Ana López"`), e.g. `<!-- generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`; the kit then stops rewriting it, and `check` warns when the code has changed since or no longer has the diagram's source. To take the code's version, remove `confirmed=` and `by=` from the marker, run `camaron diagrams` and confirm it again. The portal tells you for each diagram whether it comes from the code, was edited by hand, a person confirmed it, or the code changed. Team extensions go in `.camarones/plugins/` as plugins (`camaron plugins add` brings one in and pins it in plugins.lock); the ones that run code or steer agents are not loaded until you approve them on your machine, and any change asks again. Also without AI: `camaron history` reads the git history (hotspots, who to ask), `camaron doctor --context` counts what every agent session loads and `camaron repair` puts the kit's files back if someone touches them.

### 19. 🗺 Your day to day

```text
   1. camarones              -> opens the project's wizard (cam-docs)
   2. Next step              -> an AI session does the next unit
   3. Portal (camaron up)    -> read, edit, confirm or request changes
   4. Wikis                  -> create or refresh a repo's wiki
   5. Update                 -> when the code changes
   6. Share                  -> pull the team's work and publish yours
```

That's all, and it is all on the top part of the menu. Stop whenever you like: progress saves itself. Esc always goes back.

Is there a new Camarón? “Settings › ⬆️ Update Camarón” (or `camaron self-update`) checks the official kit, tells you what changed and, if you say yes, updates it for every project on this machine and restarts the wizard. Your projects and documentation are not touched.

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

Documentar a fondo un proyecto no cabe en una sola conversación con la IA, así que el trabajo se divide en unidades pequeñas. Cada vez que eliges «🦐 Siguiente paso» se abre una sesión que hace UNA unidad. La IA guarda checkpoints mientras trabaja: si cierras la terminal o el portátil, la próxima vez aparece «▶ Continuar» y retoma desde el último checkpoint. Al terminar cada unidad se hace un commit local en cam-docs para que nada se pierda; «🤝 Compartir con el equipo» (o `camaron share`) trae el trabajo del equipo y publica el tuyo cuando tú decides. ¿Queréis otro plan? En `.camarones/pipeline.yaml` podéis quitar, añadir o reordenar unidades sin tocar el kit (la guía de comandos trae ejemplos). Las entrevistas no te frenan: lo que depende de ellas se escribe antes como borrador y se afina cuando las haces. ¿Con prisa? `camaron run` hace varias unidades a la vez, cada una en su propia copia de cam-docs, y `camaron kpis` te dice cuánto costó y si mereció la pena. `camaron eval` examina la documentación con preguntas de oro que el equipo aprueba, y `camaron ab` compara la misma pregunta con y sin cam-docs.

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

   generar o actualizar:  portal > Wikis  |  asistente > Wikis  |  camaron wiki repo-a
```

OpenWiki escribe una wiki estándar de cada repo donde cada afirmación está anclada a un fichero y línea del código: la IA no se inventa cosas y cualquiera puede comprobarlas. La wiki se guarda en cam-docs/wikis/<repo>, así que el repo de servicio queda limpio. La generas o actualizas desde el portal (Docs › Wikis, con el log en directo), desde el asistente (📚 Wikis) o con «camaron wiki <repo>»; sus páginas aparecen en Docs, en repos/<repo>/. Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas (asistente > Wikis > elegir), y la primera espera al repo-brief, que le da el rol y el glosario del repo (desde el portal puedes lanzarla igual: elige el repo y escribe un brief inicial sin IA). Se lanzan de una en una. Camarones rellena lo que OpenWiki no cubre: visión del proyecto entero, dominio, flujos de negocio, despliegue y decisiones.

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

graphify recorre el código y construye un grafo: clases, funciones, llamadas y dependencias entre repos. La IA lo usa para responder preguntas sin leer miles de ficheros, y tú lo exploras en el «Grafo de código» del portal, en la zona Arquitectura (todos los repos juntos o uno a uno). Se actualiza solo con un hook de git, o con «Reconstruir» en el portal local.

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

El portal 🦐 junta en una sola web la documentación (con buscador, edición y revisión), el explorador C4 (bajo cada vista, sus elementos para corregir y confirmar lo que redactó la IA), el grafo de código y las wikis de OpenWiki, en español o inglés. Tiene dos modos con la misma interfaz: el portal local (`camaron up`, o asistente → 🌐 Portal → 📝 Abrir el portal), donde se puede editar, y la exportación de solo lectura (`camaron portal`) que se despliega con Docker o en cualquier hosting estático. `camaron up --static` te enseña la exportación tal cual. Todo funciona sin Internet (on-premise), también sus fuentes. Sigue el sistema de diseño de Cofundo con la marca Camarón, en claro u oscuro. Inicio pregunta primero y enseña el estado del proyecto; el menú lateral tiene siempre cinco zonas: Docs (páginas y wikis), Arquitectura (C4, grafo de código, Datos como diagrama ER y Librerías con las vulnerabilidades en rojo), Plan (el Pipeline en vivo: reintentar y aprobar aquí; lanzar y cancelar, en la app de escritorio; la Entrevista, donde cada persona responde el cuestionario del equipo, y Sincronizar, que comparte con el equipo y trae su trabajo), Calidad (KPIs: cuánto está confirmado, qué se ha quedado viejo, el coste de IA y las preguntas que nadie encontró; y CI) y Revisión. La barra de arriba dice dónde estás y Ctrl K salta a cualquier página, zona o vista, o lleva la pregunta a Preguntar. Un proyecto nuevo ofrece un primer vistazo desde el código, sin IA, desde la app. Preguntar da las secciones que responden, con su cita (entiende el sentido: «base de datos» encuentra PostgreSQL), y si hay un agente configurado también puede redactar la respuesta con ellas. El interruptor «Todo / Negocio» deja solo las páginas de qué hace el sistema y por qué.

### 12. 🖥 La app de escritorio: tu taller

```text
   +----------------------------------------------------------------------------+
   | camarón  / Taller / Generar                                                |
   |                                                                            |
   | Documentar las unidades listas en paralelo   camaron run        [IA]       |
   |   --parallel [ 2 ]   [ ] --include-interviews                              |
   |   ( Ejecutar run )   Pelándolo para ti…                                    |
   |   unit.started repo-brief:api …                                            |
   +----------------------------------------------------------------------------+
```

`camaron app` (o asistente → 🖥️ App de escritorio) abre una ventana con el mismo portal y una zona más, el Taller: todo lo que corre en tu máquina. Generar (el plan con IA, el piloto automático, una unidad en una terminal con el agente que elijas, wikis, pull requests), Analizar (sin IA: borrador C4, stack, dependencias y vulnerabilidades, datos, historia), Comprobar (requisitos, check, preguntas de control, KPIs), Entrevistas, Equipo (repo compartido, agentes, plugins, CI) y Esta máquina (setup con progreso, idioma y modelos, tokens, repos, actualizar el kit y desinstalar con vista previa). Cada comando de la CLI tiene ahí su formulario, su salida en vivo y su resultado; lo que borra o mueve datos va aparte y pregunta antes. Al abrirla eliges proyecto, creas uno o te unes al del equipo. El portal del navegador queda como visor del equipo: leer, editar, revisar y ver el estado; lo que lanza procesos o llama a un modelo dice «ábrelo en la app». La primera vez instala Electron en ~/.camarones/desktop (necesita Node.js); sin él, la CLI y este asistente funcionan igual.

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
   |    en otra carpeta        ->  selector: abrir · crear · unirse · añadir    |
   |    en el asistente        ->  menú › App de escritorio                     |
   +----------------------------------------------------------------------------+
```

La app no se instala aparte: viene con el kit. Solo necesita Node.js 22 o superior (`camaron doctor --install node` lo instala con winget en Windows o Homebrew en macOS). Lanza `camaron app`: la primera vez descarga Electron, fijado a una versión, en ~/.camarones/desktop, sin permisos de administrador y sin tocar tus proyectos. Desde la carpeta de un proyecto abre ese proyecto; desde cualquier otra, el selector, donde abres uno, creas uno nuevo, te unes al cam-docs del equipo con su URL o añades una carpeta. Dentro, tus proyectos están en el raíl de la izquierda: otro se abre en la misma ventana, que vuelve a salir donde la dejaste. Ctrl o Cmd + Shift + O vuelve a los proyectos y «camarón › Abrir en el navegador» abre el mismo portal fuera. Las secciones que la app aún está rehaciendo abren su zona del Taller, y «Volver a la app» te trae de vuelta. Un buen primer paso: Taller › Comprobar para ver qué falta, y Analizar para el primer vistazo sin IA. Si algo falla, el aviso dice qué; borrar ~/.camarones/desktop fuerza a descargar Electron otra vez.

### 14. ✏️ Dónde y cuándo se puede editar

```text
   DONDE                        QUE PUEDES HACER                     DONDE QUEDA
   ---------------------------  -----------------------------------  ------------------------
   portal local                 editar, pagina nueva, confirmar,     cam-docs + commit local
   (camaron up)               pedir cambios, generar wikis,        (el push lo haces tu)
                                reconstruir C4 y grafo
   portal desplegado            leer y buscar; "Editar" abre el      merge request en el
   (exportacion)                fichero en GitLab / GitHub           repo cam-docs
   tu editor / IDE              cualquier .md de cam-docs/docs       cam-docs (git normal)
   la IA (Siguiente paso)       solo su unidad; no pisa lo           commit local por unidad
                                confirmado sin avisar
```

En el portal local, «Editar» abre el markdown con vista previa; al guardar se escribe en cam-docs/docs y, si marcas «commit en cam-docs», se hace un commit local (compartirlo con git push es cosa tuya). «+ Nueva página» crea una página tuya y «Confirmar» firma con tu usuario de git. Con el idioma en español editas la traducción. El portal desplegado no edita: es una foto de la última exportación; su botón «Editar» te lleva al fichero en GitLab/GitHub (si cam-docs tiene remote) y el cambio entra por merge request, y el CI vuelve a publicar. Editar una página ✅ la pasa a ⚠️ hasta que alguien la mire. No edites a mano lo generado (llms.txt, llms-full.txt, .status.json, visores): las wikis mejor regenerarlas desde la vista Wikis, porque una actualización puede reescribir lo que cambies.

### 15. 🔑 Tokens de GitLab / GitHub

```text
   llavero del sistema  --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        listar proyectos    (OK)

   Claude / Codex  ---X--->  token             (nunca se les pasa)
   carpeta del proyecto ---X---> token         (nunca se escribe)
```

Si tus repos son privados, Camarones necesita un token para clonarlos y actualizarlos. Se guarda en el llavero de tu sistema operativo y solo lo usa Camarones en sus propios comandos git: no se escribe en el proyecto, ni en git config, ni se comparte con Claude, Codex u otros terceros. Al unirte al repo de cam-docs de un equipo, Camarones prueba primero con tu propio git (llavero, gestor de credenciales, claves SSH) y solo te pide un token si eso no entra. Los gestionas en «Ajustes › Tokens». La configuración de agentes que llega con el cam-docs del equipo recibe el mismo cuidado: los hooks, servidores MCP, ajustes y skills que no ha escrito el kit se listan al abrir el asistente, y Claude Code / Codex solo los cargan cuando los apruebas en esta máquina (o con `camaron trust`). Las aprobaciones viven en ~/.camarones/trust/, nunca en el repo, así que nadie puede aprobarlas por ti con un push. Lo que el kit instaló en esta máquina (sus skills y los de graphify y OpenWiki) lo reconoce sin preguntar, y `camaron repair` lo devuelve a su sitio si alguien lo edita o lo borra.

### 16. ⚙️ CI: documentación que se actualiza sola

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

### 17. 📋 El Tablero: el trabajo junto a la documentación

```text
   cam-docs/backlog/
     tasks/wi-42 - Titulo.md   -> una tarjeta (Markdown, lo lee Backlog.md)
     board.yaml                -> columna y orden de cada tarjeta
   camaron board add story "..." --repo api --doc flows/pago.md
   camaron board move WI-42 Ready
```

Un Kanban versionado con la documentación: epics, historias, bugs y tareas con repos, criterios de aceptación y páginas enlazadas. Se activa con `camaron board init` (los proyectos sin él siguen igual) y se maneja con `camaron board add|list|show|move|assign|link|archive|repair`, todos con `--json`.

Cada tarjeta es un fichero Markdown compatible con Backlog.md, así que esa herramienta también lo lee y lo edita. Lo que enlazas de la documentación se vigila: el Tablero te dice si la página cambió desde que la enlazaste o si sigue sin confirmar. En el portal, la zona «Tablero» (`#/kanban`) tiene el Kanban, con filtros por repo, epic, etiqueta y estado de la documentación, y el detalle de cada tarjeta; para escribir pide el token, que ya trae la app de escritorio y que `camaron up` imprime en la dirección (`#cam-token=…`). Sin él, solo lectura.

Tu gambita de prácticas ya ha colgado los post-its en su sitio: tú solo los mueves.

### 18. 🧰 Piezas de apoyo

```text
   uv        -> ejecuta Camarones (Python) sin instalar nada mas
   git       -> repos y el historial de la documentacion
   Node.js   -> OpenWiki, LikeC4 y mermaid-cli (el portal no necesita npm)
   gitleaks  -> busca secretos antes de cada commit y de publicar
   Docker    -> servir el portal como en produccion (opcional)
   Java      -> solo si hay repos Java/Kotlin (se detecta SDKMAN)
```

El asistente comprueba todo esto y lo instala por ti (winget en Windows, Homebrew en Mac) si eliges «Instalar todo lo recomendado». Solo git y Node.js son obligatorios. El control de calidad (mermaid-cli y gitleaks) viene con la instalación completa; mermaid-cli descarga un Chromium sin ventana la primera vez. Sin IA, cada repo recibe también `docs/repos/<repo>/reference.md`: comandos, variables de entorno, endpoints y topics leídos de sus ficheros, que `camaron blocks` y `sync` mantienen al día. También sin IA, `camaron diagrams` dibuja el mapa del sistema (`docs/architecture/system-map.md`: quién habla con quién y quién publica o consume cada topic) y, por repo, `docs/repos/<repo>/diagrams.md` (endpoints y estados de cada enum de estado; las transiciones no se adivinan). Son páginas normales de Docs (en architecture y en cada repo) hechas de bloques generados: una persona puede confirmar uno copiando el `sha=` del bloque en `confirmed=` y poniendo su nombre en `by=` (una palabra, o entre comillas si lleva espacios: `by="Ana López"`), p. ej. `<!-- generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`; entonces el kit ya no lo reescribe, y `check` avisa si el código cambió desde entonces o si ya no tiene la fuente del diagrama. Para quedarte con la versión del código, quita `confirmed=` y `by=` del marcador, ejecuta `camaron diagrams` y vuelve a confirmarlo. El portal dice de cada diagrama si viene del código, si se editó a mano, si lo confirmó alguien o si el código cambió. Las extensiones del equipo van como plugins en `.camarones/plugins/` (`camaron plugins add` las trae y las fija en plugins.lock); las que ejecutan código o guían a los agentes no se cargan hasta que las apruebas en tu máquina, y cualquier cambio vuelve a preguntar. También sin IA: `camaron history` lee el historial de git (ficheros más tocados, a quién preguntar), `camaron doctor --context` cuenta lo que carga cada sesión de un agente y `camaron repair` devuelve a su sitio los ficheros del kit si alguien los toca.

### 19. 🗺 Tu día a día

```text
   1. camarones              -> abre el asistente del proyecto (cam-docs)
   2. Siguiente paso         -> una sesion de IA hace la siguiente unidad
   3. Portal (camaron up)    -> leer, editar, confirmar o pedir cambios
   4. Wikis                  -> crear o refrescar la wiki de un repo
   5. Actualizar             -> cuando cambie el codigo
   6. Compartir              -> traer lo del equipo y publicar lo tuyo
```

Con esto basta, y todo está en la parte de arriba del menú. Puedes parar cuando quieras: el progreso se guarda solo. Esc siempre vuelve atrás.

¿Hay un Camarón nuevo? «Ajustes › ⬆️ Actualizar Camarón» (o `camaron self-update`) mira el kit oficial, te dice qué ha cambiado y, si le dices que sí, lo actualiza para todos los proyectos de esta máquina y reinicia el asistente. Tus proyectos y tu documentación no se tocan.

¿Quieres empezar de cero? «Ajustes › 🧹 Deshacer todo» (o `camaron uninstall`) guarda una copia .zip de cam-docs/, lo borra y quita todo rastro del kit de los repos y de la carpeta del workspace. Los repos quedan exactamente como en su último commit.
