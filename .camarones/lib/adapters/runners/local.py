"""`doctor --local` (H26): propose a free, open-weight model for bounded and judge work from this machine's memory.
It only detects and suggests: the kit never installs Ollama, OpenCode or models, nor writes their config (H21)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from ...common import IS_WIN, out, which

DATA = Path(__file__).with_name("local_models.yaml")


def models() -> list[dict]:
    return sorted(yaml.safe_load(DATA.read_text(encoding="utf-8")) or [], key=lambda m: -m["min_gb"])


def memory_gb() -> float | None:
    try:
        if IS_WIN:
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = Status(dwLength=ctypes.sizeof(Status))
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            total = s.ullTotalPhys
        else:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return round(total / 1024 ** 3) or None
    except (OSError, ValueError, AttributeError):
        return None


def propose(gb: float) -> dict | None:
    return next((m for m in models() if gb >= m["min_gb"]), None)


def pulled(tag: str) -> bool:
    return any(line.split()[:1] == [tag] for line in out(["ollama", "list"]).splitlines()[1:])


def report(gb: float | None = None) -> list[str]:
    gb = gb if gb is not None else memory_gb()
    lines = ["Local models — for bounded and judge work only (translations, summaries, eval judging)"]
    if not gb:
        return lines + ["  could not read this machine's memory; see .camarones/lib/adapters/runners/local_models.yaml"]
    m = propose(gb)
    lines.append(f"  memory: {gb:g} GB")
    if not m:
        smallest = min(x["min_gb"] for x in models())
        return lines + [f"  no local default under {smallest} GB: that work stays on claude / codex"]
    target = f"opencode:{m['provider']}/{m['tag']}"
    lines += [f"  proposed: {m['provider']}/{m['tag']} — {m['name']}, {m['licence']}: {m['why']}",
              f"  alternatives: {', '.join(m.get('alternatives') or [])}" if m.get("alternatives") else ""]
    has_ollama = bool(which("ollama"))
    lines += [f"  {'✔' if which('opencode') else '✖'} opencode" + ("" if which("opencode") else
                                                                     "  not installed — https://opencode.ai/docs/"),
              f"  {'✔' if has_ollama else '✖'} ollama" + ("" if has_ollama else "    not installed — https://ollama.com/download")]
    if not (has_ollama and pulled(m["tag"])):
        lines.append(f"  · model not pulled — ollama pull {m['tag']}")
    routes = {"bounded": [target, "claude", "codex"], "judge": [target, "claude", "codex"]}
    lines += ["  then point OpenCode at Ollama (https://opencode.ai/docs/providers/) and add to ~/.camarones.json:",
              f'    "routing": {json.dumps(routes)}',
              "  today only autopilot reads the routing (agentic-heavy); bounded and judge apply as those steps arrive"]
    return [l for l in lines if l]
