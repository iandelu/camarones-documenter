"""The server's background jobs: the list, one job's log, its event stream and the app's cancel button."""
from __future__ import annotations

import json
import time
from typing import BinaryIO

from lib.interfaces.http.jobs import CANCEL, JOBS
from lib.interfaces.http.messages import Request, Response, event_stream, json_response
from lib.interfaces.http.router import Access, route


def cancel_job(job_id: str) -> dict:
    """The app's cancel button: an in-process job (setup) is asked to stop between steps; a command job is killed."""
    ev = CANCEL.get(job_id)
    if ev is not None and JOBS.get(job_id, {}).get("status") == "running":
        ev.set()
        return {"cancelling": job_id}
    from lib.interfaces.http.routes.app_cmd import cancel
    return cancel(job_id)


def stream_job(job: dict, offset: int) -> Response:
    """Server-sent events of a job's log: one `line` per log line (its id the line count after it), then `end`."""
    def follow(out: BinaryIO, offset: int = offset) -> None:
        try:
            while True:
                lines, running = job["log"][offset:], job["status"] == "running"
                for line in lines:
                    offset += 1
                    ev = {"type": "line", "n": offset, "text": line}
                    out.write(f"id: {offset}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                if not running and offset >= len(job["log"]):
                    end = {"type": "end", "status": job["status"], "rc": job.get("rc"), "result": job.get("result")}
                    out.write(f"data: {json.dumps(end, ensure_ascii=False)}\n\n".encode("utf-8"))
                    out.flush()
                    return
                out.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            return
    return event_stream(follow)


@route("GET", "/api/jobs")
def get_jobs(req: Request) -> Response:
    from lib.interfaces.http.routes.app_cmd import stoppable
    return json_response([{**{k: v for k, v in j.items() if k != "log"}, "stoppable": stoppable(j["id"])}
                          for j in list(JOBS.values())])


@route("GET", "/api/jobs/{job}")
def get_job(req: Request) -> Response:
    job = req.params["job"]
    if job not in JOBS:
        return json_response({"error": "not found"}, 404)
    j = JOBS[job]
    since = int(req.query.get("since", 0))
    return json_response({**j, "log": j["log"][since:], "lines": len(j["log"])})


@route("GET", "/api/app/jobs/{job:[\\w.-]+}/events", access=Access.APP)
def get_job_events(req: Request) -> Response:
    job = req.params["job"]
    if job not in JOBS:
        return json_response({"error": "not found"}, 404)
    return stream_job(JOBS[job], int(req.headers.get("Last-Event-ID") or req.query.get("from") or 0))


@route("POST", "/api/app/jobs/{job:[\\w.-]+}/cancel", access=Access.APP)
def post_job_cancel(req: Request) -> Response:
    return json_response(cancel_job(req.params["job"]))
