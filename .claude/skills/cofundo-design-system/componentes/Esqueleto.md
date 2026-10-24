# Esqueleto

`co-esqueleto`: la forma de lo que va a llegar, con un brillo que la recorre, mientras se carga. Sustituye al spinner sobre una pantalla vacía, que no dice nada.

- **Cuándo**: mientras se espera una respuesta que va a pintar un bloque conocido.
- **Qué pones tú**: un `<div class="co-esqueleto">` con el alto del bloque que viene (por defecto 3.6rem). Si el bloque es grande, dale su alto real.
- **No**: dejar el esqueleto si la respuesta falla. Pasa a un `co-error` con salida.
