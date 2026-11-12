"""Which OS the kit runs on and where home is."""
from __future__ import annotations

import platform
from pathlib import Path

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
HOME = Path.home()
