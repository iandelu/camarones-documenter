# 🦐 Camarones Documenter — Tutorial
Español abajo · English first.

## English

### 1. 🦐 Camarones Documenter: the big picture

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

Camarones Documenter turns several repos into living documentation that serves both people and AIs. You don't write the docs: the wizard prepares everything, your AI (Claude Code or Codex) analyses the code and writes, and you review and confirm. Everything lives in the cam-docs/ folder next to your repos: its own git repo with the docs and the tool configuration, meant to be shared with the team. Your service repos get no kit files.

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

Documenting a project in depth doesn't fit in one AI conversation, so the work is split into small units. Every “🦐 Next step” opens a session that does ONE unit. The AI saves checkpoints while it works: if you close the terminal or the laptop, next time you get “▶ Continue” and it resumes from the last checkpoint. Each finished unit is committed locally in cam-docs so nothing is lost (you decide when to push).

### 3. 🤖 Claude Code / Codex: your AI

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

Claude Code (Anthropic) and Codex (OpenAI) are agents that work in your terminal: they read code, run commands and write files. Camarones gives them the instructions for each unit (PLAYBOOK) and the format rules (CONVENTIONS). One of them is enough. With none, you can copy the prompt and paste it anywhere. Later, when you implement features, the AI looks the docs up through the “camarones” MCP server (search, read pages, repo graph).

### 4. 📖 OpenWiki: each repo's wiki

```text
   cam-docs/wikis/repo-a/     <- the wiki lives here, versioned with the rest of the docs
   +-- overview.md        "The service exposes /orders"  [evidence: OrderController.java:42]
   +-- modules/...        "Publishes OrderCreated"       [evidence: OrderEvents.java:17]
   +-- .claims/*.json     <- every claim points at the code

   repo-a/openwiki  -->  link to cam-docs/wikis/repo-a (not versioned in the repo)

   generate or update:  portal > Wikis  |  wizard > Wikis  |  camarones wiki repo-a
```

OpenWiki writes a standard wiki for each repo where every claim is anchored to a file and line of code, so the AI can't make things up and anyone can check. The wiki is stored in cam-docs/wikis/<repo>, so the service repo stays clean. Generate or update it from the portal (Wikis tab, with a live log), from the wizard (📚 Wikis) or with “camarones wiki <repo>”; its pages show up under Docs as repos/<repo>/. Each wiki is a full agent run, so only the repos you choose get one (wizard > Wikis > choose), and the first one waits for the repo-brief, which gives it the repo's role and glossary. They run one at a time. Camarones fills what OpenWiki doesn't cover: the whole-project view, domain, business flows, deployment and decisions.

### 5. 🕸 graphify: the code graph

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

graphify walks the code and builds a graph: classes, functions, calls and cross-repo dependencies. The AI uses it to answer questions without reading thousands of files, and you explore it in the portal's “Code graph” tab (all repos together or one at a time). A git hook keeps it up to date, or press “Rebuild” in the local portal.

### 6. 🏗 LikeC4: architecture diagrams (C4 model)

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

C4 draws architecture at zoom levels: the system and who uses it (context), the applications and databases (containers) and the parts of each application (components). LikeC4 keeps it as code in docs/architecture/*.c4: one model generates every diagram, so they never contradict each other. You browse it in the portal's “Architecture (C4)” tab. After installing you'll see an automatic first draft (“Does it look right? Shall I save it?”). The AI also queries the model while it writes, through the “likec4” MCP server (who calls this service? what sits between A and B?).

### 7. ✅ Review & verify: how much to trust each page

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

Every page has a trust mark. 🤖 Draft: written by the AI, nobody reviewed it. ✅ Confirmed: a person read it and said “looks right”; from then on AIs treat it as the truth and don't rewrite it silently. ⚠️ Re-confirm: a confirmed page changed (by hand, in the portal or by the AI) and needs another look. Review in the portal (Confirm and Request changes buttons on every page; the Review tab lists what's pending) or in the wizard's “✅ Review”.

### 8. 🧪 Quality gate: what check looks at

```text
   camarones check
     |-- broken links between pages           ERROR
     |-- Mermaid diagrams that don't render   ERROR   (mermaid-cli)
     |-- secrets copied into the docs         ERROR   (gitleaks: blocks commit and portal)
     |-- glossary words to avoid              warning (ERROR with --strict)
     +-- sources, frontmatter, translations   ERROR / warning
```

The AI writes fast and sometimes slips on small things: a link to a page that doesn't exist, a diagram that doesn't render or a token copied from a config file. “camarones check” looks for them when each unit closes and in CI. Secrets are special: while gitleaks finds one, the checkpoint commit and the portal export don't happen (the value is never shown, only file and line). Fill the glossary's “Avoid” column (say “purchase, request” for Order) and check warns wherever those words appear. mermaid-cli and gitleaks come with the full install; without them, check says so once and skips that check.

### 9. 🌍 Bilingual: English + Spanish

```text
   docs/domain/glossary.md              (English, the official version)
          |  translation
          v
   docs/i18n/es/domain/glossary.md      (Spanish)   status: current | outdated | missing
```

Docs are written in English (best for AIs and mixed teams) and translated to Spanish. Camarones knows which translations are current and which fell behind when the original changed. The portal's language switch changes both the interface and the docs; a page with no translation yet is shown in English with a notice.

### 10. 🌐 The portal: docs as a website

```text
   +----------------------------------------------------------------------------+
   | Camarones  My Project  [Docs] Architecture Graph Wikis Review   English v  |
   |                        [ Search the docs...             ]                  |
   +----------------------------------------------------------------------------+
   | ARCHITECTURE     |  Architecture: first look                               |
   |  > Context       |  (draft)  docs/architecture/first-look.md               |
   | DOMAIN           |  [Edit] [Confirm] [Request changes]                     |
   |  > Glossary      |  ...                                                    |
   +----------------------------------------------------------------------------+
```

The 🦐 portal brings the docs (with search, editing and review), the C4 explorer, the code graph and the OpenWiki wikis together in one site, in English or Spanish. It has two modes with the same interface: the local portal (`camarones up`, or wizard → 🌐 Portal → 📝 Open the portal), where you can edit, and the read-only export (`camarones portal`) that is deployed with Docker or on any static host. `camarones up --static` shows you the export as is. Everything works offline (on-premise).

### 11. ✏️ Where and when you can edit

```text
   WHERE                        WHAT YOU CAN DO                      WHERE IT GOES
   ---------------------------  -----------------------------------  ------------------------
   local portal                 edit, new page, confirm,             cam-docs + local commit
   (camarones up)               request changes, generate wikis,     (you push it)
                                rebuild C4 and graph
   deployed portal              read and search; "Edit" opens the    merge request in the
   (export)                     file in GitLab / GitHub              cam-docs repo
   your editor / IDE            any .md in cam-docs/docs             cam-docs (plain git)
   the AI (Next step)           only its unit; never overwrites      local commit per unit
                                confirmed pages silently
```

In the local portal, “Edit” opens the markdown with a live preview; saving writes to cam-docs/docs and, with “commit to cam-docs” ticked, makes a local commit (sharing it with git push is up to you). “+ New page” creates a page of your own and “Confirm” signs with your git user name. With Spanish selected you edit the translation. The deployed portal doesn't edit: it's a snapshot of the last export; its “Edit” button takes you to the file in GitLab/GitHub (when cam-docs has a remote), the change goes in as a merge request and CI publishes it again. Editing a ✅ page turns it ⚠️ until someone checks it. Don't hand-edit generated files (llms.txt, .status.json, viewers); wikis are better regenerated from the Wikis tab, since an update can rewrite what you change.

### 12. 🔑 GitLab / GitHub tokens

```text
   OS keychain          --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        list projects       (OK)

   Claude / Codex  ---X--->  token             (never passed to them)
   project folder  ---X--->  token             (never written there)
```

If your repos are private, Camarones needs a token to clone and update them. It is stored in your OS keychain and used only by Camarones' own git commands: never written to the project or git config, never shared with Claude, Codex or other third parties.

### 13. ⚙️ CI: docs that update themselves

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- what changed in the code?
                  |-- AI updates only the affected pages
                  |-- check --secrets  (a secret stops here: no MR)
                  |-- check (links, diagrams, sources, trust)
                  +-- exports the portal (camarones portal) --> nginx image / Pages
```

Optional: a pipeline that, after each change in the repos or in cam-docs, updates the affected docs and publishes the read-only portal. So a merge request opened from the deployed portal's “Edit” shows up once merged. You can also do it by hand with “🔄 Update docs after changes” and “📦 Export the portal”.

### 14. 🧰 Supporting pieces

```text
   uv        -> runs Camarones (Python) without installing anything else
   git       -> repos and the docs history
   Node.js   -> OpenWiki, LikeC4 and mermaid-cli (the portal needs no npm)
   gitleaks  -> looks for secrets before every commit and before publishing
   Docker    -> serve the portal like production (optional)
   Java      -> only for Java/Kotlin repos (SDKMAN is detected)
```

The wizard checks all of this and installs it for you (winget on Windows, Homebrew on Mac) when you choose “Install everything recommended”. Only git and Node.js are required. The quality gate (mermaid-cli and gitleaks) comes with the full install; mermaid-cli downloads a headless Chromium the first time.

### 15. 🗺 Your day to day

```text
   1. camarones                -> opens the project's wizard (cam-docs)
   2. 🦐 Next step             -> an AI session does the next unit
   3. 🌐 Portal (camarones up) -> read, edit, confirm or request changes
   4. 📚 Wikis                 -> create or refresh a repo's wiki
   5. 🔄 Update                -> when the code changes
   6. git push in cam-docs     -> share it with the team
```

That's all. Stop whenever you like: progress saves itself. Esc always goes back.

## Español

### 1. 🦐 Camarones Documenter: la foto completa

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

Camarones Documenter convierte varios repos en una documentación viva que sirve a personas y a IAs. Tú no escribes la documentación: el asistente prepara todo, tu IA (Claude Code o Codex) analiza el código y escribe, y tú revisas y confirmas. Todo queda en la carpeta cam-docs/, junto a tus repos: es un repo git propio con la documentación y la configuración de las herramientas, pensado para compartirlo con el equipo. Tus repos de servicio no reciben archivos del kit.

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

Documentar a fondo un proyecto no cabe en una sola conversación con la IA, así que el trabajo se divide en unidades pequeñas. Cada vez que eliges «🦐 Siguiente paso» se abre una sesión que hace UNA unidad. La IA guarda checkpoints mientras trabaja: si cierras la terminal o el portátil, la próxima vez aparece «▶ Continuar» y retoma desde el último checkpoint. Al terminar cada unidad se hace un commit local en cam-docs para que nada se pierda (el push lo decides tú).

### 3. 🤖 Claude Code / Codex: tu IA

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

Claude Code (Anthropic) y Codex (OpenAI) son agentes que trabajan en tu terminal: leen el código, ejecutan comandos y escriben ficheros. Camarones les prepara las instrucciones de cada unidad (PLAYBOOK) y las reglas de formato (CONVENTIONS). Con tener uno instalado basta. Si no tienes ninguno, puedes copiar el prompt y pegarlo donde quieras. Cuando luego implementéis features, la IA consulta la documentación con el servidor MCP «camarones» (buscar, leer páginas, grafo del repo).

### 4. 📖 OpenWiki: la wiki de cada repo

```text
   cam-docs/wikis/repo-a/     <- la wiki vive aqui, versionada con el resto de la doc
   +-- overview.md        "El servicio expone /orders"  [evidencia: OrderController.java:42]
   +-- modules/...        "Publica OrderCreated"        [evidencia: OrderEvents.java:17]
   +-- .claims/*.json     <- cada afirmacion apunta al codigo

   repo-a/openwiki  -->  enlace a cam-docs/wikis/repo-a (sin versionar en el repo)

   generar o actualizar:  portal > Wikis  |  asistente > Wikis  |  camarones wiki repo-a
```

OpenWiki escribe una wiki estándar de cada repo donde cada afirmación está anclada a un fichero y línea del código: la IA no se inventa cosas y cualquiera puede comprobarlas. La wiki se guarda en cam-docs/wikis/<repo>, así que el repo de servicio queda limpio. La generas o actualizas desde el portal (pestaña Wikis, con el log en directo), desde el asistente (📚 Wikis) o con «camarones wiki <repo>»; sus páginas aparecen en Docs, en repos/<repo>/. Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas (asistente > Wikis > elegir), y la primera espera al repo-brief, que le da el rol y el glosario del repo. Se lanzan de una en una. Camarones rellena lo que OpenWiki no cubre: visión del proyecto entero, dominio, flujos de negocio, despliegue y decisiones.

### 5. 🕸 graphify: el grafo del código

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

graphify recorre el código y construye un grafo: clases, funciones, llamadas y dependencias entre repos. La IA lo usa para responder preguntas sin leer miles de ficheros, y tú lo exploras en la pestaña «Grafo de código» del portal (todos los repos juntos o uno a uno). Se actualiza solo con un hook de git, o con «Reconstruir» en el portal local.

### 6. 🏗 LikeC4: diagramas de arquitectura (modelo C4)

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

C4 es una forma de dibujar la arquitectura por niveles de zoom: el sistema y quién lo usa (contexto), las aplicaciones y bases de datos (contenedores) y las piezas de cada aplicación (componentes). LikeC4 guarda todo como código en docs/architecture/*.c4: un solo modelo genera todos los diagramas, así que nunca se contradicen. Lo navegas en la pestaña «Arquitectura (C4)» del portal. Al instalar verás un primer borrador automático («¿Está bien? ¿Lo guardo?»). La IA también consulta el modelo mientras escribe, con el servidor MCP «likec4» (¿quién llama a este servicio?, ¿qué hay entre A y B?).

### 7. ✅ Revisar y verificar: la confianza de cada página

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

Cada página lleva una marca de confianza. 🤖 Borrador: la escribió la IA y nadie la ha revisado. ✅ Confirmada: una persona la leyó y dijo «está bien»; a partir de ahí las IAs la tratan como verdad y no la reescriben sin avisar. ⚠️ Re-confirmar: alguien cambió una página confirmada (a mano, en el portal o la IA) y hay que volver a mirarla. Puedes revisar en el portal (botones Confirmar y Pedir cambios en cada página; la pestaña Revisión lista lo pendiente) o en «✅ Revisar» del asistente.

### 8. 🧪 Control de calidad: lo que revisa check

```text
   camarones check
     |-- enlaces rotos entre paginas          ERROR
     |-- diagramas Mermaid que no se dibujan  ERROR   (mermaid-cli)
     |-- secretos copiados en la doc          ERROR   (gitleaks: bloquea commit y portal)
     |-- palabras a evitar del glosario       aviso   (ERROR con --strict)
     +-- fuentes, frontmatter, traducciones   ERROR / aviso
```

La IA escribe rápido y a veces falla en lo pequeño: un enlace a una página que no existe, un diagrama que no se dibuja o un token copiado de un fichero de configuración. «camarones check» lo revisa al cerrar cada unidad y en el CI. Los secretos son especiales: mientras gitleaks encuentre uno, no se hace el commit de checkpoint ni se exporta el portal (nunca se muestra el valor, solo fichero y línea). Si en el glosario rellenas la columna «Avoid» (por ejemplo «compra, petición» para Pedido), check avisa donde aparezcan esas palabras. mermaid-cli y gitleaks vienen con la instalación completa; si faltan, check lo avisa una vez y se salta esa comprobación.

### 9. 🌍 Bilingüe: inglés + español

```text
   docs/domain/glossary.md              (ingles, la version oficial)
          |  traduccion
          v
   docs/i18n/es/domain/glossary.md      (espanol)   estado: al dia | desactualizada | falta
```

La documentación se escribe en inglés (lo que mejor entienden las IAs y los equipos mixtos) y se traduce al español. Camarones sabe qué traducciones están al día y cuáles se quedaron atrás cuando cambió el original. El selector de idioma del portal cambia la interfaz y la documentación; si una página aún no tiene traducción, se muestra en inglés con un aviso.

### 10. 🌐 El portal: la documentación como web

```text
   +----------------------------------------------------------------------------+
   | Camarones  Mi Proyecto  [Docs] Arquitectura Grafo Wikis Revision  Espanol v|
   |                         [ Buscar en la doc...            ]                 |
   +----------------------------------------------------------------------------+
   | ARQUITECTURA     |  Arquitectura: primer vistazo                           |
   |  > Contexto      |  (borrador)  docs/architecture/first-look.md            |
   | DOMINIO          |  [Editar] [Confirmar] [Pedir cambios]                   |
   |  > Glosario      |  ...                                                    |
   +----------------------------------------------------------------------------+
```

El portal 🦐 junta en una sola web la documentación (con buscador, edición y revisión), el explorador C4, el grafo de código y las wikis de OpenWiki, en español o inglés. Tiene dos modos con la misma interfaz: el portal local (`camarones up`, o asistente → 🌐 Portal → 📝 Abrir el portal), donde se puede editar, y la exportación de solo lectura (`camarones portal`) que se despliega con Docker o en cualquier hosting estático. `camarones up --static` te enseña la exportación tal cual. Todo funciona sin Internet (on-premise).

### 11. ✏️ Dónde y cuándo se puede editar

```text
   DONDE                        QUE PUEDES HACER                     DONDE QUEDA
   ---------------------------  -----------------------------------  ------------------------
   portal local                 editar, pagina nueva, confirmar,     cam-docs + commit local
   (camarones up)               pedir cambios, generar wikis,        (el push lo haces tu)
                                reconstruir C4 y grafo
   portal desplegado            leer y buscar; "Editar" abre el      merge request en el
   (exportacion)                fichero en GitLab / GitHub           repo cam-docs
   tu editor / IDE              cualquier .md de cam-docs/docs       cam-docs (git normal)
   la IA (Siguiente paso)       solo su unidad; no pisa lo           commit local por unidad
                                confirmado sin avisar
```

En el portal local, «Editar» abre el markdown con vista previa; al guardar se escribe en cam-docs/docs y, si marcas «commit en cam-docs», se hace un commit local (compartirlo con git push es cosa tuya). «+ Nueva página» crea una página tuya y «Confirmar» firma con tu usuario de git. Con el idioma en español editas la traducción. El portal desplegado no edita: es una foto de la última exportación; su botón «Editar» te lleva al fichero en GitLab/GitHub (si cam-docs tiene remote) y el cambio entra por merge request, y el CI vuelve a publicar. Editar una página ✅ la pasa a ⚠️ hasta que alguien la mire. No edites a mano lo generado (llms.txt, .status.json, visores): las wikis mejor regenerarlas desde la pestaña Wikis, porque una actualización puede reescribir lo que cambies.

### 12. 🔑 Tokens de GitLab / GitHub

```text
   llavero del sistema  --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        listar proyectos    (OK)

   Claude / Codex  ---X--->  token             (nunca se les pasa)
   carpeta del proyecto ---X---> token         (nunca se escribe)
```

Si tus repos son privados, Camarones necesita un token para clonarlos y actualizarlos. Se guarda en el llavero de tu sistema operativo y solo lo usa Camarones en sus propios comandos git: no se escribe en el proyecto, ni en git config, ni se comparte con Claude, Codex u otros terceros.

### 13. ⚙️ CI: documentación que se actualiza sola

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- que ha cambiado en el codigo?
                  |-- IA actualiza solo las paginas afectadas
                  |-- check --secrets  (un secreto para aqui: no hay MR)
                  |-- check (enlaces, diagramas, fuentes, confianza)
                  +-- exporta el portal (camarones portal) --> imagen nginx / Pages
```

Opcional: un pipeline que, tras cada cambio en los repos o en cam-docs, actualiza la documentación afectada y publica el portal de solo lectura. Así, un merge request hecho desde «Editar» del portal desplegado aparece publicado al fusionarse. También se puede hacer a mano con «🔄 Actualizar doc tras cambios» y «📦 Exportar el portal».

### 14. 🧰 Piezas de apoyo

```text
   uv        -> ejecuta Camarones (Python) sin instalar nada mas
   git       -> repos y el historial de la documentacion
   Node.js   -> OpenWiki, LikeC4 y mermaid-cli (el portal no necesita npm)
   gitleaks  -> busca secretos antes de cada commit y de publicar
   Docker    -> servir el portal como en produccion (opcional)
   Java      -> solo si hay repos Java/Kotlin (se detecta SDKMAN)
```

El asistente comprueba todo esto y lo instala por ti (winget en Windows, Homebrew en Mac) si eliges «Instalar todo lo recomendado». Solo git y Node.js son obligatorios. El control de calidad (mermaid-cli y gitleaks) viene con la instalación completa; mermaid-cli descarga un Chromium sin ventana la primera vez.

### 15. 🗺 Tu día a día

```text
   1. camarones                -> abre el asistente del proyecto (cam-docs)
   2. 🦐 Siguiente paso        -> una sesion de IA hace la siguiente unidad
   3. 🌐 Portal (camarones up) -> leer, editar, confirmar o pedir cambios
   4. 📚 Wikis                 -> crear o refrescar la wiki de un repo
   5. 🔄 Actualizar            -> cuando cambie el codigo
   6. git push en cam-docs     -> compartir con el equipo
```

Con esto basta. Puedes parar cuando quieras: el progreso se guarda solo. Esc siempre vuelve atrás.
