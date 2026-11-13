"""The static export of the portal (what CI deploys): the read-only site, its edit links and steps, and the check that
the cache can be written."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from lib import docs
from lib.app import components, services, viewers, wiki
from lib.common import CACHE, DOCS, IS_WIN, ROOT, out, ws_rel
from lib.ports import Log


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
    from lib import quality
    from lib.app import portal_views
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
    if "likec4" in components.components() and (not (viewers.VIEWERS / "architecture" / "index.html").exists() or viewers.viewers()["c4"]["stale"]):
        viewers.build_c4(log=log)
    if (viewers.VIEWERS / "architecture").is_dir():
        shutil.copytree(viewers.VIEWERS / "architecture", tmp / "architecture")
    if "graphify" in components.components() and not viewers.code_graphs():
        viewers.graph(rebuild=False, log=log)
    for n, f in viewers.code_graphs().items():
        dst = tmp / "code-graph" / ("" if n == "all" else n) / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
    log(f"✔ code graphs ({len(viewers.code_graphs())})")
    for w in wiki.wikis():
        if w["pages"] and (not w["graph"] or w["graphStale"]):
            wiki.wiki_graph(w["repo"], log=log)
        if (viewers.VIEWERS / "wiki-graph" / w["repo"]).is_dir():
            shutil.copytree(viewers.VIEWERS / "wiki-graph" / w["repo"], tmp / "wiki-graph" / w["repo"])
    t["codeGraphs"] = list(viewers.code_graphs())
    dump("tree.json", t)
    dump("status.json", portal_views.status())
    dump("wikis.json", wiki.wikis())
    dump("viewers.json", viewers.viewers())
    from lib import codemap
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
    wikis_n = sum(1 for n in docs.repo_names() if wiki.wiki_pages(n))
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
