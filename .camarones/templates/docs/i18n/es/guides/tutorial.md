---
title: Tutorial — Camarones Documenter, el asistente de documentación del proyecto
description: Cómo instalar Camarones Documenter en macOS o Windows, hacer las sesiones guiadas de documentación con Claude Code o Codex, confirmar borradores de IA, usar el portal (leer, editar, revisar), generar las wikis de OpenWiki y configurar el CI.
x-owner: human
---
# Tutorial — Camarones Documenter 🦐

*Camarón que se duerme, se lo lleva la corriente.* Camarones Documenter documenta un proyecto entero (todos sus repos) en sesiones
cortas con IA, guarda el progreso después de cada una y siempre te dice qué viene a continuación.

## 1. Instalación (una vez por ordenador)

Requisitos:
- **git** y **Node.js ≥ 22**. Si faltan, el asistente se ofrece a instalarlos con Homebrew o winget.
- **Docker Desktop**, solo si quieres servir el portal.
- **Claude Code** y/o **Codex**, para las sesiones con IA.

**No** hace falta Python: el lanzador instala `uv`, que ya trae su propio Python.

| | Abrir el asistente |
|---|---|
| macOS | doble clic en `camarones.command` (si macOS lo bloquea la primera vez: Terminal en la carpeta → `sh camarones.command`) o `./camarones.command` |
| Windows | doble clic en `camarones.cmd`, o `camarones.cmd` en un terminal |
| Linux / CI | `./camarones.command` (es un script de shell normal) |

**Instalación global (varios proyectos):** `sh install-global.sh` (Windows: `install-global.cmd`) desde el repo del kit deja
el comando `camarones` en tu PATH; ejecuta `camarones` en la carpeta que agrupa los repos y crea `./cam-docs/`.

**Proyecto nuevo desde el zip:** pon `camarones-documenter.zip` en la carpeta donde están los repos del proyecto, descomprímelo ahí
y abre el lanzador. Si al descomprimir se crea una subcarpeta `camarones-documenter/`, el asistente se ofrece a moverse un nivel más arriba.
Detecta los repos que ya estén en la carpeta, y puedes añadir más por URL.

Todo lo que escribe el kit vive en **`cam-docs/`**, junto a los repos: un repo git propio con `docs/`, `wikis/<repo>/`, la
configuración de la herramienta (`.camarones/`) y la de los agentes (`.claude/`, `.codex/`, `.agents/`, `.mcp.json`). Los
repos de servicio no reciben archivos del kit; las rutas de abajo son relativas a `cam-docs/`.

## 2. El flujo guiado

La primera vez te lleva por 4 pasos:
1. **Workspace:** nombre del proyecto y repos.
2. **Herramientas:** tabla con lo que tienes y lo que falta; eliges **instalar todo (recomendado)** o **qué instalar** (git, Node, Docker, Java, Claude/Codex, graphify, LikeC4, OpenWiki, hooks…).
3. **Setup:** herramientas, repos, conexión de Claude/Codex y hooks de git.
4. **Sesiones:** te explica cómo funcionan.

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

## 3. Confianza: borradores de IA frente a doc confirmada

Toda página nace como **🤖 borrador** (el portal lo muestra con un banner). Confírmalas en el portal (**Confirmar** en cada
página; la pestaña **Revisión** lista lo pendiente) o en el asistente con **✅ Revisar y confirmar páginas**. La confirmación queda ligada al contenido: si alguien edita la página después, pasa a
**⚠️ pendiente de reconfirmar**. Los agentes tratan las páginas confirmadas como la fuente de verdad. Para proteger un párrafo de los agentes:

```markdown
<!-- human -->
Este párrafo solo lo editan personas.
<!-- /human -->
```

## 4. Después de la primera pasada

**🔄 Actualizar doc tras cambios** lanza una sesión incremental: solo regenera lo que ha cambiado en el código, limpia las
páginas obsoletas y nunca reescribe a escondidas las páginas confirmadas. El CI puede hacer lo mismo de forma automática (sección 8).

**Control de calidad.** `camarones check` se ejecuta al cerrar cada unidad y en el CI. Además del frontmatter, las fuentes,
la confianza y las traducciones, revisa:

| Comprobación | Gravedad | Necesita |
|---|---|---|
| Enlace roto a otra página (no se comprueban URLs externas ni `#anclas`) | ERROR | — |
| Diagrama Mermaid que no se dibuja | ERROR | mermaid-cli |
| Posible secreto en `docs/` o en una wiki (solo fichero y línea, nunca el valor) | ERROR; además bloquea los commits de checkpoint y `camarones portal` | gitleaks |
| Una palabra de la columna **Avoid** del glosario | aviso (ERROR con `--strict`) | una columna Avoid en `docs/domain/glossary.md` |

mermaid-cli y gitleaks vienen con la instalación completa (el componente `quality`; mermaid-cli descarga una vez un
Chromium sin ventana). Si faltan, `check` lo avisa una vez y se salta esa comprobación.

## 5. Portal

Un solo portal, dos modos, la misma interfaz. Pestañas: **Docs** (árbol, buscador, marcas de confianza),
**Arquitectura (C4)**, **Grafo de código** (todos los repos o uno), **Wikis** (la OpenWiki de cada repo, sus páginas y su
grafo) y **Revisión** (páginas pendientes, peticiones de cambio, código cambiado desde la doc, `check`). El selector de
idioma cambia la interfaz y la doc; una página sin traducir se muestra en inglés con un aviso.

| | Comando | Qué es |
|---|---|---|
| Local, editable | `camarones up` (asistente → 🌐 Portal → 📝 Abrir el portal) | `http://127.0.0.1:8080`, solo en tu equipo |
| Exportación para desplegar | `camarones portal` (asistente → 📦 Exportar) | HTML + JSON de solo lectura en `.camarones/.cache/site`, sin npm |
| Ver la exportación | `camarones up --static` o `camarones up --docker` | exactamente lo que servirá el servidor |

La exportación son ficheros estáticos (imagen nginx, GitLab/GitHub Pages) y funciona sin internet. En un servidor, arranca la
imagen que publicó el CI: `docker run -d -p 8080:80 <registry>/<grupo>/cam-docs/portal:latest`.

## 6. Editar: dónde y cuándo

| Dónde | Qué puedes hacer | Dónde queda el cambio |
|---|---|---|
| Portal local (`camarones up`) | editar (markdown + vista previa), **+ Nueva página**, **Confirmar**, **Pedir cambios**, generar wikis, reconstruir C4 / grafo | `cam-docs/docs` + commit local si marcas «commit en cam-docs»; el push lo haces tú |
| Portal desplegado (exportación) | leer y buscar; **Editar** abre el fichero en GitLab / GitHub (si `cam-docs` tiene remote) | un merge request en `cam-docs`; el CI lo vuelve a publicar |
| Tu editor / IDE | cualquier `.md` de `cam-docs/docs` | git normal en `cam-docs` |
| La IA (🦐 Siguiente paso) | solo su unidad; nunca reescribe a escondidas lo confirmado | un commit local por unidad |

- **Confirmar** firma con tu `git config user.name`. **Pedir cambios** guarda el comentario y añade una unidad
  `review-fixes` que la IA aplica en la siguiente sesión.
- Con el idioma en español, **Editar** edita la traducción (`docs/i18n/es/…`).
- Editar una página ✅ la pasa a **⚠️ pendiente de reconfirmar** hasta que alguien la vuelva a mirar.
- No edites a mano lo generado (`llms.txt`, `docs/.status.json`, los visores). Las wikis mejor regenerarlas desde la pestaña
  **Wikis**: una actualización de OpenWiki puede reescribir lo que cambies.

## 7. OpenWiki: una wiki por repo

Portal → **Wikis** → **Generar / actualizar wiki** (log en directo), asistente → **📚 Wikis**, o `camarones wiki <repo>`. La
wiki se guarda en `cam-docs/wikis/<repo>/` (el repo ve un enlace `openwiki/` sin versionar) y sus páginas aparecen en
**Docs** como `repos/<repo>/…`. Usa el proveedor de OpenWiki si hay uno configurado (`openwiki auth configure <proveedor>`);
si no, Claude Code o Codex. Los archivos que OpenWiki añade al propio repo (`AGENTS.md`, `CLAUDE.md`, `.github/`) se quitan
al terminar.

Cada wiki es una sesión de agente completa, así que solo la llevan los repos que elijas: asistente → **📚 Wikis** →
**Elegir qué repos tienen wiki** (se guarda como `wiki: true` en `.camarones/workspace.yaml`). Elige los servicios con
lógica, no librerías ni repos de CI. La primera wiki de un repo espera a su brief (`wikis/<repo>/INSTRUCTIONS.md`, que
escribe la unidad repo-brief) para usar tu glosario; `camarones wiki <repo> --force` se salta esa comprobación. Se lanzan
de una en una, y un lote se para en cuanto el motor se queda sin cuota o sin sesión, en vez de fallar todos los repos
que quedan.

## 8. CI

En el asistente, **⚙️ CI** instala el pipeline en `cam-docs` (GitLab o GitHub): actualiza la doc afectada, pasa `check`, exporta el portal y lo publica. Las plantillas para cada repo de servicio están en `.camarones/ci/repo.*`.
Antes de subir la rama de actualización se ejecuta `camarones check --secrets`: si encuentra un posible secreto, el job falla y no se abre el MR/PR.

Variables necesarias: `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`, y un token de bot para abrir MRs/PRs. En GitLab, además, tienes que
permitir que el job token del proyecto `cam-docs` clone cada repo de servicio (repo → Settings → CI/CD → Job token permissions).

## 9. Comandos (para scripts y agentes)

`camarones help` (copia por proyecto: `./camarones.command help`, en Windows `camarones.cmd help`) lista: `setup`, `sync`,
`detect`, `plan`, `plan next`, `status`, `check [--strict|--secrets]`, `confirm`, `feedback`, `checkpoint`, `graph`, `arch` (editor C4 en vivo),
`arch-validate`, `wiki <repo>`, `portal` (exportación), `up [--static|--docker]`, `down`, `ci`, `prompt <unidad>`, `migrate` y `doctor`.

## 10. Problemas frecuentes

| Problema | Solución |
|---|---|
| macOS bloquea `camarones.command` ("no se puede abrir" / "Apple no pudo verificar…") | abre Terminal en la carpeta y ejecuta `sh camarones.command` (una vez: el lanzador quita la marca de cuarentena y a partir de ahí el doble clic funciona). Alternativa: Ajustes del Sistema → Privacidad y seguridad → "Abrir igualmente" |
| Windows: aviso de SmartScreen | "Más información" → "Ejecutar de todas formas" |
| Windows bloquea el archivo o lo borra el antivirus | antes de descomprimir: clic derecho en el zip → Propiedades → marca **Desbloquear** → Aceptar. Si ya lo descomprimiste, en PowerShell dentro de la carpeta: `Get-ChildItem -Recurse | Unblock-File`. Si el equipo es de empresa y no deja ejecutar `.cmd`: `winget install astral-sh.uv` y luego `uv run --script .camarones\camarones.py` |
| Algo se ha instalado pero no lo detecta | cierra y vuelve a abrir el asistente (para que se refresque el PATH) |
| `doctor` dice que falta una herramienta | en el asistente: 🛠 Instalar / reparar |
| Al sincronizar, un repo sale como "skip … local changes" | haz commit o stash en ese repo y vuelve a sincronizar |
| Errores en el C4 | `camarones arch-validate` te dice el fichero y la línea |
| `checkpoint` / `portal` se niegan: "possible secret" | sustituye el valor de ese fichero y línea por un marcador (`<tu token>`) y vuelve a lanzarlo |
| `check`: "mermaid-cli could not start its browser" | a Chromium le faltan librerías del sistema (suele pasar en contenedores de CI); se saltan los diagramas, el resto del check sigue |
| El agente no tiene las herramientas de OpenWiki | reinicia Claude Code / Codex en la carpeta del workspace (la que contiene `cam-docs/`) |
| El portal desplegado no tiene botón **Editar** | `cam-docs` no tiene remote de git: añádelo y vuelve a exportar |
| Falló la generación de una wiki | la línea ⚠ dice por qué (cuota o sesión → espera o vuelve a iniciar sesión); lanza otra vez `camarones wiki <repo>`: un run interrumpido se reanuda |
