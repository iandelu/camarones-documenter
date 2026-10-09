"""An agent CLI described by argv templates instead of code (H28): Gemini CLI ships this way, and a machine can add
its own in ~/.camarones.json. Placeholders: {prompt}, {cwd}, {model}, and the item {model_args}, which expands to
`model_args` when a model is set and to nothing otherwise. Each placeholder fills one argv item: no shell."""
from __future__ import annotations

from ...harness.ports import Invocation, RunRequest
from .base import CliRunner


class CommandRunner(CliRunner):
    def __init__(self, id: str, label: str, argv: list[str], interactive: list[str] | None = None,
                 model_args: list[str] | None = None, limit_hints: list[str] | None = None):
        self.id, self.label, self.command = id, label or id, argv[0]
        self.argv, self.interactive = list(argv), list(interactive) if interactive else None
        self.model_args = list(model_args or ["--model", "{model}"])
        self.limit_hints = tuple(h.lower() for h in limit_hints or ())

    def build(self, req: RunRequest) -> Invocation:
        if req.allow_tools is not None:
            raise ValueError(f"{self.label} cannot limit its tools: use a runner that can for this step")
        template = self.interactive if req.interactive else self.argv
        if template is None:
            raise ValueError(f"{self.label} has no interactive command in its template")
        values = {"{prompt}": req.prompt, "{cwd}": str(req.cwd), "{model}": req.model or ""}

        def fill(item: str) -> str:
            for k, v in values.items():
                item = item.replace(k, v)
            return item
        argv = []
        for item in template[1:]:
            if item == "{model_args}":
                argv += [fill(m) for m in self.model_args] if req.model else []
            else:
                argv.append(fill(item))
        return Invocation([self.exe() or self.command, *argv], req.cwd, req.env)

    def parse(self, line: str) -> list[dict]:
        return [{"type": "log", "text": line, "raw": True}]

    def classify(self, rc: int, tail: str) -> str:
        if rc and any(h in tail[-2000:].lower() for h in self.limit_hints):
            return "limited"
        return super().classify(rc, tail)


GEMINI = dict(label="Gemini CLI", argv=["gemini", "{model_args}", "-p", "{prompt}", "--yolo"],
              interactive=["gemini", "{model_args}", "-i", "{prompt}"])
