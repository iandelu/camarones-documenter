"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

import shutil
from pathlib import Path

from .common import KIT, ROOT, out
from . import docs
from .harness.locks import pid_alive  # noqa: F401  (pid_alive re-exported)
from .ports import Log
from .projects import git_failure  # noqa: F401  (git_failure re-exported)


# ---------- CI ----------
def detect_forge() -> str:
    urls = " ".join(r.get("url", "") for r in docs.workspace()["repos"])
    urls += " " + out(["git", "-C", str(ROOT), "remote", "get-url", "origin"])
    if "github" in urls:
        return "github"
    return "gitlab"


def install_ci(forge: str | None = None, log: Log = print) -> Path:
    forge = forge or detect_forge()
    if forge == "github":
        dst = ROOT / ".github" / "workflows" / "docs.yml"
        src = KIT / "ci" / "umbrella.github.yml"
    else:
        dst = ROOT / ".gitlab-ci.yml"
        src = KIT / "ci" / "umbrella.gitlab-ci.yml"
        if dst.exists() and "camarones" not in dst.read_text(encoding="utf-8"):
            dst = ROOT / ".gitlab-ci.camarones.yml"
            log("  existing .gitlab-ci.yml kept: add `include: local: .gitlab-ci.camarones.yml` to it")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    snippet = f"repo.{'github.yml' if forge == 'github' else 'gitlab-ci.yml'}"
    (ROOT / ".camarones" / "ci").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KIT / "ci" / snippet, ROOT / ".camarones" / "ci" / snippet)   # service repos include it from here
    from . import ci
    fresh = ROOT / ".camarones" / "ci" / ci.FILES[forge]
    fresh.write_text(ci.render(forge), encoding="utf-8", newline="\n")      # generated from lib/ci.py, ci: in workspace.yaml
    log(f"  ✔ {dst.relative_to(ROOT)} (docs repo pipeline)")
    log(f"  → per-repo snippet: .camarones/ci/{snippet}")
    log(f"  → per-repo pull request check (no AI): .camarones/ci/{ci.FILES[forge]}")
    proposal = ci.render_propose(forge)
    if proposal:                                    # ci.target: self-hosted — the AI job runs on the team's runner
        (ROOT / ".camarones" / "ci" / ci.FILES_PROPOSE[forge]).write_text(proposal, encoding="utf-8", newline="\n")
        log(f"  → per-repo docs proposal (AI, self-hosted runner): .camarones/ci/{ci.FILES_PROPOSE[forge]}")
    return dst
