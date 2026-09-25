"""End to end on real repos (Spring PetClinic REST + Angular, pinned): document with the CLI, then uninstall, and the
workspace must be indistinguishable from a fresh clone. Needs network the first time (clones are cached).
Run: uv run pytest -m e2e"""
from __future__ import annotations

import importlib.util, os, subprocess, sys

import pytest

from conftest import REPO

pytestmark = pytest.mark.e2e

spec = importlib.util.spec_from_file_location("sandbox", REPO / "scripts" / "sandbox.py")
sandbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sandbox)

WIRE = """
from lib import docs, env
ws = docs.workspace(); ws["project"]["repo_pointer"] = True; docs.save_workspace(ws)
env.wire_umbrella(print, ["agents"])
for r in docs.repo_names():
    env.link_repo_wiki(r); env.add_repo_pointer(r)
"""


@pytest.fixture
def folder(tmp_path, isolated_env):
    f = tmp_path / "petclinic"
    sandbox.clone_all(f)
    assert sandbox.traces(f, home=isolated_env) == []
    return f


def kit(folder, *args, code: str | None = None) -> subprocess.CompletedProcess:
    env = {**sandbox.kit_env(folder), "PYTHONPATH": str(sandbox.KIT.parent)}
    cmd = [sys.executable, "-c", code] if code else [sys.executable, str(sandbox.KIT), *args]
    r = subprocess.run(cmd, cwd=folder, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"{args or 'python'}:\n{r.stdout}\n{r.stderr}"
    return r


def test_document_then_uninstall_leaves_no_trace(folder, isolated_env):
    (folder / sandbox.CAM_DIR).mkdir()
    kit(folder, "init")
    assert "2 repo(s)" in kit(folder, "detect").stdout
    kit(folder, code=WIRE)                                   # the offline part of setup: links, pointer, agent config
    kit(folder, "arch-draft", "--save")
    kit(folder, "plan", "sync")
    kit(folder, "status")
    subprocess.run([sys.executable, str(sandbox.KIT), "check"], cwd=folder, env=sandbox.kit_env(folder),
                   capture_output=True)                     # a fresh project may fail the gate; it only must not crash
    kit(folder, "llms")
    kit(folder, "checkpoint", "e2e")
    assert (folder / sandbox.CAM_DIR / "docs" / "architecture" / "model.c4").is_file()
    left = sandbox.traces(folder, home=isolated_env)
    assert any("openwiki" in t for t in left) and any("cam-docs" in t for t in left)

    preview = kit(folder, "uninstall", "--dry-run").stdout
    assert "spring-petclinic-rest/openwiki" in preview
    kit(folder, "uninstall", "--yes", "--no-backup")
    assert sandbox.traces(folder, home=isolated_env) == []
    assert sorted(os.listdir(folder)) == sorted(sandbox.REPOS)
