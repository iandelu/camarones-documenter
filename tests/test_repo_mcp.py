"""Claude Code opened inside one service repo finds the docs too (S16): setup registers the `camarones` MCP server in
Claude Code's *local* scope for each repo folder — kept in the user's Claude config, nothing written into the repo —
`doctor` reports a repo without it, `repair` puts it back and `uninstall` removes it."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import wire_project


@pytest.fixture
def claude(kit, isolated_env, monkeypatch):
    """A fake `claude mcp add|remove --scope local` that edits ~/.claude.json the way Claude Code does."""
    env = kit.env
    cfg = isolated_env / ".claude.json"
    calls = []
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    real_which = env.which
    monkeypatch.setattr(env, "which", lambda name: "/bin/claude" if name == "claude" else real_which(name))
    real_run = env.run

    def run(cmd, cwd=None, **kw):
        if cmd[:2] != ["claude", "mcp"]:
            return real_run(cmd, cwd=cwd, **kw)
        calls.append((cmd, Path(cwd)))
        data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {"projects": {}}
        servers = data["projects"].setdefault(str(Path(cwd).resolve()), {}).setdefault("mcpServers", {})
        if cmd[2] == "add":                     # like Claude Code: `-e` takes every value up to the next option or --
            sep, opts, name, envs, i = cmd.index("--"), cmd[3:cmd.index("--")], None, [], 0
            while i < len(opts):
                if opts[i] == "--scope":
                    i += 2
                elif opts[i] == "-e":
                    i += 1
                    while i < len(opts) and not opts[i].startswith("-"):
                        assert "=" in opts[i], f"Invalid environment variable format: {opts[i]}"
                        envs.append(opts[i])
                        i += 1
                else:
                    name, i = opts[i], i + 1
            servers[name] = {"type": "stdio", "command": cmd[sep + 1], "args": cmd[sep + 2:],
                             "env": dict(e.split("=", 1) for e in envs)}
        elif cmd[2] == "remove":
            servers.pop(cmd[-1], None)
        cfg.write_text(json.dumps(data), encoding="utf-8")
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(env, "run", run)
    return cfg, calls


def test_each_repo_gets_the_docs_mcp_in_claude_codes_local_scope(kit, claude):
    cfg, calls = claude
    from fixtures.builder import snapshot
    before = snapshot(kit.ws / "api")
    for r in kit.docs.repo_names():
        assert kit.env.wire_repo_mcp(r, log=lambda _: None) is True
    data = json.loads(cfg.read_text(encoding="utf-8"))
    entry = data["projects"][str((kit.ws / "api").resolve())]["mcpServers"]["camarones"]
    assert entry["env"]["CAMARONES_ROOT"] == str(kit.root) and entry["args"][-1] == "mcp"
    assert all("--scope" in c and c[c.index("--scope") + 1] == "local" for c, _ in calls)
    assert snapshot(kit.ws / "api") == before                                      # nothing written into the repo
    assert all(kit.env.repo_mcp_registered(r) for r in kit.docs.repo_names())
    calls.clear()
    assert kit.env.wire_repo_mcp("api", log=lambda _: None) is False and not calls  # idempotent


def test_without_claude_code_nothing_is_attempted(kit, monkeypatch):
    monkeypatch.setattr(kit.env, "which", lambda name: None)
    assert kit.env.wire_repo_mcp("api", log=lambda _: None) is False


def test_doctor_reports_and_repair_restores_a_repo_without_it(kit, claude, monkeypatch):
    wired = wire_project(kit)
    from lib import install_state
    off = {(d["path"], d["what"]) for d in install_state.drift()}
    assert ("api", "repo MCP (Claude Code)") in off
    monkeypatch.setattr(wired.env, "wire_umbrella", lambda *a, **kw: None)          # repair's other steps need tools
    install_state.repair(log=lambda _: None)
    assert not [d for d in install_state.drift() if d["what"] == "repo MCP (Claude Code)"]


def test_uninstall_removes_it(kit, claude):
    cfg, calls = claude
    for r in kit.docs.repo_names():
        kit.env.wire_repo_mcp(r, log=lambda _: None)
    from lib import uninstall
    assert any("camarones MCP" in s.label for s in uninstall.steps(backup=False))
    for r in uninstall.repo_names():
        uninstall.forget_repo_mcp(r)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert not any(p.get("mcpServers", {}).get("camarones") for p in data["projects"].values())
    assert not any("camarones MCP" in s.label for s in uninstall.steps(backup=False))
