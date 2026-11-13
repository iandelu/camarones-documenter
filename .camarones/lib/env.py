"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import json, os, re, shutil, subprocess
from pathlib import Path

from .common import KIT, ROOT, DOCS, CACHE, IS_WIN, run, out, which, ws_rel
from . import docs
from .app import services
from .harness.locks import pid_alive  # noqa: F401  (pid_alive re-exported)
from .ports import Log
from .projects import git_failure  # noqa: F401  (git_failure re-exported)



# ---------- portal: static export (what CI deploys) ----------
def forge_edit_base() -> str:
    """https://…/-/edit/<branch>/ (GitLab) or …/edit/<branch>/ (GitHub) for the cam-docs repo, '' without a remote."""
    url = out(["git", "remote", "get-url", "origin"], cwd=ROOT)
    if not url:
        return ""
    url = re.sub(r"^git@([^:]+):", r"https://\1/", url).removesuffix(".git")
    url = re.sub(r"^https://[^@/]+@", "https://", url)
    branch = out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT) or "main"
    return f"{url}/edit/{branch}/" if "github" in url else f"{url}/-/edit/{branch}/"


def export_site(log: Log = print) -> Path:
    """The same portal app, read-only: HTML + JSON snapshots of the API, the viewers and the libraries they need.
    No npm build — any static host (nginx image, GitLab/GitHub Pages) serves it."""
    from . import quality
    from .app import portal_views
    quality.assert_no_secrets()
    writable(CACHE)
    site, tmp = CACHE / "site", CACHE / "site.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(portal_views.UI, tmp)
    html = (tmp / "index.html").read_text(encoding="utf-8")
    (tmp / "index.html").write_text(html.replace('content="live"', 'content="static"'), encoding="utf-8")
    docs.llms()
    shutil.copyfile(DOCS / "llms.txt", tmp / "llms.txt")
    shutil.copyfile(DOCS / "llms-full.txt", tmp / "llms-full.txt")
    api = tmp / "api"

    def dump(rel: str, data) -> None:
        f = api / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    t = portal_views.tree()
    t["editBase"] = forge_edit_base()
    langs = [""] + t["langs"]
    index = []
    for d in t["docs"]:
        decisions = portal_views.covering(d["path"])
        for lang in langs:
            doc = portal_views.read(d["path"], lang)
            if lang and not doc["exists"]:
                continue
            doc["decisions"] = decisions
            dump(f"doc/{lang or '_'}/{d['path']}.json", doc)
            index.append({"path": d["path"], "lang": lang, "title": doc["title"], "trust": d["trust"],
                          "text": docs.split_fm(doc["raw"])[1][:20000]})
    log(f"✔ {len(t['docs'])} docs" + (f" + translations ({', '.join(t['langs'])})" if t["langs"] else ""))
    images = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
    folders = [(DOCS, tmp / "raw")] + [(docs.wiki_dir(n), tmp / "raw" / "wikis" / n) for n in docs.repo_names()]
    for src, out_dir in folders:                    # a wiki page's images: raw/wikis/<repo>/… as the server serves them
        for f in (src.rglob("*") if src.is_dir() else ()):
            if f.is_file() and f.suffix.lower() in images:
                dst = out_dir / f.relative_to(src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dst)
    if "likec4" in services.current().components.components() and (not (services.current().viewers.VIEWERS / "architecture" / "index.html").exists() or services.current().viewers.viewers()["c4"]["stale"]):
        services.current().viewers.build_c4(log=log)
    if (services.current().viewers.VIEWERS / "architecture").is_dir():
        shutil.copytree(services.current().viewers.VIEWERS / "architecture", tmp / "architecture")
    if "graphify" in services.current().components.components() and not services.current().viewers.code_graphs():
        services.current().viewers.graph(rebuild=False, log=log)
    for n, f in services.current().viewers.code_graphs().items():
        dst = tmp / "code-graph" / ("" if n == "all" else n) / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
    log(f"✔ code graphs ({len(services.current().viewers.code_graphs())})")
    for w in services.current().wiki.wikis():
        if w["pages"] and (not w["graph"] or w["graphStale"]):
            services.current().wiki.wiki_graph(w["repo"], log=log)
        if (services.current().viewers.VIEWERS / "wiki-graph" / w["repo"]).is_dir():
            shutil.copytree(services.current().viewers.VIEWERS / "wiki-graph" / w["repo"], tmp / "wiki-graph" / w["repo"])
    t["codeGraphs"] = list(services.current().viewers.code_graphs())
    dump("tree.json", t)
    dump("status.json", portal_views.status())
    dump("wikis.json", services.current().wiki.wikis())
    dump("viewers.json", services.current().viewers.viewers())
    from . import codemap
    for n in codemap.available():
        dump(f"codemap/{n}.json", codemap.load(n))
    dump("search.json", index)
    for lib in portal_views.UI_LIBS:
        f = docs.vendor_file(*lib)
        if f:
            dst = tmp / "vendor" / f"{lib[0]}@{lib[1]}" / lib[2]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
    k, failed = docs.vendor(tmp)
    log(f"✔ offline libraries ({k + len(portal_views.UI_LIBS)})" + (f" — still on CDN: {failed}" if failed else ""))
    shutil.rmtree(site, ignore_errors=True)
    tmp.rename(site)
    services.current().containers.image_context()
    log(f"✔ portal exported → {ws_rel('.camarones/.cache/site')}")
    return site


portal = export_site


def portal_steps() -> int:
    wikis_n = sum(1 for n in docs.repo_names() if services.current().wiki.wiki_pages(n))
    c4 = 1 if (services.current().diagrams.arch_dir() / "likec4.config.json").exists() else 0
    return 4 + 2 * c4 + 2 * wikis_n


def writable(d: Path) -> None:
    """A cache left behind by a `sudo` run would make every later build fail half-way with a bare PermissionError."""
    if IS_WIN or not d.exists():
        return
    uid = os.getuid()
    bad = [p for p in (d, *d.iterdir()) if p.stat().st_uid != uid]
    if bad:
        raise RuntimeError(f"{bad[0]} belongs to another user (an earlier run with sudo?). Fix it with:\n"
                           f"  sudo chown -R $(whoami) \"{d}\"")


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


# ---------- CI ----------
def detect_forge() -> str:
    urls = " ".join(r.get("url", "") for r in docs.workspace()["repos"])
    urls += " " + out(["git", "-C", str(ROOT), "remote", "get-url", "origin"])
    if "github" in urls:
        return "github"
    return "gitlab"


def install_ci(forge: str | None = None, log: Log = print) -> Path:
    forge = forge or detect_forge()
    if forge == "github":
        dst = ROOT / ".github" / "workflows" / "docs.yml"
        src = KIT / "ci" / "umbrella.github.yml"
    else:
        dst = ROOT / ".gitlab-ci.yml"
        src = KIT / "ci" / "umbrella.gitlab-ci.yml"
        if dst.exists() and "camarones" not in dst.read_text(encoding="utf-8"):
            dst = ROOT / ".gitlab-ci.camarones.yml"
            log("  existing .gitlab-ci.yml kept: add `include: local: .gitlab-ci.camarones.yml` to it")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    snippet = f"repo.{'github.yml' if forge == 'github' else 'gitlab-ci.yml'}"
    (ROOT / ".camarones" / "ci").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KIT / "ci" / snippet, ROOT / ".camarones" / "ci" / snippet)   # service repos include it from here
    from . import ci
    fresh = ROOT / ".camarones" / "ci" / ci.FILES[forge]
    fresh.write_text(ci.render(forge), encoding="utf-8", newline="\n")      # generated from lib/ci.py, ci: in workspace.yaml
    log(f"  ✔ {dst.relative_to(ROOT)} (docs repo pipeline)")
    log(f"  → per-repo snippet: .camarones/ci/{snippet}")
    log(f"  → per-repo pull request check (no AI): .camarones/ci/{ci.FILES[forge]}")
    proposal = ci.render_propose(forge)
    if proposal:                                    # ci.target: self-hosted — the AI job runs on the team's runner
        (ROOT / ".camarones" / "ci" / ci.FILES_PROPOSE[forge]).write_text(proposal, encoding="utf-8", newline="\n")
        log(f"  → per-repo docs proposal (AI, self-hosted runner): .camarones/ci/{ci.FILES_PROPOSE[forge]}")
    return dst
