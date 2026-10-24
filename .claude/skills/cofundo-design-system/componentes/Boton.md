# Boton

`co-btn`: la acción principal, en píldora negra (`color-accent`, texto blanco); `co-btn--ghost` para la acción secundaria y `co-btn--sm` para la versión compacta.

- **Cuándo**: una acción principal por bloque (`co-btn`), a lo sumo una secundaria a su lado (`co-btn--ghost`). Nunca dos botones negros juntos.
- **Qué pones tú**: un `<a>` o `<button>` con el texto de lo que pasa al pulsar («Ver el precio», «Darle asiento»), y si lleva flecha, `<span aria-hidden>→</span>` al final.
- **Estados**: hover a `color-accent-soft`; al pulsar baja 1px. Desactivado solo con la explicación de por qué al lado, nunca un botón gris mudo.
- **Medidas**: 0.85rem × 1.5rem de padding, `body-sm` en peso 500 (unos 46px de alto); `--sm` usa `meta`. En controles táctiles deja al menos 44px.
- **No**: botones de colores del aurora, mayúsculas, sombras.
