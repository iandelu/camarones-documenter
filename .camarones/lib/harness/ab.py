"""A/B with vs without cam-docs (R19): the same question, once through the docs (camarones MCP tools, the workspace)
and once with only the code, in a throwaway folder that links the repos and nothing else — no cam-docs, no
AGENTS.md/CLAUDE.md, no MCP config. Tokens, time, tool calls and the exact identifiers each answer names are compared
and kept in docs/.work/evals/ab/ for the team. `ab: {enabled: false}` in workspace.yaml turns it off."""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import tempfile
from pathlib import Path

from ..common import IS_WIN, WORK, WORKSPACE, load_json, repo_dir, run, save_json
from . import evals
from .ports import RunRequest

RESULTS = WORK / "evals" / "ab"
CODE_TOOLS = ("Read", "Glob", "Grep")
METRICS = ("seconds", "tokens_in", "tokens_cache", "tokens_out", "cost_usd", "tool_calls", "mentions", "judge")


def enabled() -> bool:
    from .. import docs
    return bool((docs.workspace().get("ab") or {}).get("enabled", True))


@contextlib.contextmanager
def control_workspace():
    """A folder with links to the repos only, outside the project (so walking up never reaches cam-docs). Links are
    removed without following them: repos are never touched."""
    from .. import docs, env
    tmp = Path(tempfile.mkdtemp(prefix="camaron-ab-")).resolve()
    try:
        for r in docs.repo_names():
            if repo_dir(r).is_dir():
                _link(tmp / r, repo_dir(r).resolve())
        yield tmp
    finally:
        for child in tmp.iterdir():
            if env._is_link(child):
                try:
                    child.unlink()
                except OSError:
                    os.rmdir(child)                       # a Windows junction: rmdir drops the link only
        tmp.rmdir()


def _link(dst: Path, target: Path) -> None:
    """Absolute link: the temp folder may be on another drive than the repos (Windows), where relative links fail."""
    try:
        dst.symlink_to(target, target_is_directory=True)
    except OSError:
        if not IS_WIN or run(["cmd", "/c", "mklink", "/J", str(dst), str(target)], check=False, quiet=True).returncode:
            raise


def control_request(question: str, cwd: Path) -> RunRequest:
    prompt = (f"Answer a question about this software project by reading its source code in this folder (one "
              f"subfolder per repo). Do not change any file. Question: {question} Reply with one JSON object on the "
              'last line: {"answer": "<your answer, naming exact endpoints, topics, tables or classes>", '
              '"cited": ["<repo>/<file path>", ...]}')
    return RunRequest(prompt=prompt, cwd=cwd, env={}, allow_tools=CODE_TOOLS, stream=True)


def _variant(q: dict, target: str, req: RunRequest, judge: str | None) -> dict:
    got = evals._ask(target, req)
    answer, cited = evals.extract(got["lines"])
    mentions = evals.score({"mention": q.get("mention")}, answer, [])["mentions"] if q.get("mention") else None
    return {**{k: got.get(k, 0) for k in ("seconds", "tokens_in", "tokens_cache", "tokens_out", "cost_usd", "tool_calls",
                                          "rc")},
            "mentions": mentions, "judge": evals._grade(q, answer, judge) if judge else None,
            "answer": answer[:2000], "cited": cited}


def _total(rows: list[dict], side: str, key: str):
    vals = [r[side][key] for r in rows if r[side].get(key) is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 3) if key in ("mentions", "judge") else round(sum(vals), 4)


def run(questions: list[dict], target: str, judge: str | None = None, echo=print) -> dict:
    if not enabled():
        raise RuntimeError("A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)")
    rows = []
    for q in questions:
        echo(f"? {q.get('id') or 'question'}: {q['q']}")
        with_docs = _variant(q, target, evals.request(q["q"], WORKSPACE), judge)
        with control_workspace() as tmp:
            without = _variant(q, target, control_request(q["q"], tmp), judge)
        rows.append({"id": q.get("id"), "q": q["q"], "with": with_docs, "without": without})
        echo(f"  with cam-docs: {with_docs['tokens_in'] + with_docs['tokens_cache']} context tokens, "
             f"{with_docs['seconds']}s · without: {without['tokens_in'] + without['tokens_cache']} context tokens, "
             f"{without['seconds']}s")
    totals = {side: {k: _total(rows, side, k) for k in METRICS} for side in ("with", "without")}
    delta = {k: round(totals["with"][k] - totals["without"][k], 4) for k in METRICS
             if totals["with"][k] is not None and totals["without"][k] is not None}
    context = {s: (totals[s]["tokens_in"] or 0) + (totals[s]["tokens_cache"] or 0) for s in ("with", "without")}
    base = context["without"]           # the whole context read, cached or not: what the docs should save
    result = {"at": dt.datetime.now().replace(microsecond=0).isoformat(), "runner": target, "judge_runner": judge,
              "questions": rows, "totals": totals, "delta": delta,
              "tokens_saved_pct": round(100 * (base - context["with"]) / base, 1) if base else None}
    RESULTS.mkdir(parents=True, exist_ok=True)
    save_json(RESULTS / f"{result['at'].replace(':', '').replace('-', '')}.json", result)
    return result


def latest() -> dict | None:
    files = sorted(RESULTS.glob("*.json")) if RESULTS.is_dir() else []
    return load_json(files[-1], None) if files else None
