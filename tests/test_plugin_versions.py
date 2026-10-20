"""R37 (H25): team plugins are vendored into cam-docs/.camarones/plugins/ and pinned in .camarones/plugins.lock
(version, source, folder fingerprint). Updates are explicit; a code plugin whose files change is asked about again in
trust; check warns when a folder no longer matches the lock; a pipeline node can pin a major version."""
from __future__ import annotations

import os, subprocess, sys

import pytest
import yaml


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def plugin_src(path, version="0.1.0", kit=">=4,<5", provides=None, extra=None):
    path.mkdir(parents=True, exist_ok=True)
    manifest = {"name": "adr-lint", "version": version, "kit": kit,
                "provides": provides or {"checks": [{"id": "adr-lint", "entry": "check.py:run"}]}}
    (path / "plugin.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (path / "check.py").write_text(f"def run(rows, strict=False):\n    return [], []  # {version}\n", encoding="utf-8")
    for rel, text in (extra or {}).items():
        (path / rel).write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def store(wired):
    import importlib
    wired.trust = importlib.import_module("lib.trust")
    wired.plugins = importlib.import_module("lib.harness.plugins")
    return importlib.import_module("lib.harness.plugin_store")


@pytest.fixture
def remote(tmp_path):
    """A plugin repo with tags v0.1.0 and v0.2.0."""
    repo = tmp_path / "adr-lint-repo"
    plugin_src(repo)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "0.1.0")
    git(repo, "tag", "v0.1.0")
    plugin_src(repo, "0.2.0", extra={"README.md": "# adr-lint\n"})
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "0.2.0")
    git(repo, "tag", "v0.2.0")
    return repo


def lock(kit):
    return yaml.safe_load((kit.root / ".camarones" / "plugins.lock").read_text(encoding="utf-8"))["plugins"]


def test_add_from_a_folder_vendors_and_locks_it(wired, store, tmp_path):
    p = store.add(str(plugin_src(tmp_path / "src")))
    assert p.name == "adr-lint" and (wired.root / ".camarones" / "plugins" / "adr-lint" / "check.py").exists()
    entry = lock(wired)["adr-lint"]
    assert entry["version"] == "0.1.0" and entry["source"].startswith("path:") and entry["sha256"] == p.fingerprint()


def test_add_from_git_at_a_tag(wired, store, remote):
    store.add(f"git:{remote}@v0.1.0")
    assert lock(wired)["adr-lint"] == {"version": "0.1.0", "source": f"git:{remote}@v0.1.0",
                                         "sha256": lock(wired)["adr-lint"]["sha256"]}
    assert not (wired.root / ".camarones" / "plugins" / "adr-lint" / ".git").exists()


def test_an_incompatible_plugin_is_refused_and_nothing_is_written(wired, store, tmp_path):
    with pytest.raises(store.PluginError, match="kit: needs kit >=9,<10"):
        store.add(str(plugin_src(tmp_path / "src", kit=">=9,<10")))
    assert not (wired.root / ".camarones" / "plugins" / "adr-lint").exists()
    assert not (wired.root / ".camarones" / "plugins.lock").exists()


def test_adding_twice_says_to_update(wired, store, tmp_path):
    store.add(str(plugin_src(tmp_path / "src")))
    with pytest.raises(store.PluginError, match="plugins update adr-lint"):
        store.add(str(plugin_src(tmp_path / "src")))


def test_outdated_lists_newer_tags(wired, store, remote):
    store.add(f"git:{remote}@v0.1.0")
    assert store.outdated() == [{"name": "adr-lint", "version": "0.1.0", "latest": "0.2.0",
                                 "source": f"git:{remote}@v0.1.0"}]


def test_update_rewrites_the_folder_and_the_lock_and_asks_trust_again(wired, store, remote):
    store.add(f"git:{remote}@v0.1.0")
    wired.trust.approve()
    assert wired.trust.pending() == []
    [change] = store.update("adr-lint", to="v0.2.0")
    assert (change["from"], change["to"]) == ("0.1.0", "0.2.0")
    assert change["files"] == {"added": ["README.md"], "removed": [], "changed": ["check.py", "plugin.yaml"]}
    assert lock(wired)["adr-lint"]["source"] == f"git:{remote}@v0.2.0" and lock(wired)["adr-lint"]["version"] == "0.2.0"
    assert [(it.id, s) for it, s in wired.trust.pending()] == [("plugin adr-lint", "changed")]
    assert store.update("adr-lint") == []                                           # already there: nothing to do


def test_check_warns_about_hand_edits_and_unlocked_folders(wired, store, tmp_path):
    store.add(str(plugin_src(tmp_path / "src")))
    folder = wired.root / ".camarones" / "plugins" / "adr-lint"
    (folder / "check.py").write_text("print('edited')\n", encoding="utf-8")
    other = wired.root / ".camarones" / "plugins" / "loose"
    other.mkdir()
    (other / "plugin.yaml").write_text("name: loose\nversion: 1.0.0\nprovides: {prompts: [p.md]}\n", encoding="utf-8")
    _, warns = wired.docs.check()
    assert any("adr-lint" in w and "plugins.lock" in w and "edited" in w for w in warns)
    assert any("loose" in w and "not in plugins.lock" in w for w in warns)


def test_projects_without_a_lock_keep_working(wired, store):
    folder = wired.root / ".camarones" / "plugins" / "old"
    folder.mkdir(parents=True)
    (folder / "plugin.yaml").write_text("name: old\nversion: 1.0.0\nprovides: {prompts: [p.md]}\n", encoding="utf-8")
    errors, _ = wired.docs.check()
    assert not any("plugins" in e for e in errors)


def test_vendored_plugins_travel_with_checkpoints(wired, store):
    assert {".camarones/plugins", ".camarones/plugins.lock"} <= set(wired.env.CHECKPOINT_PATHS)


def test_remove(wired, store, tmp_path):
    store.add(str(plugin_src(tmp_path / "src")))
    assert store.remove("adr-lint")
    assert not (wired.root / ".camarones" / "plugins" / "adr-lint").exists() and lock(wired) == {}
    with pytest.raises(store.PluginError):
        store.remove("adr-lint")


def test_text_only_plugins_ask_as_steering_agents(wired, store, tmp_path):
    store.add(str(plugin_src(tmp_path / "src", provides={"prompts": ["adr.md"]})))
    (wired.root / ".camarones" / "plugins" / "adr-lint" / "check.py").unlink()
    [(item, status)] = wired.trust.pending()
    assert item.id == "plugin adr-lint" and "steers agents" in item.detail
    assert not next(p for p in wired.plugins.discover() if p.name == "adr-lint").active


# ---------- major pins on pipeline nodes ----------
def test_a_node_can_pin_a_major_version(wired, store, tmp_path):
    store.add(str(plugin_src(tmp_path / "src")))
    wired.trust.approve()
    from lib.harness import pipeline
    spec = pipeline.load("quick")
    spec["nodes"].append({"id": "adr", "type": "decisions-quality", "uses": "adr-lint@0"})
    assert not [e for e in pipeline.validate(spec) if ".uses" in e]
    spec["nodes"][-1]["uses"] = "adr-lint@1"
    assert any(e.endswith(".uses: adr-lint is 0.1.0, the node needs 1.x") for e in pipeline.validate(spec))
    spec["nodes"][-1]["uses"] = "ghost@0"
    assert any(e.endswith(".uses: no plugin 'ghost'") for e in pipeline.validate(spec))


def test_the_commands(wired, store, remote):
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "plugins", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    r = cli("add", f"git:{remote}@v0.1.0")
    assert r.returncode == 0 and "adr-lint 0.1.0" in r.stdout and "trust" in r.stdout          # code: approve it next
    assert "0.2.0" in cli("outdated").stdout
    r = cli("update", "adr-lint", "--to", "v0.2.0")
    assert r.returncode == 0 and "0.1.0 → 0.2.0" in r.stdout and "README.md" in r.stdout
    assert cli("remove", "adr-lint").returncode == 0
    assert cli("add", "nowhere/at/all").returncode == 2
    assert "adr-lint" not in cli("--json").stdout
