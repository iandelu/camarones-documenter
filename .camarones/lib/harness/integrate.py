"""Integration (R12): bring a parallel unit's worktree back into the main cam-docs, deterministically. Main is merged
into the unit's branch first, inside the worktree, and the gates run there; main then receives a --no-ff merge that
cannot conflict. A conflict, new gate errors or local changes in main block the unit and leave main untouched.
Derived files are never merged: they are regenerated after the merge, so two units never conflict over them."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..common import KIT, out, run
from .ctx import Ctx
from .locks import FileLock
from .worktrees import Worktrees

DERIVED = ("docs/llms.txt", "docs/.status.json")         # regenerated from the pages; never merged by hand
SHARED_C4 = tuple(f"docs/architecture/{n}" for n in ("model.c4", "spec.c4", "views.c4", "deployment.c4"))
EXCLUDED = (*DERIVED, "docs/.work")                       # plan state lives in the main cam-docs only

GATE_SCRIPT = {
    "check": "from lib import docs\nprint(json.dumps(docs.check()[0]))",
    "arch-validate": "from lib import env\nok, msg = env.arch_validate()\nprint(json.dumps([] if ok else [msg or 'C4 model invalid']))",
}


@dataclass(frozen=True)
class Result:
    unit: str
    outcome: str                  # merged | nothing | conflict | gate-failed | main-dirty
    detail: str = ""


def _env(ctx: Ctx) -> dict:
    return {**os.environ, "CAMARONES_ROOT": str(ctx.root), "CAMARONES_STATE_ROOT": str(ctx.state_root),
            "CAMARONES_WORKSPACE": str(ctx.workspace), "LC_ALL": "C"}


def _kit(ctx: Ctx, code: str) -> str:
    """Run kit code against another tree in its own process (the kit resolves its paths at import)."""
    r = subprocess.run([sys.executable, "-c", f"import json, sys\nsys.path.insert(0, {str(KIT)!r})\n{code}"],
                       env=_env(ctx), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"kit call failed in {ctx.root}: {(r.stderr or r.stdout).strip()[-500:]}")
    return r.stdout


def _gate(name: str) -> Callable[[Ctx], set[str]]:
    def gate(ctx: Ctx) -> set[str]:
        found = json.loads(_kit(ctx, GATE_SCRIPT[name]).strip().splitlines()[-1])
        return {str(e).replace(str(ctx.root), "<root>").replace(ctx.root.as_posix(), "<root>") for e in found}
    return gate


GATES = [("check", _gate("check")), ("arch-validate", _gate("arch-validate"))]


def handoff_file(uid: str) -> Path:
    from .. import plan
    return plan.handoff_file(uid)


def _fold_handoff(uid: str) -> None:
    from .. import plan
    f = handoff_file(uid)
    if not f.exists():
        return
    text = plan.HANDOFF.read_text(encoding="utf-8") if plan.HANDOFF.exists() else "# Session handoff 🦐\n"
    text = text.replace("\n## Last session", "\n## Earlier session")
    head, sep, rest = text.partition("\n## ")
    section = f"\n## Last session — {uid}\n{f.read_text(encoding='utf-8').strip()}\n"
    plan.HANDOFF.write_text(head.rstrip() + "\n" + section + (f"\n## {rest}" if sep else ""), encoding="utf-8",
                            newline="\n")
    f.unlink()


def _git(path: Path, *args: str, check: bool = False):
    return run(["git", *args], cwd=path, check=check, capture=True, env={"LC_ALL": "C"})


def _ident(path: Path) -> list[str]:
    return [] if out(["git", "config", "user.email"], cwd=path) else ["-c", "user.name=Camarón",
                                                                      "-c", "user.email=camarones@localhost"]


def _commit(path: Path, message: str, paths: tuple[str, ...] = (".",)) -> bool:
    _git(path, "add", "-A", "--", *paths, *(f":(exclude){p}" for p in EXCLUDED))
    if _git(path, "diff", "--cached", "--quiet").returncode == 0:
        return False
    _git(path, *_ident(path), "commit", "-q", "--no-verify", "-m", message, check=True)
    return True


def _drop_derived(path: Path, paths: tuple[str, ...] = DERIVED) -> None:
    """Throw away local versions of derived files so a merge never trips over them. Only a worktree also drops its
    stray copy of docs/.work: in the main cam-docs that folder holds the live plan."""
    for rel in paths:
        if _git(path, "ls-files", "--error-unmatch", rel).returncode == 0:
            _git(path, "checkout", "HEAD", "--", rel)
        _git(path, "clean", "-fdq", "--", rel)


def _block(uid: str, why: str, fix: str | None) -> None:
    from .. import plan
    plan.set_status(uid, "blocked", f"integrate: {why}")
    if fix:
        u = plan.ensure(f"integrate:{uid}", "integrate", title=f"Integrate {uid}: resolve it against the main docs")
        plan.set_status(u["id"], "todo", fix, record=False)


def integrate(uid: str, ctx: Ctx, gates=GATES, policy: str = "on-conflict", emit=lambda kind, **f: None) -> Result:
    wts = Worktrees(ctx)
    w = wts.get(uid)
    if not w:
        return Result(uid, "nothing", "no worktree")
    main, tree = ctx.state_root, Ctx.for_root(w.path, state_root=ctx.state_root, workspace=ctx.workspace)
    rel = Path(os.path.relpath(w.path, ctx.workspace)).as_posix()
    with FileLock(ctx.state_root / ".camarones" / ".cache" / "locks" / "integrate.lock", wait=600):
        _commit(w.path, f"docs(camarones): {uid}")
        _drop_derived(w.path, EXCLUDED)
        if _git(main, "rev-list", "--count", f"HEAD..{w.branch}").stdout.strip() == "0":
            wts.remove(uid)
            return Result(uid, "nothing")
        target = _git(main, "rev-parse", "HEAD", check=True).stdout.strip()
        shared = sorted(_git(main, "diff", "--name-only", f"{target}...{w.branch}", "--", *SHARED_C4).stdout.split())
        if shared:                     # parallel units are meant to write their own fragment (CONVENTIONS §4)
            emit("c4.shared", unit=uid, files=shared)
        if _git(w.path, *_ident(w.path), "merge", "--no-edit", "-m", f"docs(camarones): {uid} on main", target).returncode:
            files = sorted(_git(w.path, "diff", "--name-only", "--diff-filter=U").stdout.split())
            _git(w.path, "merge", "--abort")
            emit("merge.conflict", unit=uid, files=files)
            _block(uid, f"conflicts with the main docs in {', '.join(files)}",
                   f"Unit {uid} conflicts with the main docs in: {', '.join(files)}. Its work is committed in {rel} "
                   f"(branch {w.branch}). There, merge {target[:12]} and resolve keeping both units' facts, commit, then "
                   f"mark this unit done; the kit merges it again." if policy == "on-conflict" else None)
            return Result(uid, "conflict", ", ".join(files))
        main_ctx = Ctx.for_root(main, state_root=main, workspace=ctx.workspace)
        new = {f"{name}: {e}" for name, gate in gates for e in gate(tree) - gate(main_ctx)}
        _drop_derived(main)
        if new:
            detail = "\n".join(sorted(new))
            emit("gate.failed", unit=uid, errors=sorted(new))
            _block(uid, "new errors after merging — " + "; ".join(sorted(new))[:300],
                   f"Unit {uid} merges cleanly but adds errors: {detail}. Its work is in {rel} (branch {w.branch}): fix "
                   "them there, commit, then mark this unit done; the kit merges it again." if policy == "on-conflict" else None)
            return Result(uid, "gate-failed", detail)
        _kit(tree, "from lib import docs\ndocs.collect()\ndocs.llms()")
        _git(w.path, "add", "-A", "--", *DERIVED)
        if _git(w.path, "diff", "--cached", "--quiet").returncode:
            _git(w.path, *_ident(w.path), "commit", "-q", "--no-verify", "-m", f"docs(camarones): {uid} derived files",
                 check=True)
        r = _git(main, *_ident(main), "merge", "--no-ff", "--no-edit", "-m", f"docs(camarones): integrate {uid}", w.branch)
        if r.returncode:
            if (main / ".git" / "MERGE_HEAD").exists():
                _git(main, "merge", "--abort")
            files = re.findall(r"^\s+(\S+)$", r.stderr or "", re.M) or [(r.stderr or r.stdout).strip()[-200:]]
            emit("merge.blocked", unit=uid, files=files)
            _block(uid, f"uncommitted changes in the main docs would be overwritten: {', '.join(files)} — commit "
                        "them (checkpoint) and the unit merges on the next run", None)
            return Result(uid, "main-dirty", ", ".join(files))
        emit("merge.ok", unit=uid)
    _fold_handoff(uid)
    wts.remove(uid)
    return Result(uid, "merged")
