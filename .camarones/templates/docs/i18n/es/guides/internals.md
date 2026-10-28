---
type: guide
title: Cómo funciona Camarón
description: Camarón por dentro — sus piezas, dónde vive cada fichero, el servidor del proyecto y sus tokens, las APIs de la CLI y HTTP, el plan y el harness, el enrutado de agentes, la confianza y la frescura, los servidores MCP y los plugins.
tags: [architecture, tooling, mcp, api]
x-owner: human
---
# Cómo funciona Camarón

> **TL;DR:** Una sola CLI de Python (`camaron`) hace todo el trabajo. El asistente de la terminal, la app de escritorio
> y el portal son tres caras de ella: la app ejecuta comandos del catálogo a través de un servidor local por proyecto,
> el portal lee y edita por ese mismo servidor, y los agentes leen la documentación por el servidor MCP `camarones`.
> Todo lo que el kit escribe para un proyecto vive en `cam-docs/`, un repo git junto al código.

## Las piezas

```text
  tus repos (nunca reciben ficheros del kit)             cam-docs/ (su propio repo git)
  orders-api/  payments-api/  web/                       docs/  wikis/  backlog/  .camarones/
        |  lee                                                 ^  escribe        |  lee
        v                                                      |                 v
  +------------------------------- camaron (CLI de Python) ---------------------------+
  |  asistente (terminal)   catálogo de comandos   harness: plan, ejecuciones, KPIs     |
  +-----------+--------------------+--------------------------+-----------------------+
              |                    |                          |
     servidor del proyecto    ejecutores de agentes      servidor MCP "camarones"
     /  portal   /desktop/    Claude Code, Codex,        search_docs, read_doc, ask,
     /api/...                 OpenCode, comandos         propose_edit, board_next…
        |          |                                          |
   navegador    app de escritorio (Electron)           sesiones de Claude Code / Codex
   (portal)     una ventana por proyecto               (también dentro de un solo repo)
```

| Pieza | Qué es | Dónde |
|---|---|---|
| CLI | `camaron <comando>`, un script en línea de `uv`; todo el comportamiento del kit | `.camarones/camarones.py`, `.camarones/lib/` |
| Asistente | Los menús de la terminal sobre los mismos comandos | `camaron` (sin argumentos) |
| Servidor del proyecto | Sirve el portal, la interfaz de la app y la API HTTP de un proyecto | `camaron up`; la app arranca uno por ventana |
| Portal | App de React que lee y edita la documentación | `/` del servidor, o un exportado estático |
| App de escritorio | Ventanas de Electron sobre los servidores de cada proyecto, más la pantalla de inicio | `camaron app`; Electron fijado en `~/.camarones/desktop` |
| Harness | El plan como datos, ejecuciones en paralelo en worktrees, enrutado de agentes, registros, KPIs | `lib/harness/`, `lib/pipelines/` |
| Servidores MCP | `camarones` (la documentación, el plan, el tablero) y `likec4` (el modelo de arquitectura) para los agentes | `.mcp.json`, `.codex/` |

## Dónde vive cada cosa

**En la carpeta del workspace** (la que agrupa los repos):

```text
mi-proyecto/
├── cam-docs/                 el repo git propio del proyecto: compártelo con el equipo
│   ├── .camarones/           workspace.yaml (repos, stack, ajustes), PLAYBOOK.md, CONVENTIONS.md, skeletons/,
│   │                         pipeline.yaml (tus cambios al plan), plugins/ + plugins.lock, .cache/ (ignorada)
│   ├── docs/                 la documentación; docs/i18n/es/ las traducciones al español
│   │   └── .work/            plan.yaml, handoff.md, units/ (checkpoints), kpis/, usage/, proposals/
│   ├── wikis/<repo>/         la wiki OpenWiki de cada repo
│   ├── backlog/              el tablero: tasks/*.md (formato Backlog.md) y board.yaml
│   ├── graph/<repo>/         el grafo del código (ignorado)
│   ├── .claude/ .codex/ .agents/ .mcp.json AGENTS.md CLAUDE.md     la configuración de los agentes
├── .claude → cam-docs/.claude   .mcp.json → …   AGENTS.md → …       enlaces: un agente abierto aquí lo ve todo
├── .cw/<n>/                  la copia de cam-docs de una unidad mientras dura una ejecución en paralelo
└── orders-api/  payments-api/  …   los repos de servicio, intactos
```

`.camarones/.cache/` guarda lo que se puede reconstruir: los registros de las ejecuciones (`runs/<run>/events.jsonl`),
la web exportada (`site/`), el índice del tablero (`board.db`), la foto de la salud y copias de los ficheros del kit
sustituidos; y lo que dejan en esta máquina las sesiones de la app: el prompt de cada una (`prompts/`), el registro de
la sesión de cada unidad (`sessions/`) y las terminales del lienzo (`terminals/`).

**En esta máquina:**

| Ruta | Guarda |
|---|---|
| `~/.camarones.json` | Lo que eliges en esta máquina: idioma, modelos de Claude Code y de Codex, dónde abre la app las sesiones (`sessions`), ejecutores extra, cambios al enrutado, modo en línea de OSV |
| `~/.camarones/kit` (Windows: `%LOCALAPPDATA%\camarones-documenter\kit`) | La instalación global del kit, compartida por todos los proyectos |
| `~/.camarones/desktop` | El Electron fijado para `camaron app` |
| `~/.camarones/bin`, `~/.camarones/osv-db` | Binarios fijados (gitleaks, OSV-Scanner) y la base de datos sin conexión de OSV |
| `~/.camarones/trust/` | Lo que aprobaste de la configuración de agentes de cada equipo; nunca en un repo |
| `~/.camarones/install/` | Lo que el kit instaló aquí (sus skills, los de graphify y OpenWiki), para que no pida aprobación |
| `~/.camarones/mcp-token` | El token de `camaron mcp --http` |
| `~/.camarones/hosts.json` | Qué servidor es GitLab, GitHub o SonarQube, y su usuario (sin secretos) |
| Llavero del sistema | Los tokens en sí (`credentials.json` solo donde no hay llavero) |

## El servidor del proyecto

`camaron up` arranca el servidor del proyecto actual (puerto 8080 por defecto). Sirve el portal en `/`, la interfaz de
la app en `/desktop/` y la API en `/api/`. La app de escritorio arranca su propio servidor por ventana
(`camaron up --foreground --port 0`) y lo para al cerrar la ventana.

Quién puede hacer qué depende de lo que lleve la petición:

| Quién llama | Cabecera o token | Puede |
|---|---|---|
| Cualquier página del portal en vivo | `X-Camarones: 1` al escribir (un navegador en otra web no puede mandarla) | Leer todo; editar y crear páginas, hacer commit, confirmar, pedir cambios, decidir revisiones, editar el modelo C4, responder la entrevista, compartir, aprobar o reintentar unidades, anotar búsquedas sin respuesta |
| El portal con el **token del portal** (`#cam-token=…` de `camaron up`, o el de la sesión que la app le da al navegador) | `X-Camaron-Token` | Lo anterior, y además escribir en el Tablero y guardar o sugerir historias |
| La app de escritorio (**token de la app**, uno aleatorio por cada arranque del servidor) | `X-Camaron-Token` | Todo, también lo que se ejecuta en la máquina: ejecuciones, wikis, builds, análisis, ficheros de CI, la respuesta con IA, recoger el coste del plan y todo `/api/app/` |

Con cualquiera de los dos tokens, el servidor rechaza peticiones cuyo `Host` no sea `localhost` o `127.0.0.1` en su
puerto (sin *DNS rebinding*). La ventana de la app no puede salir de `/desktop/`: los enlaces al portal y a la web se
abren en el navegador del sistema. Los tokens nunca llegan a los comandos que ejecuta el servidor.

## La CLI es la API

Cada función es un comando `camaron`; el asistente, la app y la CI solo llaman a comandos.

- `camaron catalog --json` lista cada comando con su zona, dónde vive (portal, app, CLI), sus nombres en español e
  inglés, si usa IA o borra datos, y sus argumentos tal como los define el parser. `camaron catalog --check` falla si
  un comando no tiene sitio.
- La mayoría de los comandos aceptan `--json` y entonces imprimen JSON en stdout, para scripts y para la app, en lugar
  del texto para personas.
- Códigos de salida: `0` hecho, `1` rechazado o fallido, `2` un error de uso. Un rechazo con `--json` imprime
  `{"error": "<código>", "detail": "…"}`; los scripts leen `error`, y `detail` es para personas y puede venir en
  español.
- Un comando que cambia datos pregunta antes; `--yes` responde por ti y `--dry-run` enseña la lista sin tocar nada.

La app ejecuta comandos con `POST /api/app/cmd`: los argumentos se comprueban contra el parser (se rechazan los
desconocidos o los valores que empiezan por `-`), no hay shell de por medio, y un comando destructivo o con `--yes`
responde 409 hasta que la app confirma; entonces el servidor añade `--yes` él mismo.

<!-- cmd:check -->

## La API HTTP

La API sirve al portal y a la app; no es una interfaz pública estable (esa es la CLI). Por grupos:

| Grupo | Endpoints |
|---|---|
| Documentación | `GET tree`, `doc?path&lang`, `search?q`, `ask?q`, `status`, `reviews`, `viewers`, `wikis`, `codemap?repo`; `POST doc`, `commit`, `new`, `confirm`, `feedback`, `review/decide` |
| Arquitectura | `GET c4/view?id`; `POST c4/element`, `c4/confirm`, `c4/relation`, `c4/remove` |
| Tablero e historias | `GET kanban`, `kanban/item?id`, `kanban/waves`, `stories`, `stories/item`, `stories/files`; `POST stories/analyze`; con un token: `POST kanban/init`, `add`, `move`, `assign`, `link`, `archive`, `stories/save`, `stories/suggest` |
| Plan | `GET pipeline?lang`, `runs/<id>`, `runs/<id>/events` (eventos enviados por el servidor), `plan/cost`, `interview`, `sync`; `POST units/approve`, `units/retry`, `interview/answer`, `sync/share` |
| Calidad | `GET health`, `kpis`, `inventory`, `schemas`, `ci`; `POST kpis/miss` |
| Trabajo en la máquina (token de la app) | `POST runs`, `runs/<id>/cancel`, `wiki`, `build`, `inventory`, `schemas`, `ci`, `ask/answer`, `plan/cost` |
| La app (token de la app) | `GET app/info`, `catalog`, `summary`, `machine`, `guide`, `creds`, `agents`, `terminals`, `terminals/stream` (eventos enviados por el servidor), `doctor`, `kitdev`, `onboard/*`, `jobs/<id>/events`; `POST app/cmd`, `terminals` (una sesión, en el lienzo o en una ventana; su nombre antiguo, `agent`, sigue valiendo), `terminals/<id>/input`, `terminals/<id>/resize`, `terminals/<id>/close`, `creds`, `doctor`, `kitdev`, `onboard/*`, `jobs/<id>/cancel` |

El trabajo largo es un **trabajo**: `GET jobs` los lista y `GET jobs/<id>?since=n` lee sus líneas desde la `n`.

## El plan y el harness

La documentación de un proyecto es demasiado grande para una sola sesión de agente, así que se parte en **unidades**.
El plan (`docs/.work/plan.yaml`) las guarda con su estado: por hacer, en curso, hecha, bloqueada, descartada o
esperando la aprobación de una persona.

**Tipos de unidad** (`lib/pipelines/units.yaml`): cada uno tiene una fase, quién lo hace (un agente, o un paso del
asistente como `setup` o `confirm`), la sección de `PLAYBOOK.md` que sigue, un nivel (ver [el
enrutado](#agentes-y-enrutado)) y si trabaja en su propia copia de `cam-docs` durante una ejecución en paralelo. Por
orden de fase: la preparación; el descubrimiento de cada repo y la correlación entre repos; el cuestionario, las
respuestas y tres entrevistas; la ficha y la wiki de cada repo; el sistema en C4, el dominio, los datos, el despliegue,
las decisiones y la calidad; el catálogo de flujos y una unidad por flujo, diagramas, revisiones; la traducción al
español; el portal, la CI, la confirmación humana y el traspaso.

**Pipelines** (`lib/pipelines/full.yaml`, `quick.yaml`) dicen qué unidades existen y qué necesita cada una (`needs`).
Las necesidades `soft` no bloquean: la ficha de un repo puede empezar antes de las entrevistas, como borrador, y al
terminar la entrevista se reabre para afinarla. Un proyecto cambia su plan en `cam-docs/.camarones/pipeline.yaml`
—quitar unidades, cambiar lo que necesitan, añadir unidades, fijar su agente o su nivel, o marcar una con
`approval: true` para que las siguientes esperen a una persona— y lo aplica con `camaron plan sync`. Un fichero con
errores deja el plan como estaba y dice dónde.

**Una sesión** trabaja en una unidad: lee `handoff.md` y los checkpoints de la unidad, escribe sus páginas, guarda notas
(`camaron plan note`), y al cerrar o bloquear la unidad se hace un commit local en `cam-docs`. Una unidad interrumpida
sigue desde su último checkpoint.

**Ejecuciones.** `camaron run` (el **Ejecutar las listas** de la app) hace varias unidades a la vez. Las unidades
marcadas para aislarse trabajan en `<workspace>/.cw/<n>/`, un worktree de git de `cam-docs` en su propia rama. Cuando
una termina, el kit trae a esa copia lo último de `cam-docs`, comprueba que no aparezcan errores nuevos (`check`,
`arch-validate`) y la fusiona. Una copia que choca con el trabajo de otra unidad bloquea su unidad, deja `cam-docs` sin
tocar y añade una unidad `integrate:<unidad>`. Las demás unidades van de una en una, y una unidad nunca empieza antes de
que se haya fusionado lo que necesita. `camaron autopilot` hace las unidades una tras otra sin worktrees. Mientras
cualquiera de los dos corre, la máquina no se suspende, y una sesión cortada por algo pasajero (suspensión, red, una API
saturada) vuelve una vez a la cola. Ninguno de los dos empieza una unidad cuya sesión tiene abierta la app (en el
lienzo o en una ventana); si solo quedan de esas, se para y las nombra. Una ejecución parada desde fuera (su trabajo
parado, su proceso terminado) no puede apuntar su final: en cuanto el cerrojo de las ejecuciones queda libre o
caducado, `GET pipeline` la da por `finished` e `interrupted`, y su flujo `runs/<id>/events` acaba tras su último
evento.

**Lo que costó.** Cada ejecución escribe `.camarones/.cache/runs/<run>/events.jsonl` (`camaron runs`). Cada máquina
suma su parte —ejecuciones, wikis que escribió un agente y las sesiones interactivas leídas del historial de Claude
Code— en `docs/.work/kpis/<persona-máquina>.json`, que `share` lleva al equipo. `camaron plan cost` y `camaron kpis` lo
suman; los dólares son el equivalente de la API (la cifra del propio agente, o si no tokens × `lib/pricing.yaml`, que
`pricing:` en `workspace.yaml` puede cambiar).

<!-- go:plan -->

## Agentes y enrutado

Los agentes se lanzan a través de un único adaptador (`lib/adapters/runners/`): Claude Code, Codex, OpenCode (la vía
para modelos locales como Qwen en Ollama) y plantillas de comando (Gemini CLI viene como plugin del kit; cualquier otro
CLI se declara en `~/.camarones.json`, en `runners`). El repo del equipo puede elegir agentes, pero nunca definir
comandos.

Cada unidad tiene un **nivel**: `agentic-heavy` (unidades largas como el descubrimiento o los flujos), `bounded`
(traducir, proponer preguntas de oro) o `judge` (puntuar). Cada nivel tiene una lista ordenada y gana el primer agente
instalado; `runner:modelo` elige además el modelo. El equipo lo fija en `workspace.yaml` y `~/.camarones.json` lo
cambia en una máquina:

```yaml
agents:
  routing:
    agentic-heavy: [claude, codex:gpt-5.6-terra]
    bounded: [opencode:ollama/qwen3-coder:30b, claude]
```

Los modelos locales nunca reciben trabajo `agentic-heavy`. `camaron doctor --local` propone uno que quepa en la memoria
de esta máquina.

Una **sesión interactiva** (Empezar, Seguir en la app; el Siguiente paso del asistente) abre el agente en el workspace
con el prompt de la unidad: en la app, como una terminal en el lienzo del Plan, o en una ventana de terminal propia si
el ajuste `sessions` de esta máquina es `window`; en el asistente, siempre en una ventana. Pasa por el mismo enrutado:
con el agente que elijas, el modelo que fije el nodo de la unidad en `pipeline.yaml` o, si no, el de su nivel (la
actualización de la doc es `agentic-heavy`); si no hay ninguno para ese agente, el modelo de esta máquina en Ajustes.
El asistente y la app dicen con qué modelo la abren. Cada sesión que abre la app lee un fichero de prompt propio en la
caché del proyecto, `.camarones/.cache/prompts/<unidad>.md` (`update.md` para la actualización de la doc), así que dos
sesiones abiertas a la vez nunca leen la de la otra; el asistente y el refinado del C4 del primer arranque siguen usando
`docs/.work/next-prompt.md`. La sesión de una unidad ejecuta su agente dentro de `session_run.py`, que guarda el
registro de la unidad en `.camarones/.cache/sessions/` (su pid mientras el agente corre, y después cuándo acabó):
mientras sigue abierta, o su ventana aún se está abriendo (hasta 30 s antes de que el envoltorio apunte su pid), la app
no abre otra para la misma unidad, `run` y `autopilot` dejan la unidad en paz, y la app enseña qué está haciendo el
agente leyendo su historial.

**Terminales en el lienzo.** El servidor del proyecto tiene las terminales del lienzo (`lib/terminals.py`): PTY de
verdad, el `pty` de la biblioteca estándar en macOS y Linux y ConPTY con pywinpty 3.1.0 en Windows (si no se puede
importar, `GET app/terminals` dice `available: false` y las sesiones se abren en una ventana). Como mucho hay 8 vivas a
la vez: una novena se rechaza (409) antes de que cambien la unidad o el registro de su sesión, igual que una unidad que
ya tiene la suya (409 con el id de su terminal). Cada una guarda en memoria sus últimos 256 KB, que
`GET app/terminals/stream` repite desde el punto que pide el cliente (`from=<id>:<offset>,…`) y luego sigue, todas las
terminales en un mismo flujo de eventos del servidor con sus bytes en base64 (de una que cerraste solo llega su final, y
la app da pantalla solo a las terminales que enseña el lienzo). `GET app/terminals` da el `offset` de cada una, por
dónde iba su salida 2 s antes: la app repite lo anterior como historia, sin volver a contestar las preguntas que trae, y
lo más reciente como vivo, así que un agente abierto desde otra vista recibe la respuesta a su pregunta de arranque en
cuanto se monta el lienzo. En disco, `.camarones/.cache/terminals/<id>.log` guarda sus últimos 5 MB junto a `<id>.json`
(su unidad, su agente, su tamaño, cuándo empezó y acabó, su código de salida). Lo que tecleas y un tamaño nuevo son
`POST app/terminals/<id>/input` y `resize`; `close` cuelga su grupo de procesos y mata lo que quede 3 s después
(`taskkill` en Windows). Las terminales viven lo que vive el servidor: cuando sale (se cierra la ventana de la app),
cuelga cada una, mata lo que quede 2 s después y apunta su final en los registros de sesión de las unidades, así que
estas quedan en pausa y **Seguir** las vuelve a abrir. En Windows la app termina el servidor con `taskkill /T /F`, que
se lleva las terminales con él sin tiempo para apuntar nada; las unidades quedan en pausa igualmente, porque el pid de
su sesión está muerto. `sessions: window` en `~/.camarones.json`
(`camaron config set sessions window`) abre las sesiones en una ventana de terminal, como antes.

## Confianza en las páginas: revisión y frescura

**Revisión.** Cada página es `draft` (la escribió la IA y nadie la ha revisado), `confirmed` (una persona confirmó
exactamente ese contenido: la confirmación va atada al hash de la página) o `needs-reconfirm` (cambió después de
confirmarla). Los agentes nunca reescriben en silencio una página confirmada o con `x-owner: human`, y nunca tocan los
bloques `<!-- human -->`. Al confirmar una página, el kit mide qué parte de las palabras de la IA cambió la persona: una
señal barata de la calidad de los borradores.

**Frescura.** Al escribir una página, el kit guarda una huella del código que cita en `x-sources` (líneas, o un símbolo
como `orders:src/OrderService.java#OrderService.place`, que vuelve a encontrar aunque se mueva). Si ese código cambia,
la página pasa a **sospechosa**; si desaparece, a **obsoleta**; si solo se movió, sigue fresca. Una página que cita otras
páginas o elementos C4 (`c4:shop.orders`) es sospechosa cuando alguno de ellos lo es. Los agentes no reciben páginas
sospechosas ni obsoletas, ni páginas sin revisar y sin fuentes: el MCP y `llms.txt` las retienen y dicen qué código leer
en su lugar (`freshness: {ai_policy: warn}` se las da con un aviso). Las personas las siguen viendo, con un aviso.
`camaron fresh` las lista, `--plan` añade una unidad que las actualiza y `--ack <página> --by <nombre>` dice que una
sigue valiendo.

**La puerta de calidad.** `camaron check` se pasa al cerrar cada unidad y en CI: frontmatter o fuentes que faltan,
enlaces y anclas rotos, Mermaid que no se dibuja (mermaid-cli), posibles secretos (gitleaks; bloquean el checkpoint y la
exportación), palabras que el glosario pide evitar, bloques generados editados a mano, bloques `:::rule` cuyo código ya
no existe y la estructura de cada página (TL;DR, las secciones que pide su plantilla, un tamaño máximo). `--strict`
convierte los avisos en errores.

## Los servidores MCP

**`camarones`** está registrado para Claude Code y Codex en `cam-docs` y, con `setup`, en el ámbito local de Claude
Code de cada repo (en `~/.claude.json`, nunca en el repo), así que también funciona con un agente abierto dentro de un
solo repo. `camaron doctor` avisa si falta y `camaron repair` lo vuelve a poner. Habla JSON-RPC por stdio;
`camaron mcp --http` lo sirve en `http://127.0.0.1:8765/mcp` (Streamable HTTP) con el token de
`~/.camarones/mcp-token`.

| Herramienta | Hace |
|---|---|
| `search_docs` | Búsqueda con ranking; cada resultado dice su sección, su confianza y su frescura |
| `read_doc` | Una página o, con `section`, solo su TL;DR y esa sección |
| `list_docs`, `doc_status` | El índice con la confianza; la salud de la documentación |
| `ask` | Las mejores secciones para una pregunta, cada una con su cita `[ruta#sección]`; no llama a ningún modelo |
| `propose_edit` | Cambia un borrador de IA en su sitio; en una página confirmada o de una persona, guarda una propuesta para revisar. Nunca confirma |
| `add_feedback`, `mark_suspect` | Deja un comentario de revisión; retiene una página que ya no cuadra con el código |
| `pipeline_status`, `run_events`, `kpis` | El plan, los eventos de una ejecución, los KPIs |
| `run_node` | Lanza una unidad lista, solo con `mcp: {pipeline_control: true}` en `workspace.yaml` |
| `repo_graph` | Pregunta al grafo de código de graphify de un repo o de todos |
| `board_next`, `board_waves` | Lo que puede empezar ya sin choques; el trabajo abierto en oleadas. Los agentes leen el tablero; nunca mueven tarjetas |

También ofrece cada página como recurso (`camdocs://<ruta>`, más `camdocs://llms.txt`) y dos prompts,
`implement-feature` y `update-docs`. Todo pasa por la misma puerta de frescura.

**`likec4`** responde preguntas sobre el modelo de arquitectura (quién llama a este servicio, qué hay entre A y B). Las
skills `cam-docs-lookup`, `cam-docs-update` y `cam-docs-diagrams` enseñan a los agentes cuándo usarlos.

## Plugins y confianza

Un plugin es una carpeta con un `plugin.yaml` que aporta agentes, comprobaciones, prompts, skills, hooks, servidores MCP
o tipos de unidad. El kit trae Gemini, Confluence y Notion; un equipo añade los suyos con
`camaron plugins add <carpeta | git:<url>@<tag>>`, que lo copia en `cam-docs/.camarones/plugins/` y fija su versión,
origen y huella en `plugins.lock`. `plugins outdated`, `update` y `remove` los gestionan; `check` avisa si alguien edita
uno a mano.

El kit calcula si un plugin ejecuta código en lugar de fiarse de su manifiesto. Todo lo que ejecuta código o guía a los
agentes y llegó con el repo del equipo —plugins, hooks, servidores MCP, ajustes, skills— no se carga hasta que lo
apruebas en tu máquina (`camaron trust`, o Equipo en la app). La aprobación cubre todos los ficheros, así que cualquier
cambio vuelve a preguntar. Lo que instaló el propio kit se reconoce sin preguntar, y `camaron repair` lo devuelve a su
sitio si alguien lo edita o lo borra.

<!-- go:team -->

## Páginas escritas sin IA

Una instalación nueva ya documenta mucho con análisis estático, con fuentes en cada fila:

| Comando | Escribe |
|---|---|
| `camaron pages` (alias `diagrams`) | `docs/index.md` (qué es el proyecto, una tarjeta por repo, el mapa de contexto), `docs/repos/<repo>/index.md` (endpoints, datos como diagrama ER, diagramas de estados por cada enum de estado, mensajes, variables de entorno y comandos) y `docs/architecture/messaging.md` |
| `camaron radar`, `camaron stack` | `docs/overview/tooling.md`: el stack de cada repo y las herramientas que usa |
| `camaron inventory [--cves]` | `docs/overview/libraries.md`: dependencias directas por categoría, versiones que difieren, vulnerabilidades conocidas; un módulo Maven toma sus versiones del pom padre y los BOM del mismo repo |
| `camaron schemas` | Tablas y colecciones desde migraciones, entidades, Mongo y Firestore |
| `camaron history` | `docs/overview/history.md`: puntos calientes, quién trabaja dónde, ficheros que cambian juntos |
| `camaron arch-draft` | Un primer modelo C4 para verificar |
| `camaron llms` | `llms.txt` y `llms-full.txt` para los agentes |

Son **bloques generados** (`<!-- generated:… sha=… -->`) que `pages`, `blocks` y `sync` mantienen al día. Una persona
confirma uno copiando su `sha=` en `confirmed=` con `by=<nombre>`; desde entonces un refresco no lo toca y `check` avisa
cuando el código se movió después.

<!-- cmd:pages -->

## Versiones y compatibilidad

La versión del kit y cada herramienta que instala (Electron, LikeC4, graphify, OpenWiki, mermaid-cli, gitleaks,
OSV-Scanner…) están fijadas en `lib/common.py` (`VERSIONS`); `camaron version` las enseña y `camaron doctor` las
comprueba. Un proyecto hecho con cualquier kit 3.x o 4.x se abre con un kit más nuevo sin pasos manuales; las
estructuras más antiguas pasan por `camaron migrate`. La instalación global se actualiza con `camaron self-update`
(todos los proyectos a la vez); una copia del kit dentro de un proyecto, con `camaron upgrade <carpeta-del-kit-nuevo>`.
Las plantillas como estas guías se copian en un proyecto una vez y nunca se sobrescriben: una guía nueva llega con el
siguiente `camaron setup`, y una guía que el equipo editó sigue siendo suya.
