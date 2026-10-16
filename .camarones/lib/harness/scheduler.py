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
from . import awake, kpis, routing
from .ctx import Ctx
from .events import EventLog
from .integrate import GATES, _kit, integrate
from .locks import FileLock, LockBusy
from .worktrees import Worktrees, slug

RESYNC = 10.0          # seconds between plan syncs while nothing changes (agents add units such as flows)
RUN_LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "run.lock"   # one run at a time, CLI or portal


def busy() -> dict | None:
    """Who holds the run lock (a run is in progress somewhere), or None."""
    try:
        with FileLock(RUN_LOCK, wait=0):
            return None
    except LockBusy as e:
        return e.holder


def cancel_file(run_id: str):
    return CTX.runs / run_id / "cancel"


def request_cancel(run_id: str) -> None:
    """Ask a run to stop, whichever process runs it: the scheduler checks for this file on every tick."""
    f = cancel_file(run_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("cancel\n", encoding="utf-8")


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


def _closed_in_copy(uid: str, log) -> bool:
    """A session that closed its unit in its worktree's copy of the plan (an older kit on PATH ignores the state
    root): carry that status over to the real plan instead of losing the work."""
    import yaml
    w = Worktrees(CTX).get(uid)
    copy = w.path / "docs" / ".work" / "plan.yaml" if w else None
    try:
        units = (yaml.safe_load(copy.read_text(encoding="utf-8")) or {}).get("units", []) if copy and copy.exists() else []
    except yaml.YAMLError:
        return False
    u = next((u for u in units if u.get("id") == uid), None)
    if not u or u.get("status") not in ("done", "blocked"):
        return False
    plan.set_status(uid, u["status"], u.get("notes") or None)
    log(f"{uid}: closed in its worktree's copy of the plan — an older kit on PATH? Carried over to {CAM_DIR}/; "
        "update the kit everywhere (`camaron self-update`)")
    return True


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
    the units finished and merged. Every run is recorded in .camarones/.cache/runs/<run>/events.jsonl. One run at a
    time: a second one (CLI or portal) raises RuntimeError naming who holds the run lock."""
    lock = FileLock(RUN_LOCK, wait=0, info={"what": "documentation run"})
    try:
        lock.acquire()
    except LockBusy as e:
        raise RuntimeError(f"another documentation run is in progress (pid {e.holder.get('pid')} on "
                           f"{e.holder.get('host') or 'this machine'}) — wait for it or cancel it") from None
    try:
        return _run(lang, max_parallel, per_runner, max_units, poll_seconds, include_interviews, policy, gates, echo, poll)
    finally:
        lock.release()


def _run(lang, max_parallel, per_runner, max_units, poll_seconds, include_interviews, policy, gates, echo, poll) -> int:
    run_id = f"r-{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    events = EventLog(CTX.runs / run_id / "events.jsonl")

    def emit(kind: str, **fields) -> None:
        events.emit(kind, run=run_id, **fields)
    jobs: dict[str, Job] = {}
    emit("run.started", parallel=max_parallel, per_runner=per_runner or {}, max_units=max_units)
    try:
        with awake.keep_awake():
            done = _loop(jobs, lang, max_parallel, per_runner or {}, max_units, poll_seconds, include_interviews, policy,
                         gates, emit, echo, poll, run_id)
    except BaseException:                       # Ctrl+C or a crash: stop the agents, and say the run ended
        for j in jobs.values():
            if j.proc is not None and j.proc.poll() is None:
                j.proc.kill()
        emit("run.finished", interrupted=True)
        kpis.record_run(run_id)
        raise
    cancelled = cancel_file(run_id).exists()
    emit("run.finished", done=done, **({"interrupted": True, "cancelled": True} if cancelled else {}))
    kpis.record_run(run_id)
    return done


def _loop(jobs, lang, max_parallel, per_runner, max_units, poll_seconds, include_interviews, policy, gates, emit,
          echo, poll, run_id: str = "") -> int:
    log = lambda t: plan._autopilot_log(t, echo)                               # noqa: E731
    noted: set[str] = set()

    def log_once(text: str) -> None:
        if text not in noted:
            noted.add(text)
            log(text)
    skip = set() if include_interviews or docs.interview_mode() == "team" else plan.INTERVIEW_TYPES
    limited: dict[str, dt.datetime] = {}
    retried: set[str] = set()                # one more try per unit after a transient failure
    pending: list[str] = []
    started = done = 0
    stop = ""
    synced = 0.0
    for problem in plan.pipeline_problems():
        log(f"pipeline.yaml: {problem} — the plan is used as it was")
    units = {u["id"]: u for u in plan.load()["units"]}
    for w in Worktrees(CTX).list():                  # work finished earlier but never merged (crash, main was busy)
        u = units.get(w.unit) or {}
        waiting = u.get("status") == "blocked" and str(u.get("notes", "")).startswith("integrate:")
        if u.get("status") == "done" or waiting:                   # merging again is free: no agent involved
            if waiting:
                plan.set_status(w.unit, "done", record=False)
            pending.append(w.unit)
            log(f"{w.unit}: finished work found in {plan._at(w.path)} — merging it before anything else")
    log(f"Parallel run started: up to {max_parallel} unit(s) at a time" + (f", max {max_units}" if max_units else ""))
    agents = {routing.parse(t).runner for t in plan._agents(lambda _: None)}
    if 0 < len(agents) < max_parallel:                 # one session per agent by default (quotas): say how to allow more
        for rid in sorted(agents):
            if per_runner.get(rid, 1) * len(agents) < max_parallel:
                log(f"{rid}: {per_runner.get(rid, 1)} session at a time — --per-runner {rid}={max_parallel} lets it "
                    "take more (each session uses your quota)")
    cancelled = False
    while True:
        if not cancelled and run_id and cancel_file(run_id).exists():          # 0. a cancel from the portal
            cancelled, stop = True, "cancelled"
            for j in jobs.values():
                if j.proc is not None and j.proc.poll() is None:
                    j.proc.kill()
            log("Cancelling: stopping the agents; their units go back to the queue (worktrees are kept)")
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
            if cancelled and st != "done":
                if st == "doing":
                    plan.set_status(uid, "todo", record=False)
                emit("unit.finished", unit=uid, runner=j.target, outcome="cancelled", rc=j.result.returncode,
                     status="todo" if st == "doing" else st, seconds=seconds)
                continue
            emit("unit.finished", unit=uid, runner=j.target, outcome=outcome, rc=j.result.returncode, status=st,
                 seconds=seconds)
            if outcome == "limited":
                limited[j.target] = dt.datetime.now() + dt.timedelta(seconds=poll_seconds)
                started -= 1                          # back in the queue: it does not use up --max-units
                if st == "doing":
                    plan.set_status(uid, "todo", record=False)
                log(f"{j.target} hit its usage limit — {uid} goes back to the queue")
            elif outcome == "retry" and uid not in retried:
                retried.add(uid)
                started -= 1
                if st == "doing":
                    plan.set_status(uid, "todo", record=False)
                log(f"{uid}: the session broke ({output.strip().splitlines()[-1][:120] if output.strip() else 'no output'})"
                    " — retrying once")
            elif outcome != "ok":
                stop = stop or (f"{j.target} failed on {uid} (exit {j.result.returncode}). Last output:\n"
                                + output.strip()[-1500:])
            elif st == "done":
                log(f"{j.target} finished {uid}")
                if j.inplace:
                    done += 1
                else:
                    pending.append(uid)
            elif st in ("todo", "doing") and not j.inplace and _closed_in_copy(uid, log):
                synced = 0.0
                if plan.get(plan.load(), uid)["status"] == "done":
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
                    if str(plan.get(plan.load(), uid).get("notes") or "").startswith("integrate:"):
                        plan.set_status(uid, "done", f"merged into {CAM_DIR}/ by the kit", record=False)
                    fix = next((u for u in plan.load()["units"] if u["id"] == f"integrate:{uid}"), None)
                    if fix and fix["status"] not in ("done", "dropped"):
                        plan.set_status(fix["id"], "dropped", "merged by the kit, nothing left to resolve")
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
