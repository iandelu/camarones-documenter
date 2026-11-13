"""The project server moved to lib/interfaces/http; this path stays for old imports."""
from __future__ import annotations

from .app.portal_views import APP, UI, UI_LIBS, doc_file, read, reviewer, status, tree
from .interfaces.http.jobs import CANCEL, JOB_IDS, JOB_LOCK, JOBS, claim_job, fail_job, job_running, run_job, start_job
from .interfaces.http.router import APP_ONLY_MSG
from .interfaces.http.routes.analysis import (
    api_inventory, api_schemas, build, first_look, inventory_job, schemas_write, wiki,
)
from .interfaces.http.routes.architecture import api_c4_view, c4_change
from .interfaces.http.routes.board import kanban_marks, kanban_state
from .interfaces.http.routes.docs import api_ask, api_doc, api_search, create, write
from .interfaces.http.routes.jobs import cancel_job
from .interfaces.http.routes.machine import app_creds, app_kitdev, app_summary, ui_lang
from .interfaces.http.routes.onboard import app_onboard
from .interfaces.http.routes.runs import api_pipeline, approve_unit, retry_unit, run_stopped, start_run
from .interfaces.http.routes.team import api_interview, kpis_miss
from .interfaces.http.routes.terminals import STREAM_FROM, app_session, app_terminal, app_unit
from .interfaces.http.server import DESKTOP, SITE, Handler, cdn_local, run_server, take_tokens, token_matches, watch_app

__facade__ = "lib.interfaces.http"
__all__ = [
    "APP", "APP_ONLY_MSG", "CANCEL", "DESKTOP", "Handler", "JOBS", "JOB_IDS", "JOB_LOCK", "SITE", "STREAM_FROM", "UI",
    "UI_LIBS", "api_ask", "api_c4_view", "api_doc", "api_interview", "api_inventory", "api_pipeline", "api_schemas",
    "api_search", "app_creds", "app_kitdev", "app_onboard", "app_session", "app_summary", "app_terminal", "app_unit",
    "approve_unit", "build", "c4_change", "cancel_job", "cdn_local", "claim_job", "create", "doc_file", "fail_job",
    "first_look", "inventory_job", "job_running", "kanban_marks", "kanban_state", "kpis_miss", "read", "retry_unit",
    "reviewer", "run_job", "run_server", "run_stopped", "schemas_write", "start_job", "start_run", "status",
    "take_tokens", "token_matches", "tree", "ui_lang", "watch_app", "wiki", "write",
]
