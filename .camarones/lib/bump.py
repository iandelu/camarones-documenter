"""Update one library of one service repo (the app's Libraries, `camaron bump`): the one place the kit writes into a
documented repo, and only when a person asks for that library. The change goes on a new branch
(`camaron/bump-<name>-<version>`) made by the repo's own package manager (npm, pnpm, yarn, uv, poetry, go), so its
lockfile follows; manifests without one (Maven, Gradle, requirements, a pyproject without a lock) get the version
rewritten in place. A repo with uncommitted changes is refused, nothing is committed or pushed, and an update that
fails leaves the repo as it was, on the branch it was on."""
from __future__ import annotations

import re
from pathlib import Path

from .common import repo_dir, run, which

VERSION = re.compile(r"v?[0-9A-Za-z][0-9A-Za-z.+_-]*")
NORM = lambda n: re.sub(r"[-_.]+", "-", n).lower()  # noqa: E731 — PEP 503 names
OPS = r"===|==|~=|!=|>=|<=|>|<"


def _row(repo: str, name: str, ecosystem: str | None) -> dict:
    from . import inventory
    rows = [r for r in inventory.scan_repo(repo, repo_dir(repo))
            if r["name"] == name and (not ecosystem or r["ecosystem"] == ecosystem)]
    if not rows:
        raise KeyError(f"{name} is not declared by {repo}")
    return rows[0]


def _npm(row: dict, cwd: Path, version: str) -> list[str]:
    declared = row["declared"]
    spec = f"{row['name']}@{declared[0]}{version}" if declared[:1] in ("^", "~") else f"{row['name']}@{version}"
    exact = declared[:1] not in ("^", "~")
    dev = row["scope"] == "dev"
    if (cwd / "pnpm-lock.yaml").is_file():
        return ["pnpm", "add", spec, *(["--save-exact"] if exact else []), *(["--save-dev"] if dev else [])]
    if (cwd / "yarn.lock").is_file():
        return ["yarn", "add", spec, *(["--exact"] if exact else []), *(["--dev"] if dev else [])]
    return ["npm", "install", spec, *(["--save-exact"] if exact else []), *(["--save-dev"] if dev else [])]


def _pypi(row: dict, cwd: Path, version: str) -> list[str] | None:
    pinned = row["declared"].startswith("==")
    dev = row["scope"] == "dev"
    if (cwd / "uv.lock").is_file():
        return ["uv", "add", f"{row['name']}{'==' if pinned else '>='}{version}", *(["--dev"] if dev else [])]
    if (cwd / "poetry.lock").is_file():
        return ["poetry", "add", f"{row['name']}{'==' if pinned else '@^'}{version}", *(["--group", "dev"] if dev else [])]
    return None


def _requirement(spec: str, name: str, version: str) -> str | None:
    """One PEP 508 requirement with its version set to `version` (its operator kept), or None if it names another."""
    m = re.match(rf"^(\s*)([A-Za-z0-9][\w.-]*)(\[[^\]]*\])?(\s*)((?:{OPS})\s*[^\s;#,]+(?:\s*,\s*(?:{OPS})\s*[^\s;#,]+)*)?(.*)$",
                 spec, re.S)
    if not m or NORM(m.group(2)) != NORM(name):
        return None
    current = m.group(5) or ""
    op = re.match(rf"({OPS})", current.strip())
    new = f"{op.group(1) if op and op.group(1) in ('==', '>=', '~=', '===') else '>='}{version}"
    return f"{m.group(1)}{m.group(2)}{m.group(3) or ''}{m.group(4)}{new}{m.group(6)}"


def _edit_python(text: str, name: str, version: str, requirements: bool) -> str:
    if requirements:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            body, hash_, comment = line.partition("#")
            if (new := _requirement(body, name, version)) is not None:
                lines[i] = new + hash_ + comment
                return "\n".join(lines)
    else:
        for m in re.finditer(r"([\"'])([^\"'\n]+)\1", text):
            if (new := _requirement(m.group(2), name, version)) is not None:
                return text[:m.start(2)] + new + text[m.end(2):]
    raise ValueError(f"{name}: not found in the manifest")


def _edit_maven(text: str, row: dict, version: str) -> str:
    group, artifact = row["name"].split(":", 1)
    declared = row["declared"]
    if not declared:
        raise ValueError(f"{row['name']}: its version comes from the parent {row.get('managedBy') or 'pom'}; "
                         "update the parent, or give the dependency a version of its own")
    if m := re.fullmatch(r"\$\{([\w.-]+)\}", declared):
        prop = re.escape(m.group(1))
        new, n = re.subn(rf"(<{prop}>)\s*[^<]*?\s*(</{prop}>)", rf"\g<1>{version}\g<2>", text, count=1)
        if n:
            return new
        raise ValueError(f"{row['name']}: the property {m.group(1)} is not in this pom (a parent sets it)")
    for block in re.finditer(r"<dependency>.*?</dependency>", text, re.S):
        b = block.group(0)
        if re.search(rf"<groupId>\s*{re.escape(group)}\s*</groupId>", b) and \
                re.search(rf"<artifactId>\s*{re.escape(artifact)}\s*</artifactId>", b):
            nb = re.sub(rf"<version>\s*{re.escape(declared)}\s*</version>", f"<version>{version}</version>", b, count=1)
            return text[:block.start()] + nb + text[block.end():]
    raise ValueError(f"{row['name']}: not found in the pom")


def _edit_gradle(text: str, row: dict, version: str, catalog: bool) -> str:
    old = row["declared"]
    if catalog:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if row["name"] in line and re.search(rf"[\"']{re.escape(old)}[\"']", line):
                lines[i] = re.sub(rf"([\"']){re.escape(old)}([\"'])", rf"\g<1>{version}\g<2>", line, count=1)
                return "\n".join(lines)
        raise ValueError(f"{row['name']}: its version is a reference in the catalog; change it in [versions]")
    new, n = re.subn(rf"{re.escape(row['name'])}:{re.escape(old)}\b", f"{row['name']}:{version}", text)
    if not n:
        raise ValueError(f"{row['name']}: not found in the build file")
    return new


def plan(repo: str, name: str, version: str, ecosystem: str | None = None) -> dict:
    """What an update would do, without doing it: the package manager's command (argv) or None when the manifest is
    rewritten in place, the branch, the manifest and the version it leaves."""
    if not VERSION.fullmatch(version or ""):
        raise ValueError(f"version: {version!r} is not a version")
    row = _row(repo, name, ecosystem)
    rel = row["source"].split(":", 1)[1]
    manifest = repo_dir(repo) / rel
    cwd, base, eco = manifest.parent, manifest.name, row["ecosystem"]
    if eco == "npm":
        argv = _npm(row, cwd, version)
    elif eco == "PyPI":
        argv = _pypi(row, cwd, version) if base == "pyproject.toml" else None
    elif eco == "Go":
        argv = ["go", "get", f"{name}@{version if version.startswith('v') else 'v' + version}"]
    elif eco == "Maven":
        argv = None
        if base == "pom.xml":
            _edit_maven(_read(manifest), row, version)     # refused now, not on the branch
        elif not base.startswith("build.gradle") and base != "libs.versions.toml":
            raise ValueError(f"{base}: updating it from here is not supported yet")
    else:
        raise ValueError(f"{eco}: updating it from here is not supported yet; change {rel} by hand")
    slug = re.sub(r"[^\w.-]+", "-", name.rsplit(":", 1)[-1].rsplit("/", 1)[-1]).strip("-")
    return {"repo": repo, "ecosystem": eco, "name": name, "from": row["version"] or row["declared"], "to": version,
            "scope": row["scope"], "manifest": f"{repo}/{rel}", "argv": argv, "branch": f"camaron/bump-{slug}-{version}",
            "_row": row, "_file": manifest}


def _read(f: Path) -> str:
    """The manifest as it is on disk, line endings included: a CRLF file stays CRLF."""
    with open(f, encoding="utf-8", newline="") as h:
        return h.read()


def _edit(p: dict) -> None:
    f, row, v = p["_file"], p["_row"], p["to"]
    text = _read(f)
    if p["ecosystem"] == "PyPI":
        new = _edit_python(text, p["name"], v, requirements=f.name != "pyproject.toml")
    elif f.name == "pom.xml":
        new = _edit_maven(text, row, v)
    else:
        new = _edit_gradle(text, row, v, catalog=f.name == "libs.versions.toml")
    with open(f, "w", encoding="utf-8", newline="") as h:
        h.write(new)


def _tool(argv: list[str], cwd: Path, log) -> int:
    r = run(argv, cwd=cwd, check=False, capture=True)
    for line in ((r.stdout or "") + (r.stderr or "")).splitlines():
        log(line)
    return r.returncode


def _git(repo: Path, *args: str) -> tuple[int, str]:
    r = run(["git", *args], cwd=repo, check=False, capture=True)
    return r.returncode, (r.stdout or "").strip()


def apply(repo: str, name: str, version: str, ecosystem: str | None = None, log=print) -> dict:
    p = plan(repo, name, version, ecosystem)
    where = repo_dir(repo)
    if _git(where, "rev-parse", "--is-inside-work-tree")[0]:
        raise RuntimeError(f"{repo} is not a git repo: nothing was changed")
    if _git(where, "status", "--porcelain")[1]:
        raise RuntimeError(f"{repo} has uncommitted changes: commit or stash them first; nothing was changed")
    if p["argv"] and not which(p["argv"][0]):
        raise RuntimeError(f"{p['argv'][0]} is not installed on this machine: nothing was changed")
    if not _git(where, "rev-parse", "--verify", "--quiet", f"refs/heads/{p['branch']}")[0]:
        raise RuntimeError(f"the branch {p['branch']} already exists in {repo}: nothing was changed")
    was = _git(where, "rev-parse", "--abbrev-ref", "HEAD")[1]
    if _git(where, "checkout", "-q", "-b", p["branch"])[0]:
        raise RuntimeError(f"could not create the branch {p['branch']} in {repo}")
    try:
        log(f"{repo}: {p['name']} {p['from']} → {version} on {p['branch']}")
        if p["argv"]:
            if rc := _tool(p["argv"], p["_file"].parent, log):
                raise RuntimeError(f"{' '.join(p['argv'])} failed (exit {rc}): the repo is back as it was")
        else:
            _edit(p)
        files = _git(where, "diff", "--name-only")[1].splitlines()
        if not files:
            raise RuntimeError(f"{p['name']} {version}: nothing changed in {repo}")
    except Exception:
        _git(where, "reset", "-q", "--hard")
        _git(where, "clean", "-fdq")
        _git(where, "checkout", "-q", was)
        _git(where, "branch", "-q", "-D", p["branch"])
        raise
    from . import inventory
    inventory.run(log=lambda _: None)
    log(f"✔ {', '.join(files)} changed on {p['branch']}: review it, run the tests, then commit and push")
    return {**{k: v for k, v in p.items() if not k.startswith("_")}, "was": was, "files": files}


def public(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}
