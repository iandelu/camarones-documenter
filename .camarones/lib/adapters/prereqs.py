"""The Toolchain port (lib/ports/toolchain.py) on the machine's prerequisites and the kit's pinned tools: the Node.js
major, the OS package manager's install of a prereq, the version of a tool on PATH, `npm install -g`, and whether a
pinned tool (OpenWiki, gitleaks, the npm and uv ones) is the pinned one."""
from __future__ import annotations

import re
from pathlib import Path

from lib import binaries
from lib.common import HOME, IS_MAC, IS_WIN, VERSIONS, ensure_path, load_json, out, run, sdkman_dir, which
from lib.ports import Log


def node_major() -> int:
    v = out(["node", "-v"])
    m = re.match(r"v(\d+)", v)
    return int(m.group(1)) if m else 0


def install_prereq(name: str, log: Log = print) -> bool:
    """Best-effort install with the OS package manager. Returns True if a command ran successfully."""
    cmds: dict[str, list[list[str]]] = {}
    if IS_WIN and which("winget"):
        base = ["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements", "--id"]
        cmds = {"git": [base + ["Git.Git"]], "node": [base + ["OpenJS.NodeJS.LTS"]],
                "docker": [base + ["Docker.DockerDesktop"]]}
    elif IS_MAC and which("brew"):
        cmds = {"git": [["brew", "install", "git"]], "node": [["brew", "install", "node@22"], ["brew", "link", "--overwrite", "node@22"]],
                "docker": [["brew", "install", "--cask", "docker"]]}
    if name == "java":
        if (sdkman_dir() / "bin" / "sdkman-init.sh").exists() and not IS_WIN:
            cmds["java"] = [["bash", "-c", f'source "{sdkman_dir()}/bin/sdkman-init.sh" && yes | sdk install java']]
        elif IS_MAC and which("brew"):
            cmds["java"] = [["brew", "install", "openjdk@21"]]
        elif IS_WIN and which("winget"):
            cmds["java"] = [["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements",
                             "--id", "EclipseAdoptium.Temurin.21.JDK"]]
    npm_cli = {"claude": [["npm", "install", "-g", "@anthropic-ai/claude-code"]],
               "codex": [["npm", "install", "-g", "@openai/codex"]]}
    cmds.update(npm_cli)
    if name not in cmds:
        return False
    for c in cmds[name]:
        log("$ " + " ".join(c))
        if run(c, check=False).returncode != 0:
            return False
    ensure_path()
    return True


# ---------- pinned tools ----------
def tool_version(name: str) -> str:
    m = re.search(r"\d+\.\d+\.\d+", out([name, "--version"]))
    return m.group(0) if m else ""


def npm_global(pkg: str, log: Log) -> None:
    if run(["npm", "install", "-g", pkg], check=False, quiet=True).returncode != 0:
        if IS_WIN:
            raise RuntimeError(f"npm install -g {pkg} failed")
        log(f"  npm -g needs permissions: installing {pkg} into ~/.local")
        run(["npm", "install", "-g", "--prefix", str(HOME / ".local"), pkg], quiet=True)
        ensure_path()


def npm_global_version(exe: Path, name: str) -> str:
    """The version of the global package behind a command, "" when its package.json is not where `npm install -g` puts
    it: on POSIX the command links into <prefix>/lib/node_modules/<name>/, on Windows a shim sits beside
    node_modules/<name>/."""
    for folder in (exe.parent / "node_modules" / name, *(p for p in exe.resolve().parents if p.name == name)):
        try:
            meta = load_json(folder / "package.json", {})
        except OSError:
            continue
        if isinstance(meta, dict) and meta.get("name") == name:
            return str(meta.get("version") or "")
    return ""


def openwiki_installed() -> bool:
    """The pinned OpenWiki is what the command runs. The portal asks on every page load and `npm ls -g` takes seconds,
    so npm only answers for a command whose package is elsewhere (a version manager's shim)."""
    exe = which("openwiki")
    if not exe:
        return False
    found = npm_global_version(Path(exe), "openwiki")
    if found:
        return found == VERSIONS["openwiki"]
    r = run(["npm", "ls", "-g", "--depth=0", f"openwiki@{VERSIONS['openwiki']}"], check=False, quiet=True)
    if r.returncode == 0:
        return True
    r = run(["npm", "ls", "-g", "--prefix", str(HOME / ".local"), "--depth=0", f"openwiki@{VERSIONS['openwiki']}"],
            check=False, quiet=True)
    return r.returncode == 0


def tool_ok(name: str) -> bool:
    if name == "openwiki":
        return openwiki_installed()
    if name == "quality":
        return tool_ok("mmdc") and tool_ok("gitleaks")
    if name == "gitleaks":
        return binaries.pinned_path("gitleaks").is_file()
    return tool_version(name) == VERSIONS[name]
