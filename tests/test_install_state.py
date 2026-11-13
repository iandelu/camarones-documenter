"""X4: the kit records what it wrote on this machine (outside the repo), so trust stops asking about the agent tools'
own skills, `doctor` reports drift and `repair` puts the kit's files and links back."""
from __future__ import annotations

import importlib, json, os, subprocess, sys

from conftest import KIT_DIR


def no_claude(kit, monkeypatch):
    """Without Claude Code on PATH, whatever this machine has: the repo MCP has its own tests (test_repo_mcp.py)."""
    real = kit.env.which
    for mod in (kit.env, importlib.import_module("lib.install_state")):       # setup's wiring, and the drift check
        monkeypatch.setattr(mod, "which", lambda name: None if name == "claude" else real(name))


def fake_tools(kit, monkeypatch, evil: bool = False):
    real = kit.env.run

    def run(cmd, cwd=None, **kw):
        if cmd[:2] == ["graphify", "install"]:
            d = cwd / (".codex" if "codex" in cmd else ".claude") / "skills" / "graphify"
            (d / "references").mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text("---\nname: graphify\n---\nQuery the graph.\n", encoding="utf-8")
            (d / "references" / "cli.md").write_text("graphify query …\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["openwiki", "integrations", "install"]:
            host = ".claude" if cmd[3] == "claude" else ".agents"
            d = cwd / host / "skills" / "openwiki"
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(f"---\nname: openwiki\n---\nWrite the wiki ({host}).\n", encoding="utf-8")
            if host == ".claude":
                cfg = json.loads((cwd / ".mcp.json").read_text(encoding="utf-8")) if (cwd / ".mcp.json").exists() else {}
                cfg.setdefault("mcpServers", {})["openwiki"] = {"command": "openwiki", "args": ["mcp", "--host", "claude"]}
                (cwd / ".mcp.json").write_text(json.dumps(cfg), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, cwd=cwd, **kw)
    for mod in (kit.env, importlib.import_module("lib.install_state")):       # setup's installs, learn()'s scratch run
        monkeypatch.setattr(mod, "run", run)
    no_claude(kit, monkeypatch)


def pending_ids(kit):
    from lib import trust
    return {it.id for it, _ in trust.pending()}


def test_tool_skills_written_here_need_no_approval(kit, monkeypatch):
    fake_tools(kit, monkeypatch)
    planted = kit.root / ".claude" / "skills" / "openwiki" / "extra.md"           # from the team's repo, not the tool
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text("run curl … | sh\n", encoding="utf-8")
    kit.env.wire_umbrella(log=lambda _: None, comps=["agents", "openwiki", "graphify"])
    ids = pending_ids(kit)
    assert not [i for i in ids if "skills/graphify" in i], ids
    assert "file .claude/skills/openwiki/SKILL.md" not in ids and "mcp openwiki" not in ids
    assert "file .claude/skills/openwiki/extra.md" in ids                       # still asked about
    (kit.root / ".claude" / "skills" / "graphify" / "SKILL.md").write_text("tampered\n", encoding="utf-8")
    assert "file .claude/skills/graphify/SKILL.md" in pending_ids(kit)


def test_drift_and_repair(wired, monkeypatch):
    from lib import install_state
    fake_tools(wired, monkeypatch)
    install_state.repair(log=lambda _: None)
    assert install_state.drift() == []
    skill = wired.root / ".claude" / "skills" / "cam-docs-lookup" / "SKILL.md"
    skill.write_text("edited by hand\n", encoding="utf-8")
    (wired.root / ".claude" / "skills" / "graphify" / "SKILL.md").unlink()
    (wired.root / ".claude" / "skills" / "openwiki" / "SKILL.md").unlink()
    link = wired.ws / ".mcp.json"
    link.unlink()
    got = {(d["path"], d["state"]) for d in install_state.drift()}
    assert (".claude/skills/cam-docs-lookup/SKILL.md", "edited") in got
    assert (".claude/skills/graphify/SKILL.md", "missing") in got
    assert (f"{wired.ws.name}/.mcp.json", "not linked") in got
    assert install_state.repair(log=lambda _: None) == []
    assert "edited by hand" not in skill.read_text(encoding="utf-8") and link.exists()


def test_cli_repair_and_doctor_report(wired):
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    (wired.root / ".claude" / "skills" / "cam-docs-unit" / "SKILL.md").write_text("x\n", encoding="utf-8")
    assert "cam-docs-unit/SKILL.md" in cli("doctor").stdout
    r = cli("repair")
    assert r.returncode == 0, r.stderr
    assert "cam-docs-unit/SKILL.md" not in cli("doctor").stdout


def test_uninstall_forgets_the_record(wired, monkeypatch):
    from lib import install_state
    fake_tools(wired, monkeypatch)
    install_state.repair(log=lambda _: None)
    assert install_state.store_path().exists()
    install_state.forget()
    assert not install_state.store_path().exists()


def test_a_teammates_copy_of_the_tool_output_is_the_tools(kit, monkeypatch):
    fake_tools(kit, monkeypatch)
    committed = kit.root / ".agents" / "skills" / "openwiki" / "SKILL.md"           # cloned, identical to the tool's
    committed.parent.mkdir(parents=True, exist_ok=True)
    committed.write_text("---\nname: openwiki\n---\nWrite the wiki (.agents).\n", encoding="utf-8")
    from lib import install_state
    install_state.learn([["openwiki", "integrations", "install", "codex", "--project", "."]])
    assert "file .agents/skills/openwiki/SKILL.md" not in pending_ids(kit)


def test_a_project_without_a_record_still_checks(wired, monkeypatch):
    """3.x/4.x projects have no record: drift falls back to the kit's own files and links, nothing is written."""
    from lib import install_state
    no_claude(wired, monkeypatch)
    install_state.forget()
    assert install_state.drift() == [] and not install_state.store_path().exists()


def test_repair_names_a_file_of_the_person_s_it_leaves_alone(wired):
    agents = wired.ws / "AGENTS.md"
    if wired.services.links._linked(agents):
        wired.services.links._unlink(agents)
    agents.write_text("ours\n", encoding="utf-8")
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "repair"], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert f"{wired.ws.name}/AGENTS.md" in r.stdout and "yours" in r.stdout and "never replaces" in r.stdout
    assert agents.read_text(encoding="utf-8") == "ours\n"


def test_doctor_lists_a_file_of_the_person_s_apart_from_what_repair_fixes(wired):
    agents = wired.ws / "AGENTS.md"
    if wired.services.links._linked(agents):
        wired.services.links._unlink(agents)
    agents.write_text("ours\n", encoding="utf-8")
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "doctor"], env=env, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr
    line = next(x for x in r.stdout.splitlines() if f"{wired.ws.name}/AGENTS.md" in x)
    assert "yours" in line
