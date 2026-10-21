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

from ..common import IS_WIN, WORK, WORKSPACE, load_json, repo_dir, run as run_cmd, save_json
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
        if not IS_WIN or run_cmd(["cmd", "/c", "mklink", "/J", str(dst), str(target)], check=False, quiet=True).returncode:
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


# ---------- coding tasks on throwaway worktrees (R33) ----------
DOC_LINKS = (".claude", ".codex", ".agents")
DOC_FILES = (".mcp.json", "AGENTS.md", "CLAUDE.md")


def _git(*args: str, cwd: Path) -> str:
    r = run_cmd(["git", *args], cwd=cwd, check=False, capture=True)
    return r.stdout or ""


@contextlib.contextmanager
def task_workspace(with_docs: bool):
    """A folder outside the project with a detached git worktree of every repo at HEAD (and, with docs, of cam-docs,
    with the agent config next to it like the real workspace). Your checkouts are never touched; the worktrees are
    removed afterwards."""
    from .. import docs
    from ..common import ROOT
    tmp = Path(tempfile.mkdtemp(prefix="camaron-ab-task-")).resolve()
    made: list[tuple[Path, Path]] = []
    try:
        for r in docs.repo_names():
            if repo_dir(r).is_dir():
                _git("worktree", "add", "-q", "--detach", str(tmp / r), "HEAD", cwd=repo_dir(r))
                made.append((repo_dir(r), tmp / r))
        if with_docs:
            _git("worktree", "add", "-q", "--detach", str(tmp / "cam-docs"), "HEAD", cwd=ROOT)
            made.append((ROOT, tmp / "cam-docs"))
            for name in DOC_LINKS:
                if (tmp / "cam-docs" / name).is_dir():
                    _link(tmp / name, tmp / "cam-docs" / name)
            for name in DOC_FILES:
                if (tmp / "cam-docs" / name).is_file():
                    (tmp / name).write_bytes((tmp / "cam-docs" / name).read_bytes())
        yield tmp
    finally:
        from .. import env
        for child in list(tmp.iterdir()):
            if env._is_link(child):
                try:
                    child.unlink()
                except OSError:
                    os.rmdir(child)
        for repo, path in made:
            _git("worktree", "remove", "--force", str(path), cwd=repo)
            _git("worktree", "prune", cwd=repo)
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def _task_prompt(task: str) -> str:
    return (f"Do this task in the software project in this folder (one subfolder per repo): {task} Change the code as "
            "needed; do not commit or push. End with one JSON object on the last line: "
            '{"summary": "<what you changed>", "files": ["<repo>/<path>", ...]}')


def _diff(tmp: Path) -> tuple[int, str]:
    from .. import docs
    files, text = 0, []
    for r in docs.repo_names():
        if (tmp / r).is_dir():
            _git("add", "-A", "-N", ".", cwd=tmp / r)                 # new files show in the diff too
            names = [l for l in _git("diff", "--name-only", cwd=tmp / r).splitlines() if l.strip()]
            files += len(names)
            if names:
                text.append(_git("diff", cwd=tmp / r))
    return files, "\n".join(text)[:20000]


def run_task(task: str, target: str, check: list[str] | None = None, echo=print) -> dict:
    """The same coding task with cam-docs and without it; tokens, time, tool calls, files changed, the diff, and
    whether `check` (e.g. the tests) passes in each variant."""
    import subprocess
    if not enabled():
        raise RuntimeError("A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)")
    result = {"at": dt.datetime.now().replace(microsecond=0).isoformat(), "runner": target, "task": task}
    for side in ("with", "without"):
        with task_workspace(side == "with") as tmp:
            echo(f"{'with' if side == 'with' else 'without'} cam-docs: {target} works on the task…")
            env = {"CAMARONES_ROOT": str(tmp / "cam-docs") if side == "with" else str(tmp)}
            got = evals._ask(target, RunRequest(prompt=_task_prompt(task), cwd=tmp, env=env, stream=True))
            files, diff = _diff(tmp)
            outcome = None
            if check:
                r = subprocess.run(check, cwd=str(tmp), capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", stdin=subprocess.DEVNULL)
                outcome = "passed" if r.returncode == 0 else "failed"
            result[side] = {**{k: got.get(k, 0) for k in ("seconds", "tokens_in", "tokens_cache", "tokens_out",
                                                         "cost_usd", "tool_calls", "rc")},
                            "files_changed": files, "diff": diff, "check": outcome,
                            "summary": "\n".join(got.get("lines", []))[-2000:]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    save_json(RESULTS / f"{result['at'].replace(':', '').replace('-', '')}-task.json", result)
    return result


# ---------- sampling real prompts: off unless the project and this machine both opt in ----------
import hashlib, json, random, sys  # noqa: E402


def _samples_file() -> Path:
    from ..common import HOME, ROOT
    key = hashlib.sha256(os.path.normcase(str(ROOT.resolve())).encode("utf-8")).hexdigest()[:16]
    return HOME / ".camarones" / "ab-samples" / f"{key}.jsonl"


def sampling() -> dict:
    from .. import docs
    s = (docs.workspace().get("ab") or {}).get("sampling") or {}
    return {"enabled": bool(s.get("enabled")), "rate": float(s.get("rate", 0.05))}


def set_machine_sampling(on: bool) -> None:
    from ..common import PREFS
    prefs = load_json(PREFS, {})
    prefs["ab_sampling"] = bool(on)
    save_json(PREFS, prefs)


def sample_from_hook() -> bool:
    """Claude Code's UserPromptSubmit hook: keep this prompt for a later A/B replay, at the project's rate, only on a
    machine that opted in. Stored on this machine, never in the repo. Never fails the session."""
    try:
        from ..common import PREFS
        s = sampling()
        if not s["enabled"] or not load_json(PREFS, {}).get("ab_sampling") or not enabled():
            return False
        data = json.loads(sys.stdin.read() or "{}")
        prompt = str(data.get("prompt") or "").strip()
        if not prompt or random.random() >= s["rate"]:
            return False
        f = _samples_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": dt.datetime.now().replace(microsecond=0).isoformat(), "prompt": prompt,
                                 "session": data.get("session_id")}, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — a hook must never break the agent session
        return False


def samples() -> list[dict]:
    f = _samples_file()
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.is_file() else []


HOOK_MARK = " ab sample"
HOOK_ID = "claude hook UserPromptSubmit (local)"           # lib/trust.py's id for this hook in settings.local.json


def _settings_local() -> Path:
    from ..common import ROOT
    return ROOT / ".claude" / "settings.local.json"


def install_hook() -> None:
    """The sampling hook in cam-docs/.claude/settings.local.json (git-ignored: this machine only), approved here
    because you asked for it."""
    from ..common import KIT, uv
    from .. import trust
    f = _settings_local()
    st = load_json(f, {}) if f.is_file() else {}
    cmd = f'"{uv()}" run --quiet --script "{KIT / "camarones.py"}"{HOOK_MARK}'
    groups = [g for g in (st.setdefault("hooks", {}).get("UserPromptSubmit") or [])
              if not any(HOOK_MARK in str(h.get("command", "")) for h in g.get("hooks") or [])]
    st["hooks"]["UserPromptSubmit"] = groups + [{"hooks": [{"type": "command", "command": cmd}]}]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    trust.approve([HOOK_ID])


def remove_hook() -> None:
    from .. import trust
    f = _settings_local()
    if not f.is_file():
        return
    st = load_json(f, {})
    groups = [g for g in ((st.get("hooks") or {}).get("UserPromptSubmit") or [])
              if not any(HOOK_MARK in str(h.get("command", "")) for h in g.get("hooks") or [])]
    if groups:
        st["hooks"]["UserPromptSubmit"] = groups
    else:
        (st.get("hooks") or {}).pop("UserPromptSubmit", None)
    f.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    trust.approve([HOOK_ID])
