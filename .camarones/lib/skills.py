"""The agent skills the kit ships (`templates/skills/<name>/`) and the team's own copies of them in
`cam-docs/.camarones/skills/<name>/`: which exist, which one wins and the raw text of each. Pure reading, no rendering.
Imports only `.common`: anything more would join the kit's largest import cycle."""
from __future__ import annotations

import difflib
import re
import shutil
from datetime import datetime
from pathlib import Path

from .common import DOCS, KIT, ROOT, VERSIONS, load_json, save_json

KIT_SKILLS: Path = KIT / "templates" / "skills"
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_FRONT_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_DESC_RE = re.compile(r"^description:[ \t]*(.*?)[ \t]*$", re.M)


def _legacy() -> bool:
    return (ROOT / ".camarones").resolve() == KIT.resolve()


def team_dir() -> Path | None:
    return None if _legacy() else ROOT / ".camarones" / "skills"


def stamp_path() -> Path | None:
    return None if _legacy() else ROOT / ".camarones" / ".kit-skills.json"


def load_stamp() -> dict:
    p = stamp_path()
    data = load_json(p, {}) if p else {}
    if not isinstance(data, dict) or not isinstance(data.get("forks"), dict):
        return {"forks": {}}
    return data


def save_stamp(data: dict) -> None:
    p = stamp_path()
    if p is not None:
        save_json(p, data)


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _tree(folder: Path) -> dict[str, str]:
    return {f.relative_to(folder).as_posix(): _read(f) for f in sorted(folder.rglob("*")) if f.is_file()}


def kit_names() -> list[str]:
    if not KIT_SKILLS.is_dir():
        return []
    return sorted(d.name for d in KIT_SKILLS.iterdir() if d.is_dir())


def kit_files(name: str) -> dict[str, str]:
    d = KIT_SKILLS / name
    return _tree(d) if d.is_dir() else {}


def _team_folders() -> list[Path]:
    t = team_dir()
    if t is None or not t.is_dir():
        return []
    return sorted((d for d in t.iterdir() if d.is_dir() and not d.name.startswith(".")), key=lambda d: d.name)


def team_names() -> list[str]:
    return [d.name for d in _team_folders() if NAME_RE.fullmatch(d.name) and (d / "SKILL.md").is_file()]


def ignored() -> list[dict]:
    out = []
    for d in _team_folders():
        if not NAME_RE.fullmatch(d.name):
            out.append({"name": d.name, "why": "invalid name"})
        elif not (d / "SKILL.md").is_file():
            out.append({"name": d.name, "why": "no SKILL.md"})
    return out


def origin(name: str) -> str | None:
    if name in team_names():
        return "team" if name in kit_names() else "team-only"
    return "kit" if name in kit_names() else None


def sources() -> dict[str, dict[str, str]]:
    out = {}
    for name in sorted(set(kit_names()) | set(team_names())):
        if origin(name) in ("team", "team-only"):
            out[name] = _tree(team_dir() / name)
        else:
            out[name] = kit_files(name)
    return out


def description(name: str) -> str:
    text = sources().get(name, {}).get("SKILL.md", "")
    front = _FRONT_RE.match(text)
    found = _DESC_RE.search(front.group(1)) if front else None
    return found.group(1).strip("'\"") if found else ""


def fork(name: str) -> Path:
    t = team_dir()
    if t is None:
        raise ValueError("team copies need the cam-docs layout")
    if name not in kit_names():
        raise ValueError(f"{name} is not a kit skill")
    dest = t / name
    if dest.exists():
        raise ValueError(f"{name} already has a team copy")
    files = kit_files(name)
    for rel, text in files.items():
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    stamp = load_stamp()
    stamp["forks"][name] = {"files": files, "kit": VERSIONS["kit"]}
    save_stamp(stamp)
    return dest


def _udiff(old: dict[str, str], new: dict[str, str], a: str, b: str) -> str:
    out = []
    for rel in sorted(set(old) | set(new)):
        out.extend(difflib.unified_diff(old.get(rel, "").splitlines(), new.get(rel, "").splitlines(),
                                        f"{a}/{rel}", f"{b}/{rel}", lineterm=""))
    return "\n".join(out)


def diff(name: str, against_fork: bool = False) -> str:
    if against_fork:
        fork_files = load_stamp()["forks"].get(name, {}).get("files")
        if fork_files is None:
            raise ValueError(f"{name} was not forked with skills fork")
        if name not in kit_names():
            raise ValueError(f"{name} has no kit version")
        return _udiff(fork_files, kit_files(name), "fork", "kit")
    if origin(name) not in ("team", "team-only"):
        raise ValueError(f"no team copy of {name}")
    if name not in kit_names():
        raise ValueError(f"{name} has no kit version")
    return _udiff(kit_files(name), _tree(team_dir() / name), "kit", "team")


def reset(name: str, now: str | None = None) -> Path:
    o = origin(name)
    if o == "team-only":
        raise ValueError(f"{name} is a team skill: delete its folder to remove it")
    if o != "team":
        raise ValueError(f"no team copy of {name}")
    base = f"{name}-{now or datetime.now().strftime('%Y%m%d-%H%M%S')}"
    aside = team_dir() / ".reset" / base
    n = 2
    while aside.exists():
        aside = team_dir() / ".reset" / f"{base}-{n}"
        n += 1
    aside.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(team_dir() / name), str(aside))
    stamp = load_stamp()
    stamp["forks"].pop(name, None)
    save_stamp(stamp)
    return aside


def outdated() -> list[str]:
    forks = load_stamp()["forks"]
    return sorted(n for n in team_names() if origin(n) == "team" and n in forks
                  and forks[n].get("files") != kit_files(n))


SOURCES = ("retro", "review", "board")
_NOTE_RE = re.compile(r"^- (\S+) · (\S+) · step (.*?) · change (.*?) · ref (.*?) · (.*?) — (.*)$")
_NOTE_KEYS = ("date", "source", "step", "change", "ref", "by")


def notes_dir() -> Path:
    return DOCS / ".work" / "skill-notes"


def _field(value: str) -> str:
    return (value or "").replace(" · ", " - ").replace(" — ", " - ").strip() or "-"


def format_note(n: dict) -> str:
    f = {k: _field(n.get(k, "")) for k in _NOTE_KEYS}
    text = " ".join(n.get("text", "").split())
    return (f"- {f['date']} · {f['source']} · step {f['step']} · change {f['change']} · ref {f['ref']} · "
            f"{f['by']} — {text}")


def parse_note(line: str) -> dict | None:
    m = _NOTE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    vals = [("" if v == "-" else v) for v in m.groups()[:6]]
    return {**dict(zip(_NOTE_KEYS, vals)), "text": m.group(7)}


def add_note(skill: str, text: str, source: str, by: str, step: str = "", change: str = "", ref: str = "",
             today: str | None = None) -> Path:
    if origin(skill) is None:
        raise ValueError(f"unknown skill: {skill}")
    if source not in SOURCES:
        raise ValueError("source must be one of: " + ", ".join(SOURCES))
    if not " ".join(text.split()):
        raise ValueError("empty note")
    path = notes_dir() / f"{skill}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = format_note({"date": today or datetime.now().strftime("%Y-%m-%d"), "source": source, "step": step,
                        "change": change, "ref": ref, "by": by, "text": text})
    header = ""
    if not path.exists():
        header = (f"# Skill notes: {skill}\n\nWhere the `{skill}` skill got in the way. One line per note, "
                  "added with `camaron skills note`.\n\n")
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(header + line + "\n")
    return path


def notes(skill: str | None = None) -> list[dict]:
    files = [notes_dir() / f"{skill}.md"] if skill else sorted(notes_dir().glob("*.md"))
    out = []
    for f in files:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            n = parse_note(line)
            if n:
                out.append({**n, "skill": f.stem})
    return sorted(out, key=lambda n: n["date"], reverse=True)
