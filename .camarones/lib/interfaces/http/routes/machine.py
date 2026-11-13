"""The desktop app's machine: the Summary, the doctor, the kit's bench, the Machine panel, the guides, the saved tokens
and the tour's offer (all under /api/app/, app token only). This module is the HTTP layer's only reader of the machine
settings and the keychain: `ui_lang` and `sessions_setting` serve the other areas."""
from __future__ import annotations

import os
from pathlib import Path

from lib import docs, plan
from lib.core.paths import DOCS
from lib.interfaces.http.jobs import start_job
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


def sessions_setting() -> str:
    """Where this machine opens an agent session: on the Plan's canvas or in its own terminal window."""
    from lib import machine
    return machine.settings()["sessions"]


def ui_lang(lang: str = "") -> str:
    """The language of the UI that asks (es / en), else the one picked on this machine (~/.camarones.json)."""
    from lib import machine
    return lang if lang in machine.LANGS else machine.settings()["lang"]


def app_kitdev(b: dict) -> tuple[dict, int]:
    """A Kit dev task (lib/kitdev.py) as a job, outside this project's environment (the sandbox is its own project)."""
    from lib import kitdev
    from lib.interfaces.http.routes.app_cmd import stream_job
    task = str(b.get("task", ""))
    try:
        if task == "sandbox-open":
            return {"opened": kitdev.open_wizard()}, 200
        argv, cwd = kitdev.command(task, b)
    except PermissionError as e:
        return {"error": str(e)}, 403
    env = {k: v for k, v in os.environ.items() if k not in ("CAMARONES_ROOT", "CAMARONES_APP_TOKEN")}
    label = " ".join([Path(argv[0]).stem, *argv[1:]])
    return stream_job(start_job, f"kitdev:{task}", argv, cwd, {**env, "PYTHONUTF8": "1"}, label=label,
                      shown=[Path(argv[0]).stem, *argv[1:]]), 200


def app_creds(action: str, b: dict) -> tuple[dict, int]:
    """The desktop app's tokens for GitLab / GitHub / SonarQube (lib/creds.py, the OS keychain): saved only after the
    server accepts them (or with `anyway`), tested, or deleted. A token is never sent back. A SonarQube host is kept as
    given (path prefix included, trailing slash dropped) and only over https, except for a local one."""
    from lib import creds
    raw = str(b.get("host") or "").strip()
    sonar = creds.sonar_host(raw)
    if b.get("kind") == "sonarqube" or creds.hosts().get(sonar, {}).get("kind") == "sonarqube":
        try:
            creds.sonar_base(sonar)
        except ValueError as e:
            return {"error": f"host: {e}"}, 400
        host, b = sonar, {**b, "kind": "sonarqube"}
        if host.startswith("-") or any(c.isspace() for c in host):
            return {"error": "host: like sonar.example.com"}, 400
    else:
        host = creds.host_of(raw if "://" in raw else f"https://{raw}") or raw
        if not host or host.startswith("-") or "/" in host:
            return {"error": "host: like gitlab.example.com"}, 400
    if action == "/delete":
        creds.delete(host)
        return {"deleted": host}, 200
    if action == "/test":
        tok = creds.get(host)
        if not tok:
            return {"error": f"no token saved for {host}"}, 404
        ok, info = creds.verify(host, creds.hosts().get(host, {}).get("kind") or creds.guess_kind(host), tok)
        return {"ok": ok, "info": info}, 200
    if action:
        return {"error": "not found"}, 404
    kind, token = b.get("kind") or creds.guess_kind(host), str(b.get("token") or "").strip()
    if kind not in ("gitlab", "github", "sonarqube") or not token:
        return {"error": "kind (gitlab, github or sonarqube) and token are required"}, 400
    ok, info = creds.verify(host, kind, token)
    if not ok and not b.get("anyway"):
        return {"error": f"{host} did not accept the token: {info}"}, 400
    where = creds.save(host, kind, token, info if ok else "")
    return {"host": host, "user": info if ok else "", "where": where}, 200


def app_summary(lang: str = "") -> dict:
    """The desktop app's Summary: the next step (the wizard's rule, plan.next_step), the plan's progress, the pages
    waiting for a person and what the last doctor check found (None: never checked). Reads only: plan.sync() writes,
    and a page that just looks must not."""
    from lib import doctor
    review = len(docs.review_queue()) if DOCS.exists() else 0
    data = plan.load()
    done, total = plan.progress(data)
    last = doctor.checked()
    return {"step": plan.next_step(data, review=review, lang=ui_lang(lang)), "plan": {"done": done, "total": total}, "review": review,
            "doctor": doctor.problems(last["result"]) if last else None,
            "interviews": docs.interview_mode() if docs.interview_mode_chosen() else None}


@route("GET", "/api/app/summary", access=Access.APP)
def get_summary(req: Request) -> Response:
    return json_response(app_summary(req.query.get("lang", "")))


@route("GET", "/api/app/doctor", access=Access.APP)
def get_doctor(req: Request) -> Response:
    from lib import doctor
    return json_response({"checked": doctor.checked()})


@route("POST", "/api/app/doctor", access=Access.APP)
def post_doctor(req: Request) -> Response:
    from lib import doctor                  # check again: a job that keeps its result (lib/doctor.check)
    return json_response(start_job("doctor", "doctor", lambda log: bool(doctor.check(log))))


@route("GET", "/api/app/kitdev", access=Access.APP)
def get_kitdev(req: Request) -> Response:
    from lib import kitdev
    return json_response(kitdev.info())


@route("POST", "/api/app/kitdev", access=Access.APP)
def post_kitdev(req: Request) -> Response:
    return json_response(*app_kitdev(req.body))     # the bench of a kit checkout: sandbox, pytest, npm, node --test


@route("GET", "/api/app/machine", access=Access.APP)
def get_machine(req: Request) -> Response:
    from lib import machine
    return json_response(machine.panel())


@route("GET", "/api/app/guide", access=Access.APP)
def get_guide(req: Request) -> Response:
    from lib import guide
    from lib.core.fsutil import load_json
    from lib.core.paths import PREFS
    lang = req.query.get("lang") or load_json(PREFS, {}).get("lang", "es")
    return json_response({"lang": lang, "guides": guide.guides(lang)})


@route("GET", "/api/app/creds", access=Access.APP)
def get_creds(req: Request) -> Response:
    from lib import creds
    return json_response({"backend": creds.backend_name(), "hosts": [
        {"host": h, "kind": m.get("kind", ""), "user": m.get("user", ""), "saved": bool(creds.get(h))}
        for h, m in creds.hosts().items()]})


@route("POST", "/api/app/creds{action:.*}", access=Access.APP)
def post_creds(req: Request) -> Response:
    return json_response(*app_creds(req.params["action"], req.body))   # tokens travel in this body, never on a command line


@route("POST", "/api/app/tour-offered", access=Access.APP)
def post_tour_offered(req: Request) -> Response:
    from lib.core.fsutil import load_json, save_json      # the Summary's offer of the tour, once per machine
    from lib.core.paths import PREFS
    save_json(PREFS, {**load_json(PREFS, {}), "tour_offered": True})
    return json_response({"ok": True})
