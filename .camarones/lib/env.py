"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import json, os, re, shutil
from pathlib import Path

from .common import KIT, ROOT, DOCS, CACHE, IS_WIN, out, ws_rel
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
