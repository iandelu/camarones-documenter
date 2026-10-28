---
type: guide
title: La app de escritorio
description: Cada pantalla de la app de escritorio de Camarón — la ventana, la pantalla de inicio, el asistente de primer arranque y cada sección — con lo que ejecuta cada botón y cuándo está desactivado.
tags: [onboarding, tooling, desktop]
x-owner: human
---
# La app de escritorio

> **TL;DR:** `camaron app` abre una ventana por proyecto. El raíl de la izquierda cambia de proyecto, las secciones
> ejecutan lo que pasa en tu máquina (plan, entrevistas, equipo, calidad, librerías, wikis, preparación) y el portal se
> abre en tu navegador para leer. Cada botón ejecuta un comando `camaron` que podrías escribir tú, y su salida queda en
> el panel de trabajos de abajo.

La app es donde **operas** un proyecto; el [portal](portal.md) es donde lo **lees**. La app nunca muestra el portal
dentro de su ventana: **Ver portal**, la sección Docs y cada botón «Abrir en el portal» lo abren en el navegador del
sistema. Lo que el portal del navegador no puede hacer (lanzar ejecuciones, construir el explorador C4, generar wikis,
buscar vulnerabilidades, responder con IA) está aquí.

<!-- tour:app -->

## La ventana

Cada proyecto tiene su ventana, servida por el servidor local de ese proyecto (ver
[cómo funciona](internals.md#el-servidor-del-proyecto)). La ventana tiene cinco partes:

| Parte | Qué hace |
|---|---|
| Cabecera | La marca (vuelve al Resumen), dónde estás (`proyecto › sección`), **Ver portal**, **Buscar o ir a…** (<kbd>Ctrl</kbd> <kbd>K</kbd> / <kbd>⌘</kbd> <kbd>K</kbd>) y **⋯**. La cabecera es la barra de la ventana: arrástrala para moverla |
| Raíl | Un botón por cada proyecto de esta máquina, con sus iniciales. Otro proyecto se abre **en esta ventana**: la app arranca el servidor de ese proyecto, lleva la ventana a él y para el anterior. Un proyecto que no está en el disco sale apagado. **+** abre la pantalla de inicio |
| Secciones | Resumen, Tablero, Plan, Entrevistas, Equipo, Calidad, Librerías y Docs; después, bajo **Esta app**, Máquina, Guía y (solo en un checkout del kit) Kit dev. Al pasar por una ves su atajo |
| Zona central | La sección en la que estás |
| Panel de trabajos y barra de estado | Lo que corre ahora y los últimos trabajos, con su salida; la barra de estado enseña el primer trabajo en curso y la versión del kit |

El botón **⋯** abre el menú de la app debajo de sí mismo: **Proyectos…** (la pantalla de inicio, también
<kbd>Ctrl</kbd>/<kbd>⌘</kbd> <kbd>Shift</kbd> <kbd>O</kbd>), **Abrir en el navegador** (el portal de este proyecto) y
Salir. La ventana recuerda su tamaño y su sitio al cerrarla y vuelve ahí si ese sitio sigue estando en una pantalla.

Si abres `/desktop/` en un navegador verás «Esto es la app de escritorio» y un botón al portal: las secciones de la app
solo funcionan dentro de la app, con su token.

### El panel de trabajos

Cada comando que lanza un botón es un **trabajo**. El panel de abajo enseña una línea —el primer trabajo en curso, o el
último— con su estado (**En curso**, **Hecho**, **Falló**, **Parado**), su nombre y hace cuánto, y «+N» si hay más en
marcha. **Historial** despliega los seis últimos; elige uno para leer su salida, en vivo mientras corre. **Parar** sale
en los trabajos que son procesos lanzados por la app (un comando, una tarea de Kit dev) y para el comando con todo lo
que arrancó (agentes, npm, git). El trabajo que hace el propio servidor (una ejecución de la documentación, un
build, una wiki, la preparación del primer arranque) no tiene Parar ahí: una ejecución se cancela desde Plan y la
preparación desde su propio **Cancelar**.

Dentro de una sección, la tarjeta de un comando enseña lo mismo: un chip de estado, el error en palabras si falló y
una **Salida** plegada que se abre sola cuando algo falla.

### Moverse con el teclado

| Teclas | Va a |
|---|---|
| <kbd>Ctrl</kbd> <kbd>K</kbd> / <kbd>⌘</kbd> <kbd>K</kbd> | La paleta: una sección, otro proyecto, una acción o, en cuanto escribes, cualquier comando y cualquier capítulo de esta guía |
| <kbd>g</kbd> y después <kbd>s</kbd> <kbd>b</kbd> <kbd>a</kbd> <kbd>p</kbd> <kbd>i</kbd> <kbd>t</kbd> <kbd>q</kbd> <kbd>l</kbd> <kbd>d</kbd> | Resumen, Tablero, Decisiones, Plan, Entrevistas, Equipo, Calidad, Librerías, Docs |
| <kbd>g</kbd> y después <kbd>m</kbd> <kbd>h</kbd> <kbd>k</kbd> | Máquina, Guía, Kit dev (en un checkout del kit) |

La segunda letra tiene que llegar en segundo y medio desde la <kbd>g</kbd>. Los atajos no cuentan mientras escribes en
un campo o en un diálogo. En la paleta, <kbd>↑</kbd> <kbd>↓</kbd> se mueven, <kbd>Intro</kbd> va y <kbd>Esc</kbd>
cierra; la búsqueda no distingue tildes ni mayúsculas y tienen que estar todas las palabras. Un comando elegido ahí se
abre en su sección con su formulario listo.

### Claro, oscuro e idioma

La app sigue el tema claro u oscuro de tu sistema y cambia con él. Su idioma es el de Máquina › Idioma y modelos
(español o inglés), el mismo ajuste que usa el asistente de la terminal.

## La pantalla de inicio

Fuera de un proyecto —`camaron app` en cualquier otra carpeta, el **+** del raíl o **Proyectos…** en el menú— la app
pregunta una sola cosa: **¿Qué quieres documentar?**

### Elegir carpeta

**Elegir…** abre un selector de carpetas. Después la app mira la carpeta (`camaron projects --inspect`, que solo lee) y
te cuenta qué ha encontrado antes de tocar nada:

| Encuentra | Etiqueta | Qué hace Continuar |
|---|---|---|
| Un proyecto que ya tiene `cam-docs` (o elegiste el propio `cam-docs`) | Ya documentado | Lo registra y lo abre |
| Un repo git, o una carpeta dentro de uno | Código existente | Crea `cam-docs` junto al repo, en su carpeta padre, y nombra los repos hermanos que puedes sumar después |
| Una carpeta con repos | Código existente | Los lista y crea `cam-docs` en esa carpeta |
| Código que no está en git | Código existente | Nada: dice que el código no está en un repositorio y ofrece **Inicializar git aquí** (`git init` en la carpeta, o en cada carpeta de primer nivel con código; sin commits ni push) y vuelve a mirar |
| Una carpeta vacía | Proyecto nuevo | Crea un proyecto aún sin código: documentas el diseño primero |
| Tu carpeta personal o la raíz de un disco | — | La rechaza y explica por qué: `cam-docs` y el análisis de repos acabarían ahí |

Puedes cambiar el **Nombre del proyecto** (empieza con el de la carpeta) y pulsar **Continuar →**, que ejecuta
`camaron projects --adopt` y abre la ventana del proyecto.

### Unirme a la documentación de mi equipo

Pega la URL del repo **cam-docs** del equipo —el de la documentación, no el del código— y elige dónde dejarlo. La app
ejecuta `camaron join … --no-open` primero con tus propias credenciales de git. Si el servidor pide credenciales que
git no tiene, una URL https saca un campo para el token («GitLab: read_repository + write_repository · GitHub: repo»);
el token viaja solo en una variable de entorno y se guarda en el llavero del sistema cuando git consigue entrar con él.
Una URL SSH te pide que configures tu clave SSH. Los demás rechazos se dicen con palabras: sin acceso, no existe, sin
red, o una carpeta que ya tiene otro `cam-docs`.

### Recientes

Cada proyecto registrado en esta máquina, con **Abrir**, o «no está en el disco» si su carpeta ya no existe.

## El asistente de primer arranque

Un proyecto sin preparar abre en el asistente de primer arranque (`#/start`), a todo el ancho y sin raíl. El paso en el
que vas se guarda en el proyecto (`firstrun.json`) y lo comparte con el asistente de la terminal: si cierras la app a
medias, vuelves al mismo paso, en cualquiera de los dos. Mientras no termina, el Resumen ofrece **Seguir con la
preparación**.

| Paso | Qué pasa |
|---|---|
| Repos | Los repos que vas a documentar: marcados los que ya están en el proyecto, sin marcar los que encontró en la carpeta. Añade un repo de código por su URL (el nombre y la rama se rellenan). Hace falta al menos uno, salvo en una carpeta vacía |
| Herramientas | Lo que tiene y lo que le falta a esta máquina: las obligatorias marcadas y fijas, las recomendadas elegidas si faltan (basta un CLI de agente), más las herramientas fijadas del kit |
| Instalar | Empieza solo: instala lo elegido, guarda los componentes, escribe las plantillas, prepara el proyecto y sincroniza el plan, con barra de progreso y la salida en vivo. **Cancelar** para entre pasos. Si un repo no se pudo clonar, sale ahí mismo la tarjeta de Tokens con su servidor escrito |
| Stack | El stack de cada repo leído de sus manifiestos; el lápiz corrige uno mal detectado. Nunca bloquea |
| Arquitectura | Un primer borrador C4 hecho con análisis estático, sin IA: repos, bases de datos y brokers, relaciones. **Guardar borrador**, **Ver diagrama ↗**, **Guardar y mejorar con IA** (abre tu agente en una terminal sobre el modelo C4) o **Saltar** |
| Listo | Cierra el primer arranque con un commit de checkpoint. **Ir al siguiente paso** te deja en el Resumen |

Un proyecto nuevo en una **carpeta vacía** va Repos → Herramientas → Instalar → Listo (aún no hay nada que leer). Un
proyecto al que te **uniste** va Herramientas → Instalar → Listo, porque el resto ya lo decidió el equipo, y se salta
el asistente entero si esta máquina ya tiene todos los repos y herramientas.

## Resumen

El proyecto de un vistazo y lo único que toca hacer ahora (`#/summary`, <kbd>g</kbd> <kbd>s</kbd>).

<!-- go:summary -->
<!-- tour:summary -->

**Siguiente paso** es el mismo que propone el asistente de la terminal: primero una unidad a medias, después la
siguiente unidad lista, después las páginas que esperan revisión, y si no queda nada, «Todo al día: no queda nada que
pelar». Su botón depende de qué paso sea:

| El paso es | El botón |
|---|---|
| Una unidad que hace un agente | **Empezar con {agente}** o **Seguir con {agente}** (eliges el agente si tienes dos o más): abre el agente en su propia terminal, con esa unidad |
| Una entrevista, antes de que nadie eligiera cómo se hacen | **Elige cómo se hacen las entrevistas** → Entrevistas |
| Preparar la máquina (`setup`) | **Preparar la máquina** → Máquina |
| Las respuestas del equipo (`answers`) | **Recoger las respuestas** → Entrevistas |
| La CI (`ci`) | **Configurar la CI** → Equipo |
| La revisión humana (`confirm`) o páginas que esperan | **Revisar en el portal** |
| Construir el portal (`portal`), o no queda nada | **Leer la documentación** |
| Cualquier otra cosa | **Ver el plan** |

Sin ningún agente instalado, la tarjeta lo dice y ofrece **Preparar la máquina**. Debajo, un aviso si la última
comprobación encontró algo que le falta a esta máquina o un fichero del kit fuera de su sitio (**Verlo en Calidad**), y
tres cifras: el plan (hechas de total), las páginas por revisar (enlazan a la Revisión del portal) y los trabajos en
curso.

## Tablero

El Kanban del proyecto, guardado en `cam-docs/backlog/` y versionado con la documentación (`#/board`, <kbd>g</kbd>
<kbd>b</kbd>). La app escribe en él con su propio token. El [Tablero del portal](portal.md#tablero) enseña las mismas
tarjetas, con filtros.

<!-- go:board -->
<!-- tour:board -->

Un proyecto sin tablero enseña **Activar el tablero** (`camaron board init`). Con tablero:

- **Seis columnas**: Backlog, Listo, En curso, En revisión, Hecho, Bloqueado. Una tarjeta enseña su id, su tipo
  (Épica, Historia, Bug, Spike, Tarea), su prioridad, su título, su padre (`↳ WI-3`) y a quién está asignada.
- **Mueve una tarjeta** arrastrándola, o con el teclado: las flechas eligen tarjeta, <kbd>Espacio</kbd> la coge, las
  flechas la mueven, <kbd>Intro</kbd> o <kbd>Espacio</kbd> la sueltan, <kbd>Esc</kbd> la devuelve. <kbd>Intro</kbd> sobre
  una tarjeta que no has cogido la abre.
- **La puerta de salida.** Mover una tarjeta a En curso comprueba que sus dependencias estén hechas y que los ficheros
  que toca no choquen con trabajo ya en curso. Si algo la bloquea, la app nombra qué y pregunta si moverla de todos
  modos; decir que sí fuerza el movimiento (y el movimiento forzado se cuenta).
- **Abre una tarjeta** para leer su descripción, sus criterios de aceptación y su definición de hecho. Una historia
  lista sus tareas y tiene **Añadir tarea**. **Eliminar** la quita del tablero tras preguntar: su fichero pasa a
  `backlog/archive/tasks` (sus tareas se quedan).
- **Añadir** (arriba) crea un elemento: tipo, título, dentro de qué va (una tarea bajo una épica o una historia; una
  historia, un bug o un spike bajo una épica) y prioridad.

Escribir historias con sus subtareas y oleadas se hace en las [Historias del portal](portal.md#historias).

## Decisiones

Los ADR del proyecto, decididos con la evidencia delante y escritos, sin IA (`#/decisions`, <kbd>g</kbd>
<kbd>a</kbd>). Cada ADR es `docs/decisions/<NNNN>-<título>.md`; lo que su revisión va decidiendo se guarda en
`docs/.work/adr/<NNNN>.yaml`, que va a git. La guía de comandos tiene [todas las reglas](tutorial.md#-decisiones).

<!-- go:decisions -->

- **La lista**: cada ADR con su estado (En curso, En revisión, Propuesta, Aceptada, Sustituida, Rechazada…), filtros y
  búsqueda por título, número o repo. Un ADR que el kit no escribió aparece con su estado y no se reescribe.
- **Nuevo ADR**: un título, *nuevo* o *retroactivo* y, si quieres, el problema, los drivers, las restricciones, las
  opciones candidatas y el ADR al que sustituye. **Toca** elige los ficheros, grupos del mapa y páginas que afecta.
- **Candidatas**: las decisiones que el código ya tomó y que ningún ADR nombra (librerías de runtime, tecnologías del
  C4, ficheros de Docker Compose y Helm). **Crear ADR retro** abre el formulario ya relleno.
- **Evidencia**: el paquete de lo que el proyecto sabe de lo que toca el ADR (vecinos en el grafo del código, páginas
  que lo citan, ADR relacionados, commits, C4, librerías, preguntas abiertas). **Escribir sin IA** escribe con él el ADR
  propuesto.
- **Revisión**: parte por parte (aprobar, editar o aplazar cada sección y las páginas afectadas) y punto por punto
  (elegir una opción u *Otra*, con un motivo), más los asistentes. **Presentar** (<kbd>P</kbd>) enseña una parte por
  pantalla para una reunión: <kbd>←</kbd> <kbd>→</kbd> cambian de parte, <kbd>1</kbd>–<kbd>9</kbd> eligen,
  <kbd>E</kbd> edita, <kbd>D</kbd> aplaza, <kbd>A</kbd> acepta, <kbd>Esc</kbd> sale.
- **Aceptar** confirma el ADR con `x-owner: human` y *Decided by*; lo que aún no está decidido no se acepta, y la app
  dice qué punto o sección falta. **Rechazar** pide un motivo.

<!-- cmd:adr -->

## Plan

Ejecuta el plan de documentación y ve cada unidad (`#/plan`, <kbd>g</kbd> <kbd>p</kbd>). Qué es una unidad, en
[el plan y el harness](internals.md#el-plan-y-el-harness).

<!-- go:plan -->
<!-- tour:plan -->

Un proyecto sin plan ofrece **Crear el plan** (`camaron plan sync`). Si no, de arriba abajo:

**Ejecutar el plan.** **Ejecutar las listas** lanza una ejecución de la documentación: varias unidades a la vez
(**A la vez**, de 1 a 4, 2 por defecto), cada descubrimiento, ficha de repo y flujo en su propia copia de `cam-docs`,
que se fusiona al terminar. **Opciones** tiene las sesiones por agente (`claude=2,codex=1`), un máximo de unidades y si
incluir las entrevistas. **Piloto automático** hace en cambio una unidad tras otra, sin vigilancia. Los dos están
apagados mientras no haya ninguna unidad lista. Con una ejecución en marcha, la tarjeta enseña su avance y **Cancelar
la ejecución** (los agentes se paran, sus unidades vuelven a la cola y su trabajo se conserva); con el piloto en marcha,
**Parar el piloto**. Solo existe una ejecución a la vez, se lance desde la app o desde la terminal.

**Mantenerla al día.** **Empezar con {agente}** abre una sesión que actualiza la documentación con lo que cambió en el
código desde que se escribió.

**Las unidades.** Hechas de total, y cada unidad como tarjeta en un **Tablero** (Listas para empezar, En curso, Te
necesitan, Esperan a otras, Hechas), por **Fases** o en el **Lienzo** (más abajo). Colores: en curso ámbar, en pausa ámbar apagado, hecha verde,
bloqueada rojo, espera tu aprobación violeta, espera a otras con borde discontinuo. Al pulsar una tarjeta se abre su
detalle: fase, quién la hace, su repo, de qué depende, sus notas y, con su terminal abierta, qué está haciendo el agente
(la herramienta y el fichero de su último paso, o que te está esperando). El botón del detalle la mueve:

| La unidad | Botón |
|---|---|
| Espera aprobación | **Aprobar**: las siguientes pueden empezar |
| Bloqueada | **Reintentar**: vuelve a la cola |
| Hecha | **Rehacer**: se reabre para su agente (`camaron plan redo`) |
| Empezada, terminal cerrada (en pausa) | **Seguir** su conversación, o **Empezar de cero** |
| Lista | **Empezar** con el agente que elijas |
| Una entrevista antes de elegir el modo | **Cuestionario del equipo** o **En vivo, con un agente** |

**Ver su registro en el portal** abre la unidad en el Pipeline del portal.

**El lienzo.** La tercera vista, junto a Tablero y Fases: las unidades como un grafo con sus dependencias. Mientras
corre una ejecución (el piloto automático o **Ejecutar las listas**), cada unidad en la que trabaja un agente se abre en
su nodo como una **terminal de solo lectura** con lo que hace, línea a línea (✎ edita, ⌕ lee o busca, ▶ ejecuta, »
dice, ✕ falla), el agente, el tiempo que lleva y el coste. Su cabecera dice **hecha** solo cuando el plan la tiene
hecha: una cuyo agente terminó sin acabarla dice cómo la tiene el plan (por hacer, en pausa, bloqueada, espera tu
aprobación), y una que no pudo empezar dice por qué. Unos 4 segundos después de acabar vuelve a una tarjeta
compacta con su tiempo y su coste (**Ver terminal** la reabre); una que falla conserva su terminal. Si subes dentro de
una terminal, deja de seguir el final hasta que pulses **Ir al final**; **⤢** la maximiza y Escape vuelve al lienzo.
**Encajar** enmarca cada terminal abierta (todas las unidades si no hay ninguna), **Reordenar** devuelve todo el lienzo
a la disposición automática, y las posiciones que arrastres se conservan mientras la ventana de ese proyecto siga
abierta. Tab y las flechas se mueven entre nodos e Intro abre el detalle de la unidad. Sin elegir vista, el Plan pasa al
lienzo en cuanto hay una ejecución en marcha (ya al entrar, o lanzada desde el propio Plan; una unidad que empiezas a
mano en su propia terminal no cuenta) y se queda ahí, también al acabar, hasta que elijas otra. El lienzo lee el registro de la ejecución (el mismo que lee el portal) y sigue el tema claro u oscuro de la
app; parar sigue en la tarjeta **Ejecutar el plan**. Una ejecución parada desde fuera (su trabajo parado, su proceso
terminado) se ve acabada en unos segundos: sus terminales dejan de decir «en marcha», y una unidad que dejó a medias
dice cómo la tiene el plan, con su reloj parado en su última línea.

**Plan desde 0**, debajo de las unidades. Lo que ha costado el plan desde que empezó (o desde el último borrado), para todo el equipo: tiempo
de agente desatendido, tiempo con una persona delante, tiempo de calendario, tokens y dólares equivalentes de la API,
las unidades más caras y una tabla por fase. **Actualizar** recoge antes las sesiones de agente de esta máquina. Lo que
no se pudo medir o no tiene precio sale con su nombre, nunca como 0.

**Todos los comandos** tiene el resto de comandos del plan (`plan`, `wiki`, `pr`, `runs`), cada uno con su formulario.

**Empezar la documentación otra vez.** Para documentación escrita con un kit antiguo: **Rehacer** reabre cada unidad
terminada para que su agente la revise con el playbook de hoy (no borra nada); **Borrar y empezar de cero** etiqueta
`cam-docs` en git, borra las páginas generadas, el modelo C4, las wikis y el estado de las ejecuciones y empieza el plan
de nuevo, conservando las entrevistas, las páginas que una persona escribió o confirmó, el tablero y los comentarios de
revisión. Primero **Ver qué haría**; después un diálogo repite la lista.

<!-- cmd:docs -->

## Entrevistas

Cómo se hacen las entrevistas y cómo llegan las respuestas del equipo (`#/interviews`, <kbd>g</kbd> <kbd>i</kbd>).

<!-- go:interviews -->
<!-- tour:interviews -->

Hasta que alguien elige, la sección pregunta **¿Cómo hacéis las entrevistas?**: un **Cuestionario del equipo** (responde
el equipo y después un agente lo consolida) o **En vivo, con un agente**. Una vez elegido puedes cambiar
(**Pasar a en vivo** / **Pasar a cuestionario**). En modo cuestionario:

- el estado del cuestionario: preguntas, personas que han respondido y cuántas preguntas no tienen acuerdo;
- **Responder en el portal** abre la Entrevista del portal, donde cada persona responde;
- **Exportar el formulario** escribe un formulario HTML sin conexión (`camaron interview export`) y lo enseña en tu
  explorador de archivos;
- **Importar respuestas** elige los ficheros de respuestas que te mandaron (`camaron interview import`);
- **Cerrar la ronda** da por hecha la unidad de respuestas cuando alguien ha respondido.

Debajo, **Entrevistas con un agente** lista las unidades de entrevista con los mismos botones que en Plan.

## Equipo

El repo `cam-docs` del equipo y lo que llegó con él (`#/team`, <kbd>g</kbd> <kbd>t</kbd>).

<!-- go:team -->
<!-- tour:team -->

**Repo del equipo.** Pega su URL y **Guardar** (`camaron remote`). Con remoto, tres cifras —por enviar, por traer, sin
guardar— y **Compartir ahora** (un checkpoint, después tu trabajo rebasado sobre el del equipo y subido),
**Comprobar** (pregunta al remoto qué hay de nuevo) y **Compartir cada vez que se guarda el progreso**
(`camaron share --auto on|off`, solo en esta máquina). Un conflicto se deshace sin tocar nada; algo que parece un
secreto no se publica.

**Lo que llegó con el repo del equipo.** Los hooks, servidores MCP, ajustes, skills, ficheros y plugins de `cam-docs`
que no escribió el kit esperan aquí a que los apruebes en esta máquina: **Aprobar (n)** los lista y ejecuta
`camaron trust --yes`. Las aprobaciones viven en `~/.camarones/trust/`, nunca en el repo. **Hooks del método en Claude
Code** activa o quita los tres hooks del kit (`camaron hooks`).

**Plugins.** Los del kit (Gemini, Confluence, Notion) y los del equipo (`.camarones/plugins/`), con lo que aporta cada
uno, si ejecuta código o envía la documentación fuera, y su estado aquí. **Activar**/**Desactivar** solo afectan a esta
máquina.

**Todos los comandos** tiene board, checkpoint, ci, export, portal, removed y translated.

## Calidad

La salud del proyecto en un solo panel: esta máquina, la documentación y el código (`#/quality`, <kbd>g</kbd>
<kbd>q</kbd>). Lee `camaron health`, que no usa IA.

<!-- go:quality -->
<!-- tour:quality -->

Arriba, un veredicto («Páginas desactualizadas: 3 · Críticas o altas: 2», o «Todo lo comprobado está en orden») y
**Comprobar todo** (`camaron health --refresh`). Después tres áreas, cada una con su estado, dos cifras y **Abrir**:

| Área | Estados | Cifras | Qué enseña Abrir |
|---|---|---|---|
| Máquina | Lista · Revisar · Riesgo | herramientas, faltan | **Requisitos y herramientas**: primero lo que falta, cada cosa con **Instalar** (`camaron doctor --install …`), **Instalar las fijadas** (`camaron setup`), **Volver a comprobar**, y ficheros del kit fuera de su sitio con **Reparar**. **Ficheros del kit**: **Reparar** |
| Documentación | Al día · Revisar · Riesgo | páginas desactualizadas, por revisar | **Páginas desactualizadas** (cada una con **Sigue valiendo**, o **Añadir una unidad que las actualice**), **Preguntas de control (IA)** (confirmar preguntas de oro, hacerlas, o **Proponer preguntas con {agente}**), **Contexto de cada sesión** (los tokens que carga cada sesión de agente frente al presupuesto), **Páginas por revisar** (portal), **Bloques generados** (actualizarlos) y **Con y sin cam-docs (IA)** (la misma pregunta dos veces) |
| Código | Sano · Revisar · Riesgo | librerías, críticas o altas | **Repos**: por repo su puerta de calidad de SonarQube (Aprobado, Aviso, Suspendido) o si usa Sonar, la cobertura (la de Sonar, si no la de sus informes locales) con su fecha, las vulnerabilidades por gravedad y la deuda técnica, y **Ver completo →** (la página del repo en el portal). **Librerías** → la sección Librerías |

Un repo que usa SonarQube sin token guardado enseña **Conectar SonarQube**, que abre Máquina › Tokens con el servidor
escrito. Una cifra que no se pudo leer sale como «—», nunca como 0. Debajo del panel: **Ver los KPIs** (portal) y
**Todos los comandos** (los de análisis y comprobación: check, graph, pages, schemas, radar, history, kpis, stats…).

<!-- cmd:health -->
<!-- cmd:check -->

## Librerías

Las dependencias de cada repo, leídas de sus manifiestos y lockfiles sin IA (`#/libs`, <kbd>g</kbd> <kbd>l</kbd>).

<!-- go:libs -->
<!-- tour:libs -->

- **Buscar vulnerabilidades** ejecuta `camaron inventory --cves` (OSV-Scanner con su base de datos sin conexión, que se
  descarga una vez); **Releer del código** ejecuta `camaron inventory`. El escaneo va repo a repo —en el que está
  buceando, cuántos lleva, una barra y **Parar**— y acaba con un tick con lo que encontró («5 repos revisados · 3
  librerías con avisos conocidos», y los repos que no pudo escanear). Si sales de Librerías y vuelves mientras corre,
  retoma su progreso. Sin OSV-Scanner en la máquina, las librerías se releen sin vulnerabilidades y lo dice.
- Filtros: búsqueda, categoría, servicio, ámbito y **Solo vulnerables**. La tabla es librería × servicio, las peores
  primero, con un chip cuando dos repos usan versiones distintas. Bajo cada librería, los repos donde está, primero
  donde tiene avisos y en rojo (tres nombres y luego «+N más»); su columna se queda fija al desplazar la tabla.
- Abre una librería: **Por qué está aquí** (qué repo la declara, en qué manifiesto, con qué rango y ámbito) y **Por qué
  está marcada** (cada aviso con su gravedad, versiones afectadas, fechas, CWE, texto completo y enlaces).
- **Actualizar** propone la versión que corrige todos sus avisos, pregunta una vez y ejecuta `camaron bump`: una rama
  nueva `camaron/bump-<librería>-<versión>` en ese repo, sin commit ni push. Un repo con cambios sin commit no se toca.
  En un módulo Maven que hereda su versión cambia donde el repo la escribe: la propiedad o el `<version>` de su pom
  padre o de un BOM del mismo repo. Si la fija algo de fuera del repo, no la toca y dice quién la fija.

## Docs

Leer es cosa del portal; esta sección lo abre y hace el trabajo que él no puede (`#/docs`, <kbd>g</kbd> <kbd>d</kbd>).

<!-- go:docs -->
<!-- tour:docs -->

- **Leer la documentación**, **Revisar borradores** y **Buscar o preguntar** abren el portal en tu navegador.
- **Construir el explorador C4** construye el mapa interactivo de LikeC4 que el portal enseña en Arquitectura; **Ver**
  lo abre.
- **Un bloque por repo**: **Generar la wiki** escribe la wiki OpenWiki de ese repo. Si el repo no estaba elegido para
  tener wiki, lo elige; si aún no tiene brief, antes escribe uno inicial sin IA. Está desactivado, con el motivo, si el
  repo no está clonado, no hay ningún motor de wiki instalado o se está generando la wiki de otro repo (una a la vez).
  Cuando la wiki tiene páginas: **Ver** y **Grafo del wiki · {repo}** (construir su grafo).
- **Preguntar con IA** responde una pregunta solo con la documentación, a través del agente de esta máquina, y enlaza
  sus fuentes en el portal. Espera hasta 90 segundos; `ask.ai: false` en `workspace.yaml` lo apaga y `ask.model` elige
  el modelo.

<!-- portal:#/docs -->

## Máquina

Esta máquina y la preparación de este proyecto (`#/machine`, <kbd>g</kbd> <kbd>m</kbd>).

<!-- go:machine -->
<!-- tour:machine -->

| Tarjeta | Qué hace |
|---|---|
| Guía y recorrido | Abre esta guía, o el recorrido por la app |
| Preparar esta máquina | **Ejecutar setup** (`camaron setup`): herramientas, repos, conexión de los agentes, con barra de progreso |
| Idioma y modelos | El idioma de las sesiones de IA, el modelo de Claude Code y el de Codex (la lista del propio Codex, u **Otro…** para escribirlo): los que usa una sesión cuando el enrutado no da ninguno para su unidad. Cada cambio es un `camaron config set` |
| Tokens de GitLab, GitHub y SonarQube | Los servidores guardados con **Probar** y **Borrar**; un formulario (servidor, tipo, token) cuyo **Comprobar y guardar** prueba antes el token contra el servidor (**Guardarlo igualmente** si insistes). Los tokens viven en el llavero del sistema, nunca en el proyecto ni en una línea de comandos. SonarQube solo por https (http solo en localhost) |
| Repos y plan | Cada repo, clonado o no, con su stack (edítalo, o **Volver al detectado**); **Clonar o actualizar los repos** (`sync`), **Detectar repos en la carpeta** (`detect`) y el perfil del plan, rápido o completo |
| El kit | **Actualizar el kit** (`self-update`, solo con la instalación global) y después **Reiniciar la app con la versión nueva**; **Reparar los archivos del kit** (`repair`) |
| Todos los comandos | down, upgrade, version; con cuidado: migrate, unlink |
| Desinstalar este proyecto | Primero **Ver qué borraría**; después **Desinstalar** abre un diálogo que repite la lista. Opcional: también los ajustes, tokens y cachés de esta máquina, y sin copia de seguridad. Por defecto se guarda una copia `.zip` de `cam-docs` en la carpeta temporal del sistema, y un tablero que ya existía se conserva (copiado junto a los repos) |

La dirección `#/machine?host=<servidor>&kind=sonarqube` (o `gitlab`, `github`) abre el formulario de Tokens relleno.

<!-- cmd:setup -->

## Guía

Esta guía (`#/guide`, <kbd>g</kbd> <kbd>h</kbd>): cómo se usa Camarón, esta app, el portal, cómo funciona por dentro y
la referencia de comandos, en el idioma de la máquina, sacada del kit instalado en ella. La búsqueda mira en todas las
guías; los botones bajo un párrafo te llevan a lo que describe, y **Enséñamelo** empieza un recorrido que señala los
controles de verdad. Las mismas guías se copian en `docs/guides/` de cada proyecto, así que también las leen el portal y
los agentes.

## Todos los comandos

Plan, Equipo, Calidad y Máquina terminan con **Todos los comandos**, plegado: los comandos de esa zona que ninguna
tarjeta ejecuta ya, cada uno con un formulario sacado del propio parser de la CLI (`camaron catalog`). Un flag es una
casilla, una elección un desplegable, un número un campo numérico; `--yes` y `--json` nunca son campos. Los comandos que
borran o mueven datos van al final, bajo **Con cuidado: borran o mueven datos**, con un **Ejecutar** en rojo; ellos y
cualquier comando con `--yes` preguntan antes en un diálogo, salvo que el formulario pida solo una prueba en seco. El
resultado es la salida del propio comando, en la tarjeta y en el panel de trabajos.

La paleta llega a todos: un comando con tarjeta abre su sección; los demás abren su tarjeta en **Todos los comandos**,
ya a la vista.

## Kit dev

Solo en un checkout del kit (`uv run --script .camarones/camarones.py app` desde el repositorio del kit), no en la
instalación global. Es el banco para cambiar el kit:

- **Sandbox**: el proyecto Spring PetClinic en `$CAMARONES_SANDBOX` (por defecto `~/projects/camarones-sandbox`). **Qué
  dejó el kit** lista los rastros tras una desinstalación, **Abrir el asistente en él**, **Reiniciar el sandbox**
  (pregunta antes) y una línea para ejecutar sobre él cualquier comando del catálogo.
- **Tests**: `pytest` con un filtro `-k` y rutas bajo `tests/`, con el recuento.
- **Builds**: `npm ci`, `npm test` y `npm run build` del portal y de esta app, **¿Coinciden los builds?** (los builds
  commiteados frente al repo) y los tests del proceso principal (`node --test`).

## Cuando algo falla

| Ves | Qué hacer |
|---|---|
| `the desktop app needs Node.js >= 22` | Instala Node 22 (`camaron doctor --install node`) y vuelve a lanzar `camaron app` |
| La pantalla de inicio en vez de tu proyecto | Estabas fuera de la carpeta del proyecto: ábrelo desde **Recientes** o con **Elegir carpeta** |
| «Este código no está en un repositorio git» | **Inicializar git aquí** y después Continuar |
| «Aquí no puedo crear el proyecto» | Elegiste tu carpeta personal o la raíz de un disco: elige la carpeta que contiene tus repos, o una vacía |
| «No he podido arrancar el servidor del proyecto» | El cuadro trae el error del servidor; `camaron doctor` en esa carpeta suele decir qué falta |
| En el portal del navegador no está el botón que esperabas | Es a propósito: el portal del navegador no ejecuta nada en tu máquina. Hazlo aquí |
| Quieres que vuelva a descargar Electron | Borra `~/.camarones/desktop` y lanza `camaron app` |

En Linux con los *user namespaces* restringidos (Ubuntu 24.04 y posteriores) el kit abre la app con `--no-sandbox`;
sus ventanas solo cargan el servidor local de tu proyecto.
