"""What a pull request does to the docs, without AI (R27). The pages whose cited code (`x-sources`) the PR changes,
checked against the fingerprints in docs/.work/fresh.json: left out of date by this PR, or already out of date at
its base. One PR/MR comment, found by its marker and updated in place. It warns; it never fails a pipeline (H27)."""
from __future__ import annotations

import json, os
import urllib.error, urllib.request

from .common import repo_dir, run
from . import docs
from .harness import freshness

MARKER = "<!-- camaron:docs-fresh -->"

T = {
    "en": {
        "title": "Docs affected by this PR",
        "intro": "This PR changes code that {n} documentation page(s) describe. Once it is merged, agents stop reading "
                 "them until someone refreshes them or confirms they still hold.",
        "head": "| Page | State | Code |", "before": "Already out of date before this PR (the code it changes had moved on):",
        "how": "Refresh them with `camaron fresh --plan` (adds a unit an agent works on), or, if a page still holds, "
               "`camaron fresh --ack <page> --by <name>`.",
        "none": "No documented code changed in this PR.",
        "generated": "Pages marked ⚙ are generated from the code: `camaron blocks` refreshes them, no AI needed.",
    },
    "es": {
        "title": "Documentación afectada por esta PR",
        "intro": "Esta PR cambia código que describen {n} página(s) de la documentación. Cuando se fusione, los agentes "
                 "dejarán de leerlas hasta que alguien las actualice o confirme que siguen siendo válidas.",
        "head": "| Página | Estado | Código |",
        "before": "Ya estaban desactualizadas antes de esta PR (el código que cambia ya había cambiado):",
        "how": "Actualízalas con `camaron fresh --plan` (añade una unidad para un agente) o, si una página sigue siendo "
               "válida, `camaron fresh --ack <página> --by <nombre>`.",
        "none": "Esta PR no cambia código documentado.",
        "generated": "Las páginas marcadas con ⚙ se generan desde el código: `camaron blocks` las actualiza, sin IA.",
    },
}


def _git(repo, *args: str) -> str | None:
    r = run(["git", "-C", str(repo), *args], check=False, capture=True)
    return r.stdout if r.returncode == 0 else None


def changed_files(repo: str, base: str, head: str = "HEAD") -> list[str]:
    d = repo_dir(repo)
    out = _git(d, "diff", "--name-only", f"{base}...{head}")
    if out is None:                                 # no merge base (shallow clone): compare the trees directly
        out = _git(d, "diff", "--name-only", base, head) or ""
    return sorted({l.strip() for l in out.splitlines() if l.strip()})


def _reader_at(base: str):
    def read(repo, path):
        text = _git(repo_dir(repo), "show", f"{base}:{path}") if repo else None
        return text.splitlines() if text is not None else None
    return read


def impact(repo: str, base: str | None = None, files: list[str] | None = None, head: str | None = None) -> dict:
    """{repo, base, files, pages: [{path, title, trust, state, since: pr|before, code}]} for the pages citing the files
    this PR changes; pages whose cited code only moved or was reformatted are left out. `head` is the PR's commit when
    it is not checked out (read from git); default: the working tree."""
    files = sorted(set(files)) if files is not None else changed_files(repo, base or "main", head or "HEAD")
    at_head = _reader_at(head) if head else None
    touched = set(files)
    rows = {r["path"]: r for r in docs.collect()}
    pages_now = freshness._pages()
    freshness.stamp_all(pages_now)                  # pages never fingerprinted get their baseline, as `fresh` does
    data = freshness._load()["pages"]
    at_base = _reader_at(base) if base else None
    pages = []
    for logical, (fm, _) in sorted(pages_now.items()):
        mine = [s for s in freshness._sources(fm) if freshness.parse(s)[0] == repo and freshness.parse(s)[1] in touched]
        if not mine:
            continue
        stamps = (data.get(logical) or {}).get("sources", {})
        now = {s: freshness.check_source(s, stamps.get(s), at_head) for s in mine}
        hit = [s for s, r in now.items() if r != "fresh"]
        if not hit:
            continue
        before = at_base and any(freshness.check_source(s, stamps.get(s), at_base) != "fresh" for s in hit)
        r = rows.get(logical, {})
        pages.append({"path": logical, "title": r.get("title", logical), "trust": r.get("trust", "draft"),
                      "state": "stale" if "missing" in now.values() else "suspect", "since": "before" if before else "pr",
                      "generated": bool(fm.get("x-generated")),
                      "code": freshness.code_paths(hit)})
    return {"repo": repo, "base": base, "files": files, "pages": pages}


def comment(result: dict, lang: str = "en") -> str:
    t = T.get(lang, T["en"])
    new = [p for p in result["pages"] if p["since"] == "pr"]
    old = [p for p in result["pages"] if p["since"] == "before"]
    lines = [MARKER, f"### {t['title']}", ""]
    if not result["pages"]:
        return "\n".join(lines + [t["none"]]) + "\n"
    row = lambda p: (f"| `{p['path']}`{' ⚙' if p.get('generated') else ''} | {p['state']} | "  # noqa: E731
                     + ", ".join(f"`{c}`" for c in p["code"]) + " |")
    if new:
        lines += [t["intro"].format(n=len(new)), "", t["head"], "|---|---|---|", *map(row, new), ""]
    if old:
        lines += [t["before"], "", t["head"], "|---|---|---|", *map(row, old), ""]
    lines.append(t["how"])
    if any(p.get("generated") for p in result["pages"]):
        lines += ["", t["generated"]]
    return "\n".join(lines) + "\n"


# ---------- posting ----------
def _target(env: dict) -> dict | None:
    if env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_TOKEN") and env.get("GITHUB_REPOSITORY"):
        number = env.get("PR_NUMBER")
        if not number and env.get("GITHUB_EVENT_PATH"):
            try:
                with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
                    number = str((json.load(fh).get("pull_request") or {}).get("number") or "")
            except (OSError, ValueError):
                number = ""
        if not number:
            return None
        api = env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        base = f"{api}/repos/{env['GITHUB_REPOSITORY']}/issues"
        return {"list": f"{base}/{number}/comments?per_page=100", "create": f"{base}/{number}/comments",
                "update": lambda i: f"{base}/comments/{i}", "edit": "PATCH",
                "headers": {"Authorization": f"Bearer {env['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}}
    if env.get("GITLAB_CI") == "true" and env.get("DOCS_BOT_TOKEN") and env.get("CI_MERGE_REQUEST_IID"):
        base = f"{env['CI_API_V4_URL'].rstrip('/')}/projects/{env['CI_PROJECT_ID']}/merge_requests/{env['CI_MERGE_REQUEST_IID']}/notes"
        return {"list": f"{base}?per_page=100", "create": base, "update": lambda i: f"{base}/{i}", "edit": "PUT",
                "headers": {"PRIVATE-TOKEN": env["DOCS_BOT_TOKEN"]}}
    return None


def post(body: str, env: dict | None = None, opener=urllib.request.urlopen, affected: bool = True,
         marker: str = MARKER) -> str:
    """created | updated | skipped | not in a PR … | failed: …  — never raises."""
    env = dict(os.environ) if env is None else env
    target = _target(env)
    if not target:
        return "not in a PR/MR pipeline with a token: comment not posted"

    def call(method, url, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={**target["headers"], **({"Content-Type": "application/json"} if data else {})})
        with opener(req, timeout=20) as r:
            return json.loads(r.read() or b"null")
    try:
        existing = next((c["id"] for c in call("GET", target["list"]) or [] if marker in (c.get("body") or "")), None)
        if existing is not None:
            call(target["edit"], target["update"](existing), {"body": body})
            return "updated"
        if not affected:
            return "skipped"
        call("POST", target["create"], {"body": body})
        return "created"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"failed: {e}"
