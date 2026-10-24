# Aviso

`co-aviso` es un mensaje neutro dentro de un bloque: texto `color-ink-soft` sobre `color-canvas-elevated`, borde `color-rule` y `radius-campo`. `co-error` es lo mismo con el borde teñido de coral. Los enlaces dentro van en `color-acento-texto`, subrayados.

- **Cuándo**: `co-aviso` cuando el producto dice que no o explica algo (un rechazo del servidor, «uno de tus asientos es tuyo»); `co-error` cuando algo ha fallado de verdad.
- **Qué pones tú**: qué ha pasado y qué hacer, en una o dos frases, con la salida escrita (un correo, un botón de reintento). Un rechazo del servidor se enseña con su frase tal cual.
- **Con `role`**: `role="alert"` para los fallos, `role="status"` para la confirmación de una acción.
- **No**: «Ha ocurrido un error» sin más; un 5xx dicho como «no puedes».
