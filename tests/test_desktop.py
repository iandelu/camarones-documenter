"""`camaron app` (lib/desktop.py): Electron pinned in VERSIONS, installed once into ~/.camarones/desktop with npm (no
admin rights), then the kit's own desktop/ folder started with the interpreter and kit the app must call back. Without
Node the CLI and the wizard keep working; the app says what to install."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

import pytest


@pytest.fixture
def desk(kit, monkeypatch):
    from lib import desktop
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        pkg = desktop.DEST / "node_modules" / "electron"
        if cmd[:2] == ["npm", "install"]:                     # what npm leaves behind
            (pkg / "dist").mkdir(parents=True, exist_ok=True)
            (pkg / "package.json").write_text(json.dumps({"version": cmd[-1].split("@")[-1]}), encoding="utf-8")
            if not desktop.SKIPS_SCRIPTS:
                (pkg / "path.txt").write_text("electron.exe" if desktop.IS_WIN else "electron", encoding="utf-8")
        if cmd[:1] == ["node"]:                               # Electron's own download script
            (pkg / "path.txt").write_text("electron", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(desktop, "run", fake_run)
    monkeypatch.setattr(desktop, "node_major", lambda: 22)
    desktop.calls = calls
    desktop.SKIPS_SCRIPTS = False
    return desktop


def test_electron_is_pinned_and_installed_once(desk):
    v = desk.VERSIONS["electron"]
    assert v.count(".") == 2 and v[0].isdigit()
    b = desk.ensure(log=lambda _: None)
    assert b.parent == desk.DEST / "node_modules" / "electron" / "dist"
    npm = [c for c in desk.calls if c[:2] == ["npm", "install"]]
    assert npm == [["npm", "install", "--prefix", str(desk.DEST), "--no-audit", "--no-fund", "--save-exact",
                    f"electron@{v}"]]
    desk.ensure(log=lambda _: None)
    assert len([c for c in desk.calls if c[:2] == ["npm", "install"]]) == 1          # idempotent


def test_another_installed_version_is_replaced(desk):
    desk.ensure(log=lambda _: None)
    pkg = desk.DEST / "node_modules" / "electron" / "package.json"
    pkg.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    desk.ensure(log=lambda _: None)
    assert len([c for c in desk.calls if c[:2] == ["npm", "install"]]) == 2


def test_when_npm_skips_install_scripts_electron_downloads_itself(desk):
    desk.SKIPS_SCRIPTS = True                                 # npm 11 runs no dependency scripts by default
    b = desk.ensure(log=lambda _: None)
    assert ["node", str(desk.ELECTRON / "install.js")] in desk.calls
    assert b == desk.ELECTRON / "dist" / "electron"


def test_without_node_it_says_what_to_install(desk, monkeypatch):
    monkeypatch.setattr(desk, "node_major", lambda: 0)
    with pytest.raises(RuntimeError, match="Node.js"):
        desk.ensure(log=lambda _: None)
    assert not desk.calls


def test_the_app_is_started_with_the_kit_and_this_project(desk, kit):
    b = desk.ensure(log=lambda _: None)
    cmd, env = desk.command(b)
    assert cmd[:2] == [str(b), str(desk.KIT / "desktop")]
    assert env["CAMARONES_PY"] == sys.executable and env["CAMARONES_KIT"] == str(desk.KIT)
    assert Path(env["CAMARONES_ROOT"]).resolve() == kit.root.resolve()
    assert "CAMARONES_APP_TOKEN" not in env


def test_the_desktop_folder_is_shipped_with_the_kit(kit):
    from lib import desktop
    pkg = json.loads((desktop.KIT / "desktop" / "package.json").read_text(encoding="utf-8"))
    assert pkg["main"] == "main.cjs" and (desktop.KIT / "desktop" / "main.cjs").is_file()
    assert (desktop.KIT / "desktop" / "preload.cjs").is_file()
    assert not pkg.get("dependencies")                      # Electron itself comes from `camaron app`, pinned


def cli(kit, *args, cwd=None):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8", cwd=cwd)


def test_projects_add_registers_a_folder(kit):
    r = cli(kit, "projects", "--add", str(kit.ws), "--json")
    assert r.returncode == 0, r.stderr
    row = json.loads(r.stdout)
    assert Path(row["path"]).resolve() == kit.root.resolve()
    r = cli(kit, "projects", "--add", str(kit.ws / "api" / "nowhere"), "--json")
    assert r.returncode == 1 and "cam-docs" in r.stderr


def test_new_without_opening_the_wizard(kit, tmp_path):
    parent = tmp_path / "elsewhere"
    parent.mkdir()
    e = {k: v for k, v in os.environ.items() if k != "CAMARONES_ROOT"}
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "new", "shop", "--no-open"], env=e, cwd=parent,
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)
    assert r.returncode == 0, r.stderr
    dest = Path(json.loads(r.stdout.strip().splitlines()[-1])["path"])
    assert dest.resolve() == (parent / "shop" / "cam-docs").resolve() and dest.is_dir()
