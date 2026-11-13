"""The desktop app's command API moved to lib/interfaces/http/routes/app_cmd.py; this path stays for old imports."""
from __future__ import annotations

from .interfaces.http.routes.app_cmd import HUB, PROCS, argv, cancel, catalog, entry, info, start, stoppable, stream_job

__facade__ = "lib.interfaces.http.routes.app_cmd"
__all__ = ["HUB", "PROCS", "argv", "cancel", "catalog", "entry", "info", "start", "stoppable", "stream_job"]
