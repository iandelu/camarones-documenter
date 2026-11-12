"""The suite runs the same on a laptop as on CI: the kit's tools and the agent CLIs a machine happens to have are off PATH
for every test (tests/fixtures/host_tools.py), unless the test asks for one by name."""
from __future__ import annotations

import os, re, shutil, subprocess, sys
from pathlib import Path

import pytest
import yaml

from conftest import KIT_DIR
from fixtures.host_tools import HIDDEN, KEPT, hidden_tools, masked_path


def tool(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / (f"{name}.cmd" if os.name == "nt" else name)
    f.write_text("@echo off\r\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
    f.chmod(0o755)
    return f


def test_a_folder_with_only_hidden_tools_drops_out_and_one_without_any_stays(tmp_path):
    only, plain = tmp_path / "only", tmp_path / "plain"
    tool(only, "openwiki")
    tool(plain, "tidy")
    assert masked_path(os.pathsep.join([str(only), str(plain)]), HIDDEN).split(os.pathsep) == [str(plain)]


def test_a_mixed_folder_keeps_everything_but_the_hidden_tools(tmp_path):
    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except OSError:
        pytest.skip("this machine cannot make links (see the next test)")
    mixed = tmp_path / "mixed"
    tool(mixed, "gitleaks")
    tidy = tool(mixed, "tidy")
    path = masked_path(str(mixed), HIDDEN)
    assert path != str(mixed)
    assert shutil.which("gitleaks", path=path) is None
    assert Path(shutil.which("tidy", path=path)).resolve() == tidy.resolve()


def test_where_links_cannot_be_made_a_mixed_folder_stays_as_it_is(tmp_path, monkeypatch):
    def refuse(*_a, **_kw):
        raise OSError("no symlink rights")
    monkeypatch.setattr(Path, "symlink_to", refuse)
    mixed = tmp_path / "mixed"
    tool(mixed, "gitleaks")
    tool(mixed, "tidy")
    assert masked_path(str(mixed), HIDDEN) == str(mixed)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """This machine's own gitleaks and tidy, on PATH before isolated_env sees it."""
    tools, other = tmp_path / "machine-tools", tmp_path / "machine-other"
    tool(tools, "gitleaks")
    tool(other, "tidy")
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), str(other), os.environ["PATH"]]))
    return tools


def test_a_test_sees_none_of_the_machines_tools_but_the_rest_of_its_path(machine, kit):
    assert shutil.which("gitleaks") is None and kit.common.which("gitleaks") is None
    assert shutil.which("tidy") and shutil.which("git")


def test_a_kit_process_the_test_starts_keeps_that_path(machine, kit):
    code = ("import os, sys; sys.path.insert(0, sys.argv[1]); from lib import common; "
            "print(os.environ['PATH']); print(common.which('gitleaks'))")
    r = subprocess.run([sys.executable, "-c", code, str(KIT_DIR)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [os.environ["PATH"], "None"]


@pytest.mark.host_tools("gitleaks")
def test_a_test_can_ask_for_one_of_the_machines_tools(machine, kit):
    assert Path(kit.common.which("gitleaks")).parent == machine


class Node:
    def __init__(self, *marks):
        self.marks = {m.mark.name: m.mark for m in marks}

    def get_closest_marker(self, name):
        return self.marks.get(name)


def test_which_tools_a_test_runs_without(monkeypatch):
    monkeypatch.delenv("CAMARONES_TEST_HOST_TOOLS", raising=False)
    assert hidden_tools(Node()) == hidden_tools() == HIDDEN
    assert hidden_tools(Node(pytest.mark.host_tools("likec4", "gitleaks"))) == HIDDEN - {"likec4", "gitleaks"}
    assert hidden_tools(Node(pytest.mark.e2e)) == hidden_tools(Node(pytest.mark.eval)) == frozenset()
    monkeypatch.setenv("CAMARONES_TEST_HOST_TOOLS", "1")
    assert hidden_tools(Node()) == hidden_tools() == frozenset()


def test_every_program_the_kit_looks_up_is_hidden_or_one_ci_has_too():
    lib = KIT_DIR / "lib"
    found = set(re.findall(r'(?:which|bin_path)\("([\w.-]+)"\)',
                           "\n".join(p.read_text(encoding="utf-8") for p in lib.rglob("*.py"))))
    for manifest in lib.glob("plugins/*/plugin.yaml"):
        found |= {r["argv"][0] for r in yaml.safe_load(manifest.read_text(encoding="utf-8"))
                  .get("provides", {}).get("runners", [])}
    assert found - HIDDEN - KEPT == set()
    assert not HIDDEN & KEPT


def test_the_kit_adds_its_tool_folders_unless_told_path_is_final(kit, tmp_path, monkeypatch):
    extra = tmp_path / "extra"
    extra.mkdir()
    from lib.core import process
    monkeypatch.setattr(process, "extra_bin_dirs", lambda: [extra])
    monkeypatch.setenv("PATH", "base")
    monkeypatch.setenv("CAMARONES_KEEP_PATH", "1")
    process.ensure_path()
    assert os.environ["PATH"] == "base"
    monkeypatch.delenv("CAMARONES_KEEP_PATH")
    process.ensure_path()
    assert os.environ["PATH"].split(os.pathsep) == [str(extra), "base"]
