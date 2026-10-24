# Campo

`co-input`: campo de texto de 2.9rem de alto, borde `color-rule`, `radius-campo`, fondo `color-canvas-elevated` y placeholder en `color-ink-dim`. Va en fila con su botón, que salta a la línea de abajo cuando no cabe.

- **Cuándo**: correos y textos cortos (entrar, dar acceso a alguien).
- **Qué pones tú**: un `<label>` (visible, o `sr-only` si el contexto lo dice), el `type` correcto (`email`) y su `autocomplete`, y un placeholder de ejemplo real («tu@empresa.com»), nunca la instrucción.
- **Errores**: debajo del campo, con `co-error` y `aria-describedby`.
