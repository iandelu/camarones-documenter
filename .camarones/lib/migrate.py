"""`migrate`: move a pre-3.0 project (docs + agent config at the workspace root and inside every repo) to the
cam-docs layout — <workspace>/cam-docs holds docs, config and history; the repos get their kit files removed.

Phase 1 (this process, old ROOT): preview, then move the docs repo (its .git included, so history is kept) into
cam-docs/. Phase 2 (`migrate --finish`, relaunched with the new ROOT): links, agent config, repo cleanup, commit.
Repo cleanup only removes what the kit wrote: untracked kit files, and kit lines/sections that are not in HEAD."""
from __future__ import annotations

import json, os, re, shutil, subprocess, sys
from pathlib import Path

from .common import KIT, ROOT, WS_FILE, CAM_DIR, CAM_LAYOUT, GRAPHS, WORKSPACE, run, out, repo_dir, load_json

ROOT_ITEMS = ("docs", "wikis", ".camarones", ".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md",
              ".gitignore", ".gitlab-ci.yml", ".gitlab-ci.camarones.yml", ".github", ".git")
KIT_DIRS = (".claude/skills/graphify", ".claude/skills/openwiki", ".codex/skills/graphify", ".agents/skills/openwiki")
KIT_LINES = {".gitignore": ["graphify-out/", "*.graphify-bak"],
             ".graphifyignore": [".claude/", ".codex/", ".agents/", "openwiki/", "graphify-out/"],
             ".claudeignore": ["graphify-out/"],
             ".gitattributes": ["graphify-out/graph.json merge=graphify"]}
HOOK_BLOCK = re.compile(r"\n?# graphify-[\w-]*start.*?# graphify-[\w-]*end\n?", re.S)
SECTION = re.compile(r"\n*^## graphify\n.*?(?=^## |\Z)", re.S | re.M)


def needed() -> bool:
    """An older global-install project: config at the workspace root (a co-located kit copy is left alone)."""
    return not CAM_LAYOUT and WS_FILE.exists() and not (ROOT / ".camarones" / "lib").exists()


# ---------- repo cleanup ----------
def tracked(repo: Path, rel: str) -> bool:
    return bool(out(["git", "ls-files", "--", rel], cwd=repo))


def head_text(repo: Path, rel: str) -> str | None:
    r = run(["git", "show", f"HEAD:{rel}"], cwd=repo, check=False, capture=True)
    return r.stdout if r.returncode == 0 else None


class Cleaner:
    def __init__(self, name: str, dry: bool):
        self.name, self.repo, self.dry, self.done = name, repo_dir(name), dry, []

    def act(self, what: str, fn=None) -> None:
        self.done.append(what)
        if not self.dry and fn:
            fn()

    def remove(self, rel: str) -> None:
        p = self.repo / rel
        if p.is_symlink() or p.is_file():
            self.act(f"delete {rel}", p.unlink)
        elif p.is_dir():
            self.act(f"delete {rel}/", lambda: shutil.rmtree(p))

    def settle(self, rel: str, new: str) -> None:
        """Write the cleaned text back — as HEAD's exact bytes when that is all that is left, or delete an untracked
        file that the kit alone created."""
        p, head = self.repo / rel, head_text(self.repo, rel)
        cur = p.read_text(encoding="utf-8")
        if head is not None and new.strip() == head.strip():
            new = head
        if new == cur:
            return
        if head is None and not new.strip():
            return self.remove(rel)
        self.act(f"clean {rel}", lambda: p.write_text(new, encoding="utf-8"))

    def lines(self, rel: str, kit: list[str]) -> None:
        p = self.repo / rel
        if not p.is_file():
            return
        head = set((head_text(self.repo, rel) or "").splitlines())
        keep = [l for l in p.read_text(encoding="utf-8").splitlines() if l not in kit or l in head]
        self.settle(rel, "\n".join(keep) + ("\n" if keep else ""))

    def section(self, rel: str) -> None:
        p = self.repo / rel
        if p.is_file() and "## graphify" not in (head_text(self.repo, rel) or ""):
            text = p.read_text(encoding="utf-8")
            self.settle(rel, SECTION.sub("", text).rstrip() + "\n" if SECTION.search(text) else text)

    def json_hooks(self, rel: str) -> None:
        p = self.repo / rel
        if not p.is_file():
            return
        data = load_json(p, None)
        if not isinstance(data, dict):
            return
        from .env import without_graphify_hooks
        data = without_graphify_hooks(data)
        self.settle(rel, json.dumps(data, indent=2) + "\n" if data else "")

    def mcp(self) -> None:
        p = self.repo / ".mcp.json"
        data = load_json(p, None)
        if isinstance(data, dict) and "openwiki" in data.get("mcpServers", {}):
            del data["mcpServers"]["openwiki"]
            if not data["mcpServers"]:
                del data["mcpServers"]
            self.settle(".mcp.json", json.dumps(data, indent=2) + "\n" if data else "")

    def codex_toml(self) -> None:
        p = self.repo / ".codex" / "config.toml"
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            self.settle(".codex/config.toml", re.sub(r"# OPENWIKI:MCP:START.*?# OPENWIKI:MCP:END\n?", "", text, flags=re.S))

    def git_hooks(self) -> None:
        hooks = Path(out(["git", "rev-parse", "--git-path", "hooks"], cwd=self.repo) or ".git/hooks")
        dirs = {(self.repo / hooks).resolve(), (self.repo / ".husky").resolve()}
        for d in dirs:
            for f in (d / "post-checkout", d / "post-commit"):
                if not f.is_file() or "graphify-" not in (text := f.read_text(encoding="utf-8", errors="replace")):
                    continue
                rel = os.path.relpath(f, self.repo)
                new = HOOK_BLOCK.sub("\n", text)
                if not new.replace("#!/bin/sh", "").strip():
                    if rel.startswith(".git") or not tracked(self.repo, rel):
                        self.remove(rel)
                        continue
                self.settle(rel, new)

    def run(self) -> list[str]:
        if not (self.repo / ".git").exists():
            return []
        out_dir = self.repo / "graphify-out"
        if out_dir.is_dir() and not tracked(self.repo, "graphify-out"):
            dst = GRAPHS / self.name
            self.act(f"move graphify-out/ → {CAM_DIR}/graph/{self.name}/",
                     lambda: (shutil.rmtree(dst, ignore_errors=True), dst.parent.mkdir(parents=True, exist_ok=True),
                              shutil.move(str(out_dir), str(dst))))
        for d in KIT_DIRS:
            if (self.repo / d).exists() and not tracked(self.repo, d):
                self.remove(d)
        for f in (".claude/settings.json.graphify-bak", ".codex/hooks.json.graphify-bak"):
            if (self.repo / f).exists() and not tracked(self.repo, f):
                self.remove(f)
        cm = self.repo / ".claude" / "CLAUDE.md"
        if cm.is_file() and not tracked(self.repo, ".claude/CLAUDE.md") and "graphify" in cm.read_text(encoding="utf-8"):
            self.remove(".claude/CLAUDE.md")
        self.json_hooks(".claude/settings.json")
        self.json_hooks(".codex/hooks.json")
        self.codex_toml()
        self.mcp()
        for rel, kit in KIT_LINES.items():
            self.lines(rel, kit)
        for rel in ("AGENTS.md", "CLAUDE.md"):
            self.section(rel)
        self.git_hooks()
        if not self.dry:
            for d in (".claude/skills", ".codex/skills", ".agents/skills", ".claude", ".codex", ".agents"):
                p = self.repo / d
                if p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
        return self.done


def clean_repos(dry: bool) -> dict[str, list[str]]:
    from . import docs
    return {n: Cleaner(n, dry).run() for n in docs.repo_names()}


# ---------- phase 1: move ----------
def plan_moves() -> tuple[list[str], list[str]]:
    dest = ROOT / CAM_DIR
    moves = [n for n in ROOT_ITEMS if (ROOT / n).exists() or (ROOT / n).is_symlink()]
    tracked_top = {Path(p).parts[0] for p in out(["git", "ls-files"], cwd=ROOT).splitlines()} if (ROOT / ".git").exists() else set()
    from . import docs
    repos = set(docs.repo_names()) | {CAM_DIR}
    moves += sorted(t for t in tracked_top - set(moves) if t not in repos)   # anything else the docs repo versions
    left = sorted(p.name for p in ROOT.iterdir() if p.name not in moves and p.name not in repos and p.name != ".DS_Store"
                  and p != dest)
    return moves, left


def main(yes: bool = False, dry_run: bool = False, finish: bool = False) -> int:
    if finish:
        return finish_phase()
    if CAM_LAYOUT:
        print(f"Already on the {CAM_DIR} layout ({ROOT}). Checking the repos for leftover kit files…")
        return finish_phase(dry=dry_run, ask=not yes)
    if not needed():
        print("Nothing to migrate here." if not (ROOT / ".camarones" / "lib").exists() else
              "This project carries its own kit copy: run `unlink` first (it then uses the global install), then migrate.")
        return 1
    dest = ROOT / CAM_DIR
    if dest.exists() and any(dest.iterdir()):
        print(f"{dest} already exists and is not empty — move it away first.")
        return 1
    moves, left = plan_moves()
    print(f"🦐 Migrate {ROOT.name} → {ROOT.name}/{CAM_DIR}/\n\nMove into {CAM_DIR}/ (git history kept):")
    print("".join(f"  • {m}\n" for m in moves), end="")
    print(f"\nLink from {ROOT.name}/ → {CAM_DIR}/: .claude .codex .agents .mcp.json AGENTS.md CLAUDE.md")
    if left:
        print(f"\nLeft where they are (not part of the docs repo): {', '.join(left)}")
    print("\nClean kit files out of the repos:")
    for repo, acts in clean_repos(dry=True).items():
        print(f"  {repo}: " + ("; ".join(acts) if acts else "clean"))
    if dry_run:
        print("\n(dry run — nothing changed)")
        return 0
    if not yes and input("\nProceed? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
        print("Cancelled.")
        return 1
    dest.mkdir(exist_ok=True)
    for m in moves:
        shutil.move(str(ROOT / m), str(dest / m))
    from . import projects
    projects.register(dest)
    env = {**os.environ, "CAMARONES_ROOT": str(dest)}
    sys.stdout.flush()
    return subprocess.run([sys.executable, str(KIT / "camarones.py"), "migrate", "--finish"], env=env).returncode


# ---------- phase 2: wire the new layout ----------
def finish_phase(dry: bool = False, ask: bool = False) -> int:
    from . import docs, env
    report = clean_repos(dry=True)
    if ask and any(report.values()):
        for repo, acts in report.items():
            if acts:
                print(f"  {repo}: " + "; ".join(acts))
        if input("\nClean these? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            return 1
    if dry:
        return 0
    for repo, acts in clean_repos(dry=False).items():
        print(f"✔ {repo}: {len(acts)} change(s)" if acts else f"· {repo}: clean")
    ws = docs.workspace()
    ws["project"].pop("agent_branch", None)
    docs.save_workspace(ws)
    comps = env.components()
    for n in docs.repo_names():
        if "openwiki" in comps and (repo_dir(n) / "openwiki").exists():
            env.link_repo_wiki(n)
    env.wire_umbrella(print, comps)
    run(["git", "add", "-A"], cwd=ROOT, check=False, quiet=True)
    ident = [] if out(["git", "config", "user.email"], cwd=ROOT) else ["-c", "user.name=Camarones Documenter",
                                                                       "-c", "user.email=camarones@localhost"]
    run(["git", *ident, "commit", "-q", "--no-verify", "-m", f"chore(camarones): move docs and agent config to {CAM_DIR}/"],
        cwd=ROOT, check=False, quiet=True)
    print(f"\n🦐 Done. Docs repo: {ROOT}\n   Open your agent in {WORKSPACE} — it sees every repo and the docs.")
    return 0
