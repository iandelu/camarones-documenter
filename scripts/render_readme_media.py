# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=11,<13"]
# ///
"""Build README screenshots and GIFs from real Playwright captures.

Capture the live demo portal into ``.cache/readme-capture`` first, then run:

    uv run scripts/render_readme_media.py

The script deliberately does not invent UI frames: every source PNG must come
from a browser capture of the running portal.
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / ".cache" / "readme-capture"
OUT = ROOT / ".github" / "media"
MAX_WIDTH = 1200


def source(name: str) -> Path:
    path = CAPTURES / name
    if not path.is_file():
        raise SystemExit(f"Missing browser capture: {path}")
    return path


def resized(image: Image.Image, width: int = MAX_WIDTH) -> Image.Image:
    image = image.convert("RGB")
    if image.width <= width:
        return image
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def screenshot(name: str) -> None:
    image = resized(Image.open(source(name)))
    image.save(OUT / name, optimize=True)


def gif(name: str, frames: list[str], durations: list[int]) -> None:
    images = [resized(Image.open(source(frame)), 1080) for frame in frames]
    # One adaptive palette keeps text sharp and the recordings small enough for a README.
    palette = images[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    converted = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    converted[0].save(
        OUT / name,
        save_all=True,
        append_images=converted[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("portal-docs.png", "portal-c4.png", "portal-review.png"):
        screenshot(name)
    gif(
        "portal-docs.gif",
        ["docs-01.png", "docs-02.png", "docs-03.png", "docs-04.png"],
        [1800, 2200, 900, 2600],
    )
    gif(
        "portal-review.gif",
        ["review-01.png", "review-02.png", "review-03.png", "review-02.png"],
        [2000, 2200, 2200, 1300],
    )
    for name in ("portal-docs.png", "portal-c4.png", "portal-review.png", "portal-docs.gif", "portal-review.gif"):
        path = OUT / name
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
