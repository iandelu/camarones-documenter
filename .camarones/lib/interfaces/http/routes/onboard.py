"""The desktop app's first run (`/api/app/onboard/*`, app token only): lib/onboard.py does the work; a job for what
takes a while (setup, the repo scan, the C4 draft)."""
from __future__ import annotations

import threading

from lib.app import services
from lib.interfaces.http import inputs
from lib.interfaces.http.jobs import CANCEL, job_running, start_job
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


def app_onboard(name: str, b: dict) -> tuple[dict, int]:
    """POST /api/app/onboard/<name>: the desktop app's first run (lib/onboard.py does the work). A job for what takes
    a while (setup, the repo scan, the C4 draft); errors the app can act on are 400s with a short code."""
    from lib import agents, onboard
    if name == "step":
        return onboard.go_to(str(b.get("id", ""))), 200
    if name == "repos":
        return onboard.set_repos(b.get("repos")), 200
    if name == "setup":
        system = inputs.text_list(b, "system")
        comps = [c for c in inputs.text_list(b, "components") if c in services.current().components.ALL_COMPONENTS] if "components" in b else services.current().components.components()
        ev = threading.Event()
        job = start_job("onboard:setup", "setup", lambda log: onboard.setup_job(system, comps, log, ev.is_set))
        CANCEL.setdefault(job["id"], ev)           # a click that attached to the running job keeps that job's flag
        return job, 200
    if name == "scan":
        return start_job("onboard:scan", "scan", onboard.scan_job), 200
    if name == "stack":
        text = inputs.text(b, "text")
        return onboard.set_stack(str(b.get("repo", "")), text), 200
    if name == "arch":
        action = b.get("action")
        if action == "draft":
            return start_job("onboard:arch", "arch", onboard.arch_draft), 200
        if action in ("save", "save-ai"):
            if job_running("onboard:arch"):         # the draft's folder is being rebuilt: saving now would copy half of it
                return {"error": "busy"}, 409
            res = onboard.arch_save(bool(b.get("overwrite")))
            if action == "save-ai" and not res.get("exists"):
                lang = b.get("lang") or "es"
                try:
                    res["agent"] = agents.launch_prompt(onboard.arch_prompt(lang), str(b.get("agent", "")), lang)
                except (RuntimeError, ValueError) as e:     # the model is written already: the save stands, say why
                    res.update(launched=False, error="terminal" if isinstance(e, RuntimeError) else "agent",
                               prompt=agents.ws_rel(agents.PROMPT))
            return res, 200
        raise ValueError("action")
    return onboard.done(), 200


@route("GET", "/api/app/onboard/state", access=Access.APP)
def get_state(req: Request) -> Response:
    from lib import onboard
    return json_response(onboard.state())


@route("GET", "/api/app/onboard/tools", access=Access.APP)
def get_tools(req: Request) -> Response:
    from lib import onboard
    rows = onboard.tool_rows()
    return json_response({"rows": rows, "required_ok": all(r["ok"] for r in rows if r["kind"] == "t_required")})


@route("GET", "/api/app/onboard/stack", access=Access.APP)
def get_stack(req: Request) -> Response:
    from lib import onboard
    return json_response(onboard.stack_rows())


@route("POST", "/api/app/onboard/{name:step|repos|setup|scan|stack|arch|done}", access=Access.APP)
def post_onboard(req: Request) -> Response:
    return json_response(*app_onboard(req.params["name"], req.body))
