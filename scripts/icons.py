# /// script
# requires-python = ">=3.10"
# dependencies = ["resvg-py==0.5.0"]
# ///
"""Render the desktop app's icons from the portal's favicon, the one drawing of the shrimp:

    uv run scripts/icons.py

icon.png is the whole tile (Windows and Linux windows); icon-mac.png sits on macOS's dock grid (an 824 tile on a 1024
canvas), so the dock shows it at the size of its neighbours. Run it again after changing favicon.svg.
"""
import re
from pathlib import Path

import resvg_py

ROOT = Path(__file__).resolve().parents[1]
FAVICON = ROOT / ".camarones" / "portal" / "app" / "public" / "favicon.svg"
DESKTOP = ROOT / ".camarones" / "desktop"
SIZE = 512


def padded(svg: str) -> str:
    side = 64 * 1024 / 824
    m = (side - 64) / 2
    return re.sub(r'viewBox="0 0 64 64"', f'viewBox="{-m:.3f} {-m:.3f} {side:.3f} {side:.3f}"', svg, count=1)


def main() -> None:
    svg = FAVICON.read_text(encoding="utf-8")
    for name, source in (("icon.png", svg), ("icon-mac.png", padded(svg))):
        png = bytes(resvg_py.svg_to_bytes(svg_string=source, width=SIZE, height=SIZE))
        (DESKTOP / name).write_bytes(png)
        print(f"{name}: {len(png)} bytes")


if __name__ == "__main__":
    main()
