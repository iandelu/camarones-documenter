"""OpenCode (`opencode run --format json`): the one gateway to local models (Ollama, LM Studio…), H21."""
from __future__ import annotations

import json
import re

from ...harness.ports import Invocation, RunRequest
from .base import CliRunner

ARG_KEYS = ("filePath", "path", "command", "pattern", "url", "description")
WRITES = {"edit", "write", "patch"}


def permissions(allow_tools: tuple[str, ...]) -> dict:
    """Claude-style tool names → OpenCode's permission config: edits allowed when asked for, shell limited to the
    listed command prefixes, no web access."""
    bash = {"*": "deny"}
    for t in allow_tools:
        m = re.fullmatch(r"Bash\((.+?):\*\)", t)
        if m:
            bash[f"{m.group(1)} *"] = "allow"
    edits = any(t in ("Edit", "Write", "MultiEdit") for t in allow_tools)
    return {"edit": "allow" if edits else "deny", "webfetch": "deny", "bash": bash}


class OpenCode(CliRunner):
    id = "opencode"
    label = "OpenCode"

    def build(self, req: RunRequest) -> Invocation:
        model = ["--model", req.model] if req.model else []
        env = req.env
        if req.interactive:
            argv = [self.exe(), *model, *(["--continue"] if req.resume else []), "--prompt", req.prompt]
        elif req.allow_tools is not None:
            argv = [self.exe(), "run", "--format", "json", *model, req.prompt]
            env = {**req.env, "OPENCODE_PERMISSION": json.dumps(permissions(req.allow_tools))}
        else:
            argv = [self.exe(), "run", "--format", "json", "--auto", *model, req.prompt]
        return Invocation(argv, req.cwd, env)

    def parse_event(self, ev: dict) -> list[dict]:
        kind, part = ev.get("type"), ev.get("part") or {}
        if kind == "text":
            text = part.get("text") or ""
            return [{"type": "log", "text": text}] if text.strip() else []
        if kind == "tool_use":
            state = part.get("state") or {}
            inp = state.get("input") or {}
            arg = next((inp[k] for k in ARG_KEYS if inp.get(k)), "")
            out = [{"type": "tool.call", "name": part.get("tool"), "arg": arg}]
            if part.get("tool") in WRITES and state.get("status") == "completed" and arg:
                out.append({"type": "file.changed", "path": arg})
            return out
        if kind == "step_finish":
            tok = part.get("tokens") or {}
            cache = tok.get("cache") or {}
            usage = {"type": "usage", "in": tok.get("input", 0), "out": tok.get("output", 0),
                     "cache_read": cache.get("read", 0), "cache_write": cache.get("write", 0)}
            if part.get("cost") is not None:
                usage["cost_usd"] = part["cost"]
            return [usage]
        if kind == "error":
            err = ev.get("error") or {}
            return [{"type": "error", "text": str(ev.get("message") or (err.get("data") or {}).get("message")
                                                  or err.get("name") or "")}]
        return []
