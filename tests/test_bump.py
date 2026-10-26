"""Updating a library from the app (inventory → bump): on a new branch of that service repo, with its own package
manager (npm, pnpm, yarn, uv, poetry, go) or, for manifests without one, by rewriting the version in place (Maven,
Gradle, requirements). Never on a repo with uncommitted changes, never a commit or a push: the person reviews the
branch. A failed update leaves the repo as it was, on the branch it was on."""
from __future__ import annotations

import json, subprocess

import pytest

from test_inventory import LOCK, PACKAGE, POM, PYPROJECT, UVLOCK, repos  # noqa: F401 — the three-repo fixture


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def committed(kit, repos):  # noqa: F811
    for name in ("api", "web", "worker"):
        git(kit.ws / name, "add", "-A")
        git(kit.ws / name, "commit", "-q", "-m", "manifests")
    from lib import bump
    return bump


@pytest.fixture
def tools(committed, monkeypatch):
    """The package managers, faked: each call is recorded and writes what the real one would change."""
    calls = []

    def fake(argv, cwd, log):
        calls.append((argv, cwd.name))
        if argv[0] == "npm":
            pkg = json.loads((cwd / "package.json").read_text(encoding="utf-8"))
            name, spec = argv[2].rsplit("@", 1)
            pkg["devDependencies" if "--save-dev" in argv else "dependencies"][name] = spec
            (cwd / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        return 0
    monkeypatch.setattr(committed, "_tool", fake)
    monkeypatch.setattr(committed, "which", lambda name: f"/bin/{name}")
    return calls


def test_npm_keeps_the_range_style_and_the_dev_section(kit, committed, tools):
    p = committed.plan("web", "react", "18.3.1")
    assert p["argv"] == ["npm", "install", "react@^18.3.1"] and p["branch"] == "camaron/bump-react-18.3.1"
    assert p["manifest"] == "web/package.json" and p["from"] == "18.2.0"
    assert committed.plan("web", "lodash", "4.17.21")["argv"] == ["npm", "install", "lodash@4.17.21", "--save-exact"]
    assert committed.plan("web", "vitest", "1.6.1")["argv"] == ["npm", "install", "vitest@^1.6.1", "--save-dev"]
    (kit.ws / "web" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    assert committed.plan("web", "vitest", "1.6.1")["argv"] == ["pnpm", "add", "vitest@^1.6.1", "--save-dev"]


def test_an_update_goes_on_its_own_branch_and_is_not_committed(kit, committed, tools):
    web = kit.ws / "web"
    head = git(web, "rev-parse", "HEAD")
    r = committed.apply("web", "lodash", "4.17.21", log=lambda _: None)
    assert r["branch"] == "camaron/bump-lodash-4.17.21" and r["was"] == "main" and r["files"] == ["package.json"]
    assert git(web, "rev-parse", "--abbrev-ref", "HEAD") == "camaron/bump-lodash-4.17.21"
    assert git(web, "rev-parse", "HEAD") == head                        # nothing committed: the person reviews it
    assert json.loads((web / "package.json").read_text(encoding="utf-8"))["dependencies"]["lodash"] == "4.17.21"
    assert tools == [(["npm", "install", "lodash@4.17.21", "--save-exact"], "web")]
    lodash = next(x for x in __import__("lib.inventory").inventory.load()["libraries"]
                  if x["repo"] == "web" and x["name"] == "lodash")
    assert lodash["declared"] == "4.17.21"                              # the inventory is read again


def test_a_repo_with_uncommitted_changes_is_not_touched(kit, committed, tools):
    (kit.ws / "web" / "notes.txt").write_text("wip", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted"):
        committed.apply("web", "lodash", "4.17.21", log=lambda _: None)
    assert git(kit.ws / "web", "rev-parse", "--abbrev-ref", "HEAD") == "main" and not tools


def test_a_failed_update_puts_the_repo_back(kit, committed, tools, monkeypatch):
    web = kit.ws / "web"

    def broken(argv, cwd, log):
        (cwd / "package.json").write_text("{}", encoding="utf-8")
        return 1
    monkeypatch.setattr(committed, "_tool", broken)
    with pytest.raises(RuntimeError, match="npm"):
        committed.apply("web", "lodash", "4.17.21", log=lambda _: None)
    assert git(web, "rev-parse", "--abbrev-ref", "HEAD") == "main" and git(web, "status", "--porcelain") == ""
    assert "camaron/bump-lodash-4.17.21" not in git(web, "branch")


def test_python_with_uv_and_a_requirements_file(kit, committed, tools):
    p = committed.plan("worker", "sqlalchemy", "2.0.30")
    assert p["argv"] == ["uv", "add", "sqlalchemy==2.0.30"]
    assert committed.plan("worker", "pytest", "8.3.0")["argv"] == ["uv", "add", "pytest>=8.3.0", "--dev"]
    worker = kit.ws / "worker"
    (worker / "uv.lock").unlink()
    (worker / "pyproject.toml").unlink()
    (worker / "requirements.txt").write_text("fastapi>=0.110\nrequests==2.31.0  # http\n", encoding="utf-8")
    git(worker, "add", "-A")
    git(worker, "commit", "-q", "-m", "requirements")
    assert committed.plan("worker", "requests", "2.32.3")["argv"] is None            # rewritten in place
    committed.apply("worker", "requests", "2.32.3", log=lambda _: None)
    assert (worker / "requirements.txt").read_text(encoding="utf-8") == "fastapi>=0.110\nrequests==2.32.3  # http\n"
    assert not tools


def test_maven_rewrites_the_property_or_the_version(kit, committed, tools):
    committed.apply("api", "io.jsonwebtoken:jjwt-api", "0.12.7", log=lambda _: None)
    pom = (kit.ws / "api" / "pom.xml").read_text(encoding="utf-8")
    assert "<jjwt.version>0.12.7</jjwt.version>" in pom and pom.count("0.12.6") == 0
    git(kit.ws / "api", "checkout", "-q", "main")
    git(kit.ws / "api", "checkout", "-q", "--", ".")
    git(kit.ws / "api", "branch", "-q", "-D", "camaron/bump-jjwt-api-0.12.7")
    committed.apply("api", "com.acme:acme-utils", "1.1", log=lambda _: None)
    pom = (kit.ws / "api" / "pom.xml").read_text(encoding="utf-8")
    assert "<artifactId>acme-utils</artifactId><version>1.1</version>" in pom
    with pytest.raises(ValueError, match="parent"):                    # its version comes from the parent pom
        committed.plan("api", "org.postgresql:postgresql", "42.7.2")


def test_what_cannot_be_updated_says_why(kit, committed, tools):
    with pytest.raises(KeyError):
        committed.plan("web", "left-pad", "1.3.0")
    with pytest.raises(ValueError, match="version"):
        committed.plan("web", "lodash", "--force")


def test_a_crlf_manifest_keeps_its_line_endings(kit, committed, tools):
    worker = kit.ws / "worker"
    (worker / "uv.lock").unlink()
    (worker / "pyproject.toml").unlink()
    (worker / "requirements.txt").write_bytes(b"fastapi>=0.110\r\nrequests==2.31.0\r\n")
    git(worker, "add", "-A")
    git(worker, "commit", "-q", "-m", "requirements")
    committed.apply("worker", "requests", "2.32.3", log=lambda _: None)
    assert (worker / "requirements.txt").read_bytes() == b"fastapi>=0.110\r\nrequests==2.32.3\r\n"
