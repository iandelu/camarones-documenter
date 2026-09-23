# 🦐 Camarones Documenter — Tutorial
Español abajo · English first.

## English

### 1. 🦐 Camarones Documenter: the big picture

```text
   your repos            the wizard              your AI               result
  +---------+          +-------------+       +------------+       +--------------+
  | repo-a  |--+       |             |       |  Claude    |       |  docs/       |
  | repo-b  |--+-----> |  CAMARONES  | ----> |  Code  or  | ----> |  README      |
  | repo-c  |--+       |  (wizard)   |       |  Codex     |       |  diagrams    |
  +---------+          +-------------+       +------------+       |  flows, ADRs |
                        installs, plans       reads the code       +------+-------+
                        and saves progress    and writes docs             |
                                                                          v
                                                                   +--------------+
                                                                   |  web portal  |
                                                                   +--------------+
```

Camarones Documenter turns several repos into living documentation that serves both people and AIs. You don't write the docs: the wizard prepares everything, your AI (Claude Code or Codex) analyses the code and writes, and you review and confirm. Everything lives in the project's docs/ folder (versioned with git) and can be browsed as a website.

### 2. 🧭 The wizard and the work plan

```text
   PLAN  (docs/.work/plan.yaml)
   [x] setup                       <- done by the wizard
   [x] discovery:repo-a            <- 1 AI session = 1 unit
   [>] discovery:repo-b   ...      <- half done: resumes by itself
   [ ] interview-context           <- the AI asks you questions
   [ ] arch-system
   [ ] flows-catalog  ...

   session 1 --> [x]   session 2 --> [x]   session 3 --> [>] (closed)  --> session 4 resumes
```

Documenting a project in depth doesn't fit in one AI conversation, so the work is split into small units. Every “🦐 Next step” opens a session that does ONE unit. The AI saves checkpoints while it works: if you close the terminal or the laptop, next time you get “▶ Continue” and it resumes from the last checkpoint. Each finished unit is committed locally so nothing is lost.

### 3. 🤖 Claude Code / Codex: your AI

```text
        +-----------------------------+
        |  > Follow docs/.work/       |      reads:  code, config, OpenAPI,
        |    next-prompt.md           |              graph, wiki, your answers
        |                             |
        |  * reading repo-a ...       |      writes: docs/*.md, C4 diagrams,
        |  * question: who calls      |              README, AGENTS.md
        |    this endpoint?           |
        +-----------------------------+      you only need ONE of them
```

Claude Code (Anthropic) and Codex (OpenAI) are agents that work in your terminal: they read code, run commands and write files. Camarones gives them the instructions for each unit (PLAYBOOK) and the format rules (CONVENTIONS). One of them is enough. With none, you can copy the prompt and paste it anywhere.

### 4. 📖 OpenWiki: each repo's wiki

```text
   repo-a/
   +-- src/ ...
   +-- openwiki/
       +-- overview.md        "The service exposes /orders"  [evidence: OrderController.java:42]
       +-- modules/...        "Publishes OrderCreated"       [evidence: OrderEvents.java:17]
       +-- claims.json        <- every claim points at the code
```

OpenWiki generates a standard wiki inside each repo (openwiki/ folder) where every claim is anchored to a file and line of code, so the AI can't make things up and anyone can check. Camarones fills what OpenWiki doesn't cover: the whole-project view, domain, business flows, deployment and decisions.

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

graphify walks the code and builds a graph: classes, functions, calls and cross-repo dependencies. The AI uses it to answer questions without reading thousands of files, and you can explore it in the portal (Explore → Code graph). A git hook keeps it up to date.

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

C4 draws architecture at zoom levels: the system and who uses it (context), the applications and databases (containers) and the parts of each application (components). LikeC4 keeps it as code in docs/architecture/*.c4: one model generates every diagram, so they never contradict each other. After installing you'll see an automatic first draft (“Does it look right? Shall I save it?”).

### 7. ✅ Review & verify: how much to trust each page

```text
    AI writes          you review              confirmed              code changes
   +----------+      +------------+         +-------------+         +----------------+
   |  draft   | ---> |  I read it | --ok--> | source of   | ------> | re-confirm     |
   |   (AI)   |      |            |         | truth       |         | (change seen)  |
   +----------+      +-----+------+         +-------------+         +----------------+
                           | something wrong
                           v
                   "request changes" --> the AI fixes it in the next session
```

Every page has a trust mark. 🤖 Draft: written by the AI, nobody reviewed it. ✅ Confirmed: a person read it and said “looks right”; from then on AIs treat it as the truth and don't rewrite it silently. ⚠️ Re-confirm: a confirmed page changed and needs another look. In “✅ Review” you go page by page: confirm, or write what's wrong and the AI fixes it.

### 8. 🌍 Bilingual: English + Spanish

```text
   docs/domain/glossary.md              (English, the official version)
          |  translation
          v
   docs/i18n/es/domain/glossary.md      (Spanish)   status: current | outdated | missing
```

Docs are written in English (best for AIs and mixed teams) and translated to Spanish. Camarones knows which translations are current and which fell behind when the original changed; the portal has a language switcher.

### 9. 🌐 The portal: docs as a website

```text
   +--------------------------------------------------------------+
   |  o o o   http://localhost:8080                               |
   +--------------------------------------------------------------+
   |  My Project           [ Search...        ]        [ES | EN]  |
   |  > Architecture       +--------------------------------+     |
   |  > Domain             |  Interactive C4 diagram        |     |
   |  > Flows              |  [web] --> [api] --> [DB]      |     |
   |  > Code graph         +--------------------------------+     |
   +--------------------------------------------------------------+
```

The portal (Starlight) brings all docs together in a website with search, interactive diagrams, the code graph and trust marks. Serve it with Docker (same as on a company server) or instantly without Docker, just on your computer. Everything works offline (on-premise).

### 10. 🔑 GitLab / GitHub tokens

```text
   OS keychain          --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        list projects       (OK)

   Claude / Codex  ---X--->  token             (never passed to them)
   project folder  ---X--->  token             (never written there)
```

If your repos are private, Camarones needs a token to clone and update them. It is stored in your OS keychain and used only by Camarones' own git commands: never written to the project or git config, never shared with Claude, Codex or other third parties.

### 11. ⚙️ CI: docs that update themselves

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- what changed in the code?
                  |-- AI updates only the affected pages
                  |-- check (links, sources, trust)
                  +-- builds the portal image --> server
```

Optional: a pipeline that, after each change in the repos, updates the affected docs and publishes the portal. You can also do it by hand with “🔄 Update docs after changes”.

### 12. 🧰 Supporting pieces

```text
   uv        -> runs Camarones (Python) without installing anything else
   git       -> repos and the docs history
   Node.js   -> OpenWiki, LikeC4 and the portal
   Docker    -> serve the portal like production (optional)
   Java      -> only for Java/Kotlin repos (SDKMAN is detected)
```

The wizard checks all of this and installs it for you (winget on Windows, Homebrew on Mac) when you choose “Install everything recommended”. Only git and Node.js are required.

### 13. 🗺 Your day to day

```text
   1. Open camarones.command (Mac) or camarones.cmd (Windows)
   2. 🦐 Next step          -> an AI session does the next unit
   3. ✅ Review & verify    -> confirm or request changes
   4. 🌐 Portal             -> browse it as a website
   5. 🔄 Update             -> when the code changes
```

That's all. Stop whenever you like: progress saves itself. Esc always goes back.

## Español

### 1. 🦐 Camarones Documenter: la foto completa

```text
   tus repos             el asistente            tu IA                 resultado
  +---------+          +-------------+       +------------+       +--------------+
  | repo-a  |--+       |             |       |  Claude    |       |  docs/       |
  | repo-b  |--+-----> |  CAMARONES  | ----> |  Code  o   | ----> |  README      |
  | repo-c  |--+       |  (wizard)   |       |  Codex     |       |  diagramas   |
  +---------+          +-------------+       +------------+       |  flujos, ADR |
                        instala, planifica    lee el codigo        +------+-------+
                        y guarda progreso     y escribe docs              |
                                                                          v
                                                                   +--------------+
                                                                   |  portal web  |
                                                                   +--------------+
```

Camarones Documenter convierte varios repos en una documentación viva que sirve a personas y a IAs. Tú no escribes la documentación: el asistente prepara todo, tu IA (Claude Code o Codex) analiza el código y escribe, y tú revisas y confirmas. Todo queda en la carpeta docs/ del proyecto (versionada con git) y se puede ver como una web.

### 2. 🧭 El asistente y el plan de trabajo

```text
   PLAN  (docs/.work/plan.yaml)
   [x] setup                       <- lo hace el asistente
   [x] discovery:repo-a            <- 1 sesion de IA = 1 unidad
   [>] discovery:repo-b   ...      <- a medias: se retoma sola
   [ ] interview-context           <- la IA te pregunta
   [ ] arch-system
   [ ] flows-catalog  ...

   sesion 1 --> [x]   sesion 2 --> [x]   sesion 3 --> [>] (cerraste)  --> sesion 4 continua
```

Documentar a fondo un proyecto no cabe en una sola conversación con la IA, así que el trabajo se divide en unidades pequeñas. Cada vez que eliges «🦐 Siguiente paso» se abre una sesión que hace UNA unidad. La IA guarda checkpoints mientras trabaja: si cierras la terminal o el portátil, la próxima vez aparece «▶ Continuar» y retoma desde el último checkpoint. Al terminar cada unidad se hace un commit local para que nada se pierda.

### 3. 🤖 Claude Code / Codex: tu IA

```text
        +-----------------------------+
        |  > Sigue docs/.work/        |      lee:  codigo, config, OpenAPI,
        |    next-prompt.md           |            grafo, wiki, tus respuestas
        |                             |
        |  * leyendo repo-a ...       |      escribe: docs/*.md, diagramas C4,
        |  * pregunta: ¿quien usa     |               README, AGENTS.md
        |    este endpoint?           |
        +-----------------------------+      solo necesitas UNO de los dos
```

Claude Code (Anthropic) y Codex (OpenAI) son agentes que trabajan en tu terminal: leen el código, ejecutan comandos y escriben ficheros. Camarones les prepara las instrucciones de cada unidad (PLAYBOOK) y las reglas de formato (CONVENTIONS). Con tener uno instalado basta. Si no tienes ninguno, puedes copiar el prompt y pegarlo donde quieras.

### 4. 📖 OpenWiki: la wiki de cada repo

```text
   repo-a/
   +-- src/ ...
   +-- openwiki/
       +-- overview.md        "El servicio expone /orders"  [evidencia: OrderController.java:42]
       +-- modules/...        "Publica OrderCreated"        [evidencia: OrderEvents.java:17]
       +-- claims.json        <- cada afirmacion apunta al codigo
```

OpenWiki genera dentro de cada repo una wiki estándar (carpeta openwiki/) donde cada afirmación está anclada a un fichero y línea del código. Así la IA no se inventa cosas y cualquiera puede comprobarlas. Camarones rellena lo que OpenWiki no cubre: visión del proyecto entero, dominio, flujos de negocio, despliegue y decisiones.

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

graphify recorre el código y construye un grafo: clases, funciones, llamadas y dependencias entre repos. La IA lo usa para responder preguntas sin leer miles de ficheros, y tú puedes verlo interactivo en el portal (Explorar → Grafo de código). Se actualiza solo con un hook de git.

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

C4 es una forma de dibujar la arquitectura por niveles de zoom: el sistema y quién lo usa (contexto), las aplicaciones y bases de datos (contenedores) y las piezas de cada aplicación (componentes). LikeC4 guarda todo como código en docs/architecture/*.c4: un solo modelo genera todos los diagramas, así que nunca se contradicen. Al instalar verás un primer borrador automático («¿Está bien? ¿Lo guardo?»).

### 7. ✅ Revisar y verificar: la confianza de cada página

```text
    IA escribe         tu revisas              confirmada             el codigo cambia
   +----------+      +------------+         +-------------+         +----------------+
   | borrador | ---> |  lo leo    | --ok--> | fuente de   | ------> | re-confirmar   |
   |   (IA)   |      |            |         | verdad      |         | (cambio visto) |
   +----------+      +-----+------+         +-------------+         +----------------+
                           | algo mal
                           v
                   "pedir cambios" --> la IA lo corrige en la siguiente sesion
```

Cada página lleva una marca de confianza. 🤖 Borrador: la escribió la IA y nadie la ha revisado. ✅ Confirmada: una persona la leyó y dijo «está bien»; a partir de ahí las IAs la tratan como verdad y no la reescriben sin avisar. ⚠️ Re-confirmar: alguien cambió una página confirmada y hay que volver a mirarla. En «✅ Revisar» lees página a página: confirmas, o escribes qué está mal y la IA lo arregla.

### 8. 🌍 Bilingüe: inglés + español

```text
   docs/domain/glossary.md              (ingles, la version oficial)
          |  traduccion
          v
   docs/i18n/es/domain/glossary.md      (espanol)   estado: al dia | desactualizada | falta
```

La documentación se escribe en inglés (lo que mejor entienden las IAs y los equipos mixtos) y se traduce al español. Camarones sabe qué traducciones están al día y cuáles se quedaron atrás cuando cambió el original; el portal tiene selector de idioma.

### 9. 🌐 El portal: la documentación como web

```text
   +--------------------------------------------------------------+
   |  o o o   http://localhost:8080                               |
   +--------------------------------------------------------------+
   |  Mi Proyecto          [ Buscar...        ]        [ES | EN]  |
   |  > Arquitectura       +--------------------------------+     |
   |  > Dominio            |  Diagrama C4 interactivo       |     |
   |  > Flujos             |  [web] --> [api] --> [DB]      |     |
   |  > Grafo de codigo    +--------------------------------+     |
   +--------------------------------------------------------------+
```

El portal (Starlight) junta toda la documentación en una web con buscador, diagramas interactivos, grafo de código y marcas de confianza. Puedes servirlo con Docker (igual que en un servidor de la empresa) o sin Docker, al momento, solo en tu ordenador. Todo funciona sin Internet (on-premise).

### 10. 🔑 Tokens de GitLab / GitHub

```text
   llavero del sistema  --->  Camarones  --->  git clone / pull   (OK)
   (Keychain / Windows)                        listar proyectos    (OK)

   Claude / Codex  ---X--->  token             (nunca se les pasa)
   carpeta del proyecto ---X---> token         (nunca se escribe)
```

Si tus repos son privados, Camarones necesita un token para clonarlos y actualizarlos. Se guarda en el llavero de tu sistema operativo y solo lo usa Camarones en sus propios comandos git: no se escribe en el proyecto, ni en git config, ni se comparte con Claude, Codex u otros terceros.

### 11. ⚙️ CI: documentación que se actualiza sola

```text
   git push --> pipeline (GitLab CI / GitHub Actions)
                  |-- que ha cambiado en el codigo?
                  |-- IA actualiza solo las paginas afectadas
                  |-- check (enlaces, fuentes, confianza)
                  +-- construye la imagen del portal --> servidor
```

Opcional: un pipeline que, tras cada cambio en los repos, actualiza la documentación afectada y publica el portal. También se puede hacer a mano con «🔄 Actualizar doc tras cambios».

### 12. 🧰 Piezas de apoyo

```text
   uv        -> ejecuta Camarones (Python) sin instalar nada mas
   git       -> repos y el historial de la documentacion
   Node.js   -> OpenWiki, LikeC4 y el portal
   Docker    -> servir el portal como en produccion (opcional)
   Java      -> solo si hay repos Java/Kotlin (se detecta SDKMAN)
```

El asistente comprueba todo esto y lo instala por ti (winget en Windows, Homebrew en Mac) si eliges «Instalar todo lo recomendado». Solo git y Node.js son obligatorios.

### 13. 🗺 Tu día a día

```text
   1. Abre camarones.command (Mac) o camarones.cmd (Windows)
   2. 🦐 Siguiente paso      -> una sesion de IA hace la siguiente unidad
   3. ✅ Revisar y verificar -> confirmas o pides cambios
   4. 🌐 Portal              -> lo ves como web
   5. 🔄 Actualizar          -> cuando cambie el codigo
```

Con esto basta. Puedes parar cuando quieras: el progreso se guarda solo. Esc siempre vuelve atrás.
