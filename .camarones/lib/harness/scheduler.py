"""Parallel scheduler (R13): run ready units at the same time. A unit with `isolation: worktree` works in its own copy
of cam-docs and is integrated when it finishes; other units run in the main cam-docs, one at a time. Integration waits
until no in-place unit is running, and a unit's dependents wait for its integration. A usage limit pauses only that
runner and puts only its unit back in the queue (its worktree, with any work, is kept)."""
from __future__ import annotations

import datetime as dt
import os
import threading
import time
from dataclasses import dataclass, field

from .. import docs, plan
from ..common import CAM_DIR, CTX, cli_cmd
from . import kpis, routing
from .ctx import Ctx
from .events import EventLog
from .integrate import GATES, _kit, integrate
from .worktrees import Worktrees, slug

RESYNC = 10.0          # seconds between plan syncs while nothing changes (agents add units such as flows)


def parse_slots(text: str) -> dict[str, int]:
    """`claude=2,codex=1` → {"claude": 2, "codex": 1}: how many sessions each runner may run at once."""
    out = {}
    for part in filter(None, (p.strip() for p in (text or "").split(","))):
        name, sep, n = part.partition("=")
        if not sep or not n.strip().isdigit():
            raise ValueError(f"'{part}': use runner=N, e.g. claude=2,codex=1")
        out[name.strip()] = int(n)
    return out


@dataclass
class Job:
    uid: str
    target: str
    inplace: bool
    thread: threading.Thread | None = None
    proc: object = None
    result: object = None
    error: str = ""
    started: float = field(default_factory=time.monotonic)


def _work(job: Job, lang: str, emit, echo) -> None:
    try:
        env = {"CAMARONES_UNIT": job.uid}
        if job.inplace:
            text = plan.prompt(job.uid, lang=lang, unattended=True)
        else:
            w = Worktrees(CTX).add(job.uid)
            tree = Ctx.for_root(w.path, state_root=CTX.state_root, workspace=CTX.workspace)
            env.update(CAMARONES_ROOT=str(w.path), CAMARONES_STATE_ROOT=str(CTX.state_root),
                       CAMARONES_WORKSPACE=str(CTX.workspace))
            text = _kit(tree, f"from lib import plan\nprint(plan.prompt({job.uid!r}, {lang!r}, unattended=True))")
        prompt_file = CTX.state_root / ".camarones" / ".cache" / "prompts" / f"{slug(job.uid)}.md"
        job.result = plan._run_agent(job.target, text, lang, job.uid, echo=lambda l: echo(f"[{job.uid}] {l.strip()}"),
                                     prompt_file=prompt_file, env=env, emit=emit,
                                     on_start=lambda p: setattr(job, "proc", p))
    except Exception as e:                  # noqa: BLE001 — reported by the coordinator, never lost in a thread
        job.error = f"{type(e).__name__}: {e}"


def run_parallel(lang: str = "es", max_parallel: int = 2, per_runner: dict[str, int] | None = None,
                 max_units: int | None = None, poll_seconds: int = 900, include_interviews: bool = False,
                 policy: str = "on-conflict", gates=GATES, echo=print, poll: float = 0.5) -> int:
    """Run ready agent units, up to `max_parallel` at once and `per_runner[runner]` (default 1) per runner. Returns
    the units finished and merged. Every run is recorded in .camarones/.cache/runs/<run>/events.jsonl."""
    run_id = f"r-{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    events = EventLog(CTX.runs / run_id / "events.jsonl")

    def emit(kind: str, **fields) -> None:
        events.emit(kind, run=run_id, **fields)
    jobs: dict[str, Job] = {}
    emit("run.started", parallel=max_parallel, per_runner=per_runner or {}, max_units=max_units)
    try:
        done = _loop(jobs, lang, max_parallel, per_runner or {}, max_units, poll_seconds, include_interviews, policy,
                     gates, emit, echo, poll)
    except BaseException:                       # Ctrl+C or a crash: stop the agents, and say the run ended
        for j in jobs.values():
            if j.proc is not None and j.proc.poll() is None:
                j.proc.kill()
        emit("run.finished", interrupted=True)
        kpis.record_run(run_id)
        raise
    emit("run.finished", done=done)
    kpis.record_run(run_id)
    return done


def _loop(jobs, lang, max_parallel, per_runner, max_units, poll_seconds, include_interviews, policy, gates, emit,
          echo, poll) -> int:
    log = lambda t: plan._autopilot_log(t, echo)                               # noqa: E731
    noted: set[str] = set()

    def log_once(text: str) -> None:
        if text not in noted:
            noted.add(text)
            log(text)
    skip = set() if include_interviews or docs.interview_mode() == "team" else plan.INTERVIEW_TYPES
    limited: dict[str, dt.datetime] = {}
    pending: list[str] = []
    started = done = 0
    stop = ""
    synced = 0.0
    for problem in plan.pipeline_problems():
        log(f"pipeline.yaml: {problem} — the plan is used as it was")
    log(f"Parallel run started: up to {max_parallel} unit(s) at a time" + (f", max {max_units}" if max_units else ""))
    while True:
        for uid, j in list(jobs.items()):                                       # 1. collect finished sessions
            if j.thread.is_alive():
                continue
            del jobs[uid]
            synced = 0.0
            seconds = round(time.monotonic() - j.started, 1)
            if j.result is None:
                emit("unit.finished", unit=uid, runner=j.target, outcome="failed", error=j.error, seconds=seconds)
                stop = stop or f"{uid} could not start: {j.error}"
                continue
            output = f"{j.result.stdout or ''}\n{j.result.stderr or ''}"
            outcome = plan._runner(j.target)[0].classify(j.result.returncode, output)
            st = plan.get(plan.load(), uid)["status"]
            emit("unit.finished", unit=uid, runner=j.target, outcome=outcome, rc=j.result.returncode, status=st,
                 seconds=seconds)
            if outcome == "limited":
                limited[j.target] = dt.datetime.now() + dt.timedelta(seconds=poll_seconds)
                if st == "doing":
                    plan.set_status(uid, "todo", record=False)
                log(f"{j.target} hit its usage limit — {uid} goes back to the queue")
            elif outcome != "ok":
                stop = stop or (f"{j.target} failed on {uid} (exit {j.result.returncode}). Last output:\n"
                                + output.strip()[-1500:])
            elif st == "done":
                log(f"{j.target} finished {uid}")
                if j.inplace:
                    done += 1
                else:
                    pending.append(uid)
            elif st in ("todo", "doing"):
                stop = stop or (f"{uid} ended without `plan done`/`plan block` — check its checkpoints in "
                                f"{plan._at(plan.note_file(uid))} before continuing")
            else:
                log(f"{uid} ended as {st}")
        if pending and not any(j.inplace for j in jobs.values()):              # 2. merge while main is quiet
            for uid in pending:
                res = integrate(uid, CTX, gates=gates, policy=policy, emit=emit)
                if res.outcome in ("merged", "nothing"):
                    done += 1
                    log(f"{uid} merged into {CAM_DIR}/")
                else:
                    log(f"{uid} could not be merged ({res.outcome}): {res.detail[:300]}")
            pending.clear()
            synced = 0.0
        if stop and not jobs and not pending:
            log(f"Run stopped: {stop}")
            return done
        capped = max_units is not None and started >= max_units
        if not stop and not capped:                                             # 3. start what can start
            if time.monotonic() - synced > RESYNC:
                data, synced = plan.sync(), time.monotonic()
            else:
                data = plan.load()
            hold = set(jobs) | set(pending)
            view = {**data, "units": [{**u, "status": "doing"} if u["id"] in hold else u for u in data["units"]]}
            ready = [u for u in plan.available(view) if u["id"] not in hold]
            queue = [u for u in ready if u["runner"] == "agent" and u["type"] not in skip]
            waiting_on_limits = False
            for u in queue:
                if len(jobs) >= max_parallel or (max_units is not None and started >= max_units):
                    break
                s = plan.settings(u["id"])
                inplace = s.get("isolation") != "worktree"
                if inplace and (pending or any(j.inplace for j in jobs.values())):
                    continue
                targets = plan._agents(log_once, s["tier"], s.get("runner"), bool(s.get("allow_local")))
                if not targets:
                    stop = f"no installed agent can run {u['id']} ({s.get('runner') or s['tier']})"
                    break
                now = dt.datetime.now()
                busy = {}
                for j in jobs.values():
                    rid = routing.parse(j.target).runner
                    busy[rid] = busy.get(rid, 0) + 1
                free = [t for t in targets if limited.get(t, dt.datetime.min) <= now
                        and busy.get(routing.parse(t).runner, 0) < per_runner.get(routing.parse(t).runner, 1)]
                if not free:
                    waiting_on_limits = waiting_on_limits or all(limited.get(t, dt.datetime.min) > now for t in targets)
                    continue
                job = Job(u["id"], free[0], inplace)
                job.thread = threading.Thread(target=_work, args=(job, lang, emit, echo), daemon=True)
                jobs[u["id"]] = job
                started += 1
                emit("unit.started", unit=u["id"], runner=job.target, isolation="none" if inplace else "worktree")
                log(f"{job.target} → {u['id']}: {u['title']}" + ("" if inplace else " (own worktree)"))
                job.thread.start()
            if not jobs and not pending and not stop:
                if waiting_on_limits:
                    soonest = min(limited.values())
                    wait = max(60, min(poll_seconds, int((soonest - dt.datetime.now()).total_seconds())))
                    log(f"Every agent for the next units is at its usage limit — retrying in {wait // 60} min "
                        "(machine must stay on; Ctrl+C to stop, progress is saved).")
                    time.sleep(wait)
                    continue
                if queue:
                    log(f"Run stopped: no agent slot can take {queue[0]['id']} (check per_runner)")
                    return done
                if not queue:
                    wizard = [u["id"] for u in ready if u["runner"] == "wizard"]
                    interviews = [u["id"] for u in ready if u["type"] in skip]
                    if wizard or interviews:
                        why = ([f"wizard step(s) {', '.join(wizard)} (run `{cli_cmd()}`)"] if wizard else []) + \
                              ([f"interview(s) {', '.join(interviews)} (need you, in an interactive session)"]
                               if interviews else [])
                        log(f"Run stopped: what is left needs you — {'; '.join(why)}.")
                    else:
                        d, t = plan.progress(data)
                        log(f"Run stopped: nothing ready — {d}/{t} units done.")
                    return done
        elif not jobs and not pending and not stop:
            log(f"Run stopped: reached the limit of {max_units} unit(s).")
            return done
        time.sleep(poll)
