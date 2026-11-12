"""Before the CLI parses anything: `new`, `join` and `switch` create, join or pick a project and restart the script in
it, and a global install run outside a project picks one first, unless the command says it needs none."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

from lib import projects                            # no dependency on ROOT/common state
from lib.interfaces.cli import registry

LEGACY_NO_PROJECT: frozenset[str] = frozenset()


def _relaunch(root: Path, argv: list[str], entry: str) -> None:
    """Restart this script with CAMARONES_ROOT set, so every module that captured ROOT at import
    time (docs, env, wizard, …) sees the right project from the start. Mirrors lib/upgrade.py's
    own relaunch-after-swap trick — module-level globals can't be hot-reloaded mid-process."""
    os.environ["CAMARONES_ROOT"] = str(root)
    args = [sys.executable, entry, *argv]
    if os.name == "nt":
        sys.exit(subprocess.run(args).returncode)
    os.execv(sys.executable, args)


def _team(fn, *args, no_open: bool):
    """new --from / join: a clone that fails (no access, wrong URL, folder taken) is a short error, not a traceback.
    Access is checked first with plain git; a token is asked only when that fails and there is a terminal to ask in.
    The desktop app has none: it passes the token in CAMARONES_JOIN_TOKEN (never on the command line) and, with
    --no-open, gets why access failed as one JSON line on stdout."""
    url = args[-1] if fn is projects.create else args[0]
    token = os.environ.get("CAMARONES_JOIN_TOKEN") or None
    offer = [token]                                                 # one-shot: a refused token is not offered twice

    def env_token(host, again):                                     # `again` is also true when a SAVED token was refused
        t, offer[0] = offer[0], None
        return t
    ask = projects.ask_token if sys.stdin.isatty() else env_token if token else None
    if url.strip() and not projects.connect(url, ask=ask, log=lambda m: print(m, file=sys.stderr)):
        if no_open:
            from lib import creds
            reason, detail = projects.reach(url)
            print(json.dumps({"error": reason or "unknown", "host": creds.host_of(projects.clean_remote(url)) or "",
                              "detail": detail.replace(token, "***") if token else detail}, ensure_ascii=False))
        sys.exit(1)
    try:
        return fn(*args)
    except (ValueError, RuntimeError) as e:
        print(f"✖ {e}", file=sys.stderr)
        if no_open and isinstance(e, projects.Taken):               # the app words it: a stable code, not this line
            print(json.dumps({"error": "taken", "detail": str(e)}, ensure_ascii=False))
        sys.exit(1)


def needs_project(rest: list[str]) -> bool:
    """Whether a global install run outside a project picks one before running `rest` (argv after the script)."""
    if not rest:
        return True
    cmd = registry.find(registry.load(), rest[0])
    if cmd is not None:
        return cmd.needs_project(rest[1:])
    return rest[0] not in LEGACY_NO_PROJECT and rest[:2] != ["board", "merge-driver"]


def prelaunch(argv: list[str], entry: str) -> None:
    """`argv` is sys.argv, edited in place (--no-open goes); may exit, or restart `entry` in another project."""
    cmd0 = argv[1] if len(argv) > 1 else None
    # --no-open (the desktop app's hub): create or join, print {"path": …} and stop instead of opening the wizard.
    no_open = cmd0 in ("new", "join") and "--no-open" in argv
    if no_open:
        argv.remove("--no-open")
    if cmd0 == "new" and len(argv) > 2 and not argv[2].startswith("-"):
        from_url = argv[argv.index("--from") + 1] if "--from" in argv[3:-1] else ""
        dest = _team(projects.create, argv[2], None, from_url, no_open=no_open)
        if no_open:
            print(json.dumps({"path": str(dest)}))
            sys.exit(0)
        print(f"🦐 {dest.name} → {dest}")
        _relaunch(dest, [], entry)
    elif cmd0 == "join" and len(argv) > 2 and not argv[2].startswith("-"):
        # The team's cam-docs repo: cloned into <folder or cwd>/cam-docs, or reused if this machine already has it.
        # The wizard then only prepares this machine (tools, repos) — the rest is the team's, already done.
        dest, joined = _team(projects.join, argv[2], Path(argv[3]).resolve() if len(argv) > 3 else Path.cwd(),
                             no_open=no_open)
        if no_open:
            print(json.dumps({"path": str(dest), "joined": joined}))
            sys.exit(0)
        print(f"🦐 {'joined' if joined else 'new project, remote set'} → {dest}")
        _relaunch(dest, [], entry)
    elif cmd0 == "switch":
        dest = projects.pick(allow_new=True, here=Path.cwd())
        if dest is None:
            sys.exit(1)
        _relaunch(dest, [], entry)
    elif (cmd0 == "init" and os.environ.get("CAMARONES_GLOBAL")
          and not os.environ.get("CAMARONES_ROOT") and not projects.find_marker(Path.cwd())):
        # Global install, run from inside an existing repos folder (or an empty one): adopt THIS folder as the
        # workspace — docs and agent config go to ./cam-docs, the repos stay where they are.
        _relaunch(projects.adopt(Path.cwd()), ["init"], entry)
    elif os.environ.get("CAMARONES_GLOBAL") and not os.environ.get("CAMARONES_ROOT"):
        # Only the global launcher (install-global.cmd/.sh) sets CAMARONES_GLOBAL — a project-local
        # launcher (legacy co-located kit copy) must keep resolving ROOT exactly as before (KIT.parent),
        # even on its very first run before workspace.yaml exists, with no picker involved.
        marker = projects.find_marker(Path.cwd())
        if marker:
            projects.touch(marker)
        elif needs_project(argv[1:]):
            dest = projects.pick(allow_new=True, here=Path.cwd())
            if dest is None:
                sys.exit(1)
            _relaunch(dest, argv[1:], entry)
