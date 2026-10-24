# Cofundo — guía de marca

Cofundo vende un producto concreto —el **Cerebro de ventas**: metodología de ventas destilada de contenido público de formadores, dentro del Claude o el ChatGPT de quien lo usa, siempre citada y enlazada— y, aparte, cofundación y CTO as a service. La web es calmada, tipográfica y clara sobre lo que hay y lo que no. Construye sobre estas reglas; donde algo choque con ellas, ganan ellas.

## Las tres reglas legales

No son preferencias de diseño: vienen del backend y de un abogado.

- **El nombre de un creador no es marca sin acuerdo firmado.** Se cita a un formador como *fuente* de una técnica concreta; nunca se usa su nombre, su cara o su metodología como reclamo, título, titular o imagen de producto. Lo decide el dato `puede_usar_marca` del catálogo, que hoy es `false` para todos. Tampoco nombres de metodologías ni de terceros sin acuerdo (Sandler, MEDDPICC, Reforge, Y Combinator…). En datos estructurados (JSON-LD) es peor que en la página, no mejor.
- **El guion literal de un creador no se muestra nunca.** Una técnica es un método; sus palabras exactas son lo único con copyright.
- **La interfaz no habla con la base de datos.** Lo que se pinta viene de los endpoints del backend.

## Voz y copy

- **Español primero, inglés después, y el inglés no es una traducción literal**: se traduce el argumento, no la frase. Toda cadena de interfaz existe en los dos idiomas; las emulaciones de Claude/ChatGPT dicen lo que el usuario ve en su pantalla.
- **Tuteo**, frases cortas, verbos concretos. Los botones dicen lo que pasa al pulsarlos: «Ver el precio», «Darle asiento», «Enviarme otro correo». Nunca «Enviar» a secas.
- **Nada de copia sin salida.** «No hay datos», «Sin resultados», «Ha ocurrido un error», «Algo ha salido mal» están prohibidas. Y la salida no es un sinónimo: escribe qué hacer, o por qué no hay nada que hacer. Ejemplo real: *«No quedan asientos libres. Para que entre alguien más, cede uno de los que están en uso o da de baja a quien ya no lo necesite.»*
- **No se promete lo que no se cumple.** Nada de «el minuto exacto» (no hay marcas de tiempo), ni «todas con el enlace» (no todas lo traen), ni «no guardamos tus consultas». Las cifras salen de datos reales, nunca a mano: *«323 técnicas, 230 con enlace al original.»*
- **Un 5xx no es «no puedes», es «no lo sabemos».** Un rechazo del servidor se enseña tal cual; un fallo nuestro se dice como fallo nuestro.
- **El estado de un producto es un dato** («Disponible», «En beta»), nunca una frase escrita en una plantilla.
- Sin emoji decorativos. Las flechas son el carácter `→` dentro de un `<span aria-hidden>`.

## Color

- **Lienzo `color-canvas`** (off-white cálido) en todo; **`color-canvas-elevated`** para lo que va encima. Nunca blanco puro como fondo de página.
- **Texto en tres pesos, siempre los mismos**: `color-ink` titulares, `color-ink-soft` cuerpo, `color-ink-dim` meta y eyebrows. Los tres pasan 4,5:1 sobre el lienzo.
- **El acento es alto contraste, no un color**: `color-accent` (negro) para el botón principal y las secciones oscuras.
- **El aurora** (`color-aurora-cyan`, `-violet`, `-pink`, `-coral`, `-amber`) es el color de la marca y **solo es fondo**: el degradado `aurora-bg` del hero, `aurora-bg-soft` en secciones secundarias, tintes, subrayados. **Nunca texto**: dan 2,2:1. Para un violeta que se lee, `color-acento-texto` (6,79:1).
- **Sobre el aurora, el gris más claro es `color-ink-soft`**: el degradado cambia de luminancia y `color-ink-dim` se pierde sobre la zona coral.
- **Estados** (`color-estado-bien`, `-aviso`, `-mal`): solo en la consola y siempre con su palabra, nunca color solo.
- Bordes: un solo peso, `color-rule`, 1px.
- Base neutra y color con cuentagotas. Nada de gradientes brillantes de 2010, SaaS gris plano ni sombras pesadas.

## Tipografía

- **Big Shoulders 600** (`impact`) es *la* voz: titulares, en los escalones `t-display-xl`, `t-display-lg`, `t-display-md` y `t-h1`. Cuanto más grande, más cerrado el interlineado, más negativo el tracking y más estrecha la medida: cada escalón ya lo trae; no compongas tamaño, interlineado y medida a mano.
- **Inter** (`sans`) para todo lo demás: `t-lede`, `t-body` (17px), `body-sm`, `meta`, `eyebrow`.
- **Bricolage Grotesque 500** (`display`) solo para la wordmark «cofundo».
- **Titular a dos tonos**: la primera mitad en `color-ink`, la segunda en `t-eco` (`color-ink-dim`). *«Tu equipo ya tiene IA. / Sigue sin saber qué decir.»*
- Encima de cada titular de sección, un `eyebrow` en mayúsculas.
- Al lado de un `t-display-xl` solo cabe **una** cosa más: un lede corto o los CTAs, no las dos.
- **La medida va con la fuente**: si pones `max-width` en `ch`, declara la familia y el tamaño en ese mismo elemento.
- Cargar: `https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@500;600;700&family=Bricolage+Grotesque:wght@500&family=Inter:wght@400;500;600&display=swap`.

## Espacio y maquetación

- Las secciones respiran: padding vertical `section-pad-y`, nunca a mano. Variantes de sección: lienzo, `aurora-bg-soft`, oscura (`color-accent` con texto blanco) y `aurora-bg`.
- Anchos: `container-max` por defecto; **la prosa nunca pasa de `container-narrow`**.
- El hero se acota con `clamp(34rem, 100svh, 54rem)`. **`svh`, nunca `vh`**: `vh` cuenta la barra del navegador móvil y corta el contenido al cargar.
- Breakpoint principal 899px: el menú pasa a pantalla completa y las rejillas de dos columnas (puertas, escaparate) a una. `co-cohort` lo hace a 720px.
- Rejillas y `gap`, no márgenes sueltos.

## Formas, bordes y sombras

- Tarjetas y bloques: `radius-tarjeta`, borde `color-rule`, fondo `color-canvas-elevated`. Botones y chips: siempre píldora (`radius-pildora`). Campos y avisos: `radius-campo`.
- La jerarquía se hace con espacio, no con líneas ni sombras. La sombra se reserva para lo que flota: el modal (`sombra-modal`), el hover de una tarjeta (`sombra-hover`, junto a subir 2px) y los marcos de captura.
- La consola (`/admin`) puede divergir en tres cosas y nada más: densidad, radio (`consola-radio-*`) y separación de superficies. Si no se reconoce como el mismo producto, se ha tocado algo que no tocaba.

## Movimiento

- **La animación sigue al scroll; no se lo queda.** Nada de secuestrar el scroll: sin pin, sin librerías de smooth-scroll, sin traducir la rueda a progreso.
- **Las entradas se disparan una vez** y no se repiten al subir. **El indicador de posición sí es continuo y reversible.** En recorridos largos, da un indicador de dónde está el usuario.
- Solo `transform` y `opacity`. Curva `cubic-bezier(0.16, 1, 0.3, 1)` (salida suave); 200ms para hover y foco, 400ms para cambios de estado, 800ms el máximo.
- **Nada invisible esperando a JavaScript**: el contenido se ve sin JS. `prefers-reduced-motion` se respeta siempre.

## Componentes

Son clases CSS (`components/bundle.css`), no una librería: cada uno se pinta con su marcado. `co-btn` (y `--ghost`, `--sm`), `co-chip`, `co-card`, `co-cohort`, `co-puerta`, `surface`, `aurora-bg`, `co-golpe`, `co-aviso` / `co-error`, `co-input`, `co-esqueleto`, `co-meta` y los escalones `t-*`. Cada uno tiene su ficha.

Los estados que **no** se improvisan en pantallas de producto:

- **Vacío con explicación.** «He pagado pero aún no tengo acceso» merece texto escrito, no un panel gris.
- **Bloqueo con salida.** Si algo no se puede hacer, la pantalla se adelanta y ofrece qué sí se puede, en vez de dejar chocar al usuario con el error.
- **Editar, no borrar y recrear.** Ceder un asiento es cambiar el correo en una operación; «quitar» + «añadir» abre un hueco.
- **Cargando = esqueleto** con la forma de lo que viene (`co-esqueleto`), no un spinner sobre una pantalla vacía.
- **Lo destructivo va aparte y al final**, y en un modal nativo (`<dialog>`) que dice a quién y qué pasa; nunca «¿estás seguro?» sin decir de qué.

## Iconografía y marca

- **Esta es la identidad de Cofundo en pantalla y la que manda.** Los documentos Word de consultoría usan otra (navy con punto teal) que no se mezcla con esta: no la traigas a la web ni a nada que salga de este sistema.
- **No hay logotipo en fichero.** La marca es tipográfica: la wordmark «cofundo» en minúsculas (`wordmark`) y, al encoger el header, el monograma «c». El favicon es esa «c» en `color-canvas` sobre `color-ink`. No dibujes ni reconstruyas otro logo.
- **No hay sistema de iconos.** Glifos tipográficos (`→`), emoji solo en las banderas del selector de idioma. Si una pantalla necesita iconos, es una decisión que se pide, no se improvisa.
- Las marcas de terceros (Claude, ChatGPT, Gemini) solo para decir dónde funciona el producto, nunca como reclamo.
