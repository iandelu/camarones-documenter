---
title: Tutorial — Camarones Documenter, el asistente de documentación del proyecto
description: Cómo instalar Camarones Documenter en macOS o Windows, hacer las sesiones guiadas de documentación con Claude Code o Codex, confirmar borradores de IA, levantar el portal y configurar el CI.
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
| Linux / CI | `./camarones.command` (it is a plain shell script) |

**Proyecto nuevo desde el zip:** pon `camarones-documenter.zip` en la carpeta donde están los repos del proyecto, descomprímelo ahí
y abre el lanzador. Si al descomprimir se crea una subcarpeta `camarones-documenter/`, el asistente se ofrece a moverse un nivel más arriba.
Detecta los repos que ya estén en la carpeta, y puedes añadir más por URL.

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

Toda página nace como **🤖 borrador** (el portal lo muestra con un banner). En el asistente, **✅ Revisar y confirmar páginas** te deja
marcar las páginas que has revisado. La confirmación queda ligada al contenido: si alguien edita la página después, pasa a
**⚠️ pendiente de reconfirmar**. Los agentes tratan las páginas confirmadas como la fuente de verdad. Para proteger un párrafo de los agentes:

```markdown
<!-- human -->
Este párrafo solo lo editan personas.
<!-- /human -->
```

## 4. Después de la primera pasada

**🔄 Actualizar doc tras cambios** lanza una sesión incremental: solo regenera lo que ha cambiado en el código, limpia las
páginas obsoletas y nunca reescribe a escondidas las páginas confirmadas. El CI puede hacer lo mismo de forma automática (sección 6).

## 5. Portal

En el asistente: **🌐 Portal** → construir / levantar con Docker / abrir. Sirve:
- la doc en inglés y español;
- el explorador C4 interactivo (`/architecture/`);
- el grafo de código (`/code-graph/`);
- el grafo de la wiki de cada repo (`/wiki-graph/<repo>/`);
- `/llms.txt`.

Es un nginx con ficheros estáticos y funciona sin internet. En un servidor:
`DOCS_IMAGE=<registry>/<grupo>/<umbrella>/portal:latest docker compose -f .camarones/portal/compose.yml up -d --no-build`.

## 6. CI

En el asistente, **⚙️ CI** instala el pipeline del repo umbrella (GitLab o GitHub). Las plantillas para cada repo de servicio están en `.camarones/ci/repo.*`.

Variables necesarias: `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`, y un token de bot para abrir MRs/PRs. En GitLab, además, tienes que
permitir que el job token del proyecto umbrella clone cada repo de servicio (repo → Settings → CI/CD → Job token permissions).

## 7. Comandos (para scripts y agentes)

`./camarones.command help` (en Windows: `camarones.cmd help`) lista estos comandos: `setup`, `sync`, `detect`, `plan`, `plan next`, `status`, `check`,
`confirm`, `graph`, `arch` (editor C4 en vivo), `arch-validate`, `portal`, `up`, `down`, `ci`, `prompt <unidad>` y `doctor`.

## 8. Problemas frecuentes

| Problema | Solución |
|---|---|
| macOS bloquea `camarones.command` ("no se puede abrir" / "Apple no pudo verificar…") | abre Terminal en la carpeta y ejecuta `sh camarones.command` (una vez: el lanzador quita la marca de cuarentena y a partir de ahí el doble clic funciona). Alternativa: Ajustes del Sistema → Privacidad y seguridad → "Abrir igualmente" |
| Windows: aviso de SmartScreen | "Más información" → "Ejecutar de todas formas" |
| Windows bloquea el archivo o lo borra el antivirus | antes de descomprimir: clic derecho en el zip → Propiedades → marca **Desbloquear** → Aceptar. Si ya lo descomprimiste, en PowerShell dentro de la carpeta: `Get-ChildItem -Recurse | Unblock-File`. Si el equipo es de empresa y no deja ejecutar `.cmd`: `winget install astral-sh.uv` y luego `uv run --script .camarones\camarones.py` |
| Algo se ha instalado pero no lo detecta | cierra y vuelve a abrir el asistente (para que se refresque el PATH) |
| `doctor` dice que falta una herramienta | en el asistente: 🛠 Instalar / reparar |
| Al sincronizar, un repo sale como "skip … local changes" | haz commit o stash en ese repo y vuelve a sincronizar |
| Errores en el C4 | `camarones arch-validate` te dice el fichero y la línea |
| El agente no tiene las herramientas de OpenWiki | reinicia Claude Code / Codex dentro de la carpeta del proyecto |
