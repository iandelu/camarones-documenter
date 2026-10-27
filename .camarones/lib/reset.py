"""`docs reset`: start an older project's documentation again, one of two ways.

redo — nothing is deleted: every finished unit that writes docs is reopened (`plan.redo`), so the next run reviews and
updates each page with today's playbook.
wipe — the generated docs go and the plan starts over, as on a fresh install. Kept: workspace.yaml, the interviews
(docs/interview/, and the interview units with their checkpoints stay done), every page a person wrote or confirmed
(`x-owner: human` or any `x-confirmed`, with its translations), files that are not pages (images…), the board and the
team's review and usage records. Before anything goes, cam-docs is committed and tagged `camaron/pre-reset-<stamp>`
(`git checkout <tag> -- docs` brings any page back); a cam-docs without git, or with changes git would not commit,
gets a .zip as well. The static pages are written again from the code (no AI) and the reset is its own commit.

--templates (both modes): PLAYBOOK, CONVENTIONS and the page skeletons follow the kit again even where the team edited
them; the team's text stays next to each as <name>.before-reset-<stamp>."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .common import CAM_DIR, CAM_LAYOUT, DOCS, ROOT, WORK, WS_FILE, load_json, out, rel_file, run as run_cmd
from . import docs, env, plan

MODES = ("redo", "wipe")
KEEP_TYPES = {"setup", "ci", "questionnaire", "answers", *plan.INTERVIEW_TYPES}   # stay done in both modes
WORK_FILES = ("fresh.json", "ai-drafts.json", "handoff.md", "next-prompt.md", "autopilot-prompt.md", "inventory.json")
NOTES = "interview"                                   # docs/interview/: the interviews' notes and open questions
TAG = "camaron/pre-reset-"


def guard() -> str | None:
    """Why the docs must not be reset now, or None."""
    if not WS_FILE.exists():
        return f"{ROOT} is not a Camarones project (no .camarones/workspace.yaml) — nothing to reset."
    if not CAM_LAYOUT:
        return f"This project uses the pre-3.0 layout (no {CAM_DIR}/): run `migrate` first, then reset."
    from .harness import scheduler
    holder = scheduler.busy()
    if holder:
        return (f"A documentation run is in progress ({holder.get('what', 'run')}, pid {holder.get('pid')}): "
                "wait for it or stop it, then reset.")
    lock = load_json(env.WIKI_LOCK, {}) if env.WIKI_LOCK.exists() else {}
    pid = lock.get("pid") if isinstance(lock, dict) else None
    if pid and env.pid_alive(int(pid)):
        return f"An OpenWiki run is in progress ({lock.get('repo')}, pid {pid}): wait for it to finish, then reset."
    return None


# ---------- what goes ----------
def persons(f: Path) -> bool:
    """A page a person owns: `x-owner: human` or any `x-confirmed` (as `pages` reads it)."""
    from .pages import _persons
    try:
        return bool(_persons(docs.split_fm(f.read_text(encoding="utf-8", errors="replace"))[0]))
    except OSError:
        return True


def _template_copy(f: Path) -> bool:
    """Still exactly what the kit's templates wrote (spec.c4, handoff.md…): deleting it would only copy it back."""
    t = env.TEMPLATES / f.relative_to(ROOT)
    try:
        return t.is_file() and f.read_text(encoding="utf-8") == env.fill(t.read_text(encoding="utf-8"),
                                                                         docs.workspace()["project"]["name"])
    except (OSError, UnicodeDecodeError, ValueError):
        return False


def _kept_page(f: Path) -> bool:
    rel = f.relative_to(DOCS)
    if rel.parts[0] == "i18n" and len(rel.parts) > 2:              # a translation lives as long as its page
        canon = DOCS.joinpath(*rel.parts[2:])
        if canon.relative_to(DOCS).parts[0] == NOTES or (canon.exists() and persons(canon)):
            return True
    return persons(f)


def doomed() -> tuple[list[Path], list[Path]]:
    """(files wipe deletes, a person's pages it keeps), in path order. Pages and the C4 model go; notes, other files
    and the hidden .work/ state are left to the rest of the reset."""
    gone, kept = [], []
    if DOCS.is_dir():
        for f in sorted(DOCS.rglob("*")):
            rel = f.relative_to(DOCS)
            if not f.is_file() or rel.parts[0] == NOTES or any(p.startswith(".") for p in rel.parts) \
                    or _template_copy(f):
                continue
            if f.suffix == ".md":
                (kept if _kept_page(f) else gone).append(f)
            elif f.suffix == ".c4":
                gone.append(f)
    for r in docs.repo_names():
        w = docs.wiki_dir(r)
        if not w.is_dir():
            continue
        for f in sorted(w.rglob("*")):
            if f.is_file() and not f.is_symlink():
                (kept if f.suffix == ".md" and persons(f) else gone).append(f)
    return gone, kept


def work_files() -> list[Path]:
    """The run state of the old docs: freshness, drafts, handoff, the last documented commits and the checkpoints of
    every unit that starts over."""
    files = [WORK / n for n in WORK_FILES] + [DOCS / ".state.json"]
    keep = {plan.note_file(u["id"]).name.split(".", 1)[0] for u in plan.load()["units"] if u["type"] in KEEP_TYPES}
    units = WORK / "units"
    if units.is_dir():
        files += [f for f in sorted(units.iterdir()) if f.is_file() and f.name.split(".", 1)[0] not in keep]
    return [f for f in files if f.exists() and not _template_copy(f)]


def redo_targets() -> list[dict]:
    return [u for u in plan.load()["units"] if u["status"] == "done" and u["type"] not in KEEP_TYPES]


def restarted() -> list[dict]:
    """The units wipe sends back to todo (or removes, when a later unit created them, like flows)."""
    return [u for u in plan.load()["units"] if u["type"] not in KEEP_TYPES and u["status"] != "todo"]


# ---------- preview ----------
def preview(mode: str, templates: bool = False) -> tuple[list[str], list[str]]:
    """(what changes, what is kept) as lines for the person to read before saying yes."""
    if mode == "redo":
        steps = [f"reopen {u['id']} — {plan.title(u)}" for u in redo_targets()]
        kept = ["every page and the C4 model: nothing is deleted, the agents review and update them",
                "the interviews and setup (they stay done)"]
    else:
        gone, persons_pages = doomed()
        steps = ["back up: commit and tag cam-docs as " + TAG + "<date>" if (ROOT / ".git").exists()
                 else "back up: a .zip of cam-docs (it has no git)"]
        steps += [f"delete {rel_file(f)}" for f in gone + work_files()]
        n = len(restarted())
        steps += [f"plan: {n} unit(s) start over (the interviews and setup stay done)"] if n else []
        steps += ["write the pages from the code again (no AI), the templates and llms.txt"]
        kept = [f"{rel_file(f)} (a person's page)" for f in persons_pages]
        kept += [f"{CAM_DIR}/docs/{NOTES}/ (the interviews' notes)", f"{CAM_DIR}/.camarones/workspace.yaml",
                 "images and other files that are not pages", "the board, the review comments and the usage records"]
    if templates:
        steps += [f"templates: .camarones/{n} follows the kit again (yours kept as {n}.before-reset-<date>)"
                  for n in env.edited_kit_docs()]
    return steps, kept


# ---------- doing it ----------
def _stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _dirty() -> bool:
    return bool(out(["git", "status", "--porcelain", "--", "docs", "wikis"], cwd=ROOT))


def backup(stamp: str) -> dict:
    """Commit and tag cam-docs; a .zip too when there is no git or git keeps something uncommitted (a secret scan
    that refused the checkpoint)."""
    tag = zipped = None
    if (ROOT / ".git").exists():
        env.checkpoint_commit("before docs reset")
        if run_cmd(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=ROOT, check=False, quiet=True).returncode == 0 \
                and run_cmd(["git", "tag", TAG + stamp], cwd=ROOT, check=False, quiet=True).returncode == 0:
            tag = TAG + stamp
    if tag is None or _dirty():
        from . import uninstall
        zipped = str(uninstall.backup_zip(uninstall.BACKUP_DIR))
    return {"tag": tag, "zip": zipped}


def _delete(files: list[Path]) -> None:
    for f in files:
        f.unlink(missing_ok=True)
    for d in sorted({p.parent for p in files}, key=lambda p: len(p.parts), reverse=True):
        while d not in (DOCS, WORK, ROOT / "wikis") and d.is_dir() and not any(d.iterdir()) \
                and not any(d == docs.wiki_dir(r) for r in docs.repo_names()):      # a wiki folder: a repo links to it
            d.rmdir()
            d = d.parent


@plan.locked
def _restart_plan() -> int:
    """Only the kept units survive; `sync` adds every other unit of the pipeline back as todo."""
    data = plan.load()
    n = len(data["units"])
    data["units"] = [u for u in data["units"] if u["type"] in KEEP_TYPES]
    plan.save(data)
    plan.sync()
    return n - len(data["units"])


def _log(text: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    with plan.LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"- {plan.now()} {text}\n")


def _regenerate(log) -> None:
    env.init_templates(log=lambda _: None)            # the template pages and spec.c4 a wipe removed
    try:
        from . import genblocks, pages
        pages.write(log=lambda _: None)
        genblocks.refresh()
    except Exception as e:  # noqa: BLE001 — the reset is done; the pages from the code can be written later
        log(f"⚠ the pages from the code were not written ({e}): run `pages`")
    docs.collect()
    docs.llms()


def run(mode: str, templates: bool = False, log=lambda _: None) -> dict:
    if mode not in MODES:
        raise ValueError(f"mode: one of {', '.join(MODES)}")
    stamp, result = _stamp(), {"mode": mode, "reopened": [], "deleted": [], "templates": [], "tag": None, "zip": None}
    if mode == "redo":
        ids = [u["id"] for u in redo_targets()]
        if ids:
            plan.redo(ids[0], ids[1:])
        result["reopened"] = ids
    else:
        result.update(backup(stamp))
        gone = doomed()[0] + work_files()
        _delete(gone)
        result["deleted"] = [rel_file(f) for f in gone]
        result["restarted"] = _restart_plan()
    if templates:
        result["templates"] = env.sync_kit_docs(aside=f"before-reset-{stamp}")
    if mode == "wipe":
        _regenerate(log)
    _log(f"docs reset ({mode})")
    env.checkpoint_commit(f"docs reset ({mode})")
    return result


def main(mode: str, dry_run: bool = False, yes: bool = False, templates: bool = False) -> int:
    why = guard()
    if why:
        print(why)
        return 1
    name = docs.workspace()["project"]["name"]
    what = {"redo": "redo: reopen every finished unit to review and update its pages",
            "wipe": "wipe: delete the generated docs and start the plan over"}[mode]
    print(f"Reset the docs of {name} — {what}\n")
    steps, kept = preview(mode, templates)
    if not steps:
        print("Nothing to do: no unit is finished yet.")
        return 0
    for s in steps:
        print(f"  • {s}")
    print("\nKept:")
    for k in kept:
        print(f"  · {k}")
    if dry_run:
        print("\n(dry run — nothing changed)")
        return 0
    if not yes:
        try:
            if mode == "wipe":
                ok = input(f"\nType the project name ({name}) to confirm: ").strip().casefold() == name.strip().casefold()
            else:
                ok = input("\nReopen these units? [y/N] ").strip().casefold() in ("y", "yes", "s", "si", "sí")
        except EOFError:
            ok = False
        if not ok:
            print("Cancelled — nothing changed.")
            return 1
    r = run(mode, templates, log=print)
    if mode == "redo":
        print(f"\n✔ {len(r['reopened'])} unit(s) reopened: run the plan to review and update their pages.")
    else:
        print(f"\n✔ {len(r['deleted'])} file(s) deleted, the plan starts over: run the plan to document again.")
        if r["tag"]:
            print(f"   The old docs: git tag {r['tag']} (`git checkout {r['tag']} -- docs` brings a page back)")
        if r["zip"]:
            print(f"   Backup of {CAM_DIR}/: {r['zip']}")
    for t in r["templates"]:
        print(f"   templates: {t} follows the kit again")
    return 0
