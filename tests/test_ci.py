"""R27: CI jobs from one definition (lib/ci.py). The generated GitHub and GitLab YAML is locked by golden files for both
`ci.target` values; the umbrella workflow gains a pull-request check that can never reach the AI steps."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from conftest import KIT_DIR

GOLDEN = Path(__file__).parent / "golden" / "ci"
LOCAL = {"target": "local", "runner_labels": ["self-hosted"], "runner_tags": [], "kit_repo": "https://example.test/kit.git",
         "kit_ref": "v9.9.9", "uv": "0.12.18"}
SELF = {**LOCAL, "target": "self-hosted", "runner_labels": ["self-hosted", "linux", "docs"], "runner_tags": ["docs"]}


@pytest.fixture
def ci(kit):
    import importlib
    return importlib.import_module("lib.ci")


@pytest.mark.parametrize("forge", ["github", "gitlab"])
@pytest.mark.parametrize("name, cfg", [("local", LOCAL), ("self-hosted", SELF)])
def test_generated_yaml_matches_the_golden_file(ci, forge, name, cfg):
    text = ci.render(forge, cfg=cfg)
    golden = GOLDEN / f"docs-fresh.{forge}.{name}.yml"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(text, encoding="utf-8", newline="\n")
    assert text == golden.read_text(encoding="utf-8")


def test_where_it_runs_is_config(ci):
    gh = yaml.safe_load(ci.render("github", cfg=SELF))
    assert gh["jobs"]["docs-fresh"]["runs-on"] == ["self-hosted", "linux", "docs"]
    assert yaml.safe_load(ci.render("github", cfg=LOCAL))["jobs"]["docs-fresh"]["runs-on"] == "ubuntu-latest"
    assert yaml.safe_load(ci.render("gitlab", cfg=SELF))["docs:fresh"]["tags"] == ["docs"]
    assert "tags" not in yaml.safe_load(ci.render("gitlab", cfg=LOCAL))["docs:fresh"]


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_the_job_needs_no_ai_and_never_blocks(ci, forge):
    text = ci.render(forge, cfg=LOCAL)
    assert not any(w in text for w in ("claude", "codex", "ANTHROPIC", "OPENAI"))
    assert "pr fresh" in text and "--post" in text
    if forge == "gitlab":
        assert yaml.safe_load(text)["docs:fresh"]["allow_failure"] is True
    else:
        assert yaml.safe_load(text)[True] == {"pull_request": None}         # YAML reads `on:` as True


def test_the_project_config_is_read(kit, ci):
    ws = kit.docs.workspace()
    ws["ci"] = {"target": "self-hosted", "runner_labels": ["self-hosted", "docs"], "runner_tags": ["docs-ai"]}
    kit.docs.save_workspace(ws)
    assert ci.config()["runner_tags"] == ["docs-ai"]
    assert "runs-on: [self-hosted, docs]" in ci.render("github")


def test_camaron_ci_writes_the_service_repo_job(kit, ci):
    kit.env.install_ci("github", log=lambda _: None)
    assert (kit.root / ".camarones" / "ci" / "docs-fresh.github.yml").read_text(encoding="utf-8") == ci.render("github")
    kit.env.install_ci("gitlab", log=lambda _: None)
    assert (kit.root / ".camarones" / "ci" / "docs-fresh.gitlab-ci.yml").exists()


def test_the_umbrella_checks_pull_requests_without_ai():
    wf = yaml.safe_load((KIT_DIR / "ci" / "umbrella.github.yml").read_text(encoding="utf-8"))
    assert "pull_request" in wf[True]
    assert "pull_request" in wf["jobs"]["docs"]["if"]                     # the AI job never runs for a PR
    check = wf["jobs"]["check"]
    assert check["if"] == "github.event_name == 'pull_request'"
    steps = yaml.safe_dump(check["steps"])
    assert "camaron check" in steps and "claude" not in steps and "codex" not in steps
    gl = yaml.safe_load((KIT_DIR / "ci" / "umbrella.gitlab-ci.yml").read_text(encoding="utf-8"))
    assert any("merge_request_event" in r.get("if", "") for r in gl["docs:verify"]["rules"])
    assert not any("merge_request_event" in r.get("if", "") for r in gl["docs:update"]["rules"])


@pytest.mark.parametrize("name", ["umbrella.github.yml", "umbrella.gitlab-ci.yml"])
def test_the_umbrella_installs_the_command_its_steps_call(name):
    text = (KIT_DIR / "ci" / name).read_text(encoding="utf-8")
    assert "/usr/local/bin/camaron " in text or "/usr/local/bin/camaron\n" in text or "bin/camaron >" in text
    assert "camaron check" in text


# ---------- the kit the job fetches ----------
def _kit_repo(tmp_path, tags=()):
    import subprocess
    src = tmp_path / "kit-src"
    (src / ".camarones").mkdir(parents=True)
    (src / ".camarones" / "camarones.py").write_text("# kit\n", encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "kit"], *[["tag", t] for t in tags]):
        subprocess.run(["git", *args], cwd=src, check=True, capture_output=True)
    return src


def _fetch(ci, defn_script, tmp_path, repo, ref):
    """The job's kit-fetch lines, run as the runner runs them (POSIX sh)."""
    import shutil, subprocess
    sh = shutil.which("bash") or shutil.which("sh")
    if not sh:
        pytest.skip("no POSIX shell")
    lines = defn_script.splitlines()
    start = next(i for i, l in enumerate(lines) if "CAMARONES_KIT_REPO" in l and "clone" in l)
    end = next(i for i, l in enumerate(lines) if i > start and l.startswith("CAMARONES_ROOT="))
    block = "\n".join(lines[start:end])
    w = tmp_path / "w"
    w.mkdir()
    env = {**os.environ, "W": w.as_posix(), "CAMARONES_KIT_REPO": repo.as_posix(), "CAMARONES_KIT_REF": ref}
    r = subprocess.run([sh, "-c", "set -eu\n" + block], env=env, capture_output=True, text=True)
    return r, w / ".kit"


@pytest.mark.parametrize("script", ["FRESH_SCRIPT", "PROPOSE_SCRIPT"])
def test_a_kit_version_with_no_tag_falls_back_to_the_default_branch(ci, tmp_path, script):
    """The default ref is v<kit>, but the kit repo is not tagged for every version: the job must still get a kit."""
    r, kit = _fetch(ci, getattr(ci, script), tmp_path, _kit_repo(tmp_path), "v9.9.9")
    assert r.returncode == 0, r.stderr
    assert (kit / ".camarones" / "camarones.py").is_file()
    assert "v9.9.9" in r.stderr                                        # says it fell back, and from what


def test_a_tagged_kit_version_is_fetched_at_its_tag(ci, tmp_path):
    import subprocess
    repo = _kit_repo(tmp_path, tags=["v9.9.9"])
    (repo / "later.txt").write_text("after the tag\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "later"], cwd=repo, check=True)
    r, kit = _fetch(ci, ci.FRESH_SCRIPT, tmp_path, repo, "v9.9.9")
    assert r.returncode == 0, r.stderr
    assert (kit / ".camarones" / "camarones.py").is_file() and not (kit / "later.txt").exists()
