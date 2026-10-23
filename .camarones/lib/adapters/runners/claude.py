"""Claude Code (`claude -p … --output-format stream-json`)."""
from __future__ import annotations

from ...harness.ports import Invocation, RunRequest
from .base import CliRunner

ARG_KEYS = ("file_path", "path", "command", "pattern", "url", "description")


class Claude(CliRunner):
    id = "claude"
    label = "Claude Code"

    def build(self, req: RunRequest) -> Invocation:
        model = ["--model", req.model] if req.model else []
        if req.interactive:
            argv = [self.exe(), *model, *(["--continue"] if req.resume else []), req.prompt]
        elif req.allow_tools == ():               # an answer from the prompt alone: no tools, no project MCP servers
            argv = [self.exe(), "-p", req.prompt, "--tools", "", "--strict-mcp-config", *model,
                    *(["--output-format", "stream-json", "--verbose"] if req.stream else [])]
        elif req.allow_tools is not None:
            argv = [self.exe(), "-p", req.prompt, "--permission-mode", "acceptEdits", "--allowedTools",
                    " ".join(req.allow_tools), *model,
                    *(["--output-format", "stream-json", "--verbose"] if req.stream else [])]
        else:
            argv = [self.exe(), "-p", req.prompt, "--dangerously-skip-permissions", "--output-format", "stream-json",
                    "--verbose", *model]
        return Invocation(argv, req.cwd, req.env)

    def parse_event(self, ev: dict) -> list[dict]:
        kind = ev.get("type")
        if kind == "assistant":
            out = []
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    out.append({"type": "tool.call", "name": c.get("name"),
                                "arg": next((inp[k] for k in ARG_KEYS if inp.get(k)), "")})
                elif c.get("type") == "text" and c.get("text", "").strip():
                    out.append({"type": "log", "text": c["text"]})
            return out
        if kind == "result":
            text = str(ev.get("result") or ev.get("subtype") or "")
            out = [{"type": "error" if ev.get("is_error") else "result", "text": text}]
            u = ev.get("usage")
            if u:
                usage = {"type": "usage", "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
                         "cache_read": u.get("cache_read_input_tokens", 0),
                         "cache_write": u.get("cache_creation_input_tokens", 0)}
                if ev.get("total_cost_usd") is not None:
                    usage["cost_usd"] = ev["total_cost_usd"]
                out.insert(0, usage)
            return out
        return []
