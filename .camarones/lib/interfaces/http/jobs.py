"""The server's background jobs: builds, scans, wiki generation and catalog commands run for minutes, so a click starts
a job here and the page follows its log (`GET /api/jobs/<id>`, or its event stream)."""
from __future__ import annotations

import itertools
import threading
import time

JOBS: dict[str, dict] = {}
JOB_IDS = itertools.count(1)
JOB_LOCK = threading.Lock()
CANCEL: dict[str, threading.Event] = {}      # job id → its cancel flag, for jobs that run in this process (onboard:setup)


def job_running(kind: str) -> bool:
    with JOB_LOCK:
        return any(j["kind"] == kind and j["status"] == "running" for j in JOBS.values())


def start_job(kind: str, label: str, fn, **extra) -> dict:
    """One job per kind at a time: a second click attaches to the running one. `extra`: fields the job carries (a
    wiki job's repo)."""
    with JOB_LOCK:
        running = next((j for j in JOBS.values() if j["kind"] == kind and j["status"] == "running"), None)
        if running:
            return running
        job = claim_job(kind, label, **extra)
    return run_job(job, fn)


def claim_job(kind: str, label: str, **extra) -> dict:
    """A running job registered before its work starts; the caller holds JOB_LOCK (so checking and claiming are one
    step) and then hands it to run_job, or to fail_job if what comes before the work fails."""
    job = {"id": str(next(JOB_IDS)), "kind": kind, "label": label, "status": "running", "log": [],
           "started": time.time(), "ended": None, **extra}
    JOBS[job["id"]] = job
    return job


def fail_job(job: dict, error: Exception) -> None:
    job["log"].append(f"⚠ {error}")
    job["status"], job["ended"] = "failed", time.time()


def run_job(job: dict, fn) -> dict:
    def work():
        try:
            ok = fn(job["log"].append)
            if isinstance(ok, dict):                 # a command job: its exit code decides
                job.update(ok)
                ok = ok.get("rc", 0) == 0
            job["status"] = "done" if ok is not False else "failed"
        except Exception as e:  # noqa: BLE001
            job["log"].append(f"⚠ {e}")
            job["status"] = "failed"
        job["ended"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return job
