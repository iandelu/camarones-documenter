"""Context budget (X5): the tokens an agent pays before it reads a single page in this project. Standing context is
loaded into every session (AGENTS.md, CLAUDE.md, each skill's name and description, the MCP tool schemas); a skill's
body only when it is used. Estimated at 4 characters per token: close enough to see what grows, no tokenizer needed."""
from __future__ import annotations

import json

from .common import ROOT
from . import docs

BUDGET = 6000           # standing tokens; `context: {budget: N}` in workspace.yaml changes it


def tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _skills() -> list[dict]:
    out = []
    for f in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
        head = f"{fm.get('name', f.parent.name)}: {fm.get('description', '')}"
        out.append({"kind": "skill", "path": f.relative_to(ROOT).as_posix(), "tokens": tokens(head),
                    "on_use": tokens(body), "kit": f.parent.name.startswith("cam-docs-")})
    return out


def _mcp() -> list[dict]:
    from . import mcp
    try:
        servers = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers") or {}
    except (OSError, ValueError):
        servers = {}
    out = [{"kind": "mcp", "path": f"camarones/{t['name']}", "tokens": tokens(json.dumps(t, ensure_ascii=False)),
            "on_use": 0, "kit": True} for t in mcp.TOOLS if "camarones" in servers]
    return out + [{"kind": "mcp", "path": f"{name}/* (not measured: its schemas come from the server)", "tokens": 0,
                   "on_use": 0, "kit": False} for name in sorted(servers) if name != "camarones"]


def standing() -> dict:
    items = [{"kind": "rules", "path": name, "tokens": tokens(f.read_text(encoding="utf-8")), "on_use": 0, "kit": True}
             for name in ("AGENTS.md", "CLAUDE.md") if (f := ROOT / name).is_file()]
    items += _skills() + _mcp()
    budget = int(((docs.workspace().get("context") or {}).get("budget")) or BUDGET)
    total = sum(i["tokens"] for i in items)
    return {"total": total, "budget": budget, "over": total > budget, "items": items,
            "on_use": sum(i["on_use"] for i in items)}


def report(r: dict | None = None) -> list[str]:
    r = r or standing()
    kinds = {"rules": "agent rules", "skill": "skill descriptions", "mcp": "MCP tool schemas"}
    lines = [f"Standing context: ~{r['total']} tokens of {r['budget']} "
             f"({'OVER BUDGET' if r['over'] else 'within budget'}); skill bodies add ~{r['on_use']} when used."]
    for kind, label in kinds.items():
        rows = sorted((i for i in r["items"] if i["kind"] == kind), key=lambda i: -i["tokens"])
        if rows:
            lines.append(f"  {label}: ~{sum(i['tokens'] for i in rows)}")
            shown = rows[:8] + [i for i in rows[8:] if not i["tokens"]]
            lines += [f"    {i['tokens']:>6}  {i['path']}" + ("" if i["kit"] else "  (not the kit's)") for i in shown]
    if r["over"]:
        lines.append("Trim AGENTS.md, drop unused skills, or raise context.budget in workspace.yaml.")
    return lines
