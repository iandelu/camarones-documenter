# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=11,<13"]
# ///
"""Render the illustrative README animation: uv run scripts/render_readme_media.py.

This is a diagram of the workflow, not a recording of the application.
"""
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".github" / "media"
BG, PANEL, LINE = "#0c1620", "#142430", "#2a404e"
WHITE, MUTED, CORAL, MINT = "#eef4f7", "#a5bac7", "#ff956f", "#8bd5ca"


def font(size, bold=False):
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        Path("/System/Library/Fonts/Supplemental") / ("Arial Bold.ttf" if bold else "Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("Install Segoe UI, Arial or DejaVu Sans to render the media.")


STEPS = [
    ("Conecta los repositorios", "El sistema completo empieza a tener contexto.",
     ["orders-api", "payments-api", "storefront"],
     ["Detecta carpetas Git locales", "Añade repositorios de GitHub o GitLab", "Elige las herramientas del proyecto"],
     "Repositorios conectados · un centro de documentación"),
    ("Deja que tu agente investigue", "Código + contratos + tus respuestas.",
     ["Código y configuración", "Relaciones entre servicios", "Preguntas para el equipo"],
     ["Descubre cada repositorio", "Relaciona integraciones y datos", "Documenta la evidencia y las dudas"],
     "Claude Code / Codex · una unidad por sesión"),
    ("Guarda el contexto. Continúa.", "La siguiente sesión sabe por dónde seguir.",
     ["Plan con dependencias", "Notas de progreso", "Contexto de relevo"],
     ["plan start discovery:orders-api", "plan note ... \"Falta mensajería\"", "plan next"],
     "docs/.work/ · el progreso queda en archivos"),
    ("Revisa y explora el resultado", "Un mapa del proyecto que puedes mantener.",
     ["Wikis + arquitectura C4", "Flujos + dominio + datos", "Portal en inglés y español"],
     ["draft: pendiente de validación", "confirmed: contenido revisado", "needs-reconfirm: cambió tras la revisión"],
     "Cambió el código → vuelve a revisar la documentación"),
]


def frame(step, progress):
    im = Image.new("RGB", (1200, 650), BG)
    d = ImageDraw.Draw(im)
    d.text((48, 28), "CAMARONES DOCUMENTER", font=font(19, True), fill=CORAL)
    d.text((893, 31), "FLUJO ILUSTRATIVO", font=font(14), fill=MUTED)
    title, subtitle, cards, details, footer = STEPS[step]
    d.text((48, 88), title, font=font(42, True), fill=WHITE)
    d.text((50, 148), subtitle, font=font(24), fill=MUTED)
    labels = ["01  CONECTA", "02  INVESTIGA", "03  RETOMA", "04  REVISA"]
    for i, label in enumerate(labels):
        x = 48 + i * 280
        d.rounded_rectangle((x, 205, x + 263, 250), radius=10, fill=CORAL if i == step else PANEL)
        d.text((x + 21, 215), label, font=font(17, True), fill=BG if i == step else MUTED)
    for i, title in enumerate(cards):
        y = 282 + i * 79
        d.rounded_rectangle((48, y, 428, y + 63), radius=11, fill=PANEL, outline=LINE)
        d.ellipse((65, y + 24, 77, y + 36), fill=MINT)
        d.text((92, y + 17), title, font=font(21), fill=WHITE)
    d.line((446, 389, 501, 389), fill=CORAL, width=3)
    d.polygon(((501, 389), (491, 383), (491, 395)), fill=CORAL)
    d.rounded_rectangle((521, 282, 1150, 503), radius=14, fill=PANEL, outline=LINE)
    d.text((545, 301), "EL SIGUIENTE PASO", font=font(15, True), fill=MINT)
    for i, detail in enumerate(details):
        d.text((545, 348 + i * 45), detail, font=font(22), fill=WHITE)
    d.text((49, 546), footer, font=font(22), fill=MINT)
    d.rounded_rectangle((48, 598, 1150, 603), radius=2, fill=LINE)
    d.rounded_rectangle((48, 598, 48 + int(1102 * (step + progress) / 4), 603), radius=2, fill=CORAL)
    d.text((49, 618), "Ejemplo conceptual · sin datos de proyectos reales", font=font(14), fill=MUTED)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [frame(step, (tick + 1) / 8) for step in range(4) for tick in range(8)]
    palette = frames[0].quantize(colors=128)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in frames]
    frames[0].save(OUT / "workflow.gif", save_all=True, append_images=frames[1:], duration=500, loop=0, optimize=True)
    # Static preview also makes it easy to inspect the final layout.
    frame(3, 1).save(OUT / "workflow-preview.png")
    print(f"Generated {OUT / 'workflow.gif'} ({(OUT / 'workflow.gif').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
