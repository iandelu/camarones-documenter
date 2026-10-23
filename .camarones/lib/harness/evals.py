"""Golden questions (R17): an exam with an answer key for the docs. evals/questions.yaml lists questions with the
pages an answer should cite (`expect`, logical paths as read_doc takes them) and the exact identifiers it must
mention (`mention`). `run` asks each confirmed question to an agent that may only read the docs, scores the answer
deterministically, optionally adds a judge's grade, and saves the result in docs/.work/evals/ for the team."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import time
from pathlib import Path

import yaml

from ..common import CAM_DIR, ROOT, WORK, WORKSPACE, VERSIONS, load_json, save_json
from .ports import RunRequest

FILE = ROOT / "evals" / "questions.yaml"
RESULTS = WORK / "evals"
TIMEOUT = 600
READ_ONLY = ("mcp__camarones__search_docs", "mcp__camarones__read_doc", "mcp__camarones__list_docs", "Read")


def load() -> list[dict]:
    data = yaml.safe_load(FILE.read_text(encoding="utf-8")) if FILE.exists() else None
    return list((data or {}).get("questions") or [])


def save(questions: list[dict]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text("# Golden questions: what the docs must answer, which pages to cite, which identifiers to name.\n"
                    "# Drafts count once a person confirms them: camaron eval confirm <id> --by <name>\n"
                    + yaml.safe_dump({"questions": questions}, sort_keys=False, allow_unicode=True, width=120),
                    encoding="utf-8", newline="\n")


def confirmed(qs: list[dict]) -> list[dict]:
    return [q for q in qs if q.get("x-confirmed")]


def drafts(qs: list[dict]) -> list[dict]:
    return [q for q in qs if not q.get("x-confirmed")]


def problems(qs: list[dict]) -> list[str]:
    out, seen = [], set()
    for i, q in enumerate(qs):
        if not q.get("q") or not q.get("expect"):
            out.append(f"questions[{i}]: needs q and expect")
        if q.get("id") in seen:
            out.append(f"questions[{i}].id: '{q['id']}' is used twice")
        seen.add(q.get("id"))
    return out


def confirm(ids: list[str], by: str) -> list[str]:
    qs = load()
    known = {q.get("id") for q in qs}
    missing = [i for i in ids if i not in known]
    if missing:
        raise KeyError(f"unknown question(s): {', '.join(missing)}")
    stamp = dt.datetime.now().replace(microsecond=0).isoformat()
    for q in qs:
        if q.get("id") in ids:
            q["x-confirmed"] = {"by": by, "at": stamp}
    save(qs)
    return list(ids)


def norm(path: str) -> str:
    """Any way an agent may cite a page → the logical path read_doc takes (flows/refund.md)."""
    p = str(path).strip().replace("\\", "/").lstrip("./")
    for prefix in (f"{CAM_DIR}/", "docs/"):
        p = p[len(prefix):] if p.startswith(prefix) else p
    return p


def score(q: dict, answer: str, cited: list[str]) -> dict:
    expect, mention = {norm(p) for p in q.get("expect") or []}, q.get("mention") or []
    got = {norm(p) for p in cited}
    flat = " ".join(str(answer).split())
    refs = round(len(expect & got) / len(expect), 3) if expect else None
    alts = [[m] if isinstance(m, str) else list(m) for m in mention]       # an entry may list exact alternatives
    mentions = round(sum(1 for a in alts if any(" ".join(str(x).split()) in flat for x in a)) / len(alts), 3) \
        if alts else None
    parts = [x for x in (refs, mentions) if x is not None]
    return {"refs": refs, "mentions": mentions, "score": round(sum(parts) / len(parts), 3) if parts else 0.0}


def _last_json(lines: list[str], key: str) -> dict | None:
    for line in reversed(lines):
        for m in reversed(list(re.finditer(r"\{.*\}", line))):
            try:
                obj = json.loads(m.group(0))
            except ValueError:
                continue
            if isinstance(obj, dict) and key in obj:
                return obj
    return None


def extract(lines: list[str]) -> tuple[str, list[str]]:
    obj = _last_json(lines, "answer")
    if obj is None:
        return "\n".join(lines).strip(), []
    cited = obj.get("cited") or []
    return str(obj["answer"]), [str(c) for c in cited] if isinstance(cited, list) else []


def request(prompt_question: str, cwd: Path, model: str | None = None) -> RunRequest:
    """One line (Windows .cmd shims drop the rest) and read-only tools: the agent answers from the docs only."""
    llms = Path(CAM_DIR, "docs", "llms.txt").as_posix()
    prompt = (f"Answer a question about this project using only its documentation: the camarones MCP tools "
              f"(search_docs, read_doc, list_docs) or {llms}. Do not read source code. Do not change any file. "
              f"Question: {prompt_question} Reply with one JSON object on the last line: "
              '{"answer": "<your answer, naming exact endpoints, topics, tables or classes>", '
              '"cited": ["<page path as read_doc takes it>", ...]}')
    return RunRequest(prompt=prompt, cwd=cwd, env={}, model=model, allow_tools=READ_ONLY, stream=True)


def _ask(target: str, req: RunRequest, timeout: int = TIMEOUT) -> dict:
    """One headless question: the answer's text lines plus time, exit code, tokens, cost and tool calls."""
    from .. import plan
    runner, model = plan._runner(target)
    req = RunRequest(**{**req.__dict__, "model": req.model or model})
    try:
        inv = runner.build(req)
    except ValueError:                    # a command runner cannot limit its tools: it is this machine's own command
        inv = runner.build(RunRequest(**{**req.__dict__, "allow_tools": None}))
    start = time.monotonic()
    try:
        r = subprocess.run(inv.argv, cwd=str(inv.cwd), env={**os.environ, "CAMARONES_ROOT": str(ROOT), **inv.env},
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        out, rc, late = r.stdout or "", r.returncode, False
    except (OSError, subprocess.TimeoutExpired) as e:
        out, rc, late = str(e), 124, isinstance(e, subprocess.TimeoutExpired)
    got = {"lines": [], "seconds": round(time.monotonic() - start, 1), "rc": rc, "timed_out": late, "tokens_in": 0,
           "tokens_cache": 0,
           "tokens_out": 0, "cost_usd": 0.0, "tool_calls": 0}
    for raw in out.splitlines():
        for ev in runner.parse(raw):
            if ev["type"] in ("log", "result", "error") and ev.get("text"):
                got["lines"] += str(ev["text"]).splitlines()
            elif ev["type"] == "usage":
                got["tokens_in"] += ev.get("in", 0)
                got["tokens_cache"] += ev.get("cache_read", 0) + ev.get("cache_write", 0)   # Claude's input excludes it
                got["tokens_out"] += ev.get("out", 0)
                got["cost_usd"] = round(got["cost_usd"] + (ev.get("cost_usd") or 0), 6)
            elif ev["type"] == "tool.call":
                got["tool_calls"] += 1
    return got


def _grade(q: dict, answer: str, target: str) -> float | None:
    facts = ", ".join(q.get("mention") or []) or "none listed"
    prompt = (f"Rate from 0 to 10 how well an answer answers a question about this project. Question: {q['q']} "
              f"Facts it should contain: {facts}. Answer: {' '.join(str(answer).split())[:2000]} "
              'Reply with one JSON object on the last line: {"grade": <0-10>}')
    obj = _last_json(_ask(target, RunRequest(prompt=prompt, cwd=WORKSPACE, env={}, allow_tools=()))["lines"], "grade")
    try:
        return round(max(0.0, min(10.0, float(obj["grade"]))) / 10, 3) if obj else None
    except (TypeError, ValueError):
        return None


def run(target: str, judge: str | None = None, include_drafts: bool = False, echo=print) -> dict:
    judge_target, grade = judge, _grade
    qs = load()
    asked = qs if include_drafts else confirmed(qs)
    rows = []
    for q in asked:
        echo(f"? {q['id']}: {q['q']}")
        got = _ask(target, request(q["q"], WORKSPACE))
        answer, cited = extract(got["lines"])
        s = score(q, answer, cited)
        row = {"id": q["id"], **s, "cited": cited, "answer": answer[:2000],
               **{k: got.get(k, 0) for k in ("seconds", "rc", "tokens_in", "tokens_cache", "tokens_out", "cost_usd",
                                              "tool_calls")}}
        if judge_target:
            row["judge"] = grade(q, answer, judge_target)
        rows.append(row)
        echo(f"  score {s['score']}" + (f"  judge {row['judge']}" if judge_target else ""))
    graded = [r["judge"] for r in rows if r.get("judge") is not None]
    result = {"at": dt.datetime.now().replace(microsecond=0).isoformat(), "runner": target, "judge_runner": judge_target,
              "kit": VERSIONS["kit"], "drafts_skipped": 0 if include_drafts else len(drafts(qs)), "questions": rows,
              "score": round(sum(r["score"] for r in rows) / len(rows), 3) if rows else None,
              "judge": round(sum(graded) / len(graded), 3) if graded else None}
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = result["at"].replace(":", "").replace("-", "")
    save_json(RESULTS / f"{stamp}-{re.sub(r'[^A-Za-z0-9._-]+', '-', target)}.json", result)
    return result


def latest() -> dict | None:
    files = sorted(RESULTS.glob("*.json")) if RESULTS.is_dir() else []
    return load_json(files[-1], None) if files else None


def draft_unit() -> dict:
    """The agent unit that proposes questions from the confirmed pages (bounded work: a local model can do it)."""
    from .. import plan
    return plan.ensure("eval-questions", "eval-questions",
                       title="Golden questions: draft what the docs must answer (a person confirms them)")
