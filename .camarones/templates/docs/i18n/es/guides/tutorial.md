---
title: Tutorial — Camarón, el asistente de documentación del proyecto
description: Cómo instalar Camarón en macOS o Windows, hacer las sesiones guiadas de documentación con Claude Code o Codex, confirmar borradores de IA, usar el portal (leer, editar, revisar), generar las wikis de OpenWiki y configurar el CI.
x-owner: human
---
# Tutorial — Camarón 🦐

*Camarón que se duerme, se lo lleva la corriente.* Camarón documenta un proyecto entero (todos sus repos) en sesiones
cortas con IA, guarda el progreso después de cada una y siempre te dice qué viene a continuación.

## 1. Instalación (una vez por ordenador)

Requisitos:
- **git** y **Node.js ≥ 22**. Si faltan, el asistente se ofrece a instalarlos con Homebrew o winget.
- **Docker Desktop**, solo si quieres servir el portal.
- **Claude Code** y/o **Codex**, para las sesiones con IA. También sirven OpenCode y Gemini CLI; OpenCode es la vía para modelos locales.

**No** hace falta Python: el lanzador instala `uv`, que ya trae su propio Python.

| | Abrir el asistente |
|---|---|
| macOS | doble clic en `camaron.command` (si macOS lo bloquea la primera vez: Terminal en la carpeta → `sh camaron.command`) o `./camaron.command` |
| Windows | doble clic en `camaron.cmd`, o `camaron.cmd` en un terminal |
| Linux / CI | `./camaron.command` (es un script de shell normal) |

**Instalación global (varios proyectos):** `sh install-global.sh` (Windows: `install-global.cmd`) desde el repo del kit deja
el comando `camarones` en tu PATH; ejecuta `camarones` en la carpeta que agrupa los repos y crea `./cam-docs/`.

**Proyecto nuevo desde el zip:** pon `camarones-documenter.zip` en la carpeta donde están los repos del proyecto, descomprímelo ahí
y abre el lanzador. Si al descomprimir se crea una subcarpeta `camarones-documenter/`, el asistente se ofrece a moverse un nivel más arriba.
Detecta los repos que ya estén en la carpeta, y puedes añadir más por URL.

Todo lo que escribe el kit vive en **`cam-docs/`**, junto a los repos: un repo git propio con `docs/`, `wikis/<repo>/`, la
configuración de la herramienta (`.camarones/`) y la de los agentes (`.claude/`, `.codex/`, `.agents/`, `.mcp.json`). Los
repos de servicio no reciben archivos del kit; las rutas de abajo son relativas a `cam-docs/`.

La configuración de los agentes se comparte con el equipo, así que nunca se carga a ciegas: los hooks, servidores MCP,
ajustes y skills que no ha escrito el kit se listan al abrir el asistente, y el workspace solo los enlaza cuando los
apruebas en esta máquina (`camaron trust`). Las aprobaciones viven en `~/.camarones/trust/`, nunca en el repo.

## 2. El flujo guiado

La primera vez te lleva por 6 pasos:
1. **Workspace:** nombre del proyecto y repos.
2. **Herramientas:** tabla con lo que tienes y lo que falta; eliges **instalar todo (recomendado)** o **qué instalar** (git, Node, Docker, Java, Claude/Codex, graphify, LikeC4, OpenWiki, hooks…).
3. **Setup:** herramientas, repos, conexión de Claude/Codex y hooks de git.
4. **Stack y herramientas:** el stack de cada repo y las herramientas que ya usáis (Backstage, Sonar, librería de componentes, linters, contratos, CI), detectados sin IA; si un stack está mal lo corriges ahí o luego con `camaron stack`. Queda en `docs/overview/tooling.md`.
5. **Diagrama C4 rápido:** un primer borrador de la arquitectura, también sin IA.
6. **Sesiones:** te explica cómo funcionan.

Esc vuelve al paso anterior en cualquier momento. Las tareas largas muestran qué están haciendo, una barra de progreso y datos curiosos de crustáceos. Después, el menú principal muestra el progreso del plan y el siguiente paso.

**🦐 Siguiente paso** lista las unidades del plan que ya se pueden hacer (sus dependencias están terminadas). Eliges una
y decides si abrirla con Claude Code, con Codex o copiar el prompt. El agente arranca con instrucciones de hacer *solo esa unidad*, a fondo, y luego:
- la marca como hecha en `docs/.work/plan.yaml`;
- escribe en `docs/.work/handoff.md` lo que ha hecho y lo que queda pendiente;
- te pregunta qué hacer después.

Cierra el agente y vuelve al asistente para la siguiente unidad: una sesión nueva empieza con la ventana de contexto limpia. El plan es este:

| Fase | Unidades |
|---|---|
| 0 | setup |
| 1 | análisis de cada repo → cruce entre repos |
| 2 | 3 entrevistas cortas: contexto, actores y entornos · glosario y SLAs · decisiones, deuda y validación |
| 3 | por cada repo: README + AGENTS.md/CLAUDE.md + componentes C4 (brief) · OpenWiki (wiki) |
| 4 | C4 del sistema · dominio · datos · despliegue · ADRs y calidad |
| 5 | catálogo de flujos → una unidad por cada flujo de negocio |
| 6 | traducciones al español |
| 7 | portal · CI · confirmación humana · entrega final |

¿Una unidad es demasiado grande para una sesión? El agente la divide y añade lo que falta al plan. Todo se conserva entre sesiones
y entre ordenadores, porque el plan se commitea junto con la doc.

**Tu propio plan.** El plan sale del pipeline del kit (`full` o `quick`). Para cambiarlo en este proyecto, crea
`.camarones/pipeline.yaml` y ejecuta `camaron plan sync`:

```yaml
extends: kit:full
nodes:                                   # unidades extra
  - {id: security-review, type: security-review, needs: [arch-system]}
patch:
  - {op: disable, node: ci}              # la unidad se descarta; quita la línea y vuelve
  - {op: needs, node: domain, add: [data]}
  - {op: set, node: i18n, runner: "opencode:ollama/qwen3-coder:30b"}   # o tier: bounded / judge
```

`node` es el id tal como lo escribe el kit (`discovery:{repo}`) o un prefijo con `*` (`repo-wiki:*`). Si el fichero tiene
un error, el plan se queda como estaba y `camaron plan` dice dónde (`patch[1].node: unknown node 'cii'`).

**Plugins.** Un plugin es una carpeta en `.camarones/plugins/<nombre>/` con un `plugin.yaml` (`name`, `version`, rango
`kit`, `provides`). `camaron plugins` lista los del kit y los del proyecto, qué aportan y si ejecutan código. Un plugin
que ejecuta código (comandos de agente, hooks, servidores MCP, scripts) llega a todo el equipo a través del repo, así
que no se carga hasta que se aprueba en cada máquina, y lo mismo uno que guía a los agentes (prompts, skills): el
asistente lo pregunta junto al resto de la configuración de agentes, o `camaron trust` (`--yes` para aprobar). La
aprobación cubre todos los ficheros de la carpeta del plugin: cualquier cambio vuelve a preguntar. Los agentes que
aporte un plugin aprobado quedan disponibles como los del kit.

Los plugins del equipo se copian en el repo y se fijan: `camaron plugins add <carpeta | git:<url>@<tag>[#subcarpeta]>`
lo copia en `.camarones/plugins/` y apunta versión, origen y huella en `.camarones/plugins.lock`; si su rango `kit` no
incluye este kit, se rechaza. `plugins outdated` lista versiones nuevas, `plugins update [nombre] [--to <tag>]` lo vuelve
a traer y lista los ficheros que cambian, y `plugins remove <nombre>` lo quita. `check` avisa si una carpeta ya no
coincide con el lock. Un nodo del pipeline puede fijar una versión mayor: `uses: adr-lint@0`.

## 3. Confianza: borradores de IA frente a doc confirmada

Toda página nace como **✨ borrador** (el portal lo muestra con un banner). Confírmalas en el portal (**Confirmar** en cada
página; la pestaña **Revisión** lista lo pendiente) o en el asistente con **✅ Revisar y confirmar páginas**. La confirmación queda ligada al contenido: si alguien edita la página después, pasa a
**⚠️ pendiente de reconfirmar**. Los agentes tratan las páginas confirmadas como la fuente de verdad.

**Frescura.** Cuando se escribe una página, se guarda una huella del código que cita (`x-sources`). Si ese código cambia,
la página queda **sospechosa**; si desaparece, **obsoleta** (el código que solo se movió no cuenta). Los agentes no
reciben páginas sospechosas ni obsoletas, ni páginas sin fuentes que nadie ha revisado: el MCP, `llms.txt` y `llms-full.txt` las retienen
y les indican el código. Las personas las siguen viendo, con un aviso. `camaron fresh` las lista, `fresh --plan` añade
una unidad para actualizarlas y `fresh --ack <página> --by <nombre>` dice que una sigue siendo válida. Con
`freshness: {ai_policy: warn}` en `workspace.yaml` se entregan con una advertencia en lugar de retenerlas.

Para proteger un párrafo de los agentes:

```markdown
<!-- human -->
Este párrafo solo lo editan personas.
<!-- /human -->
```

## 4. Después de la primera pasada

**🔄 Actualizar doc tras cambios** lanza una sesión incremental: solo regenera lo que ha cambiado en el código, limpia las
páginas obsoletas y nunca reescribe a escondidas las páginas confirmadas. El CI puede hacer lo mismo de forma automática (sección 8).

**Control de calidad.** `camaron check` se ejecuta al cerrar cada unidad y en el CI. Además del frontmatter, las fuentes,
la confianza y las traducciones, revisa:

| Comprobación | Gravedad | Necesita |
|---|---|---|
| Enlace roto a otra página (no se comprueban URLs externas) | ERROR | — |
| Un `#ancla` sin título que le corresponda en la página de destino | aviso (ERROR con `--strict`) | — |
| Diagrama Mermaid que no se dibuja | ERROR | mermaid-cli |
| Posible secreto en `docs/` o en una wiki (solo fichero y línea, nunca el valor) | ERROR; además bloquea los commits de checkpoint y `camaron portal` | gitleaks |
| Una palabra de la columna **Avoid** del glosario | aviso (ERROR con `--strict`) | una columna Avoid en `docs/domain/glossary.md` |
| Bloque generado editado a mano o desfasado respecto al código (`camaron blocks`) | aviso (ERROR con `--strict`) | — |
| Estructura de la página: TL;DR bajo el título, las secciones de su plantilla en `.camarones/skeletons/`, tamaño máximo, referencias vagas | aviso (ERROR con `--strict`) | — |

mermaid-cli y gitleaks vienen con la instalación completa (el componente `quality`; mermaid-cli descarga una vez un
Chromium sin ventana). Si faltan, `check` lo avisa una vez y se salta esa comprobación.

## 5. Portal

Un solo portal, dos modos, la misma interfaz. Pestañas: **Docs** (árbol, buscador, marcas de confianza),
**Arquitectura (C4)**, **Grafo de código** (todos los repos o uno), **Wikis** (la OpenWiki de cada repo, sus páginas y su
grafo) y **Revisión** (páginas pendientes, peticiones de cambio, código cambiado desde la doc, `check`). El selector de
idioma cambia la interfaz y la doc; una página sin traducir se muestra en inglés con un aviso.

El portal nuevo se está construyendo en `http://127.0.0.1:8080/next/`, a un clic desde la pestaña **Pipeline ↗** del
portal de siempre (blanco y negro, modo oscuro; viene ya compilado
con el kit, no hace falta Node). Su pestaña **Pipeline** muestra el plan en vivo: un grafo de las unidades por fase, un
tablero por estado y, por unidad, su agente, resultado, tiempo, tokens, coste y el log del agente línea a línea. Si lanzas
`camaron run` con la página abierta, la ejecución aparece sola. Desde la pestaña también puedes lanzar una ejecución,
cancelarla (los agentes se paran y sus unidades vuelven a la cola sin perder su trabajo) y reintentar una unidad
bloqueada. Una ejecución a la vez, desde la terminal o desde el portal.

| | Comando | Qué es |
|---|---|---|
| Local, editable | `camaron up` (asistente → 🌐 Portal → 📝 Abrir el portal) | `http://127.0.0.1:8080`, solo en tu equipo |
| Exportación para desplegar | `camaron portal` (asistente → 📦 Exportar) | HTML + JSON de solo lectura en `.camarones/.cache/site`, sin npm |
| Ver la exportación | `camaron up --static` o `camaron up --docker` | exactamente lo que servirá el servidor |

La exportación son ficheros estáticos (imagen nginx, GitLab/GitHub Pages) y funciona sin internet. En un servidor, arranca la
imagen que publicó el CI: `docker run -d -p 8080:80 <registry>/<grupo>/cam-docs/portal:latest`.

## 6. Editar: dónde y cuándo

| Dónde | Qué puedes hacer | Dónde queda el cambio |
|---|---|---|
| Portal local (`camaron up`) | editar (markdown + vista previa), **+ Nueva página**, **Confirmar**, **Pedir cambios**, generar wikis, reconstruir C4 / grafo | `cam-docs/docs` + commit local si marcas «commit en cam-docs»; el push lo haces tú |
| Portal desplegado (exportación) | leer y buscar; **Editar** abre el fichero en GitLab / GitHub (si `cam-docs` tiene remote) | un merge request en `cam-docs`; el CI lo vuelve a publicar |
| Tu editor / IDE | cualquier `.md` de `cam-docs/docs` | git normal en `cam-docs` |
| La IA (🦐 Siguiente paso) | solo su unidad; nunca reescribe a escondidas lo confirmado | un commit local por unidad |

- **Confirmar** firma con tu `git config user.name`. **Pedir cambios** guarda el comentario y añade una unidad
  `review-fixes` que la IA aplica en la siguiente sesión.
- Con el idioma en español, **Editar** edita la traducción (`docs/i18n/es/…`).
- Editar una página ✅ la pasa a **⚠️ pendiente de reconfirmar** hasta que alguien la vuelva a mirar.
- No edites a mano lo generado (`llms.txt`, `llms-full.txt`, `docs/.status.json`, los visores). Las wikis mejor regenerarlas desde la pestaña
  **Wikis**: una actualización de OpenWiki puede reescribir lo que cambies.

## 7. OpenWiki: una wiki por repo

Portal → **Wikis** → **Generar / actualizar wiki** (log en directo), asistente → **📚 Wikis**, o `camaron wiki <repo>`. La
wiki se guarda en `cam-docs/wikis/<repo>/` (el repo ve un enlace `openwiki/` sin versionar) y sus páginas aparecen en
**Docs** como `repos/<repo>/…`. Usa el proveedor de OpenWiki si hay uno configurado (`openwiki auth configure <proveedor>`);
si no, Claude Code o Codex. Los archivos que OpenWiki añade al propio repo (`AGENTS.md`, `CLAUDE.md`, `.github/`) se quitan
al terminar.

Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas: asistente → **📚 Wikis** →
**Elegir qué repos tienen wiki** (se guarda como `wiki: true` en `.camarones/workspace.yaml`). Elige los servicios con
lógica, no librerías ni repos de CI. La primera wiki de un repo espera a su brief (`wikis/<repo>/INSTRUCTIONS.md`, que
escribe la unidad repo-brief) para usar tu glosario; `camaron wiki <repo> --force` se salta esa comprobación. Se lanzan
de una en una, y un lote se para en cuanto el motor se queda sin cuota o sin sesión, en vez de fallar todos los repos
que quedan.

## 8. CI

En el asistente, **⚙️ CI** instala el pipeline en `cam-docs` (GitLab o GitHub): actualiza la doc afectada, pasa `check`, exporta el portal y lo publica. Las plantillas para cada repo de servicio están en `.camarones/ci/repo.*`.
Antes de subir la rama de actualización se ejecuta `camaron check --secrets`: si encuentra un posible secreto, el job falla y no se abre el MR/PR.

Variables necesarias: `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`, y un token de bot para abrir MRs/PRs. En GitLab, además, tienes que
permitir que el job token del proyecto `cam-docs` clone cada repo de servicio (repo → Settings → CI/CD → Job token permissions).

**En cada pull request, sin IA.** `camaron ci` también escribe `.camarones/ci/docs-fresh.github.yml` (o `.gitlab-ci.yml`)
para cada repo de servicio. En cada PR/MR comenta qué páginas deja desactualizadas el cambio y cuáles ya lo estaban; un
solo comentario por PR, que se actualiza con cada push. No necesita clave de IA y nunca bloquea el merge. Necesita
`DOCS_REPO_URL` y un `DOCS_READ_TOKEN` que pueda leer `cam-docs` (en GitLab, además, `DOCS_BOT_TOKEN` para comentar). En
local: `camaron pr fresh <repo> --base main`. Por defecto corre en runners alojados; para que use los vuestros, pon
`ci: {target: self-hosted, runner_labels: [self-hosted, docs], runner_tags: [docs]}` en `workspace.yaml` y vuelve a
ejecutar `camaron ci`. Las PR del propio `cam-docs` solo pasan `check`.

## 9. Comandos (para scripts y agentes)

`camaron help` (copia por proyecto: `./camaron.command help`, en Windows `camaron.cmd help`) lista: `setup`, `sync`,
`detect`, `plan`, `plan next`, `status`, `check [--strict|--secrets]`, `confirm`, `feedback`, `checkpoint`, `graph`, `arch` (editor C4 en vivo),
`arch-validate`, `wiki <repo>`, `portal` (exportación), `up [--static|--docker]`, `down`, `ci`, `prompt <unidad>`, `migrate`, `doctor`,
`doctor --local` (propone un modelo local libre para este equipo, sin instalar nada), `autopilot`, `plugins [--json]`,
`run`, `runs`, `kpis`, `eval`, `ab`, `pipeline show|validate`, `blocks [--force]`, `pr fresh <repo>` y
`plugins add|update|outdated|remove`.

**Datos del código, sin IA.** `camaron blocks` escribe `docs/repos/<repo>/reference.md` para cada repo: comandos
(Maven, Gradle, `package.json`, Makefile, Docker Compose), variables de entorno (placeholders `${VAR:valor}` de Spring,
`.env.example`, `environment.ts` de Angular; los valores que parecen secretos se ocultan), endpoints HTTP (OpenAPI o, si
no hay, anotaciones de Spring) y topics de mensajería, cada fila con su fichero y línea. Son bloques
`<!-- generated:<tipo> repo=<repo> -->` que puedes poner en cualquier página; `blocks` y `sync` los actualizan. Si
alguien edita uno a mano, se conserva y `check` lo avisa; `blocks --force` toma la versión del código.

**En paralelo.** `camaron run --parallel 3 --per-runner claude=2,codex=1` hace varias unidades a la vez. Los
descubrimientos, las fichas de repo y los flujos trabajan cada uno en su propia copia de `cam-docs/` (un worktree de git
en `.cw/<n>/`) y se integran al terminar, si `check` y `arch-validate` no muestran errores nuevos. Las demás unidades
van de una en una, y una unidad espera a que se integre lo que necesita. Si hay un choque, la unidad se bloquea,
`cam-docs/` no se toca y se añade una unidad `integrate:<unidad>`. `camaron runs` muestra qué hizo y cuánto costó cada
ejecución; `camaron pipeline show` lista las unidades y dónde trabaja cada una. `autopilot` sigue siendo secuencial.
Las ejecuciones mantienen el ordenador despierto (un portátil que se duerme corta la sesión del agente); una sesión
cortada por algo pasajero (suspensión, red, API saturada) se reintenta una vez. Por defecto, una sesión por agente: con
un solo agente instalado, `--per-runner claude=2` le deja hacer más.

**¿Está funcionando?** `camaron kpis` muestra las ejecuciones del equipo por mes (tiempo, tokens, coste por unidad,
paralelismo, límites, fallos), la cobertura (repos con ficha, flujos, ficheros C4, errores de `check`), la confianza
(confirmadas, borradores, reconfirmaciones, repos que cambiaron desde que se documentaron, y cuánto cambian las
personas lo que escribió la IA antes de confirmarlo) y el uso (consultas de agentes
y del portal, búsquedas sin resultado). Las ejecuciones se suman a través de `docs/.work/kpis/` (se commitea, un fichero
por persona y máquina). `camaron kpis --compare <run-a> <run-b>` dice si un cambio de prompt, de modelo o del kit ayudó.

**Preguntas de oro.** Un examen con solucionario para la documentación: `evals/questions.yaml` lista preguntas reales,
las páginas que deberían citarse (`expect`, tal como las toma `read_doc`) y los identificadores exactos que una buena
respuesta nombra (`mention`). `camaron eval draft` añade una unidad en la que un agente las propone; `camaron eval
confirm <id> --by <nombre>` las aprueba (solo cuentan las confirmadas); `camaron eval run` se las pregunta a un agente que
solo puede leer la documentación y puntúa, sin IA, las páginas citadas y los identificadores (`--judge` añade la nota de
un modelo). `kpis` muestra la última nota.

**¿Ayuda cam-docs?** `camaron ab --qa "<pregunta>"` hace la misma pregunta dos veces: con la documentación, y solo con el
código, en una carpeta temporal fuera del proyecto que enlaza los repos y nada más (sin `cam-docs/`, sin `AGENTS.md`, sin
MCP). Compara el contexto leído (tokens de entrada más los de caché), tiempo, coste, herramientas usadas y los
identificadores exactos que nombra cada respuesta; `--golden` lo
hace con las preguntas de oro. Los repos no se tocan. `ab: {enabled: false}` en `workspace.yaml` lo desactiva.

**Qué agente hace cada trabajo.** Cada tipo de trabajo tiene una lista ordenada y lo hace el primer agente instalado:
`agentic-heavy` (unidades largas), `bounded` (traducciones, resúmenes) y `judge` (puntuar evaluaciones). `runner:modelo`
elige también el modelo. El equipo lo fija en `.camarones/workspace.yaml` (`agents: routing:`); `~/.camarones.json`
(`routing`) manda en esta máquina. Los modelos locales solo pasan por OpenCode (`opencode:ollama/qwen3-coder:30b`) y nunca
hacen trabajo `agentic-heavy`. `autopilot` y `run` lo leen unidad a unidad. Cada ejecución queda registrada en
`.camarones/.cache/runs/` (`camaron runs`).

## 10. Problemas frecuentes

| Problema | Solución |
|---|---|
| macOS bloquea `camaron.command` ("no se puede abrir" / "Apple no pudo verificar…") | abre Terminal en la carpeta y ejecuta `sh camaron.command` (una vez: el lanzador quita la marca de cuarentena y a partir de ahí el doble clic funciona). Alternativa: Ajustes del Sistema → Privacidad y seguridad → "Abrir igualmente" |
| Windows: aviso de SmartScreen | "Más información" → "Ejecutar de todas formas" |
| Windows bloquea el archivo o lo borra el antivirus | antes de descomprimir: clic derecho en el zip → Propiedades → marca **Desbloquear** → Aceptar. Si ya lo descomprimiste, en PowerShell dentro de la carpeta: `Get-ChildItem -Recurse | Unblock-File`. Si el equipo es de empresa y no deja ejecutar `.cmd`: `winget install astral-sh.uv` y luego `uv run --script .camarones\camarones.py` |
| Algo se ha instalado pero no lo detecta | cierra y vuelve a abrir el asistente (para que se refresque el PATH) |
| `doctor` dice que falta una herramienta | en el asistente: 🛠 Instalar / reparar |
| Al sincronizar, un repo sale como "skip … local changes" | haz commit o stash en ese repo y vuelve a sincronizar |
| Errores en el C4 | `camaron arch-validate` te dice el fichero y la línea |
| `checkpoint` / `portal` se niegan: "possible secret" | sustituye el valor de ese fichero y línea por un marcador (`<tu token>`) y vuelve a lanzarlo |
| `check`: "mermaid-cli could not start its browser" | a Chromium le faltan librerías del sistema (suele pasar en contenedores de CI); se saltan los diagramas, el resto del check sigue |
| El agente no tiene las herramientas de OpenWiki | reinicia Claude Code / Codex en la carpeta del workspace (la que contiene `cam-docs/`) |
| El portal desplegado no tiene botón **Editar** | `cam-docs` no tiene remote de git: añádelo y vuelve a exportar |
| Falló la generación de una wiki | la línea ⚠ dice por qué (cuota o sesión → espera o vuelve a iniciar sesión); lanza otra vez `camaron wiki <repo>`: un run interrumpido se reanuda |
