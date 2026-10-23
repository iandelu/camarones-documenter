"""Codex CLI (`codex exec --json`)."""
from __future__ import annotations

from ...harness.ports import Invocation, RunRequest
from .base import CliRunner


class Codex(CliRunner):
    id = "codex"
    label = "Codex"

    def build(self, req: RunRequest) -> Invocation:
        model = ["--model", req.model] if req.model else []
        if req.interactive and req.resume:
            argv = [self.exe(), "resume", "--last"]
        elif req.interactive:
            argv = [self.exe(), *model, req.prompt]
        elif req.allow_tools == ():               # an answer from the prompt alone, in a folder that may not be a repo
            argv = [self.exe(), "exec", "-s", "read-only", "--skip-git-repo-check", "-C", str(req.cwd), *model,
                    *(["--json"] if req.stream else []), req.prompt]
        elif req.allow_tools is not None:
            # Codex has no per-tool allow list: its full-auto sandbox (edits inside cwd only) is the closest scope
            argv = [self.exe(), "exec", "--full-auto", "-C", str(req.cwd), *model, *(["--json"] if req.stream else []),
                    req.prompt]
        else:
            argv = [self.exe(), "exec", "--approve-for-me", "--skip-git-repo-check", "--json", *model, req.prompt]
        return Invocation(argv, req.cwd, req.env)

    def parse_event(self, ev: dict) -> list[dict]:
        kind = ev.get("type")
        item = ev.get("item") or {}
        if kind == "item.started" and item.get("type") == "command_execution":
            # on Windows the command arrives wrapped in `powershell … -Command '…'`
            cmd = str(item.get("command", "")).split("-Command", 1)[-1].strip("' ")
            return [{"type": "tool.call", "name": "$", "arg": cmd}]
        if kind == "item.completed":
            if item.get("type") == "agent_message":
                return [{"type": "log", "text": item.get("text")}]
            if item.get("type") == "file_change":
                return [{"type": "file.changed", "path": c.get("path")} for c in item.get("changes", [])]
            if item.get("type") == "mcp_tool_call":
                return [{"type": "tool.call", "name": f"{item.get('server')}.{item.get('tool')}", "arg": None}]
        if kind == "turn.completed" and ev.get("usage"):
            u = ev["usage"]
            return [{"type": "usage", "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
                     "cache_read": u.get("cached_input_tokens", 0)}]
        if kind in ("turn.failed", "error"):
            return [{"type": "error", "text": str((ev.get("error") or {}).get("message") or ev.get("message") or "")}]
        return []
