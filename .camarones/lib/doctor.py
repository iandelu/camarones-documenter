"""`camaron doctor` as data: the prerequisites of this machine, the pinned tools and the kit files or links that
drifted, each with the catalog command that fixes it (lib/catalog.py), so the desktop app can offer the button and
the CLI prints the same facts."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .common import CACHE, VERSIONS, WS_FILE
from . import env

INSTALLABLE = ("git", "node", "docker", "java", "claude", "codex")   # env.install_prereq knows how, per OS
PINNED = ("graphify", "likec4", "mmdc")                               # versions read from the tool itself
CACHE_FILE = CACHE / "doctor.json"     # the last check, so the app shows it at once and checks again on request


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


def check(log=print) -> dict:
    """report(), kept with its time (UTC) in the project's cache: what the desktop app reads instead of running the
    checks (seconds of version probes) on every visit."""
    log("checking prerequisites, pinned tools and the kit's files…")
    rec = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "result": report()}
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    p = problems(rec["result"])
    log(f"missing: {', '.join(p['missing']) or '—'} · tools: {', '.join(p['tools']) or '—'} · drift: {p['drift']}")
    return rec


def checked() -> dict | None:
    """The last check(), or None (never checked here, or a cache that does not read)."""
    try:
        rec = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) and "result" in rec else None


def problems(result: dict) -> dict:
    """What needs doing, for the Summary: needed prerequisites missing, pinned tools missing or off, files drifted."""
    return {"missing": [p["name"] for p in result.get("prerequisites", []) if p.get("need") and not p.get("ok")],
            "tools": [t["name"] for t in result.get("tools", []) if not t.get("ok")],
            "drift": len(result.get("drift", []))}


def install(name: str, log=print) -> bool:
    if name not in INSTALLABLE:
        raise ValueError(f"{name}: one of {', '.join(INSTALLABLE)}")
    return env.install_prereq(name, log=log)
