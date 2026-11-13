"""What the static scans and the builds give the portal and the app: the libraries, the data models, the health
snapshot, the CI files, the code maps and the viewers; and the jobs that build them (first look, C4, graphs, wikis)."""
from __future__ import annotations

from lib import docs, env, plan
from lib.app import portal_views, services
from lib.core.paths import DOCS
from lib.core.process import which
from lib.interfaces.http.jobs import JOB_LOCK, JOBS, claim_job, fail_job, run_job, start_job
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


def api_schemas() -> dict:
    """Each repo's tables and collections (lib/schemas.py) with the same markdown its data page holds. `page`: its
    data page, else its repo page (the new layout), else None."""
    from lib import pages, schemas
    out = []
    for name, r in schemas.scan().items():
        page = next((p for p in (schemas.PAGE.format(repo=name), pages.REPO_PAGE.format(repo=name))
                     if (DOCS / p).is_file()), None)
        out.append({"repo": name, "tools": r["tools"], "stores": [{"kind": s["kind"], "engines": s["engines"],
                                                                   "entities": s["entities"]} for s in r["stores"]],
                    "entities": sum(len(s["entities"]) for s in r["stores"]), "markdown": schemas.block_body(r),
                    "page": page})
    return {"repos": out}


def schemas_write() -> dict:
    """The portal's Data view button: the data pages (old layout) or the pages from the code (new layout)."""
    from lib import genblocks, pages, schemas
    write = schemas.write_pages if pages.layout() == "old" else pages.write
    written = write(log=lambda _: None)
    genblocks.refresh()
    docs.llms()
    return {"written": written}


def api_inventory() -> dict:
    """The last inventory (docs/.work/inventory.json), or a fresh scan of the manifests when there is none yet."""
    from lib import inventory
    return inventory.load() or inventory.scan()


def inventory_job(b: dict) -> dict:
    from lib import inventory
    cves = bool(b.get("cves"))
    return start_job("inventory", "Libraries" + (" + vulnerabilities" if cves else ""),
                     lambda log: bool(inventory.run(log=log, cves=cves)))


def first_look(log) -> bool:
    """A fresh project's first pages without AI, from the static scan: the C4 draft, the stack and tools, the project
    home and a page per repo (an old-layout project: the first-look, data and diagram pages instead), llms.txt; then
    the C4 explorer when LikeC4 is installed. What the empty Docs and Architecture tabs offer."""
    from lib import diagrams, inventory, pages, quickarch, radar, schemas
    new = pages.layout() == "new"
    quickarch.save(quickarch.draft(log=log), page=not new)          # the new layout has no first-look.md
    radar.run(log=log)
    inventory.run(log=log)
    if new:
        try:
            pages.write(log=log)
        except Exception as e:  # noqa: BLE001 — the pages are a bonus: llms.txt and the C4 build still run
            log(f"⚠ pages skipped: {e}")
    else:
        schemas.write_pages(log=log)
        try:
            diagrams.write_pages(log=log)
        except Exception as e:  # noqa: BLE001 — the diagrams are a bonus: llms.txt and the C4 build still run
            log(f"⚠ diagrams skipped: {e}")
    docs.llms()
    if which("likec4"):
        services.current().viewers.build_c4(log=log)
    wrote = "index.md, a page per repo" if new else "architecture/first-look.md, architecture/system-map.md"
    log(f"✔ first look written: {wrote}, overview/tooling.md and the C4 draft")
    return True


def build(b: dict) -> dict:
    what, repo = b.get("what"), b.get("repo") or ""
    if what == "first-look":
        return start_job("first-look", "First look (no AI)", first_look)
    if what == "c4":
        return start_job("c4", "C4 explorer", lambda log: services.current().viewers.build_c4(log=log))
    if what == "graph":
        return start_job("graph", "Code graphs", lambda log: services.current().viewers.build_graphs(log=log))
    if what == "wiki-graph" and repo in docs.repo_names():
        # a kind per repo: start_job attaches a second start of the same kind to the running job, whatever the repo
        return start_job(f"wiki-graph:{repo}", f"Wiki graph {repo}", lambda log: env.wiki_graph(repo, log=log))
    raise ValueError(f"unknown build {what!r}")


def wiki(b: dict) -> dict:
    """`choose`: add the repo to the ones with a wiki (its plan unit comes back); `starter`: write a starter brief
    (no AI) when repo-brief has not written one. The card says both before the click. One wiki runs at a time: while
    another repo's runs, the answer is {"error": "busy", "repo"} and nothing is chosen or written (the same repo
    attaches to its run). The run is claimed before choosing and writing, in the same step as that check, so a second
    repo clicked while the first one is still being prepared is busy too."""
    repo, mode, engine = b.get("repo", ""), b.get("mode", ""), b.get("engine", "")
    if repo not in docs.repo_names() or mode not in ("", "init", "update"):
        raise ValueError("unknown repo or mode")
    choose = repo not in docs.wiki_repos() and not env.wiki_pages(repo)
    if choose and not b.get("choose"):
        raise ValueError(f"{repo} is not chosen for a wiki")
    with JOB_LOCK:
        running = next((j for j in JOBS.values() if j["kind"] == "wiki" and j["status"] == "running"), None)
        if running and running.get("repo") != repo:
            return {"error": "busy", "repo": running.get("repo", "")}
        if running:
            return running
        job = claim_job("wiki", f"OpenWiki {repo}", repo=repo)
    try:
        if choose:
            docs.set_wiki_repos([*docs.wiki_repos(), repo])
            plan.sync()
        if b.get("starter"):
            env.starter_brief(repo)
    except Exception as e:
        fail_job(job, e)
        raise
    return run_job(job, lambda log: env.openwiki_generate(repo, mode, log, engine))


@route("GET", "/api/inventory")
def get_inventory(req: Request) -> Response:
    return json_response(api_inventory())


@route("POST", "/api/inventory", access=Access.APP)
def post_inventory(req: Request) -> Response:
    return json_response(inventory_job(req.body))


@route("GET", "/api/schemas")
def get_schemas(req: Request) -> Response:
    return json_response(api_schemas())


@route("POST", "/api/schemas", access=Access.APP)
def post_schemas(req: Request) -> Response:
    return json_response(schemas_write())


@route("GET", "/api/health")
def get_health(req: Request) -> Response:
    from lib import health                  # a read: the snapshot `camaron health` or the app built, never a build
    return json_response({"snapshot": health.load()})


@route("GET", "/api/ci")
def get_ci(req: Request) -> Response:
    from lib import ci
    return json_response(ci.status())


@route("POST", "/api/ci", access=Access.APP)
def post_ci(req: Request) -> Response:
    from lib import ci
    b = req.body
    if b.get("forge") not in ("github", "gitlab"):
        raise ValueError("forge: github or gitlab")
    env.install_ci(b["forge"], log=lambda _: None)
    return json_response(ci.status(b["forge"]))


@route("GET", "/api/codemap")
def get_codemap(req: Request) -> Response:
    m = portal_views.code_map(req.query.get("repo", ""))
    return json_response(m) if m else json_response({"error": "no code map"}, 404)


@route("GET", "/api/viewers")
def get_viewers(req: Request) -> Response:
    return json_response(req.services.viewers.viewers())


@route("GET", "/api/wikis")
def get_wikis(req: Request) -> Response:
    return json_response(env.wikis())


@route("POST", "/api/build", access=Access.APP)
def post_build(req: Request) -> Response:
    return json_response(build(req.body))


@route("POST", "/api/wiki", access=Access.APP)
def post_wiki(req: Request) -> Response:
    r = wiki(req.body)
    return json_response(r, 409 if r.get("error") == "busy" else 200)
