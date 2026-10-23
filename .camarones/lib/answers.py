"""Ask with an optional AI answer: the sections Ask retrieves (only those agents may read, through the freshness gate)
go to the runner routed for bounded work — a local model is allowed — which answers from them alone, citing them.
Made-up citations are dropped. One headless call, no tools, in an empty folder so the project's agent config (hooks,
MCP servers, CLAUDE.md) does not load; `ask: {ai: false}` in workspace.yaml turns it off, `ask: {model: …}` picks it."""
from __future__ import annotations

import re, tempfile
from pathlib import Path

from . import docs

LIMIT = 9000                   # characters of excerpts: a bounded model's context, with room for the answer
TIMEOUT = 90                   # seconds a person waits in the portal
CHEAP = {"claude": "haiku"}    # answering from given excerpts needs no large model


def runner() -> str | None:
    if (docs.workspace().get("ask") or {}).get("ai") is False:
        return None
    from . import plan
    found = plan._agents(lambda _: None, "bounded", allow_local=True)
    return found[0] if found else None


def model(target: str) -> str | None:
    """The model to ask for: `ask.model`, else the route's own (`claude:opus`), else the runner's cheap one."""
    from .harness import routing
    chosen = (docs.workspace().get("ask") or {}).get("model")
    if chosen:
        return str(chosen)
    route = routing.parse(target)
    return None if route.model else CHEAP.get(route.runner)


def answer(question: str) -> dict:
    from . import mcp
    from .harness.evals import _ask, _last_json
    from .harness import routing
    from .harness.ports import RunRequest
    target = runner()
    if not target:
        raise RuntimeError("no AI answer here: no runner for bounded work (or ask.ai is false in workspace.yaml)")
    context = mcp.ask(question, limit=4)
    if context.startswith("Nothing in the docs"):
        return {"answer": None, "cited": [], "runner": target}
    known = re.findall(r"^\[([^\]]+)\]", context, re.M)
    excerpts = " ".join(context.split("\n\n", 1)[1].split())[:LIMIT]
    prompt = (f"Answer a question about this project using only these documentation excerpts; each starts with its "
              f"citation in brackets. Cite every claim. If the excerpts do not answer it, say so. Excerpts: {excerpts} "
              f"Question: {' '.join(question.split())} Reply with one JSON object on the last line: "
              '{"answer": "<the answer, in the language of the question>", "cited": ["<citation>", ...]}')
    chosen = model(target)
    with tempfile.TemporaryDirectory(prefix="cam-ask-") as empty:
        got = _ask(target, RunRequest(prompt=prompt, cwd=Path(empty), env={}, model=chosen, allow_tools=(), stream=True),
                   timeout=TIMEOUT)
    if got.get("timed_out"):
        raise RuntimeError(f"no answer within {TIMEOUT} s: {target} is slow or waiting for a login; try again or "
                           "set a faster model with `ask: {model: …}` in workspace.yaml")
    from . import usage
    obj = _last_json(got["lines"], "answer")
    if obj is None:                                    # plain text (models often skip the JSON): cites in brackets
        text = "\n".join(got["lines"]).strip()
        obj = {"answer": text, "cited": re.findall(r"\[([^\]\s]+)\]", text)} if got["rc"] == 0 and text else {}
    cited = obj.get("cited") if isinstance(obj.get("cited"), list) else []
    usage.record("portal:ask-ai", channel="human", hit=bool(obj.get("answer")))
    return {"answer": str(obj["answer"]) if obj.get("answer") else None, "runner": target,
            "model": chosen or routing.parse(target).model,
            "cited": list(dict.fromkeys(c for c in map(str, cited) if c in known)),
            **{k: got[k] for k in ("seconds", "tokens_in", "tokens_out", "cost_usd")}}
