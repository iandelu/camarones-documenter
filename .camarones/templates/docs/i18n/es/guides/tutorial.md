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
apruebas en esta máquina (`camaron trust`). Las aprobaciones viven en `~/.camarones/trust/`, nunca en el repo. Lo que
el kit instaló en esta máquina (sus skills y los de graphify y OpenWiki, anotados en `~/.camarones/install/`) se
reconoce sin preguntar; `camaron doctor` enseña un fichero del kit editado o un enlace que falta, y `camaron repair` los
devuelve a su sitio.

## 2. El flujo guiado

La primera vez te lleva por 6 pasos:
1. **Workspace:** nombre del proyecto y repos.
2. **Herramientas:** tabla con lo que tienes y lo que falta; eliges **instalar todo (recomendado)** o **qué instalar** (git, Node, Docker, Java, Claude/Codex, graphify, LikeC4, OpenWiki, hooks…).
3. **Setup:** herramientas, repos, conexión de Claude/Codex y hooks de git.
4. **Stack y herramientas:** el stack de cada repo y las herramientas que ya usáis (Backstage, Sonar, librería de componentes, linters, contratos, CI), detectados sin IA; si un stack está mal lo corriges ahí o luego con `camaron stack`. Queda en `docs/overview/tooling.md`, y cada dependencia directa por categoría (framework, datos, caché, seguridad,
   mensajería, tests…) en `docs/overview/libraries.md` (también `camaron inventory`, y `camaron bump <repo> <librería> <versión>` actualiza una en una rama nueva de su repo; `--cves` añade las vulnerabilidades conocidas
   con la base de datos offline de OSV-Scanner), y las tablas y colecciones de cada repo, con su diagrama ER, en
   la página del repo (`docs/repos/<repo>/index.md`; `docs/data/<repo>.md` antes de la 4.52), también `camaron schemas`).
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

Las entrevistas no frenan la redacción: las fichas de repo, el dominio, los datos, las decisiones y el catálogo de flujos
empiezan desde el código como borradores provisionales (`✎ draft` en `plan`), dejan sus preguntas en
`docs/interview/open-questions.md` y se reabren para afinarlas cuando termina la entrevista. Las traducciones y la
confirmación sí esperan a las entrevistas. Como cuestionario del equipo, cada persona lo responde en el portal
(Plan › Entrevista) o en el formulario sin conexión (`camaron interview export` y después `interview import`); las dos
vías escriben el mismo `responses/<nombre>.yaml`.

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
  - {op: set, node: "repo-brief:*", approval: true}   # una persona aprueba cada brief antes de seguir
```

Una unidad con `approval: true` se queda «awaiting approval» cuando su agente termina; las que dependen de ella empiezan
tras `camaron plan approve <unidad>` o el botón «Approve» del Pipeline del portal (zona Plan).

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
coincide con el lock. Un nodo del pipeline puede seguir un plugin, fijado a una versión mayor: en
`.camarones/pipeline.yaml`, `patch: [{op: set, node: decisions-quality, uses: adr-style@1}]`. El prompt de esa unidad
lleva entonces los prompts del plugin y le indica sus skills; una versión mayor distinta o un plugin sin aprobar es un
error del pipeline.

## 3. Confianza: borradores de IA frente a doc confirmada

Toda página nace como **✨ borrador** (el portal lo muestra con un banner). Confírmalas en el portal (**Confirmar** en cada
página; la zona **Revisión** lista lo pendiente) o en el asistente con **✅ Revisar y confirmar páginas**. La confirmación queda ligada al contenido: si alguien edita la página después, pasa a
**⚠️ pendiente de reconfirmar**. Los agentes tratan las páginas confirmadas como la fuente de verdad.

**Frescura.** Cuando se escribe una página, se guarda una huella del código que cita (`x-sources`). Si ese código cambia,
la página queda **sospechosa**; si desaparece, **obsoleta** (el código que solo se movió no cuenta). Los agentes no
reciben páginas sospechosas ni obsoletas, ni páginas sin fuentes que nadie ha revisado: el MCP, `llms.txt` y `llms-full.txt` las retienen
y les indican el código. Las personas las siguen viendo, con un aviso y un icono de frescura en cada fuente; al pasar
el ratón por una fuente que cambió se ven los commits, la PR/MR y los tickets que la tocaron, y un clic abre sus líneas
en tu editor (o en el repositorio desde el portal desplegado). `camaron fresh` las lista, `fresh --plan` añade
una unidad para actualizarlas y `fresh --ack <página> --by <nombre>` dice que una sigue siendo válida. Con
`freshness: {ai_policy: warn}` en `workspace.yaml` se entregan con una advertencia en lugar de retenerlas.
Mejor citar un símbolo que unas líneas (`orders:src/…/OrderService.java#OrderService.place`): se vuelve a encontrar
aunque se mueva, así que solo cuenta un cambio en su propio cuerpo. Una página que se apoya en otras páginas o en
elementos C4 los cita (`docs/flows/checkout.md`, `c4:shop.orders`) y pasa a sospechosa cuando alguno lo es.

Para proteger un párrafo de los agentes:

```markdown
<!-- human -->
Este párrafo solo lo editan personas.
<!-- /human -->
```

## 4. Después de la primera pasada

**🔄 Actualizar doc tras cambios** lanza una sesión incremental: solo regenera lo que ha cambiado en el código, limpia las
páginas obsoletas y nunca reescribe a escondidas las páginas confirmadas. El CI puede hacer lo mismo de forma automática (sección 8).

**Salud del proyecto.** `camaron health` imprime, sin IA, un veredicto y tres áreas (máquina, documentación, código) con la
siguiente acción de cada una, y una tabla por repo: si usa SonarQube (con su puerta de calidad cuando hay token guardado), la
cobertura, las vulnerabilidades y la deuda técnica que registra `docs/quality/`. La cobertura sale de SonarQube cuando hay un
token de SonarQube guardado en la máquina (Máquina > Tokens) y se puede leer el proyecto; si no, de los informes que deja la
build en local. `--refresh` la recalcula antes (es el único momento en que pregunta al servidor de SonarQube) y `--json`
imprime la foto. La Calidad de la app de escritorio y la vista Salud del portal (solo lectura) enseñan la misma foto.

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

Un proyecto recién instalado nunca enseña vistas en blanco: Inicio, Docs y Arquitectura ofrecen un **primer vistazo
desde el código (sin IA)** —el borrador C4 con su página, el stack y las herramientas— y Código ofrece construir el grafo.

Un solo portal, dos modos y la misma interfaz, con el lenguaje visual de Cofundo y la marca Camarón (claro u oscuro, con las fuentes servidas por el propio portal). No hay barra de pestañas: **Inicio** pregunta primero (Preguntar en vivo, el buscador en el exportado), enseña el estado del proyecto (confirmadas, por reconfirmar, borradores, feedback pendiente); el menú lateral mantiene cinco zonas —Docs, Arquitectura, Plan, Calidad y Revisión— en todas las vistas; la barra de arriba dice dónde estás y Ctrl K / ⌘K salta a cualquier página, zona o vista, o (en vivo) lleva la pregunta a Preguntar. Las direcciones de siempre (`#/c4`, `#/docs/…`) siguen funcionando. Las vistas: **Docs** (árbol, búsqueda, confianza), **Arquitectura (C4)** (bajo cada vista, sus elementos: edita título,
tecnología, descripción y relaciones, elimina un elemento y confirma lo que redactó la IA, de uno en uno o la vista entera;
lo confirmado se pliega en su propia sección),
**Grafo de código** (todos los repos o uno), **Wikis** (OpenWiki por repo, sus páginas y su grafo), **Revisión**
(páginas pendientes con sus fuentes, que se confirman varias a la vez; revisiones que espera un agente, peticiones de cambio, código cambiado desde la doc, `check`),
**Preguntar** (las secciones que mejor responden a una pregunta, con citas, sin IA; «base de datos» también encuentra PostgreSQL y las preguntas en español encuentran páginas en inglés; con un agente configurado, «Answer
with AI» redacta la respuesta solo con ellas), **Librerías** (las dependencias de cada repo como matriz librería × servicio, con filtros por
categoría, lenguaje, repo o ámbito y las vulnerabilidades conocidas en rojo), **Datos** (las tablas y colecciones de cada
repo leídas del código, como diagrama ER), **Pipeline** y **KPIs** (páginas y elementos C4 confirmados, páginas desactualizadas, coste de IA por
mes y las preguntas que nadie encontró, que con un clic pasan a pregunta abierta). El selector de idioma cambia la interfaz y
la documentación. Las tablas se ordenan por columna (las largas se filtran), `:::tabs`/`:::steps`/`:::details`/`:::cards`
se ven como pestañas, pasos, desplegables y tarjetas, un interruptor «Todo / Negocio» (en cada página y encima del menú) oculta los bloques `:::tech` y, en Negocio, deja
en el menú y en la portada solo las páginas de visión general, dominio, glosario, flujos y decisiones; la portada tiene
además una caja «¿Cómo funciona…?» que lleva la pregunta a Preguntar, y en
Mermaid los nombres que coinciden con una página o un repo son enlaces. Un bloque `:::rule ORD-1 Título` explica una
regla de negocio con anclas `enforced:`/`test:` (`repo:ruta#Símbolo`); `check` falla si ese código ya no existe.

La vista **Pipeline** (zona Plan; viene ya compilada
con el kit, no hace falta Node) muestra el plan en vivo: un grafo de las unidades por fase, un
tablero por estado y, por unidad, su agente, resultado, tiempo, tokens, coste y el log del agente línea a línea. Si lanzas
`camaron run` con la página abierta, la ejecución aparece sola. Desde la vista también puedes lanzar una ejecución,
cancelarla (los agentes se paran y sus unidades vuelven a la cola sin perder su trabajo) y reintentar una unidad
bloqueada. Una ejecución a la vez, desde la terminal o desde el portal.

| | Comando | Qué es |
|---|---|---|
| Local, editable | `camaron up` (asistente → 🌐 Portal → 📝 Abrir el portal) | `http://127.0.0.1:8080`, solo en tu equipo |
| Exportación para desplegar | `camaron portal` (asistente → 📦 Exportar) | HTML + JSON de solo lectura en `.camarones/.cache/site`, sin npm |
| Ver la exportación | `camaron up --static` o `camaron up --docker` | exactamente lo que servirá el servidor |

La exportación son ficheros estáticos (imagen nginx, GitLab/GitHub Pages) y funciona sin internet. En un servidor, arranca la
imagen que publicó el CI: `docker run -d -p 8080:80 <registry>/<grupo>/cam-docs/portal:latest`.

### 🖥️ La app de escritorio

Donde se opera un proyecto; el portal es donde se lee. Cada proyecto se abre en su ventana: a la izquierda el raíl con
tus proyectos y las secciones, abajo el panel de trabajos (lo que corre y los últimos, su salida y **Parar**). El portal
del navegador queda como visor del equipo (leer, editar, revisar, estado de la pipeline, la entrevista): **Ver portal**, en la
cabecera, y **Docs** lo abren en tu navegador, y no enseña lo que no puede hacer. Con el teclado, Ctrl K / ⌘K va a una sección, a otro proyecto o a cualquier comando, y `g` y una letra salta de
sección (`g s` Resumen, `g b` Tablero, `g p` Plan, `g q` Calidad…).

| Sección | Qué haces ahí |
|---|---|
| 🏠 Resumen | el siguiente paso con un solo botón (el mismo que propone el asistente), lo que le falta a esta máquina, cómo van el plan, la revisión y los trabajos |
| 📋 Tablero | las columnas de Backlog a Hecho: mueves una tarjeta arrastrándola o con el teclado (Tab hasta la tarjeta, Espacio la coge, las flechas la mueven, Intro la suelta, Escape la devuelve); una tarjeta abre su descripción, sus criterios y la definición de hecho, y una historia lista sus tareas y tiene **Añadir tarea**; **Eliminar** archiva la tarjeta (su fichero pasa a `backlog/archive/tasks`); **Añadir** crea un elemento (tipo, título, dentro de qué, prioridad); si el tablero no está activado, **Activar el tablero** |
| 🗺️ Plan | ejecutar las unidades listas en paralelo o el piloto automático, y pararlos; las unidades agrupadas por lo que te piden (aprobar, reintentar, seguir, empezar, rehacer) con el agente que elijas; la actualización de la doc; y, con vista previa, empezar la documentación otra vez (`docs reset`: rehacer o borrar) |
| 🎙️ Entrevistas | cuestionario del equipo o en vivo, exportar el formulario sin conexión, importar respuestas, cerrar la ronda, cada entrevista con su agente |
| 🤝 Equipo | el repo del equipo y compartir, aprobar la configuración de agentes que vino con él, hooks, plugins |
| ✅ Calidad | requisitos y herramientas (guardados entre visitas, «Volver a comprobar»), el contexto que carga cada sesión de agente, preguntas de control, con y sin cam-docs; sin IA, vulnerabilidades conocidas, páginas desactualizadas, bloques generados |
| 📖 Docs | **Leer la documentación**, **Revisar borradores** y **Buscar o preguntar** abren el portal en tu navegador. Debajo, **Construir el explorador C4**; por cada repo, **Generar la wiki** (elige el repo y escribe un brief inicial sin IA si aún no tiene) y, cuando ya tiene páginas, **Grafo del wiki**: cada uno un trabajo con su salida y, al acabar, **Ver** abre el resultado en el portal (**Reintentar** si falló); y **Preguntar con IA**, que responde con lo que dice la documentación y enlaza sus fuentes en el portal |
| 🧰 Máquina | setup con progreso, idioma y modelos, tokens de GitLab / GitHub, repos y su stack, el perfil del plan, actualizar el kit, repair y, aparte y con vista previa, uninstall |

Cada sección acaba con **Todos los comandos**, plegado: el resto de su zona del catálogo, cada uno con su formulario.

**Instalarla y abrirla**

1. El kit instalado (instalación global: el comando `camaron` en tu PATH).
2. Node.js 22 o superior: `node --version`. ¿Falta? `camaron doctor --install node` (winget en Windows, Homebrew en
   macOS).
3. `camaron app`. La primera vez descarga Electron (fijado, unos 100 MB) en `~/.camarones/desktop`, sin permisos de
   administrador y sin tocar tus proyectos; después se abre al momento.

Desde la carpeta de un proyecto abre ese proyecto; desde cualquier otra, la pantalla de inicio (más abajo). El
asistente tiene la misma entrada (🖥️ App de escritorio). Dentro, la cabecera es la barra de la ventana (arrástrala
para moverla) y tus proyectos están en el raíl: otro se abre en la misma ventana, que vuelve a salir donde la dejaste.
<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>O</kbd> (o el **+** del raíl) vuelve a la pantalla de inicio,
**Ver portal** abre el portal en tu navegador y el botón **⋯** de la barra abre el menú de la app, con **Abrir en el
navegador**. En Linux con los *user namespaces* restringidos (Ubuntu
24.04 o posterior) el kit la arranca con `--no-sandbox`: sus ventanas solo cargan el servidor local de tu proyecto.

**La pantalla de inicio y el primer arranque**

Fuera de un proyecto la app pregunta una sola cosa, **¿Qué quieres documentar?**, y ofrece los **Recientes**:

- **Elegir carpeta**: cualquier carpeta. Antes de tocar nada dice qué ha encontrado:
  - varios repos: los documenta, con `cam-docs` en esa carpeta;
  - un repo, o una carpeta dentro de uno: `cam-docs` va junto al repo, en su carpeta padre, y se pueden sumar los repos hermanos;
  - una carpeta vacía: un proyecto nuevo, aún sin nada que leer (se documenta el diseño antes de programar);
  - un proyecto que ya tiene `cam-docs`: se abre tal cual;
  - código que no está en git: no deja continuar, y **Inicializar git aquí** hace `git init` (sin commits ni push) en cada carpeta con código y vuelve a mirar;
  - tu carpeta personal o la raíz de un disco: la rechaza y explica por qué. Elige la carpeta de un proyecto.

  Confirmas el nombre y pulsas **Continuar**.
- **Unirme a la documentación de mi equipo**: pega la URL del repo `cam-docs` del equipo (la de la documentación, no la
  del código) y elige dónde clonarlo. Si git no tiene acceso, la app pide un token y lo guarda en el llavero del
  sistema, nunca en el proyecto; cualquier otro motivo (sin permisos, no existe, sin red) lo dice con esas palabras.

«Crear proyecto», «Unirse» y «Añadir carpeta» ya no están en la app; la CLI conserva `camaron new` y `camaron projects --add`.

Un proyecto sin preparar abre en su ventana el asistente de primer arranque (`#/start`, a pantalla completa):
**Repos** (añade un repo de código con su URL, nombre y rama) → **Herramientas** → **Instalar** (progreso, salida en
vivo, **Cancelar**) → **Stack** (editable) → **Arquitectura** (un borrador C4 sin IA que guardas, miras con **Ver
diagrama** o mejoras con IA) → **Listo**, que te lleva al **Resumen**. Es el mismo estado que usa el asistente de la
terminal, así que puedes cerrar la app a medias y seguir en cualquiera de los dos; si te vas a otra sección antes
de terminar, el **Resumen** te ofrece **Seguir con la preparación**. Un proyecto del equipo al que te
uniste solo pasa por Herramientas, Instalar y Listo. Una carpeta vacía permite cero repos y se salta Stack y
Arquitectura.

### 📋 El tablero

Un Kanban guardado en `cam-docs/backlog/` y versionado con la documentación. Cada tarjeta es un fichero Markdown
compatible con Backlog.md (lo lee y lo edita sin romper nada); el estado propio del kit (columna y orden de cada
tarjeta) está en `backlog/board.yaml`, una línea por tarjeta para que git fusione por tarjeta. Se activa con
`camaron board init`; un proyecto sin `backlog/` se comporta como antes.

```sh
camaron board add story "Reintentos idempotentes" --epic WI-3 --repo payments --doc FLOW-k3f9#retries
camaron board list --status Ready --repo payments     # también --epic, --label, --docs suspect|unconfirmed
camaron board show WI-42                              # la tarjeta y la confianza de sus páginas
camaron board move WI-42 "In Progress"                # Backlog, Ready, In Progress, In Review, Done, Blocked
camaron board assign WI-42 ana
camaron board link WI-42 flows/payments.md#retries
camaron board archive WI-42
camaron board repair                                  # también corre antes de cada checkpoint y share
```

Todos aceptan `--json`. Los enlaces a páginas van por `x-id`, así que sobreviven a moverlas o renombrarlas, y el
tablero sabe si una página enlazada cambió desde que se enlazó. En el portal, la zona **Tablero** (`#/kanban`) tiene
el Kanban con filtros por repo, epic, etiqueta y estado de la documentación, y el detalle de cada tarjeta; escribir
pide el token de la máquina: el portal que la app de escritorio abre en tu navegador lo lleva mientras la app está
abierta, y `camaron up` lo imprime en la dirección como `#cam-token=…`; sin él el tablero es de solo lectura. Al desinstalar, `camaron uninstall` (CLI) pregunta si conservas `backlog/` (`--keep-board` / `--drop-board`
lo deciden sin preguntar); el asistente y la app de escritorio lo conservan siempre.

## 6. Editar: dónde y cuándo

| Dónde | Qué puedes hacer | Dónde queda el cambio |
|---|---|---|
| Portal local (`camaron up`) | editar (markdown + vista previa), **+ Nueva página**, **Confirmar**, **Pedir cambios** | `cam-docs/docs` + commit local si marcas «commit en cam-docs»; el push lo haces tú |
| App de escritorio (**Docs**) | construir el explorador C4, generar la wiki de cada repo y su grafo, preguntar con IA | se lee en el portal; nada en `cam-docs/docs` |
| Portal desplegado (exportación) | leer y buscar; **Editar** abre el fichero en GitLab / GitHub (si `cam-docs` tiene remote) | un merge request en `cam-docs`; el CI lo vuelve a publicar |
| Tu editor / IDE | cualquier `.md` de `cam-docs/docs` | git normal en `cam-docs` |
| La IA (🦐 Siguiente paso) | solo su unidad; nunca reescribe a escondidas lo confirmado | un commit local por unidad |

- **Confirmar** firma con tu `git config user.name`. **Pedir cambios** guarda el comentario y añade una unidad
  `review-fixes` que la IA aplica en la siguiente sesión.
- Con el idioma en español, **Editar** edita la traducción (`docs/i18n/es/…`).
- Editar una página ✅ la pasa a **⚠️ pendiente de reconfirmar** hasta que alguien la vuelva a mirar.
- No edites a mano lo generado (`llms.txt`, `llms-full.txt`, `docs/.status.json`, los visores). Las wikis mejor regenerarlas con
  **Generar la wiki** (app, **Docs**): una actualización de OpenWiki puede reescribir lo que cambies.

## 7. OpenWiki: una wiki por repo

App → **Docs** → **Generar la wiki** (log en directo), asistente → **📚 Wikis**, o `camaron wiki <repo>` en una terminal. La
wiki se guarda en `cam-docs/wikis/<repo>/` (el repo ve un enlace `openwiki/` sin versionar); la lees en el portal del
navegador (**Docs** → **Wikis**), donde sus páginas aparecen como `repos/<repo>/…`. Usa el proveedor de OpenWiki si hay uno configurado (`openwiki auth configure <proveedor>`);
si no, Claude Code o Codex. Los archivos que OpenWiki añade al propio repo (`AGENTS.md`, `CLAUDE.md`, `.github/`) se quitan
al terminar.

Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas: asistente → **📚 Wikis** →
**Elegir qué repos tienen wiki** (se guarda como `wiki: true` en `.camarones/workspace.yaml`). Elige los servicios con
lógica, no librerías ni repos de CI. La primera wiki de un repo espera a su brief (`wikis/<repo>/INSTRUCTIONS.md`, que
escribe la unidad repo-brief) para usar tu glosario; `camaron wiki <repo> --force` se salta esa comprobación, y el comando ni elige el repo ni escribe un brief: pide el repo
clonado y un motor. En **Docs** de la app, todos los repos tienen **Generar la wiki**: si el repo aún no está elegido, lo
elige, y si no tiene brief, antes escribe uno inicial con el análisis estático (sin IA), que la unidad repo-brief
sustituye después. El botón queda cerrado, con el motivo, si el repo no está clonado (clónalo desde **Máquina**) o no
hay ningún motor de wiki instalado. Se lanzan de una en una (mientras se genera la de un repo, el botón de los demás espera), y un lote se para en cuanto el motor se queda sin cuota o sin sesión, en vez de fallar todos los repos
que quedan.

## 8. CI

En el asistente, **⚙️ CI** instala el pipeline en `cam-docs` (GitLab o GitHub): actualiza la doc afectada, pasa `check`, exporta el portal y lo publica. Las plantillas para cada repo de servicio están en `.camarones/ci/repo.*`.
La vista **CI** del portal (zona Calidad) enseña lo mismo: qué ficheros de pipeline hay y si siguen igual que la definición del kit, un
botón para generarlos para GitHub o GitLab, el `check` y la frescura actuales, los ficheros de cada repo para copiar y el
último pipeline cuando `gh` o `glab` está instalado y con sesión.
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

**Una propuesta con IA para una PR.** `camaron pr propose <url de la PR>` trae la PR a `refs/camaron/pr/<n>` del repo
de servicio (tu checkout no se toca) y un agente actualiza las páginas que deja desactualizadas en la rama de cam-docs
`docs/pr-<repo>-<n>`, en su propio worktree. El kit hace el commit, la sube y abre la PR de documentación (`--comment`
la enlaza en la PR del servicio, `--preview` exporta esa rama como portal estático); `--dry-run` enseña antes el plan. Con `ci.target: self-hosted`, `camaron ci` escribe
también `docs-propose`: el mismo comando en vuestro runner cuando alguien del proyecto etiqueta una PR con
`docs:update` (otra etiqueta: `ci: {propose_label: …}` en `workspace.yaml`), nunca para forks. Cómo montar el runner: [guía del runner propio](self-hosted-runner.md).

**El servidor MCP.** Los agentes llegan a la documentación con el servidor MCP `camarones`: `search_docs`,
`read_doc(path, section)`, `ask` (las secciones que mejor responden a una pregunta, con citas), los recursos
`camdocs://<página>` y dos prompts. También puede escribir, pero solo borradores: `propose_edit` cambia un borrador de IA
y nunca toca una página que una persona confirmó o es suya (la propuesta se guarda en `docs/.work/proposals/` y aparece
en Revisión), `add_feedback` deja un comentario de revisión y `mark_suspect` retiene una página hasta que se actualiza o
se confirma que sigue valiendo. Nada de lo que hace confirma una página. `pipeline_status`, `run_events` y `kpis`
informan del plan; `run_node` lanza una unidad solo con `mcp: {pipeline_control: true}` en `workspace.yaml`.
`camaron mcp --http` sirve lo mismo en `http://127.0.0.1:8765/mcp` para clientes que hablen Streamable HTTP: necesitan
`Authorization: Bearer <token>`, con el token en `~/.camarones/mcp-token`, y se rechazan peticiones de otros orígenes.

**Claude Code dentro de un repo.** `setup` (y `repair`) registra el servidor MCP `camarones` en el ámbito local de
Claude Code para la carpeta de cada repo, así que una sesión abierta en `<repo>/` también busca y lee la documentación.
Vive en tu propia configuración de Claude Code (`~/.claude.json`), nunca en el repo; `doctor` avisa si a un repo le
falta y `uninstall` lo quita.

**Hooks del método (opcionales).** `camaron hooks on` añade tres hooks de Claude Code en `cam-docs/.claude/settings.json`,
que son del kit (`trust` no pregunta por ellos): al empezar la sesión el agente recibe el estado del plan, el último
relevo y las revisiones pendientes; justo después de editar una página de la doc, esa página se revisa y los problemas
vuelven al agente; antes de terminar, si los repos han cambiado desde la doc, se le recuerda una vez actualizarla.
`camaron hooks off` los quita.

**¿Se cumple el método?** `camaron eval comply <unidad>` ejecuta de verdad una unidad lista y puntúa lo que ha escrito
(estructura, enlaces, fuentes), sin IA. Úsalo en el sandbox para comparar un cambio del playbook o de un prompt antes y
después.

**Exportar.** `camaron export pdf` junta en una sola página lista para imprimir todas las páginas que pueden leer los
agentes y la convierte en PDF con Chrome, Chromium o Edge sin ventana si hay alguno (si no, imprime la página a PDF
desde el navegador). `camaron export tour flows/<flujo>.md` hace un recorrido guiado de un flujo de negocio, una
diapositiva por fila de su tabla de pasos; `export codetour flows/<flujo>.md` lo escribe como un CodeTour de
VS Code (`.tours/<flujo>.tour`) que abre el código de cada paso. `camaron export confluence` y `export notion` publican la documentación en
esas herramientas; como la sacan de tu máquina, no funcionan hasta que ejecutas `camaron plugins enable confluence` (o
`notion`) y pones su URL y token (`CONFLUENCE_URL`, `CONFLUENCE_USER`, `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE`;
`NOTION_TOKEN`, `NOTION_PARENT_PAGE`).

**Pedir una revisión y esperar.** Un agente que necesita la respuesta de una persona sobre una página ejecuta
`camaron review request <página>` y luego `camaron review wait <id>`: se queda esperando hasta que alguien la aprueba o
pide cambios en la zona Revisión del portal, y recibe la decisión en JSON. Los comentarios de revisión pueden
apuntar a una sección: guardan su slug y una cita corta, así que se encuentran aunque cambie el título.

**Lo que se quitó a propósito.** `camaron removed add "endpoint SOAP de facturación" --why "lo sustituye la API REST"
--decision decisions/0007-drop-soap.md` añade una fila a `docs/overview/removed.md` (qué, cuándo, por qué y la
decisión). Los agentes la leen antes de volver a crear algo; el `AGENTS.md` del proyecto también tiene una tabla
«Where to look» para cada tarea. Cada sesión termina con un relevo que separa lo comprobado (con pruebas), lo no
comprobado, los comandos ejecutados y la siguiente acción.

## 9. Comandos (para scripts y agentes)

`camaron help` (copia por proyecto: `./camaron.command help`, en Windows `camaron.cmd help`) lista: `setup`, `sync`,
`detect`, `plan`, `plan next`, `status`, `check [--strict|--secrets]`, `confirm`, `feedback`, `checkpoint`, `graph`, `arch` (editor C4 en vivo),
`arch-validate`, `wiki <repo>`, `portal` (exportación), `up [--static|--docker]`, `down`, `ci`, `prompt <unidad>`, `migrate`, `doctor`,
`doctor --json` (cada comprobación con el comando que la arregla), `doctor --install git|node|docker|java|claude|codex`,
`doctor --local` (propone un modelo local libre para este equipo, sin instalar nada), `doctor --context` (los tokens
que carga cada sesión de un agente antes de leer una página, frente a `context.budget`), `autopilot`, `plugins [--json]`,
`run`, `runs`, `kpis`, `eval`, `ab`, `pipeline show|validate`, `blocks [--force]`, `pages [--adopt] [--json]`, `diagrams [--json]`, `pr fresh <repo>` y
`plugins add|update|outdated|remove`, `pr propose <url>`, `removed add`, `repair`, `export codetour <flujo>`,
`history [--months 12]` (puntos calientes, a quién preguntar en cada repo, ficheros que cambian juntos, leídos de git sin
IA en `docs/overview/history.md`), `catalog [--json|--check]` (cada comando con dónde vive: portal, app de escritorio o
solo CLI, y sus argumentos) y `projects [--json]` (los proyectos registrados en esta máquina; `--inspect DIR` dice qué es una carpeta, `--adopt DIR [--name NOMBRE]` la convierte en proyecto y `--git-init DIR` pone en git su código: los tres aceptan `--json` y un rechazo es `{"error": taken|home|no-git|git-init, "detail"}`), `join URL --no-open` / `new NOMBRE --no-open` (imprimen `{"path"}`; un acceso rechazado es `{"error": auth|denied|not-found|network|unknown, "host", "detail"}`, y el token de un repo privado llega en `CAMARONES_JOIN_TOKEN`, nunca en la línea de comandos), `config [get|set CLAVE VALOR]` (lang, model, codex_model: los ajustes del asistente), `trust --json` y `hooks --json` (lo pendiente de
aprobar, si los hooks del método están activos), **Plan › Sincronizar** en el portal (lo mismo que `share`, con dónde estás) y `app` (la app de escritorio: las secciones del proyecto por tareas, el portal para leer,
donde se lanzan ejecuciones, wikis, análisis y comprobaciones; el portal del navegador solo las enseña).

**Páginas del código, sin IA.** La instalación (y `camaron pages [--json]`, que las pone al día; `camaron diagrams`
es su alias) escribe `docs/index.md`: qué es el proyecto, una tarjeta por repo y el mapa de contexto. Por cada repo
escribe `docs/repos/<repo>/index.md`: qué expone (el mapa de endpoints, con la tabla de endpoints plegada), qué datos
guarda (diagrama ER), sus ciclos de vida (un diagrama de estados por enum de estado), sus mensajes y qué necesita para
arrancar (variables de entorno y comandos, plegados). Las variables salen de los placeholders `${VAR:valor}` de Spring,
`.env.example` y `environment.ts` de Angular (los valores que parecen secretos se ocultan), los comandos de Maven,
Gradle, `package.json`, Makefile y Docker Compose, los endpoints de OpenAPI (o, si no hay, de las anotaciones de
Spring); cada fila lleva su fichero y línea. Con topics de mensajería hay además `docs/architecture/messaging.md`. Son
bloques `<!-- generated:<tipo> repo=<repo> -->` que puedes poner en cualquier página; `pages`, `blocks` y `sync` los
actualizan. Si alguien edita uno a mano, se conserva y `check` lo avisa; `blocks --force` toma la versión del código.

**Proyectos anteriores a la 4.52.** Conservan sus páginas (`reference.md`, `diagrams.md`, `system-map.md`,
`first-look.md`, `data/<repo>.md`) hasta que ejecutes `camaron pages --adopt`. Mueve los bloques, con sus
confirmaciones, a las páginas nuevas (rellenándolas si el inicio o la página del repo la escribió un agente), borra solo
las páginas del kit que deja vacías, no escribe ni borra nunca una página de una persona (`x-owner: human` o
`x-confirmed`; una página sin `x-owner` es de un agente), apunta los enlaces de las páginas de agente a las páginas
nuevas y lista lo que no pudo tocar (páginas, enlaces, traducciones).

**Diagramas del código, sin IA.** `camaron pages` (alias `camaron diagrams`; también lo ejecutan el primer escaneo y el
primer vistazo) dibuja en Mermaid lo que el código afirma, sin adivinar: el mapa de contexto (repos, almacenes de datos,
brokers, proveedores de identidad) en `docs/index.md`; el mapa de endpoints del repo y un diagrama de estados por cada
enum de estado, solo con los estados (las transiciones no se adivinan), en `docs/repos/<repo>/index.md`; y una secuencia
por topic (quién publica, quién consume) en `docs/architecture/messaging.md`. Son páginas normales de Docs hechas de
bloques generados como los de arriba. Una persona puede confirmar uno a mano: copia el `sha=` del bloque en `confirmed=`
y pon un nombre en `by=` (una palabra, o entre comillas si lleva espacios: `by="Ana López"`), p. ej. `<!--
generated:states repo=api id=OrderStatus confirmed=3fa1c2d4e5f6 by=ana sha=3fa1c2d4e5f6 -->`. Un refresco ya no lo
reescribe y `check` avisa «el código cambió desde que se confirmó este diagrama» (o que el código ya no tiene la fuente
del diagrama). Para quedarte con la versión del código, quita `confirmed=` y `by=` del marcador, ejecuta `camaron
diagrams` (o `blocks`) y vuelve a confirmarlo. El portal etiqueta cada diagrama como «Del código», «Editado a mano»,
«Confirmado por <nombre>» o «El código cambió». Los agentes siguen la skill `cam-docs-diagrams`: elegir el diagrama
adecuado, escribir Mermaid que se dibuje y no editar nunca un bloque generado.

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
`camaron ab --task "<tarea>" [--check "<comando de tests>"]` hace una tarea de código dos veces, cada una en worktrees
desechables de los repos (con un worktree de cam-docs y la configuración de agentes, y sin ellos): compara tokens,
tiempo, herramientas, ficheros cambiados y el diff, y si el check pasa en cada una. Tus checkouts no se tocan.
`camaron ab sampling on` guarda una muestra de prompts reales en esta máquina (solo si además está
`ab: {sampling: {enabled: true, rate: 0.05}}`; se guardan en `~/.camarones/ab-samples/`, nunca en el repo) y
`ab --replay` los ejecuta como tareas.

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
| `camaron app`: "needs Node.js >= 22" | instala Node 22 (`camaron doctor --install node`) y vuelve a lanzar `camaron app` |
| La app abre la pantalla de inicio y no tu proyecto | la lanzaste fuera de la carpeta del proyecto: ábrelo desde **Recientes** o elige su carpeta con **Elegir carpeta** |
| «Este código no está en un repositorio git» | la app necesita su historial: **Inicializar git aquí** crea el repositorio (sin commits ni push) y vuelve a mirar |
| «Aquí no puedo crear el proyecto» | la carpeta es tu carpeta personal o la raíz de un disco: elige la carpeta que contiene tus repos, o una vacía |
| En el portal del navegador falta un botón que esperabas | es a propósito: el portal del navegador no lanza procesos; usa `camaron app` |
