# Tarjeta

`co-card`: bloque enlazable con borde hairline, `radius-tarjeta` y fondo `color-canvas-elevated`; en hover sube 2px, oscurece el borde y gana `sombra-hover`. Se colocan en `co-cohort`, una rejilla de dos columnas que pasa a una a 720px.

- **Cuándo**: para elementos del mismo nivel que llevan a otra página. Si no lleva a ningún sitio, usa `surface`.
- **Qué pones tú**: el `<a class="co-card">` con un eyebrow, un titular en `font-impact`, una línea de `t-body` y, al pie, `co-card__cta` con `<span class="co-card__arrow" aria-hidden>→</span>`.
- **No**: borde de color a la izquierda, iconos decorativos, sombra en reposo.
