"""The decisions API moved to lib/interfaces/http/routes/adr.py (the decisions a doc page lists to
lib/app/portal_views.py); this path stays for old imports."""
from __future__ import annotations

from .app.portal_views import covering
from .interfaces.http.routes.adr import BUSY, get, post

__facade__ = "lib.interfaces.http.routes.adr"
__all__ = ["BUSY", "covering", "get", "post"]
