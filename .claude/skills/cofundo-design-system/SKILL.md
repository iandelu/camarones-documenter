---
name: cofundo-design-system
description: El sistema de diseño de la web de Cofundo (cofundo.io) — colores, tipografía, tokens, componentes y reglas de marca y de copy. Úsalo SIEMPRE que diseñes, maquetes o escribas cualquier pantalla, página, landing, componente, prototipo, artefacto o pieza visual de Cofundo o del Cerebro de ventas, aunque no se nombre el sistema. NO es la identidad de los documentos Word de consultoría (navy con punto teal): esa es otra cosa y no se mezcla.
---

# Cofundo — sistema de diseño

La identidad de Cofundo en pantalla: lienzo off-white cálido, tinta casi negra, un degradado "aurora" (cian, violeta, rosa, coral, ámbar) solo como fondo, titulares en Big Shoulders e Inter para todo lo demás. Sacado del código de la web (`app/globals.css` y `docs/DESIGN_SYSTEM.md`, versión del 2/10/2026).

## Antes de construir

1. **Lee `guia-de-marca.md` entera.** Ahí están las reglas que no se negocian: las tres legales (nombres de formadores, guion literal, nada de base de datos), la voz y el copy, el color, la tipografía, el movimiento y los estados de pantalla. Si algo de lo que vas a hacer choca con ella, gana ella.
2. **Usa los valores, no los copies a mano.** Carga en este orden:
   - las fuentes: `https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@500;600;700&family=Bricolage+Grotesque:wght@500&family=Inter:wght@400;500;600&display=swap`
   - `tokens.css` (variables CSS con los nombres reales del código: `--color-canvas`, `--color-ink`, `--text-display-xl`…)
   - `componentes.css` (las clases reales de la web: `co-btn`, `co-card`, `aurora-bg`, `t-display-lg`…)

   Si trabajas en una página de un solo fichero, pega el contenido de los dos CSS en un `<style>`. `tokens.json` tiene los mismos valores como datos, con una nota de uso por token.
3. **Antes de usar un componente, lee su ficha** en `componentes/`:
- `componentes/Aviso.md`
- `componentes/Boton.md`
- `componentes/Campo.md`
- `componentes/Chip.md`
- `componentes/Esqueleto.md`
- `componentes/Golpe.md`
- `componentes/Marca.md`
- `componentes/Puerta.md`
- `componentes/Superficie.md`
- `componentes/Tarjeta.md`
- `componentes/Titular.md`
4. **`muestrario.html`** enseña todos los componentes pintados con el CSS real. Ábrelo en un navegador para ver cómo se ven.

## Lo mínimo que no puedes romper

- Fondo `--color-canvas`, nunca blanco puro. Texto en `--color-ink` / `--color-ink-soft` / `--color-ink-dim`.
- El aurora (`--color-aurora-*`) es **solo fondo**: como texto da 2,2:1. Para un violeta legible, `--color-acento-texto`.
- Titulares en `t-display-*` / `t-h1` (Big Shoulders 600), a dos tonos con `t-eco`. Al lado de un `t-display-xl`, una sola cosa más.
- Botones y chips siempre píldora; un solo botón negro (`co-btn`) por bloque.
- Nada de «No hay datos», «Ha ocurrido un error» ni promesas que el producto no cumple. Español primero; el inglés traduce el argumento, no la frase.
- Ningún nombre de formador ni de metodología ajena como reclamo.
- `svh`, nunca `vh`. La animación sigue al scroll, no se lo queda.
- No hay logotipo en fichero: la marca es la wordmark «cofundo» en minúsculas (Bricolage Grotesque 500). No dibujes otro.

## Lo que este paquete no trae

- Componentes de React con comportamiento (cabecera con mega-menú, raíl de pasos, acordeón de preguntas, entradas al scroll): están descritos en la guía, pero su código vive en el repositorio de la web.
- Modo oscuro: la web no lo tiene. La única zona oscura es la sección con fondo `--color-accent` y texto blanco.
