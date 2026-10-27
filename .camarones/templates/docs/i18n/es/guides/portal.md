---
type: guide
title: El portal
description: Cada zona y vista del portal web de Camarón — qué ves, qué puedes hacer, en qué dirección está y qué cambia entre el portal en vivo y el exportado.
tags: [onboarding, portal]
x-owner: human
---
# El portal

> **TL;DR:** El portal es donde el equipo lee la documentación. En vivo (`camaron up`, o **Ver portal** en la app)
> además edita, confirma, revisa, responde la entrevista y se sincroniza con el equipo; exportado (`camaron portal`) es
> una web de solo lectura que puedes publicar donde quieras. Nunca ejecuta nada en tu máquina: eso es cosa de la
> [app de escritorio](app.md).

## Tres formas de abrirlo

| Cómo | Comando | Qué puede hacer |
|---|---|---|
| Desde la app de escritorio | **Ver portal** (cabecera), la sección Docs, cualquier botón «Abrir en el portal» | Todo lo que hace el portal en vivo, y además escribir en el Tablero y guardar historias: la app le pasa al navegador un token para esa sesión |
| En vivo, desde una terminal | `camaron up` (se para con `camaron down`) | Leer, buscar, editar y crear páginas, confirmar, pedir cambios, revisar, editar el modelo C4, responder la entrevista, sincronizar con el equipo, aprobar o reintentar unidades del plan. Imprime una dirección con `#cam-token=…`: abre esa para poder escribir también en el Tablero y guardar historias |
| Exportado | `camaron portal` (lo deja en `.camarones/.cache/site`); míralo con `camaron up --static` o `camaron up --docker` | Solo leer y buscar, desde HTML y JSON estáticos: sin servidor, sin npm, funciona sin conexión. Se publica en cualquier sitio (imagen de nginx, GitLab o GitHub Pages). **Editar en el repositorio ↗** te lleva al fichero de la página en GitLab o GitHub cuando `cam-docs` tiene remoto |

El portal en vivo solo escucha en tu máquina (`localhost`). No tiene inicio de sesión: quien pueda abrirlo puede editar.
El token de la dirección se guarda solo para esa pestaña del navegador y se quita de la barra de direcciones.

### Lo que nunca hace

Lanzar o cancelar ejecuciones, construir el explorador C4, el grafo de código o el grafo de una wiki, generar wikis,
analizar librerías, escribir las páginas de datos, generar los ficheros de CI y responder con IA se ejecutan en tu
máquina, así que están en la app de escritorio. El portal enseña su resultado, no sus botones.

<!-- go:docs -->

## El marco

**Cabecera**: el nombre del proyecto (vuelve a Inicio), dónde estás (`Arquitectura › Modelo C4 › index`), **Buscar**
(<kbd>⌘</kbd> <kbd>K</kbd> / <kbd>Ctrl</kbd> <kbd>K</kbd>, o <kbd>/</kbd>), las cifras de confianza (confirmadas,
borradores, por reconfirmar, peticiones de cambio sin aplicar), el idioma y ◐ para claro u oscuro.

**Menú lateral**: Inicio y siete zonas —Docs, Tablero, Historias, Arquitectura, Plan, Calidad y Revisión—. La zona en la
que estás abre sus vistas; debajo de las zonas, el panel de lo que estás mirando (el árbol de páginas en Docs, las
wikis, el mapa del código, las vistas C4). El portal exportado tiene Docs, Arquitectura y Revisión.

**Idioma.** Un solo selector cambia a la vez la interfaz y la documentación. Aparece cuando el proyecto tiene
traducciones; una página aún sin traducir se ve en inglés con un aviso.

**Todo / Negocio.** Arriba del árbol de páginas, y dentro de cualquier página con bloques técnicos. Negocio oculta los
bloques `:::tech` y deja, en el árbol y en la portada de Docs, solo las páginas de qué hace el sistema y por qué: visión
general, dominio, glosario, flujos y decisiones.

**La paleta** (<kbd>⌘</kbd> <kbd>K</kbd>): en el portal en vivo, primero **Preguntar** (tu texto como pregunta), después
**Ir a** (zonas y vistas), **Páginas** (por título) y, desde dos letras, **Contenido** (resultados del texto completo, y
«Todos los resultados»). <kbd>↑</kbd> <kbd>↓</kbd> se mueven, <kbd>Intro</kbd> abre, <kbd>Esc</kbd> cierra.

## Inicio, búsqueda y Preguntar

**Inicio** (`#/`) pregunta primero: «Pregunta lo que sea del proyecto». La caja manda tu pregunta a Preguntar (o, en el
exportado, al buscador). Debajo: la página de inicio del proyecto (`docs/index.md`: qué es, una tarjeta por repo, el
mapa de contexto; sus nodos abren la página de cada repo) y el estado de la documentación: confirmadas, por
reconfirmar, borradores y comentarios pendientes.

Un proyecto todavía sin documentación lo dice y te manda al plan: ejecuta su siguiente unidad desde el Plan de la app
de escritorio (o con `camaron run`).

**Buscar** (`#/search/<palabras>`): las páginas que lo mencionan, con hasta tres líneas resaltadas cada una.

**Preguntar** (`#/ask/<pregunta>`, en vivo): las secciones que mejor responden a la pregunta, con su cita y su
confianza, el mismo material que recibe un agente por el MCP. Busca por sentido —«base de datos» encuentra
PostgreSQL, una pregunta en español encuentra páginas en inglés— y no usa IA. Una sección que los agentes aún no
reciben (sospechosa, obsoleta o sin revisar) lo dice. Redactar la respuesta con IA es **Docs › Preguntar con IA** en la
app de escritorio.

<!-- portal:#/ask -->

## Docs

**Portada de Docs** (`#/docs`): el título, las cifras (páginas, % confirmado, flujos, vistas C4), una tarjeta por
sección y el diagrama de contexto del sistema.

**El árbol de páginas**: **Nueva página** (en vivo), las secciones en su orden de siempre, carpetas que se pliegan, un
punto con la confianza de cada página y, al final y plegadas, las **Notas de trabajo** (descubrimiento, entrevistas,
cuestionarios).

**Una página** (`#/docs/<ruta>`) enseña:

- su **confianza**: Confirmada, Borrador o Por reconfirmar, y quién la confirmó y cuándo;
- su **frescura**: Código al día, El código cambió, Código desaparecido o Sin fuentes, frente al código que cita en
  `x-sources`;
- avisos cuando es un borrador de IA, hay que reconfirmarla, cita código que cambió o ya no existe, o su traducción
  falta o está desactualizada;
- **En esta página** (el índice), **Anterior / Siguiente** y la tarjeta de **Fuentes**: los ficheros que cita, por repo,
  cada uno con su frescura. Al pasar el ratón ves qué los cambió (commits, PR o MR, claves de ticket). Un clic abre las
  líneas en tu editor (VS Code, Cursor, Windsurf, VSCodium, IntelliJ IDEA, WebStorm, PyCharm) o, en el exportado, en el
  repositorio.

Lo que puedes hacer en ella, en vivo:

| Botón | Qué hace |
|---|---|
| **Editar** | Markdown a la izquierda y la vista previa en vivo a la derecha; **Guardar** escribe el fichero y, con «commit en cam-docs» marcado, hace un commit local. Editar una página confirmada hace que haya que reconfirmarla |
| **Confirmar como correcta** | La firma con tu nombre (tu usuario de git por defecto): desde ese momento los agentes la tratan como la verdad |
| **Pedir un cambio** | Para toda la página o una sección: un comentario para la siguiente sesión de IA (añade la unidad `review-fixes`), o **Crear un elemento del tablero →** con la página enlazada |

**Nueva página** (`#/new`) crea una página tuya (`x-owner: human`), que los agentes nunca reescriben.

<!-- portal:#/docs -->

## Wikis

`#/wikis`: una tarjeta por repo —páginas y cuándo se actualizó, o «aún sin wiki» / «sin clonar»— con **Grafo** (el
grafo de páginas conectadas de OpenWiki) y **Leer las páginas** (dentro del portal, con su propio menú y «Enlazada
desde»). Generar o actualizar una wiki es **Docs › Generar la wiki** en la app de escritorio.

<!-- portal:#/wikis -->

## Tablero

El Kanban de `cam-docs/backlog/` (`#/kanban`, en vivo), las mismas tarjetas que el [Tablero de la app](app.md#tablero).

- **Columnas**: Backlog, Listo, En curso, En revisión, Hecho, Bloqueado.
- **Tarjetas**: id, tipo, prioridad, **Oleada N** (las tareas de una oleada pueden hacerse a la vez sin tocar los
  mismos ficheros), **Bloqueada** con el motivo, el padre, la persona asignada, la épica, los repos y cuántas páginas
  enlaza (y cuántas son sospechosas).
- **Filtros**: repo, épica, etiqueta y estado de la documentación (desactualizada, sin confirmar), con **Limpiar**.
- **Mover** arrastrando o con el teclado (las flechas eligen, <kbd>Espacio</kbd> coge, las flechas mueven,
  <kbd>Intro</kbd> suelta, <kbd>Esc</kbd> cancela). Al pasar a En curso, la **puerta de salida** comprueba dependencias
  y choques de ficheros y ofrece **Mover igualmente**.
- **Una tarjeta** (`#/kanban/<ID>`): estado, tipo, prioridad, persona asignada, épica, repos, su fichero; **Objetivo**
  (descripción, criterios de aceptación, definición de hecho), **Conocimiento** (las páginas enlazadas con su
  confianza, y si cambiaron desde que se enlazaron) e **Historial**.
- **+ Añadir** crea un elemento con su página enlazada. `#/kanban?parent=WI-14` enseña una historia con sus subtareas.

Sin el token (una dirección de `camaron up` sin él, o un exportado) el Tablero es de solo lectura y dice por qué.

<!-- portal:#/kanban -->

## Historias

`#/stories` (en vivo) es donde una historia se escribe bien y se parte en subtareas que no chocan. El veredicto, las
subtareas y las oleadas salen de reglas y del mapa del código, nunca de la IA: el mismo tablero da siempre la misma
respuesta.

1. **Escribe la historia**: *Como / quiero / para*, con avisos al instante (rol genérico, dos objetivos en uno, un «para»
   que repite el «quiero», demasiado larga, una solución dentro del «quiero», sin huella). El título sigue al «quiero».
   **Toca** es la huella: los ficheros, grupos de código y páginas que cambia; escribe `repo:ruta` para añadir un
   fichero que creará una tarea. Las páginas que enlaza la historia la rellenan con sus fuentes.
2. **Revisa**: el veredicto INVEST (Bien, Mejorable, Mal) con un motivo por letra, los criterios de aceptación, la
   huella y lo que se solapa con otras historias abiertas.
3. **Subtareas propuestas**: una tarea por grupo de código y otra por página, con dependencias (quien da servicio va
   antes que quien lo usa), choques y **oleadas**. Edita títulos, quita, añade, fusiona; las oleadas se recalculan al
   momento.

No se escribe nada hasta **Añadir historia + n subtareas al backlog** (o **Guardar**). Guardar una historia que ya
existía escribe solo lo que tú cambiaste: lo que otra persona cambió mientras tanto se conserva, y si los dos
cambiasteis lo mismo te pide recargarla. **✨ Sugerir con IA** está en los tres pasos y solo gasta al pulsarlo; solo
sugiere —nunca huellas, dependencias, oleadas ni el veredicto— y sale desactivado, con el motivo, sin agente, sin el
token o con `stories: {ai: false}`. Mientras piensa, el botón brilla y no se puede volver a pulsar (<kbd>Esc</kbd>
cancela); lo que propone se queda en este navegador, por historia, hasta que lo aceptas o lo descartas, aunque pidas
otra cosa, abras otra historia o recargues. Un borrador que dejas a medias también se guarda.

<!-- portal:#/stories -->

## Arquitectura

**Modelo C4** (`#/c4/<vista>`): las vistas están en el menú lateral (sistema, contenedores y componentes, flujos,
despliegue) y `#/c4` abre la primera. Cada vista enseña su diagrama y, en vivo, **sus elementos**: su tipo, tecnología,
descripción y relaciones, primero los borradores de IA. Puedes **Editar** un elemento, añadir o quitar una relación,
**Eliminar** un elemento (se van también sus hijos, sus relaciones y sus menciones; el ámbito de una vista no se puede
eliminar) y **Confirmar** uno o **la vista entera** (`#ai-draft` pasa a `#confirmed`, con quién y cuándo). Cada cambio
toca solo esas líneas del fichero `.c4` y se comprueba con LikeC4; si rompe el modelo, no se guarda. El diagrama se
vuelve a dibujar cuando se reconstruye el explorador C4 desde la app de escritorio. **Leer el flujo** abre la página de
un flujo; el explorador completo se abre desde el menú lateral.

**Grafo de código** (`#/code`): el grafo de graphify convertido en un mapa legible —los módulos de cada repo y sus
dependencias, los ficheros más usados, los paquetes y, por fichero, qué usa y quién lo usa— con buscador. El grafo en
bruto está a un clic.

**Datos** (`#/data`, en vivo): las tablas y colecciones de cada repo leídas del código, con el diagrama ER y sus
campos.

**Librerías** (`#/libs`, en vivo): las dependencias directas de cada repo como matriz librería × repo, con filtros
(categoría, lenguaje, repo, ámbito, solo vulnerables); las vulnerables primero, con sus avisos y la versión que las
corrige. `#/libs/<repo>` la abre para un solo repo.

<!-- portal:#/c4 -->

## Plan

**Pipeline** (`#/pipeline`, en vivo): el plan como **Grafo** (las unidades por fase, con sus dependencias) o como
**Tablero** (por hacer, en curso, bloqueada, hecha, descartada). El panel de una unidad: su agente, resultado, tiempo,
tokens y coste, si trabajó en su propia copia, a qué espera, sus notas y el registro en vivo del agente. **Aprobar**
deja empezar a las unidades que van detrás de una que espera a una persona; **Reintentar** devuelve a la cola una
bloqueada. Ejecutar y cancelar son cosa de la app (Plan). Una ejecución parada desde fuera (su trabajo parado, su
proceso terminado) se ve interrumpida en unos segundos.

**Entrevista** (`#/interview`, en vivo): cuando las entrevistas van como cuestionario del equipo, cada persona responde
aquí —lo que se dedujo del código con su evidencia, las opciones, «Otra» y un comentario—. Guarda el mismo fichero que
el formulario sin conexión, así que las dos vías se mezclan, y quien vuelve ve sus respuestas para cambiarlas. Arriba:
quién ha respondido, qué no ha respondido nadie y dónde no hay acuerdo.

**Sincronizar** (`#/sync`, en vivo): este `cam-docs` frente al repo del equipo —tus commits sin compartir, los suyos que
no tienes, cuándo compartió esta máquina por última vez y los ficheros aún sin guardar—. **Sincronizar con el equipo**
hace lo mismo que `camaron share` (un checkpoint, entra el trabajo del equipo, sale el tuyo); **Comprobar si hay
novedades** pregunta al remoto. Un conflicto se deshace; un posible secreto bloquea el push.

<!-- portal:#/pipeline -->

## Calidad

**Salud** (`#/health`, en vivo): el mismo veredicto, las tres áreas y la tabla por repo que la Calidad de la app, de
solo lectura, de la última comprobación. Las filas enlazan a Revisión, Librerías o KPIs; volver a comprobar se hace en
la app o con `camaron health`. `#/health/<repo>` es un repo completo: su puerta de calidad de SonarQube y nueve cifras,
la cobertura y los informes de los que sale, sus librerías vulnerables, su deuda técnica por la página de la que sale y
las páginas que citan su código y están desactualizadas.

**KPIs** (`#/kpis`, en vivo): ¿funciona la documentación? **Plan desde 0** (lo que costó el plan), páginas y elementos
C4 confirmados, páginas desactualizadas, búsquedas sin respuesta, unidades hechas, coste de IA del mes, preguntas de
oro, confianza por repo y las **Preguntas que nadie encontró**: cada una con **Añadir a preguntas abiertas** (para la
siguiente entrevista) o **Descartar**.

**CI** (`#/ci`, en vivo): los ficheros de pipeline de `cam-docs` y si siguen igual que la definición del kit, lo que
dice `check` ahora, el fragmento para cada repo de servicio con **Copiar**, y el último pipeline si `gh` o `glab` tienen
sesión. Generar los ficheros es cosa de la app de escritorio.

<!-- portal:#/health -->

## Revisión

`#/review`: lo que espera a una persona. Filtra borradores o páginas por reconfirmar; cada una dice de dónde sale
(`x-sources`). En vivo, marca varias (<kbd>j</kbd> <kbd>k</kbd> se mueven, <kbd>x</kbd> marca, <kbd>Intro</kbd> abre) y
**Confirmar las n** de una vez. Debajo: **Revisiones que espera un agente** (un agente ejecutó
`camaron review request` y espera: **Aprobar** o **Pedir cambios**), después las peticiones de cambio, los repos cuyo
código cambió desde la documentación y las comprobaciones.

<!-- portal:#/review -->

## Lo que pueden hacer las páginas

El portal pinta el Markdown con algunos extras; los agentes leen los mismos ficheros como Markdown normal.

| Escribes | Obtienes |
|---|---|
| `> [!NOTE]` (TIP, IMPORTANT, WARNING, CAUTION) | Un recuadro destacado |
| `:::tabs` con `::tab Etiqueta` | Pestañas |
| `:::steps`, `:::details Resumen`, `:::cards` | Pasos numerados, un desplegable, tarjetas |
| `:::tech` | Un bloque que Negocio oculta |
| `:::rule ORD-1 Título` con líneas `enforced:` y `test:` | Una tarjeta de regla de negocio; `camaron check` falla cuando su código ya no existe |
| Una tabla | Se ordena por columna; un filtro desde ocho filas |
| Un bloque de código | Resaltado, con **Copiar** |
| Un diagrama Mermaid | Dibujado, con pantalla completa y zoom; los nombres que coinciden con una página o un repo son enlaces |
| Bloques `<!-- generated:… -->` | Una etiqueta: Del código, Confirmado por…, El código cambió, Editado a mano |
| Una página de flujo (`flows/<slug>.md`) | Su vista dinámica C4, interactiva, tras su primer párrafo |

## Direcciones

| Dirección | Vista |
|---|---|
| `#/` | Inicio |
| `#/docs`, `#/docs/<ruta>`, `#/new` | Portada de Docs, una página, una página nueva |
| `#/wikis`, `#/wiki/<repo>`, `#/wiki/<repo>/<página>` | Wikis, el grafo de una wiki, una página de wiki |
| `#/kanban`, `#/kanban/<ID>`, `#/stories` | Tablero, una tarjeta, Historias |
| `#/c4`, `#/c4/<vista>`, `#/code`, `#/data`, `#/libs` | Arquitectura |
| `#/pipeline`, `#/interview`, `#/sync` | Plan |
| `#/health`, `#/health/<repo>`, `#/kpis`, `#/ci` | Calidad |
| `#/review`, `#/search/<palabras>`, `#/ask/<pregunta>` | Revisión, búsqueda, Preguntar |

Las direcciones antiguas (`#/doc/…`, `#/status`, `#/wikis/<repo>`) siguen funcionando.
