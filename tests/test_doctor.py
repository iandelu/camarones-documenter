"""`camaron doctor` as data (lib/doctor.py): prerequisites, the pinned tools and the kit files that drifted, so the
desktop app shows them with the action that fixes each (`doctor --install NAME`, `setup`, `repair`)."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


def test_report_names_each_check_and_how_to_fix_it(kit, monkeypatch):
    from lib import doctor
    monkeypatch.setattr(doctor.env, "prerequisites", lambda: {
        "git": {"ok": True, "need": True, "hint": "git"},
        "codex": {"ok": False, "need": False, "hint": "Codex CLI"}})
    monkeypatch.setattr(doctor.env, "tool_version", lambda name: "1.59.4" if name == "likec4" else "")
    r = doctor.report()
    pre = {p["name"]: p for p in r["prerequisites"]}
    assert pre["git"]["ok"] and pre["git"]["fix"] is None
    assert not pre["codex"]["ok"] and pre["codex"]["fix"] == {"cmd": "doctor", "args": {"install": "codex"}}
    tools = {t["name"]: t for t in r["tools"]}
    assert tools["likec4"]["ok"] and tools["likec4"]["found"] == "1.59.4"
    assert not tools["graphify"]["ok"] and tools["graphify"]["fix"] == {"cmd": "setup", "args": {}}
    assert set(tools) >= {"graphify", "likec4", "mmdc", "openwiki", "gitleaks"}
    assert isinstance(r["drift"], list) and r["fix_drift"] == {"cmd": "repair", "args": {}}


def test_install_goes_through_the_os_package_manager(kit, monkeypatch):
    from lib import doctor
    seen = []
    monkeypatch.setattr(doctor.env, "install_prereq", lambda name, log=print: seen.append(name) or True)
    assert doctor.install("node", log=lambda _: None) is True and seen == ["node"]
    with pytest.raises(ValueError):
        doctor.install("rm -rf", log=lambda _: None)


def test_doctor_json_on_the_cli(kit):
    r = cli(kit, "doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert {"prerequisites", "tools", "drift", "fix_drift"} <= set(data)
    assert all({"name", "ok", "need", "hint", "fix"} <= set(p) for p in data["prerequisites"])
    assert cli(kit, "doctor", "--install", "nonsense").returncode == 2           # argparse: one of the known names


FAKE = {"prerequisites": [{"name": "git", "ok": True, "need": True}, {"name": "node", "ok": False, "need": True},
                          {"name": "codex", "ok": False, "need": False}],
        "tools": [{"name": "likec4", "ok": False}, {"name": "mmdc", "ok": True}],
        "drift": [{"path": "AGENTS.md"}], "fix_drift": {"cmd": "repair", "args": {}}}


def test_a_check_is_kept_with_its_time_so_the_app_does_not_run_it_on_every_visit(kit, monkeypatch):
    from lib import doctor
    monkeypatch.setattr(doctor, "report", lambda: FAKE)
    assert doctor.checked() is None                                         # never checked on this project
    rec = doctor.check(log=lambda _: None)
    assert rec["result"] == FAKE and rec["at"].endswith("Z")
    assert doctor.checked() == rec
    doctor.CACHE_FILE.write_text("{not json", encoding="utf-8")             # a broken cache is no cache
    assert doctor.checked() is None


def test_what_needs_doing_is_counted_for_the_summary(kit):
    from lib import doctor
    # node is needed and missing; codex is optional; likec4 is a pinned tool out of date; one kit file drifted
    assert doctor.problems(FAKE) == {"missing": ["node"], "tools": ["likec4"], "drift": 1}
    assert doctor.problems({"prerequisites": [], "tools": [], "drift": []}) == {"missing": [], "tools": [], "drift": 0}
