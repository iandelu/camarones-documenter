"""Method hooks (R36, X2): opt-in per project (`camaron hooks on`, `hooks: {method: true}` in workspace.yaml). The kit
writes three Claude Code hooks into cam-docs/.claude/settings.json and trust recognises them as its own:
SessionStart puts the plan state in the agent's context, PostToolUse checks a docs page right after it is edited and
feeds the problems back, Stop reminds once per session to update the docs when the repos moved on."""
from __future__ import annotations

import json, sys
from pathlib import Path

from .common import CACHE, DOCS, KIT, ROOT, uv
from . import docs

CAP = 1800                                        # characters the session start adds to the agent's context
EVENTS = {"SessionStart": ("", "session-start"), "PostToolUse": ("Edit|Write|MultiEdit", "post-edit"),
          "Stop": ("", "stop")}
TAG = '" hook '


def enabled() -> bool:
    return bool((docs.workspace().get("hooks") or {}).get("method"))


def command(name: str) -> str:
    return f'"{uv()}" run --quiet --script "{KIT / "camarones.py"}" hook {name}'


def kit_entries() -> dict[str, dict]:
    """event → the settings.json group the kit writes for it."""
    return {event: {**({"matcher": m} if m else {}), "hooks": [{"type": "command", "command": command(n)}]}
            for event, (m, n) in EVENTS.items()}


def _ours(group: dict) -> bool:
    return any(TAG in str(h.get("command", "")) and "camarones.py" in str(h.get("command", ""))
               for h in group.get("hooks") or [] if isinstance(h, dict))


def apply(st: dict) -> dict:
    """settings.json with the kit's hooks in or out, the team's own hooks untouched."""
    hooks = {e: [g for g in groups if not _ours(g)] for e, groups in (st.get("hooks") or {}).items()}
    if enabled():
        for event, group in kit_entries().items():
            hooks.setdefault(event, []).append(group)
    hooks = {e: g for e, g in hooks.items() if g}
    out = {k: v for k, v in st.items() if k != "hooks"}
    return {**out, "hooks": hooks} if hooks else out


def set_enabled(on: bool) -> None:
    from . import env
    ws = docs.workspace()
    ws["hooks"] = {**(ws.get("hooks") or {}), "method": bool(on)}
    docs.save_workspace(ws)
    env.write_agent_config(env.components())


# ---------- the hooks themselves ----------
def session_start() -> str:
    from . import plan
    data = plan.load()
    done, total = plan.progress(data)
    ready = [u for u in plan.available(data) if u["status"] != "done"][:4]
    parts = [f"Camarón documentation plan: {done}/{total} units done."]
    if ready:
        parts.append("Ready next: " + "; ".join(f"{u['id']} ({u['title']})" for u in ready) + ".")
    handoff = plan.HANDOFF
    if handoff.is_file():
        last = handoff.read_text(encoding="utf-8").split("## Last session", 1)
        if len(last) > 1:
            parts.append("Last session:" + last[1].strip()[:700])
    feedback = docs.pending_feedback()
    if feedback:
        parts.append(f"{len(feedback)} review comment(s) wait in docs/.work/review-feedback.md (unit review-fixes).")
    return "\n".join(parts)[:CAP]


def post_edit(payload: dict) -> tuple[int, str]:
    """(exit code, message): 2 sends the message back to the agent; 0 says nothing."""
    from . import quality
    path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not path.endswith(".md"):
        return 0, ""
    try:
        rel = Path(path).resolve().relative_to(DOCS.resolve()).as_posix()
    except ValueError:
        return 0, ""
    rows = [r for r in docs.collect() if r["path"] == rel]
    if not rows:
        return 0, ""
    problems = []
    for check in (quality.check_structure, quality.check_links, quality.check_generated):
        errors, warns = check(rows)
        problems += errors + warns
    problems = [p for p in problems if rel in p]
    if not problems:
        return 0, ""
    return 2, (f"Camarón check on docs/{rel} after your edit — fix these before you move on:\n"
               + "\n".join(f"- {p}" for p in problems[:12]))


def stop(payload: dict) -> str:
    """A JSON decision to block once (a reminder) or nothing."""
    if payload.get("stop_hook_active"):
        return ""
    sid = str(payload.get("session_id") or "")
    marker = CACHE / "hooks" / f"stop-{sid or 'anon'}"
    if marker.exists():
        return ""
    moved = {r: c["status"] for r, c in docs.changes().items() if c.get("status") != "up-to-date"}
    if not moved:
        return ""
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("reminded\n", encoding="utf-8")
    listed = ", ".join(f"{r} ({s})" for r, s in sorted(moved.items()))
    return json.dumps({"decision": "block", "reason": (
        f"Before you finish: these repos moved on since their docs were last updated: {listed}. If this session changed "
        "behaviour, update the affected pages in cam-docs (skill cam-docs-update) and run the kit's `check`; if not, "
        "say so and stop.")})


def main(name: str) -> int:
    """`camaron hook <name>`: Claude Code passes the event as JSON on stdin. A hook never breaks the session."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    try:
        if name == "session-start":
            print(session_start())
        elif name == "post-edit":
            code, text = post_edit(payload)
            if code:
                print(text, file=sys.stderr)
            return code
        elif name == "stop":
            out = stop(payload)
            if out:
                print(out)
    except Exception:  # noqa: BLE001 — never block the agent on a kit error
        return 0
    return 0


def owned() -> dict[str, set[str]]:
    """trust ids → digests of the hook groups the kit writes (only valid while the group is just the kit's hook)."""
    from . import trust
    if not enabled():
        return {}
    return {f"claude hook {event} {m}".rstrip(): {trust._digest([command(n)])} for event, (m, n) in EVENTS.items()}
