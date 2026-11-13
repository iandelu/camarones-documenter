"""The local portal: serving it (live editor, static export, Docker), its address and token, and stopping it."""
from __future__ import annotations

import os
import re
import subprocess

from lib import docs
from lib.app import services
from lib.common import CACHE, IS_WIN, KIT, ROOT, run, which
from lib.ports import Log


def project_id() -> str:
    return docs.workspace()["project"].get("id") or re.sub(r"[^a-z0-9]+", "-", ROOT.name.lower()).strip("-") or "project"


def compose_cmd() -> list[str]:
    """For servers/CI: `docker compose -f .camarones/portal/compose.yml` (always with an explicit file)."""
    return ["docker", "compose", "-f", str(KIT / "portal" / "compose.yml"), "-p", f"{project_id()}-docs"]


def docker_up(port: int = 8080, log: Log = print) -> str:
    """Plain `docker build` + `docker run`: no compose file or compose plugin needed (works with any Docker)."""
    ok, why = services.current().containers.docker_ready()
    if not ok:
        raise RuntimeError(why)
    stop_local()
    ctx = services.current().containers.image_context()
    pid = project_id()
    image, name = f"camarones-docs-{pid}:local", f"{pid}-docs"
    log("building the nginx image…")
    run(["docker", "build", "-t", image, str(ctx)], quiet=True)
    log("✔ image " + image)
    run(["docker", "rm", "-f", name], check=False, quiet=True)
    log(f"starting container {name} on port {port}…")
    r = run(["docker", "run", "-d", "--name", name, "--restart", "unless-stopped", "-p", f"{port}:80", image],
            check=False, quiet=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        if "port is already allocated" in err or "address already in use" in err:
            raise RuntimeError(f"port {port} is busy — choose another port")
        raise RuntimeError(f"docker run failed: {err[-1500:]}")
    url = f"http://localhost:{port}"
    log(f"✔ portal at {url}")
    return url


SERVE_PID = CACHE / "serve.pid"


def serve_local(port: int = 8080, log: Log = print) -> str:
    """Serve the exported (read-only) portal without Docker — what the deployed one looks like."""
    if not (CACHE / "site" / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — export it first (Portal → Export / `portal`)")
    return serve_editor(port, log, static=True)


def serve_editor(port: int = 8080, log: Log = print, static: bool = False) -> str:
    """The default portal: a local server (no Docker, no npm) that renders docs/ live and lets people edit,
    confirm, comment, commit and rebuild the viewers. Detached, so it outlives the wizard; `down` stops it."""
    stop_local()
    import secrets, socket, sys, time
    with socket.socket() as sck:
        if sck.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} is busy — choose another port")
    CACHE.mkdir(parents=True, exist_ok=True)
    token = "" if static else secrets.token_urlsafe(24)       # the machine token: lets this browser write the board
    penv = {k: v for k, v in os.environ.items() if k != "CAMARONES_PORTAL_TOKEN"}
    kw: dict = {"stdout": subprocess.DEVNULL, "stdin": subprocess.DEVNULL,
                "stderr": (CACHE / "serve.log").open("w", encoding="utf-8"),
                "env": {**penv, "CAMARONES_ROOT": str(ROOT), **({"CAMARONES_PORTAL_TOKEN": token} if token else {})}}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    cmd = [sys.executable, str(KIT / "camarones.py"), "up", "--foreground", "--port", str(port)] + (["--static"] if static else [])
    pr = subprocess.Popen(cmd, **kw)
    SERVE_PID.write_text(str(pr.pid), encoding="utf-8")
    for _ in range(20):
        time.sleep(0.25)
        if pr.poll() is not None:
            raise RuntimeError("the portal server did not start — see " + str(CACHE / "serve.log"))
        with socket.socket() as sck:
            if sck.connect_ex(("127.0.0.1", port)) == 0:
                break
    url = portal_url(port, token or None)       # the static export takes no writes (POST is 405): no token
    log(f"✔ portal at {url}" + (" (read-only export, no Docker)" if static else " (live: read · edit · confirm · review)"))
    return url


def portal_url(port: int, token: str | None = None, route: str = "") -> str:
    """The portal address with ONE fragment: `#<route>&cam-token=<token>` (route like `#/c4`, optional), or
    `#cam-token=<token>` without a route. The frontend takes `cam-token` out of the fragment and keeps the route."""
    parts = [p for p in (route.lstrip("#"), f"cam-token={token}" if token else "") if p]
    return f"http://localhost:{port}/" + (("#" + "&".join(parts)) if parts else "")


def portal_token(url: str) -> str | None:
    m = re.search(r"[#&]cam-token=([\w-]+)", url)
    return m.group(1) if m else None


def stop_local() -> bool:
    if not SERVE_PID.exists():
        return False
    try:
        pid = int(SERVE_PID.read_text().strip())
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except (ValueError, OSError):
        pass
    SERVE_PID.unlink(missing_ok=True)
    return True


def docker_down() -> None:
    stop_local()
    if which("docker"):
        run(["docker", "rm", "-f", f"{project_id()}-docs"], check=False, quiet=True)
        run([*compose_cmd(), "down"], cwd=ROOT, check=False, quiet=True)   # installs from older kits
