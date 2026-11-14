"""The project's templates: the files the kit copies into a project, the kit's skills rendered for each agent host, and
the playbook, conventions and page skeletons kept in step with the kit."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from lib import docs
from lib.app import services
from lib.common import (CACHE, CAM_DIR, CAM_LAYOUT, KIT, ROOT, cli_cmd, load_json, own_file, save_json, through_link)
from lib.ports import Log

TEMPLATES = KIT / "templates"


KIT_DOCS = ("PLAYBOOK.md", "CONVENTIONS.md")         # copied into the project so agents (and the team) can read them
KIT_DOCS_STAMP = ROOT / ".camarones" / ".kit-docs.json"


def _real(p: Path) -> bool:
    """Nothing from ROOT down to `p`, `p` included, is a link: reading or editing `p` in place stays in the project.
    Anyone who can push to cam-docs can commit a link, and these writers run before trust is asked."""
    return not through_link(ROOT, p)


def _own_file(p: Path) -> bool:
    """A file the kit writes whole (its config, its stamps): never through a linked folder, and a link at `p` itself
    is replaced by the file."""
    return own_file(ROOT, p)


def fill(text: str, name: str) -> str:
    return (text.replace("{{PROJECT_NAME}}", name).replace("{{CLI}}", cli_cmd())
            .replace("{{CAM}}", f"{CAM_DIR}/" if CAM_LAYOUT else ""))


def kit_skill_files(project_name: str | None = None) -> dict[str, str]:
    """cam-docs-relative path → text of the kit's own skills, rendered for this machine (Claude Code and Codex alike)."""
    name = project_name or docs.workspace()["project"]["name"]
    return {f"{host}/{src.relative_to(TEMPLATES).as_posix()}": fill(src.read_text(encoding="utf-8"), name)
            for src in sorted((TEMPLATES / "skills").rglob("*")) if src.is_file() for host in (".claude", ".agents")}


def skill_files(project_name: str | None = None) -> dict[str, str]:
    """Like kit_skill_files, but the effective skills: a team's copy of a skill wins, and a team-only skill is added."""
    from lib import skills
    name = project_name or docs.workspace()["project"]["name"]
    return {f"{host}/skills/{skill}/{rel}": fill(raw, name)
            for skill, files in skills.sources().items() for rel, raw in files.items() for host in (".claude", ".agents")}


RENDERED_SKILLS = CACHE / "skills-rendered.json"


def _real_skills_dir(d: Path) -> bool:
    """`d` is ROOT/<host>/skills or a folder in it, and nothing on the way down from ROOT is a link: a symlink (or a
    Windows junction, which only `resolve()` shows) committed at `.claude`, `.claude/skills` or deeper would carry a
    write or a delete out of the project."""
    try:
        parts = d.relative_to(ROOT).parts
    except ValueError:
        return False
    if len(parts) < 2 or parts[0] not in (".claude", ".agents") or parts[1] != "skills":
        return False
    return _real(d)


def _rendered_entry(rel) -> bool:
    """A manifest entry the cleanup may remove: `<host>/skills/<name>/…` inside ROOT/<host>/skills. The manifest is a
    file in the repo, so a teammate could commit one that names any other file."""
    from lib import skills
    if not isinstance(rel, str) or "\\" in rel:
        return False
    parts = rel.split("/")
    if (len(parts) < 4 or parts[0] not in (".claude", ".agents") or parts[1] != "skills"
            or not skills.NAME_RE.fullmatch(parts[2]) or any(p in ("", ".", "..") for p in parts)):
        return False
    return _real_skills_dir((ROOT / rel).parent)


def write_kit_skills(project_name: str | None = None) -> None:
    """Always refreshed: a copy edited in .claude/skills goes back to the effective text (the team's copy, else the
    kit's). What an earlier render wrote and the effective set no longer has is removed; foreign files stay.
    Nothing is read, written or deleted through a link (or a junction): one at a rendered file's path is replaced by
    the file; a skill whose `<host>`, `<host>/skills` or own folder is a link is not rendered in that host, the other
    host still is. The manifest of what was rendered is git-ignored, but a link force-added there arrives with a plain
    pull: a linked manifest is ignored and replaced, and a linked cache folder keeps none."""
    files, written = skill_files(project_name), []
    for rel, text in files.items():
        dst = ROOT / rel
        if not _real_skills_dir(dst.parent):
            continue
        if dst.is_symlink():
            services.current().links._unlink(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(rel)
    manifest = load_json(RENDERED_SKILLS, []) if _real(RENDERED_SKILLS) else []
    for rel in {r for r in (manifest if isinstance(manifest, list) else []) if _rendered_entry(r)} - set(files):
        gone = ROOT / rel
        if gone.is_file() or gone.is_symlink():
            gone.unlink()
        host_skills = ROOT / rel.split("/", 1)[0] / "skills"
        d = gone.parent
        while d != host_skills and _real_skills_dir(d) and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
    if _own_file(RENDERED_SKILLS):
        save_json(RENDERED_SKILLS, sorted(written))


def init_templates(project_name: str | None = None, log: Log = print) -> list[str]:
    """Copy templates that do not exist yet (never overwrites project files), plus the kit's playbook/conventions."""
    created = []
    name = project_name or docs.workspace()["project"]["name"]
    write_kit_skills(name)
    for src in sorted(TEMPLATES.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATES)
        if rel.parts[0] in ("skills", "skeletons", "board"):   # skills go to the agent hosts, skeletons via sync_kit_docs, board stays in the kit
            continue
        dst = ROOT / rel
        if not _real(dst):                                     # a link on the way or at dst, dangling too: left alone
            continue
        if dst.exists():
            if rel.as_posix() == "AGENTS.md":
                refresh_block(src, dst, project_name)
            elif rel.as_posix() == "CLAUDE.md":
                ensure_agents_import(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(fill(src.read_text(encoding="utf-8"), name), encoding="utf-8")
        created.append(rel.as_posix())
    created += sync_kit_docs()
    if not (ROOT / ".git").exists():
        subprocess.run(["git", "init", "-q", str(ROOT)])
        created.append(".git (docs repo)")
        from lib.kanban import ops
        created += ops.init(log=lambda _: None)             # a new project starts with its board (existing ones opt in)
    docs.write_gitignore()
    for c in created:
        log(f"  + {c}")
    return created


def ensure_agents_import(claude_md: Path) -> None:
    """A pre-existing CLAUDE.md (project notes) must still pull in the kit's AGENTS.md rules."""
    text = claude_md.read_text(encoding="utf-8")
    if "@AGENTS.md" not in text:
        claude_md.write_text("@AGENTS.md\n\n" + text, encoding="utf-8")


def _kit_doc_files() -> list[tuple[str, Path]]:
    files = [(n, KIT / n) for n in KIT_DOCS]
    return files + [(f"skeletons/{f.name}", f) for f in sorted((TEMPLATES / "skeletons").glob("*.md"))]


def _sha(f: Path) -> str | None:
    import hashlib
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None


def edited_kit_docs() -> list[str]:
    """PLAYBOOK/CONVENTIONS/skeletons the team edited since the last sync and that differ from this kit's."""
    if (ROOT / ".camarones").resolve() == KIT.resolve():
        return []
    stamp = load_json(KIT_DOCS_STAMP, {})
    return [n for n, src in _kit_doc_files()
            if (cur := _sha(ROOT / ".camarones" / n)) and cur != _sha(src) and stamp.get(n) != cur]


def sync_kit_docs(aside: str | None = None) -> list[str]:
    """Copy PLAYBOOK/CONVENTIONS and the page skeletons into the project's .camarones/ (versioned with the docs). A copy the team edited
    since the last sync is kept as is — only untouched copies follow kit upgrades. With `aside` (`docs reset --templates`)
    an edited copy follows the kit too, and the team's text stays next to it as <name>.<aside>."""
    if (ROOT / ".camarones").resolve() == KIT.resolve():
        return []                                   # legacy: the kit itself lives in this project
    stamp, changed = load_json(KIT_DOCS_STAMP, {}) if _real(KIT_DOCS_STAMP) else {}, []
    for n, src in _kit_doc_files():
        dst = ROOT / ".camarones" / n
        if not _own_file(dst):
            continue
        cur, new = _sha(dst), _sha(src)
        if cur == new:
            continue
        if cur and stamp.get(n) != cur:
            if not aside:
                continue
            if _own_file(kept := dst.with_name(f"{dst.name}.{aside}")):
                shutil.copyfile(dst, kept)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        stamp[n] = new
        changed.append(f".camarones/{n}")
    if _own_file(KIT_DOCS_STAMP):
        save_json(KIT_DOCS_STAMP, stamp)
    return changed


def refresh_block(src: Path, dst: Path, project_name: str | None = None) -> bool:
    """Kit upgrades: replace only the <!-- camarones:start/end --> block of an existing AGENTS.md (user text is kept)."""
    a, b = "<!-- camarones:start -->", "<!-- camarones:end -->"
    cur, tpl = dst.read_text(encoding="utf-8"), src.read_text(encoding="utf-8")
    if a not in cur or b not in cur or a not in tpl:
        return False
    block = fill(tpl[tpl.index(a):tpl.index(b) + len(b)], project_name or docs.workspace()["project"]["name"])
    new = cur[:cur.index(a)] + block + cur[cur.index(b) + len(b):]
    if new != cur:
        dst.write_text(new, encoding="utf-8")
        return True
    return False
