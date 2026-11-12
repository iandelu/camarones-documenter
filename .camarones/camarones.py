# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6", "rich>=13", "questionary>=2", "keyring>=25", "pywinpty==3.1.0; sys_platform == 'win32' and python_version < '3.16'"]
# ///
"""🦐 Camarón — project documentation wizard + CLI. No arguments opens the wizard; `help` lists the commands."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

for _stream in (sys.stdout, sys.stderr):           # before the first print: a Windows pipe is cp1252, not UTF-8
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from lib.interfaces.cli import launch              # noqa: E402

launch.prelaunch(sys.argv, __file__)

from lib.interfaces.cli.main import build_parser, main   # noqa: E402,F401 — tests/fixtures/cli_shape.py reads build_parser

if __name__ == "__main__":
    sys.exit(main())
