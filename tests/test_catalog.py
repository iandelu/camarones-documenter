"""The command catalog (lib/catalog.py): every CLI command with its verdict (portal / app / cli / both). It is the
contract between the CLI, the portal and the desktop app, so it must never drift from the real parser."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


@pytest.fixture(scope="module")
def described(tmp_path_factory):
    """`catalog --json` once for the module: the parser walk is the slow part."""
    from fixtures.builder import make_workspace
    from conftest import purge_kit_modules
    tmp = tmp_path_factory.mktemp("cat")
    home = tmp / "home"
    home.mkdir()
    ws = make_workspace(tmp)
    e = {**os.environ, "CAMARONES_ROOT": str(ws / "cam-docs"), "HOME": str(home), "USERPROFILE": str(home)}
    r = subprocess.run([sys.executable, str(REPO / ".camarones" / "camarones.py"), "catalog", "--json"], env=e,
                       capture_output=True, text=True, encoding="utf-8")
    purge_kit_modules()
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_every_parser_command_is_in_the_catalog_and_nothing_else(described):
    assert described["unlisted"] == [] and described["unknown"] == []
    names = [c["name"] for c in described["commands"]]
    assert len(names) == len(set(names))
    assert {"run", "uninstall", "share", "interview", "catalog"} <= set(names)


def test_check_fails_on_drift(kit):
    from lib import catalog
    unlisted, unknown = catalog.drift(["run", "brand-new"])
    assert "brand-new" in unlisted and "uninstall" in unknown
    assert cli(kit, "catalog", "--check").returncode == 0


def test_entries_are_well_formed(described):
    from lib import catalog
    for c in described["commands"]:
        assert c["verdict"] in catalog.VERDICTS, c
        if c["verdict"] in ("app", "both"):
            assert c["zone"] in catalog.ZONES, c
            assert c["es"].strip() and c["en"].strip(), c
        else:
            assert c["zone"] is None, c
        assert isinstance(c["ai"], bool) and isinstance(c["destructive"], bool)


def test_args_come_from_the_parser(described):
    by = {c["name"]: c for c in described["commands"]}
    run = {a["dest"]: a for a in by["run"]["args"]}
    assert run["parallel"] == {"dest": "parallel", "flag": "--parallel", "kind": "int", "default": 2,
                               "choices": None, "required": False, "positional": False, "many": False}
    assert run["include_interviews"]["kind"] == "bool" and run["include_interviews"]["default"] is False
    assert run["policy"]["kind"] == "choice" and run["policy"]["choices"] == ["on-conflict", "never"]
    assert run["only"]["many"] is True
    iv = {a["dest"]: a for a in by["interview"]["args"]}
    assert iv["action"]["positional"] is True and iv["action"]["flag"] is None
    assert {a["dest"] for a in by["migrate"]["args"]} == {"yes", "dry_run"}      # suppressed --finish stays hidden
    assert by["run"]["json"] is False and by["runs"]["json"] is True


def test_a_yes_flag_means_the_app_confirms_first(described):
    for c in described["commands"]:
        has_yes = any(a["flag"] == "--yes" for a in c["args"])
        assert (c["confirm"] == "--yes") == has_yes, c["name"]
    by = {c["name"]: c for c in described["commands"]}
    assert by["uninstall"]["destructive"] and by["uninstall"]["confirm"] == "--yes"
    assert by["run"]["ai"] and not by["inventory"]["ai"]


def test_triage_report_matches_the_catalog(described):
    from lib import catalog
    assert (REPO / "docs" / "research" / "cli-triage.md").read_text(encoding="utf-8") == \
        catalog.triage_markdown(described["commands"])
