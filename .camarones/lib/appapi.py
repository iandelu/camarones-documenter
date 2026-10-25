"""The desktop app's side of the portal server. The app launches `up --foreground` with a token
(CAMARONES_APP_TOKEN); requests that carry it may start processes and call models, and `/api/app/*` runs catalog
commands as jobs: the CLI is the app's API, so the app never re-implements a command.

Arguments are checked against the parser's own description (lib/catalog.py) before anything runs: unknown names,
wrong kinds, values outside the choices and values that look like options are refused. A command with `--yes` (or a
destructive one) runs only once the app has asked the person, and `--yes` is added here, never by the caller."""
from __future__ import annotations

import functools, json, os, signal, subprocess, sys, threading

from .common import HOME, IS_WIN, KIT, ROOT, VERSIONS, out, run

HUB = {"new", "join", "switch", "projects"}   # the app's hub opens projects itself (incl. projects --inspect/--adopt)
PROCS: dict[str, dict] = {}           # job id → {"proc": Popen} for cancel


@functools.lru_cache(maxsize=1)
def catalog() -> dict:
    r = run([sys.executable, str(KIT / "camarones.py"), "catalog", "--json"], check=False, capture=True,
            env={"CAMARONES_ROOT": str(ROOT), "PYTHONUTF8": "1"})
    return json.loads(r.stdout)


def entry(name: str) -> dict:
    e = next((c for c in catalog()["commands"] if c["name"] == name), None)
    if e is None:
        raise KeyError(name)
    if e["verdict"] not in ("app", "both") or name in HUB:
        raise ValueError(f"{name} is not run from the app")
    return e


def info() -> dict:
    from . import kitdev
    return {"kit": VERSIONS["kit"], "root": str(ROOT), "user": out(["git", "config", "user.name"], cwd=ROOT) or "",
            "kitdev": kitdev.available()}


def _value(row: dict, v) -> list[str]:
    dest = row["dest"]
    if row["many"]:
        vals = v if isinstance(v, list) else [v]
    else:
        if isinstance(v, list):
            raise ValueError(f"{dest}: one value, not a list")
        vals = [v]
    outv = []
    for x in vals:
        if row["kind"] in ("int", "float"):
            if isinstance(x, bool):
                raise ValueError(f"{dest}: expected a number")
            try:
                x = int(x) if row["kind"] == "int" else float(x)
            except (TypeError, ValueError):
                raise ValueError(f"{dest}: expected a number") from None
        elif row["choices"] is not None:
            if x not in row["choices"]:
                raise ValueError(f"{dest}: one of {', '.join(map(str, row['choices']))}")
        elif not isinstance(x, str) or not x.strip():
            raise ValueError(f"{dest}: expected text")
        x = str(x)
        if x.startswith("-") and row["kind"] not in ("int", "float"):
            raise ValueError(f"{dest}: a value cannot start with '-'")
        outv.append(x)
    return outv


def argv(e: dict, args: dict, confirmed: bool = False) -> list[str]:
    """The command line for a catalog entry and the app's form values (keyed by argparse `dest`)."""
    rows = e["args"]
    known = {r["dest"] for r in rows}
    for k in args:
        if k not in known:
            raise ValueError(f"unknown argument {k}")
    if e["confirm"] and args.get("yes"):
        raise ValueError("yes: the app asks first and adds it")
    reading = bool(e.get("reads") and args.get(e["reads"]))           # e.g. `trust --json` lists, approves nothing
    asks = (e["confirm"] or e["destructive"]) and not reading
    if asks and not confirmed:
        raise PermissionError(f"{e['name']} needs a confirmation first")
    pos, opts = [], []
    for r in rows:
        if r["dest"] == "yes" and e["confirm"]:
            continue
        v = args.get(r["dest"])
        if r["kind"] == "const":
            if v not in (None, "") and v == r["const"]:
                opts.append(r["flag"])
            elif v not in (None, "") and v not in [x["const"] for x in rows if x["dest"] == r["dest"]]:
                raise ValueError(f"{r['dest']}: unknown value {v}")
            continue
        if v is None or v == "" or v == []:
            if r["required"]:
                raise ValueError(f"{r['dest']}: required")
            continue
        if r["kind"] == "bool":
            if not isinstance(v, bool):
                raise ValueError(f"{r['dest']}: expected true or false")
            if v:
                opts.append(r["flag"])
            continue
        vals = _value(r, v)
        (pos.extend(vals) if r["positional"] else opts.extend([r["flag"], *vals]))
    if e["confirm"] and not reading:
        opts.append("--yes")
    return [e["name"], *pos, *opts]


def start(b: dict, start_job) -> dict:
    """Run a catalog command as a job of the server: its stdout and stderr lines go to the job log, its exit code
    and (for --json) its parsed output to the job."""
    e = entry(str(b.get("cmd", "")))
    cmd = argv(e, b.get("args") or {}, bool(b.get("confirmed")))
    # cwd outside the project (CAMARONES_ROOT names it): Windows cannot delete a folder a process works in
    return stream_job(start_job, "cmd:" + " ".join(cmd), [sys.executable, str(KIT / "camarones.py"), *cmd], HOME,
                      {**os.environ, "CAMARONES_ROOT": str(ROOT), "PYTHONUTF8": "1"}, parse_json="--json" in cmd,
                      label=" ".join(cmd), shown=cmd)


def stream_job(start_job, kind: str, argv: list[str], cwd, env: dict, parse_json: bool = False, label: str = "",
               shown: list[str] | None = None) -> dict:
    """A process as a job of the server: stdout and stderr lines go to the job log as they come, its exit code (and,
    with parse_json, its parsed stdout) to the job. The same kind twice attaches to the running one (the same command
    line twice is one job); cancel() stops the process and what it started."""
    holder: dict = {}

    def go(log):
        pr = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                              start_new_session=not IS_WIN)
        holder["proc"] = pr
        err = threading.Thread(target=lambda: [log(line.rstrip("\n")) for line in pr.stderr], daemon=True)
        err.start()
        lines = []
        for line in pr.stdout:
            lines.append(line.rstrip("\n"))
            log(lines[-1])
        rc = pr.wait()
        err.join(timeout=5)
        result = None
        if parse_json:
            try:
                result = json.loads("\n".join(lines))
            except json.JSONDecodeError:
                pass
        return {"rc": rc, "result": result, "argv": shown or argv}

    job = start_job(kind, label or " ".join(argv), go)
    PROCS[job["id"]] = holder
    return job


def cancel(job_id: str) -> dict:
    pr = PROCS.get(job_id, {}).get("proc")
    if pr is None or pr.poll() is not None:
        raise KeyError(job_id)
    if IS_WIN:                  # the command and what it started (agents, npm, git): Windows has no process groups
        run(["taskkill", "/PID", str(pr.pid), "/T", "/F"], check=False, quiet=True)
    else:
        try:
            os.killpg(pr.pid, signal.SIGTERM)
        except OSError:
            pr.terminate()
    return {"cancelling": job_id}
