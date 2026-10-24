"""`camaron doctor` as data: the prerequisites of this machine, the pinned tools and the kit files or links that
drifted, each with the catalog command that fixes it (lib/catalog.py), so the desktop app can offer the button and
the CLI prints the same facts."""
from __future__ import annotations

from .common import VERSIONS, WS_FILE
from . import env

INSTALLABLE = ("git", "node", "docker", "java", "claude", "codex")   # env.install_prereq knows how, per OS
PINNED = ("graphify", "likec4", "mmdc")                               # versions read from the tool itself


def report() -> dict:
    pre = [{"name": k, "ok": bool(v["ok"]), "need": bool(v["need"]), "found": v.get("found", ""), "hint": v["hint"],
            "note": v.get("note", ""), "fix": None if v["ok"] or k not in INSTALLABLE else
            {"cmd": "doctor", "args": {"install": k}}} for k, v in env.prerequisites().items()]
    tools = []
    for name in PINNED:
        found = env.tool_version(name)
        tools.append({"name": name, "found": found, "pinned": VERSIONS[name], "ok": found == VERSIONS[name]})
    tools.append({"name": "openwiki", "found": "ok" if env.openwiki_installed() else "", "pinned": VERSIONS["openwiki"],
                  "ok": env.openwiki_installed()})
    tools.append({"name": "gitleaks", "found": "ok" if env.tool_ok("gitleaks") else "", "pinned": VERSIONS["gitleaks"],
                  "ok": env.tool_ok("gitleaks")})
    for t in tools:
        t["fix"] = None if t["ok"] else {"cmd": "setup", "args": {}}
    drift = []
    if WS_FILE.exists():
        from . import install_state
        drift = install_state.drift()
    return {"prerequisites": pre, "tools": tools, "drift": drift, "fix_drift": {"cmd": "repair", "args": {}}}


def install(name: str, log=print) -> bool:
    if name not in INSTALLABLE:
        raise ValueError(f"{name}: one of {', '.join(INSTALLABLE)}")
    return env.install_prereq(name, log=log)
