"""The WikiEngine port (lib/ports/wiki_engine.py) on OpenWiki: the provider keys that let it run headless, whether an
agent reaches its MCP tools, the commands that wire it into a project, and the open and close of a run (a real
openwiki/ folder in the repo, the repo's own files restored afterwards) under one lock at a time."""
from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from lib.adapters import fs_links
from lib.common import CACHE, HOME, ROOT, load_json, repo_dir
from lib.core.locks import FileLock, LockBusy
from lib.core.paths import WIKI_LOCK
from lib.ports import Log

OPENWIKI_INSTALL = [["openwiki", "integrations", "install", host, "--project", "."] for host in ("claude", "codex")]

PROVIDER_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY",
                 "OPENAI_COMPATIBLE_API_KEY", "OPENAI_CHATGPT_ACCESS_TOKEN")


def openwiki_credentials() -> bool:
    """OpenWiki runs headless only with a provider key in the environment or saved in ~/.openwiki/.env."""
    saved = HOME / ".openwiki" / ".env"
    text = saved.read_text(encoding="utf-8", errors="replace") if saved.exists() else ""
    return any(os.environ.get(k) or re.search(rf"^{k}=\S", text, re.M) for k in PROVIDER_KEYS)


def openwiki_wired(host: str) -> bool:
    """Whether the agent can reach OpenWiki's MCP tools in this project (what `openwiki integrations install` writes)."""
    if host == "claude":
        return "openwiki" in (load_json(ROOT / ".mcp.json", {}).get("mcpServers") or {})
    cfg = ROOT / ".codex" / "config.toml"
    return cfg.is_file() and "openwiki" in cfg.read_text(encoding="utf-8", errors="replace")


OPENWIKI_REPO_FILES = ("AGENTS.md", "CLAUDE.md", ".github/workflows/openwiki-update.yml")


def wiki_open(repo: str, log: Log = print) -> None:
    """OpenWiki refuses a symlinked openwiki/ and adds agent snippets + a GitHub workflow to the repo. So a run gets a
    real openwiki/ seeded from cam-docs/wikis/<repo>, and wiki_close moves the result back and restores the repo."""
    d, wiki, state = repo_dir(repo), ROOT / "wikis" / repo, CACHE / "wiki-open" / f"{repo}.json"
    ow = d / "openwiki"
    if not state.exists():
        # as they are on disk, line endings included: a close puts the same bytes back (no CRLF churn on Windows)
        saved = {f: (d / f).read_bytes().decode("utf-8", errors="surrogateescape") if (d / f).is_file() else None
                 for f in OPENWIKI_REPO_FILES}
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(saved), encoding="utf-8")
    if fs_links._is_link(ow):
        ow.unlink()
    if not ow.exists():
        shutil.copytree(wiki, ow) if wiki.is_dir() else ow.mkdir()


def wiki_close(repo: str, log: Log = print) -> bool:
    """Only undoes a wiki_open: without its saved state it cannot tell the repo's own AGENTS.md / CLAUDE.md from
    OpenWiki's, so it leaves them alone (a second close, or a close without open, is a no-op)."""
    d, wiki, state = repo_dir(repo), ROOT / "wikis" / repo, CACHE / "wiki-open" / f"{repo}.json"
    if not state.exists():
        log(f"{repo}: no open OpenWiki run — nothing to close")
        fs_links.link_repo_wiki(repo, log)
        return False
    ow = d / "openwiki"
    if ow.is_dir() and not fs_links._is_link(ow):
        if any(ow.iterdir()):
            shutil.rmtree(wiki, ignore_errors=True)
            wiki.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ow), str(wiki))
        else:                                   # nothing written: keep the wiki cam-docs already has
            ow.rmdir()
    saved = json.loads(state.read_text(encoding="utf-8"))
    for f, text in saved.items():
        p = d / f
        if text is not None:
            raw = text.encode("utf-8", errors="surrogateescape")   # a state from kits ≤ 4.80.1 holds LF text: LF back
            if not p.is_file() or p.read_bytes() != raw:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(raw)
        elif p.is_file():
            p.unlink()
            for parent in p.relative_to(d).parents:
                if parent != Path(".") and (d / parent).is_dir() and not any((d / parent).iterdir()):
                    (d / parent).rmdir()
    state.unlink(missing_ok=True)
    fs_links.link_repo_wiki(repo, log)
    return True


@contextmanager
def wiki_workdir(repo: str, log: Log = print):
    wiki_open(repo, log)
    try:
        yield
    finally:
        wiki_close(repo, log)


@contextmanager
def wiki_lock(repo: str):
    """One OpenWiki run at a time across the wizard, the portal and the CLI: parallel runs share the agent's quota."""
    lock = FileLock(WIKI_LOCK, wait=0, info={"repo": repo})
    try:
        lock.acquire()
    except LockBusy as e:
        raise RuntimeError(f"another OpenWiki run is in progress ({e.holder.get('repo')}, pid {e.holder.get('pid')}) "
                           "— wait for it to finish") from None
    try:
        yield
    finally:
        lock.release()
