---
type: guide
title: Usar Camarón
description: Cómo se usa Camarón en el día a día — instalarlo, el primer arranque, unirte a un equipo, documentar unidad a unidad, revisar, compartir, el tablero, la salud, mantener la documentación al día y empezar de nuevo — primero en la app de escritorio y después con el comando que hace lo mismo.
tags: [onboarding, workflow]
x-owner: human
---
# Usar Camarón

> **TL;DR:** Instala el kit, ejecuta `camaron app` y elige la carpeta con tus repos. La primera pasada no necesita IA.
> Después deja que tu agente documente una unidad cada vez (o varias a la vez), revisa en el portal lo que escribió,
> confirma lo que está bien y compártelo con el equipo. Cuando cambia el código, el kit te dice qué páginas se quedaron
> atrás.

## La idea en un minuto

Camarón es un **cerebro del proyecto**: un único sitio versionado, `cam-docs/`, donde el código, la arquitectura, el
dominio y las decisiones de un proyecto con varios repos quedan explicados para personas y para agentes de IA.

1. **Instalar ya da valor, sin IA.** El kit detecta tus repos y escribe, con análisis estático, la página de inicio del
   proyecto, una página por repo (endpoints, datos, estados, mensajes, variables de entorno), las librerías y sus
   vulnerabilidades conocidas, un primer borrador C4 y el plan.
2. **Después la IA lo completa**, una **unidad** de trabajo por sesión: el descubrimiento de cada repo, las entrevistas,
   la arquitectura, el dominio, los datos, los flujos, las decisiones, las traducciones.
3. **Todo lo que escribe la IA se puede revisar**: es un borrador hasta que una persona lo confirma, lleva el código del
   que sale (`x-sources`) y pasa a sospechoso en cuanto ese código cambia.

Tres formas de entrar, los mismos comandos debajo: la **app de escritorio** (`camaron app`) para operar, el **portal**
para leer y revisar, y la **terminal** (`camaron`, el asistente, o cualquier comando) para todo, scripts y CI incluidos.

<!-- tour:app -->

## Primer arranque

**Requisitos:** git y Node.js 22 o superior; `uv` (lo instala el lanzador); Claude Code o Codex con sesión iniciada
para las sesiones con IA (también sirven OpenCode y Gemini CLI). Docker es opcional.

**Instala el kit una vez por máquina**, en una línea y sin clonar nada:

```sh
curl -fsSL https://raw.githubusercontent.com/iandelu/camarones-documenter/main/install-global.sh | sh
```

En Windows, la línea de PowerShell del README hace lo mismo. El comando `camaron` queda en tu PATH.

**Abre la app** en la carpeta que agrupa tus repos, o en cualquier otra:

```sh
camaron app
```

La primera vez descarga Electron (unos 100 MB) en `~/.camarones/desktop`. **Elegir carpeta**, mira lo que ha encontrado,
**Continuar** y sigue el asistente de primer arranque: repos, herramientas, instalar, stack, un primer borrador de
arquitectura y listo. Terminas en el **Resumen**, con el siguiente paso. ¿Prefieres la terminal? `camaron` en esa
carpeta abre los mismos pasos en el asistente; puedes cambiar de uno a otro a medias.

<!-- go:summary -->

## Unirte a tu equipo

Si tu equipo ya tiene un repo `cam-docs`: en la pantalla de inicio de la app, **Unirme a la documentación de mi equipo**
y pega su URL (la del repo de la documentación, no la del código). Desde una terminal: `camaron join <url>`. El kit lo
clona, o reutiliza la copia que ya tienes, y solo prepara tu máquina: el equipo ya eligió los repos, el stack, la
arquitectura y el plan, y las sesiones siguen donde se quedaron.

Lo que llegó con el repo del equipo y ejecuta código o guía a los agentes (hooks, servidores MCP, ajustes, skills,
plugins) espera a que lo apruebes en tu máquina: **Equipo › Lo que llegó con el repo del equipo**, o `camaron trust`.

<!-- go:team -->

## Un día normal

1. **Mira el siguiente paso**: el **Resumen** de la app, o `camaron plan next`.
2. **Haz una unidad con tu agente**: **Empezar con Claude Code** (o Codex) la abre en su propia terminal, solo con esa
   unidad. Cierra la terminal cuando quieras: la unidad queda en pausa y **Seguir** retoma la conversación.
3. **O haz varias a la vez**: **Plan › Ejecutar las listas** (`camaron run --parallel 2`), cada unidad en su propia
   copia de `cam-docs`, que se fusiona al terminar. El **Piloto automático** (`camaron autopilot`) va una a una, sin
   vigilancia.
4. **Lee y revisa** lo que escribió: **Ver portal** y después Revisión.
5. **Comparte**: **Equipo › Compartir ahora** o `camaron share`.

Cada unidad termina con un commit local en `cam-docs` y una nota de relevo, así que la siguiente sesión —tuya o de un
compañero— sabe qué se comprobó, qué no y qué viene después.

<!-- go:plan -->
<!-- tour:plan -->

## Revisar y confirmar

Los borradores de la IA son útiles pero no están verificados. En el portal:

- **Revisión** lista lo que espera a una persona: borradores, páginas por reconfirmar, revisiones que espera un agente.
  Marca varias y **Confirmar las n**.
- En una página, **Confirmar como correcta** la firma con tu nombre: desde ese momento los agentes la tratan como la
  verdad.
- **Pedir un cambio** deja un comentario para la siguiente sesión de IA (o crea un elemento del tablero con la página
  enlazada).
- **Editar** la cambia tú; una página confirmada que editas hay que reconfirmarla.

Desde una terminal: `camaron confirm <página> --by <nombre>`, `camaron feedback <página> "<qué está mal>" --by <nombre>`,
`camaron status`.

<!-- portal:#/review -->

## Compartir con el equipo

`cam-docs` es un repo git normal. Por defecto los checkpoints se quedan en local y publicar es un paso que das tú:
**Equipo › Compartir ahora**, **Plan › Sincronizar** en el portal, o `camaron share` (un checkpoint, el trabajo del
equipo rebasado dentro y el tuyo subido). **Compartir cada vez que se guarda el progreso** (`camaron share --auto on`)
lo hace tras cada checkpoint, solo en esta máquina. Un conflicto se deshace sin tocar nada; algo que parece un secreto
nunca se sube.

¿Aún no hay repo del equipo? Pega su URL en **Equipo › Repo del equipo** (`camaron remote <url>`); tu primer compartir
lo publica.

## El tablero y las historias

El tablero vive en `cam-docs/backlog/`, junto a la documentación, y Backlog.md puede leerlo. Actívalo con **Tablero ›
Activar el tablero** (`camaron board init`).

- **Escribe una historia** en las **Historias** del portal: *Como / quiero / para*, los ficheros y páginas que toca, un
  veredicto INVEST y subtareas en **oleadas** que nunca tocan los mismos ficheros. No se guarda nada hasta que lo
  apruebas.
- **Mueve tarjetas** en el Tablero de la app o en el del portal. Pasar a En curso comprueba antes dependencias y
  choques.
- **Lo que puede empezar ya**, para un agente o una persona: `camaron board next --n 3`; el trabajo abierto en oleadas:
  `camaron board waves`.

<!-- go:board -->
<!-- portal:#/stories -->

## Salud, librerías y vulnerabilidades

**Calidad**, en la app, es la salud del proyecto sin IA —máquina, documentación y código— con un veredicto, un estado
por área y una fila por repo (puerta de calidad de SonarQube, cobertura, vulnerabilidades, deuda). **Comprobar todo** la
recalcula (`camaron health --refresh`). Una herramienta que falta tiene ahí su botón **Instalar**.

**Librerías** lista cada dependencia por repo. **Buscar vulnerabilidades** las compara con la base de datos sin conexión
de OSV (`camaron inventory --cves`; nada sale de tu máquina). El **Actualizar** de una librería marcada propone la
versión que lo corrige y crea una rama en ese repo (`camaron bump`), sin commit ni push; en un módulo Maven cambia el
pom padre del mismo repo, que es donde está la versión.

SonarQube: guarda un token en **Máquina › Tokens** y la comprobación de salud lee la puerta de calidad, la cobertura y
los problemas de cada repo.

<!-- go:quality -->
<!-- go:libs -->

## Mantener la documentación al día

Cuando el código se mueve, la documentación lo sigue:

- `camaron changes` lista lo que cambió en los repos desde que se escribió la documentación; **Plan › Mantenerla al
  día** abre una sesión que actualiza las páginas afectadas.
- **Calidad › Páginas desactualizadas** (`camaron fresh`) lista las páginas cuyo código citado cambió o desapareció;
  **Sigue valiendo** da una por buena y **Añadir una unidad que las actualice** pone el trabajo en cola.
- En CI, `camaron ci` escribe un job por repo de servicio que comenta en cada pull request qué páginas deja
  desactualizadas, sin IA; `camaron pr propose <url>` deja que un agente proponga los cambios de la documentación en
  una PR de `cam-docs`.
- `camaron check` es la puerta: enlaces rotos, diagramas que no se dibujan, secretos, estructura.

## Costes y KPIs

- **Plan › Plan desde 0** (`camaron plan cost`): tokens, horas y dólares equivalentes de la API que se llevó el plan,
  para todo el equipo, por fase y por unidad.
- **Calidad › KPIs** en el portal (`camaron kpis`): proporción confirmada, páginas desactualizadas, búsquedas sin
  respuesta, coste de IA por mes y las preguntas que nadie encontró; un clic convierte cada una en pregunta abierta
  para la siguiente entrevista.
- **Preguntas de oro** (`camaron eval`): preguntas que la documentación tiene que poder responder, aprobadas por una
  persona, que se le hacen a un agente que solo puede leer la documentación. **Con y sin cam-docs** (`camaron ab`) hace
  la misma pregunta dos veces para enseñar lo que ahorra la documentación.

<!-- portal:#/kpis -->

## Empezar de nuevo y desinstalar

- **Documentación de un kit antiguo:** **Plan › Empezar la documentación otra vez**. **Rehacer** reabre cada unidad
  terminada para revisarla (sin borrar nada); **Borrar y empezar de cero** etiqueta `cam-docs` en git, borra lo generado
  y vuelve a empezar el plan, conservando las entrevistas, las páginas confirmadas y el tablero
  (`camaron docs reset --redo | --wipe`).
- **Desinstalar un proyecto:** **Máquina › Desinstalar este proyecto**, primero **Ver qué borraría**. Para el portal,
  guarda `cam-docs` en un `.zip` en la carpeta temporal del sistema, quita lo que el kit añadió a cada repo y a la
  carpeta del workspace, y borra `cam-docs`. Los repos quedan exactamente como en su último commit
  (`camaron uninstall`).
- **Actualizar el kit:** **Máquina › Actualizar el kit** (`camaron self-update`) actualiza a la vez todos los proyectos
  de esta máquina y reinicia la app.

<!-- go:machine -->

## Cuando algo falla

| Síntoma | Lo primero que probar |
|---|---|
| Falta una herramienta o tiene otra versión | **Calidad › Requisitos y herramientas**, o `camaron doctor` |
| Alguien editó o borró un fichero o un enlace del kit | **Máquina › Reparar los archivos del kit**, o `camaron repair` |
| Un repo privado no se clona | Guarda un token en **Máquina › Tokens** y **Clonar o actualizar los repos** |
| Una sesión de agente dejó una unidad a medias | **Plan**, abre la unidad y **Seguir** (o **Empezar de cero**) |
| Una unidad de una ejecución queda bloqueada al fusionar | La resuelve su unidad `integrate:<unidad>`; o **Reintentar** |
| El portal no enseña un botón que esperabas | No ejecuta nada en tu máquina: hazlo en la app |

La [guía de la app](app.md#cuando-algo-falla) tiene los mensajes propios de la app.
