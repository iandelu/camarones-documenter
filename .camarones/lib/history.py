"""Git history, no AI (X11): what each repo's log says about where change happens and who knows it — hotspots, people
by name (no emails), files that change together, work that spans repos through a shared ticket key, and how commits
are written — into docs/overview/history.md (and its translations). Read locally with `git log`; nothing leaves."""
from __future__ import annotations

import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from .common import DOCS, repo_dir, out
from . import docs

LOGICAL = "overview/history.md"
PAGE = DOCS / LOGICAL
NOISE = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|Cargo\.lock|go\.sum|"
                   r"gradle\.lockfile|composer\.lock|Gemfile\.lock|CHANGELOG\.md)$|(^|/)(dist|build|target|vendor)/")
MANIFEST = re.compile(r"(^|/)(pom\.xml|package\.json|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|angular\.json|"
                      r"tsconfig[\w.-]*\.json|\.eslintrc[\w.]*|requirements[\w.-]*\.txt|pyproject\.toml|go\.mod|"
                      r"Dockerfile|docker-compose[\w.-]*\.ya?ml|README\.md|readme\.md)$")
BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions", re.I)
CONVENTIONAL = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]*\))?!?: ")
TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

TEXT = {
    "en": {"title": "Change history",
           "description": "Hotspots, who changed each repo, files that change together and commit conventions, read "
                          "from git history without AI.",
           "tldr": "Where the code changed in the last {m} months and who changed it, read from git without AI.",
           "busiest": "The busiest repo is `{r}`: start with the hotspots and ask the people listed for each repo.",
           "none": "No repo with git history in that period yet.",
           "empty": "No commits in the last {m} months. Try a longer period: `camaron history --months {m2}`.",
           "hot": "Hotspots", "hot_lede": "The files changed in the most commits: where bugs and questions tend to be.",
           "ask": "Who to ask", "ask_lede": "The people with the most commits per repo, and the folder they touch most.",
           "together": "Changed together",
           "together_lede": "Files that keep changing in the same commit (build files left out): a change to one "
                            "usually needs the other.",
           "across": "Work that spans repos (the same ticket in commits of each):",
           "conv": "Commit conventions",
           "cols": ("Repo", "File", "Commits", "Person", "Works most in", "Files", "Times", "Ticket", "Repos",
                    "Conventional commits", "With a ticket key"),
           "footer": "Regenerate with `camaron history --months {m}`; bots and lockfiles are left out."},
    "es": {"title": "Historial de cambios",
           "description": "Puntos calientes, quién cambia cada repo, ficheros que cambian juntos y convenciones de "
                          "commit, leídos del historial de git sin IA.",
           "tldr": "Dónde cambió el código en los últimos {m} meses y quién lo cambió, leído de git sin IA.",
           "busiest": "El repo con más actividad es `{r}`: empieza por los puntos calientes y pregunta a las personas "
                      "de cada repo.",
           "none": "Todavía no hay repos con historial de git en ese periodo.",
           "empty": "No hay commits en los últimos {m} meses. Prueba un periodo más largo: "
                    "`camaron history --months {m2}`.",
           "hot": "Puntos calientes", "hot_lede": "Los ficheros con más commits: donde suelen estar los fallos y las dudas.",
           "ask": "A quién preguntar", "ask_lede": "Las personas con más commits en cada repo y la carpeta que más tocan.",
           "together": "Cambian juntos",
           "together_lede": "Ficheros que cambian en el mismo commit una y otra vez (sin los de build): cambiar uno "
                            "suele pedir cambiar el otro.",
           "across": "Trabajo que cruza repos (el mismo ticket en commits de cada uno):",
           "conv": "Convenciones de commit",
           "cols": ("Repo", "Fichero", "Commits", "Persona", "Dónde trabaja más", "Ficheros", "Veces", "Ticket", "Repos",
                    "Commits convencionales", "Con clave de ticket"),
           "footer": "Se regenera con `camaron history --months {m}`; sin bots ni lockfiles."},
}


def commits(repo: str, months: int) -> list[dict]:
    """The human commits of a repo in the last `months`, newest first, with the files each changed (lockfiles and build
    folders left out); empty when git cannot read the repo."""
    log = out(["git", "-C", str(repo_dir(repo)), "log", f"--since={months}.months", "--no-merges", "--no-renames",
               "--format=%x1e%aN%x09%s", "--name-only"])
    found = []
    for chunk in log.split("\x1e"):                                  # `out` strips the record mark in front of the first one
        if not chunk.strip():
            continue
        head, *files = chunk.strip("\n").split("\n")
        author, _, subject = head.partition("\t")
        if BOT.search(author):
            continue
        found.append({"author": author, "subject": subject,
                      "files": [f for f in files if f.strip() and not NOISE.search(f)]})
    return found


def _rank(counter: Counter) -> list[tuple]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def mine(months: int = 12, top: int = 10) -> dict:
    repos, keys = {}, {}
    for repo in docs.repo_names():
        if not (repo_dir(repo) / ".git").exists():
            continue
        found = commits(repo, months)
        files, owners, pairs, areas = Counter(), Counter(), Counter(), {}
        for c in found:
            files.update(set(c["files"]))
            owners[c["author"]] += 1
            code = sorted({f for f in c["files"] if not MANIFEST.search(f)})
            if 1 < len(code) <= 20:                                   # a sweeping commit says nothing about coupling
                pairs.update(combinations(code, 2))
            for f in code or c["files"]:                               # where they work, not the build files
                areas.setdefault(c["author"], Counter())[f.rpartition("/")[0] or "."] += 1
            for k in set(TICKET.findall(c["subject"])):
                keys.setdefault(k, set()).add(repo)
        repos[repo] = {"commits": len(found), "hotspots": _rank(files)[:top], "owners": _rank(owners)[:top],
                       "co_change": [p for p in _rank(pairs) if p[1] > 1][:top],
                       "areas": {a: _rank(c)[0][0] for a, c in areas.items()},
                       "conventional": (sum(1 for c in found if CONVENTIONAL.match(c["subject"])), len(found)),
                       "tickets": sum(1 for c in found if TICKET.search(c["subject"]))}
    across = sorted(((k, sorted(v)) for k, v in keys.items() if len(v) > 1), key=lambda kv: kv[0])
    return {"months": months, "repos": repos, "across": across}


def _short(path: str) -> str:
    parts = path.split("/")
    return path if len(parts) <= 4 else "/".join([parts[0], "…", *parts[-2:]])


def _pct(a: int, b: int) -> str:
    return f"{round(100 * a / b)} %" if b else "—"


def render(h: dict, lang: str = "en") -> str:
    t, m, repos = TEXT[lang], h["months"], h["repos"]
    c = t["cols"]
    busiest = max((kv for kv in repos.items() if kv[1]["commits"]), key=lambda kv: kv[1]["commits"],
                  default=(None, None))[0]
    lines = [f"# {t['title']}", "",
             f"> **TL;DR:** {t['tldr'].format(m=m)} " + (t["busiest"].format(r=busiest) if busiest else t["none"]), ""]
    if not busiest:
        return "\n".join(lines + [f"## {t['hot']}", "", t["empty"].format(m=m, m2=m * 2), ""])
    lines += [f"## {t['hot']}", "", t["hot_lede"], "", f"| {c[0]} | {c[1]} | {c[2]} |", "|---|---|---|"]
    lines += [f"| {r} | `{_short(f)}` | {n} |" for r, d in repos.items() for f, n in d["hotspots"][:5]]
    lines += ["", f"## {t['ask']}", "", t["ask_lede"], "", f"| {c[0]} | {c[3]} | {c[2]} | {c[4]} |", "|---|---|---|---|"]
    lines += [f"| {r} | {a} | {n} | `{_short(d['areas'].get(a, '.'))}` |"
              for r, d in repos.items() for a, n in d["owners"][:3]]
    lines += ["", f"## {t['together']}", "", t["together_lede"], "", f"| {c[0]} | {c[5]} | {c[6]} |", "|---|---|---|"]
    lines += [f"| {r} | `{_short(a)}` + `{_short(b)}` | {n} |" for r, d in repos.items() for (a, b), n in d["co_change"][:5]]
    if h["across"]:
        lines += ["", t["across"], "", f"| {c[7]} | {c[8]} |", "|---|---|"]
        lines += [f"| {k} | {', '.join(v)} |" for k, v in h["across"][:15]]
    lines += ["", f"## {t['conv']}", "", f"| {c[0]} | {c[2]} | {c[9]} | {c[10]} |", "|---|---|---|---|"]
    lines += [f"| {r} | {d['commits']} | {_pct(*d['conventional'])} | {_pct(d['tickets'], d['commits'])} |"
              for r, d in repos.items()]
    return "\n".join(lines + ["", t["footer"].format(m=m), ""])


def _fm(lang: str) -> dict:
    return {"type": "overview", "title": TEXT[lang]["title"], "description": TEXT[lang]["description"],
            "tags": ["history", "onboarding"], "x-owner": "ai"}


def write(months: int = 12) -> Path:
    h = mine(months)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    body = render(h)
    PAGE.write_text(docs.join_fm(_fm("en"), body), encoding="utf-8", newline="\n")
    sha = docs.body_sha(docs.split_fm(PAGE.read_text(encoding="utf-8"))[1])
    for lang in docs.workspace()["project"].get("translations", []):
        if lang in TEXT and lang != "en":
            tf = DOCS / "i18n" / lang / LOGICAL
            tf.parent.mkdir(parents=True, exist_ok=True)
            fm = {**_fm(lang), "x-translation-of": {"path": LOGICAL, "lang": lang, "body_sha": sha}}
            tf.write_text(docs.join_fm(fm, render(h, lang)), encoding="utf-8", newline="\n")
    return PAGE
