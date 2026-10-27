"""Library inventory (S7): every repo's direct dependencies, read from its manifests and lockfiles without AI or
network, each with its version, scope (runtime, test, build) and category (framework, data, cache, security,
messaging, testing…), the same library at two versions across repos flagged, and the result as an AI-draft page
whose x-sources are the manifests."""
from __future__ import annotations

import json

import pytest

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId>
    <version>3.4.1</version></parent>
  <artifactId>api</artifactId>
  <properties><jjwt.version>0.12.6</jjwt.version></properties>
  <dependencies>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-security</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-redis</artifactId></dependency>
    <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId><scope>runtime</scope></dependency>
    <dependency><groupId>io.jsonwebtoken</groupId><artifactId>jjwt-api</artifactId><version>${jjwt.version}</version></dependency>
    <dependency><groupId>org.springframework.kafka</groupId><artifactId>spring-kafka</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>
    <dependency><groupId>com.acme</groupId><artifactId>acme-utils</artifactId><version>1.0</version></dependency>
  </dependencies>
</project>
"""
PACKAGE = {"name": "web", "dependencies": {"react": "^18.2.0", "axios": "^1.6.0", "firebase": "^10.7.0",
                                           "lodash": "4.17.20"},
           "devDependencies": {"vitest": "^1.0.0", "typescript": "~5.3.0"}}
LOCK = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/react": {"version": "18.2.0"},
                                           "node_modules/axios": {"version": "1.6.2"},
                                           "node_modules/firebase": {"version": "10.7.1"},
                                           "node_modules/lodash": {"version": "4.17.20"},
                                           "node_modules/vitest": {"version": "1.0.4"},
                                           "node_modules/typescript": {"version": "5.3.3"}}}
PYPROJECT = """[project]
name = "worker"
dependencies = [
  "fastapi>=0.110",
  "sqlalchemy==2.0.25",
  "redis",
]

[dependency-groups]
dev = ["pytest>=8"]
"""
UVLOCK = """version = 1

[[package]]
name = "fastapi"
version = "0.110.3"

[[package]]
name = "sqlalchemy"
version = "2.0.25"

[[package]]
name = "redis"
version = "5.0.1"

[[package]]
name = "pytest"
version = "8.1.1"
"""


@pytest.fixture
def repos(kit):
    (kit.ws / "api" / "pom.xml").write_text(POM, encoding="utf-8")
    (kit.ws / "web" / "package.json").write_text(json.dumps(PACKAGE), encoding="utf-8")
    (kit.ws / "web" / "package-lock.json").write_text(json.dumps(LOCK), encoding="utf-8")
    (kit.ws / "worker" / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (kit.ws / "worker" / "uv.lock").write_text(UVLOCK, encoding="utf-8")
    from lib import inventory
    return inventory


def rows(inv, repo):
    return {r["name"]: r for r in inv.scan()["libraries"] if r["repo"] == repo}


def test_maven_with_properties_managed_versions_and_scopes(repos):
    api = rows(repos, "api")
    assert api["io.jsonwebtoken:jjwt-api"]["version"] == "0.12.6"
    web = api["org.springframework.boot:spring-boot-starter-web"]
    assert web["version"] is None and web["managedBy"] == "org.springframework.boot:spring-boot-starter-parent:3.4.1"
    assert api["org.postgresql:postgresql"]["scope"] == "runtime"
    assert api["org.springframework.boot:spring-boot-starter-test"]["scope"] == "test"
    assert web["ecosystem"] == "Maven" and web["language"] == "Java" and web["source"] == "api:pom.xml"


@pytest.mark.parametrize("repo, name, category", [
    ("api", "org.springframework.boot:spring-boot-starter-web", "framework"),
    ("api", "org.springframework.boot:spring-boot-starter-security", "security"),
    ("api", "io.jsonwebtoken:jjwt-api", "security"),
    ("api", "org.springframework.boot:spring-boot-starter-data-redis", "cache"),
    ("api", "org.postgresql:postgresql", "data"),
    ("api", "org.springframework.kafka:spring-kafka", "messaging"),
    ("api", "org.springframework.boot:spring-boot-starter-test", "testing"),
    ("api", "com.acme:acme-utils", "other"),
    ("web", "react", "framework"),
    ("web", "axios", "http"),
    ("web", "firebase", "cloud-sdk"),
    ("web", "vitest", "testing"),
    ("web", "typescript", "build"),
    ("worker", "fastapi", "framework"),
    ("worker", "sqlalchemy", "data"),
    ("worker", "redis", "cache"),
    ("worker", "pytest", "testing"),
])
def test_categories(repos, repo, name, category):
    assert rows(repos, repo)[name]["category"] == category


def test_npm_and_python_take_the_locked_version(repos):
    web, worker = rows(repos, "web"), rows(repos, "worker")
    assert (web["axios"]["version"], web["axios"]["declared"]) == ("1.6.2", "^1.6.0")
    assert web["vitest"]["scope"] == "dev" and web["react"]["scope"] == "runtime" and web["react"]["language"] == "JavaScript"
    assert worker["fastapi"]["version"] == "0.110.3" and worker["pytest"]["scope"] == "dev"
    assert worker["fastapi"]["ecosystem"] == "PyPI" and worker["fastapi"]["source"] == "worker:pyproject.toml"


# (name, version — exact or locked, declared — what the manifest says, ecosystem, category)
@pytest.mark.parametrize("files, expected", [
    ({"go.mod": "module x\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n\tgithub.com/redis/go-redis/v9 v9.4.0 // indirect\n)\n"},
     {("github.com/gin-gonic/gin", "v1.9.1", "v1.9.1", "Go", "framework")}),
    ({"build.gradle.kts": 'dependencies {\n  implementation("io.ktor:ktor-server-core:2.3.7")\n'
                          '  testImplementation("io.mockk:mockk:1.13.8")\n}\n'},
     {("io.ktor:ktor-server-core", "2.3.7", "2.3.7", "Maven", "framework"),
      ("io.mockk:mockk", "1.13.8", "1.13.8", "Maven", "testing")}),
    ({"App.csproj": '<Project><ItemGroup><PackageReference Include="Npgsql" Version="8.0.1" /></ItemGroup></Project>'},
     {("Npgsql", "8.0.1", "8.0.1", "NuGet", "data")}),
    ({"composer.json": '{"require": {"laravel/framework": "^10.0"}, "require-dev": {"phpunit/phpunit": "^10"}}'},
     {("laravel/framework", None, "^10.0", "Packagist", "framework"),
      ("phpunit/phpunit", None, "^10", "Packagist", "testing")}),
    ({"Cargo.toml": '[package]\nname = "x"\n\n[dependencies]\ntokio = { version = "1.35", features = ["full"] }\n'
                    'serde = "1.0"\n'},
     {("tokio", None, "1.35", "crates.io", "framework"), ("serde", None, "1.0", "crates.io", "other")}),
    ({"pubspec.yaml": "name: admin_dj\ndependencies:\n  flutter:\n    sdk: flutter\n  cloud_firestore: ^4.13.0\n"
                      "  firebase_auth: ^4.15.0\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\n"},
     {("flutter", None, "sdk", "Pub", "framework"), ("cloud_firestore", None, "^4.13.0", "Pub", "data"),
      ("firebase_auth", None, "^4.15.0", "Pub", "security"), ("flutter_test", None, "sdk", "Pub", "testing")}),
    ({"requirements.txt": "django==4.2.9\npsycopg2-binary>=2.9  # db\n-r other.txt\n"},
     {("django", "4.2.9", "==4.2.9", "PyPI", "framework"), ("psycopg2-binary", None, ">=2.9", "PyPI", "data")}),
])
def test_other_ecosystems(kit, files, expected):
    for rel, text in files.items():
        (kit.ws / "worker" / rel).write_text(text, encoding="utf-8")
    (kit.ws / "worker" / "pyproject.toml").unlink()
    from lib import inventory
    got = {(r["name"], r["version"], r["declared"], r["ecosystem"], r["category"])
           for r in inventory.scan()["libraries"] if r["repo"] == "worker"}
    assert got == expected


def test_the_same_library_at_two_versions_is_flagged(kit, repos):
    other = dict(PACKAGE, name="admin", dependencies={"lodash": "4.17.21"}, devDependencies={})
    (kit.ws / "api" / "package.json").write_text(json.dumps(other), encoding="utf-8")
    libs = [r for r in repos.scan()["libraries"] if r["name"] == "lodash"]
    assert {r["repo"] for r in libs} == {"web", "api"} and all(r["drift"] for r in libs)
    assert not rows(repos, "web")["react"]["drift"]


def test_the_page_is_a_draft_citing_the_manifests(kit, repos):
    page = repos.run(log=lambda _: None)
    fm, body = kit.docs.split_fm(page.read_text(encoding="utf-8"))
    assert fm["type"] == "overview" and "api:pom.xml" in fm["x-sources"] and "web:package.json" in fm["x-sources"]
    assert "spring-boot-starter-security" in body and "## api" in body and "| security |" in body
    data = json.loads((kit.root / "docs" / ".work" / "inventory.json").read_text(encoding="utf-8"))
    assert data["libraries"] and data["vulns"] is None                          # no CVE scan asked for
    fm["x-owner"] = "human"
    page.write_text(kit.docs.join_fm(fm, "# Mine\n"), encoding="utf-8")
    repos.run(log=lambda _: None)
    assert "# Mine" in page.read_text(encoding="utf-8")                         # a human's page is never rewritten


def test_a_lockfile_that_cannot_be_read_does_not_hide_the_manifest(kit, repos):
    (kit.ws / "web" / "package-lock.json").write_text("{" + " " * 400_000, encoding="utf-8")     # big and broken
    web = rows(repos, "web")
    assert web["axios"]["version"] is None and web["axios"]["declared"] == "^1.6.0" and web["lodash"]["version"] == "4.17.20"


def test_a_big_lockfile_is_still_read(kit, repos):
    lock = dict(LOCK, packages={**LOCK["packages"], **{f"node_modules/pad-{i}": {"version": "1.0.0"} for i in range(9000)}})
    (kit.ws / "web" / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    assert rows(repos, "web")["axios"]["version"] == "1.6.2"


def test_the_cli(kit, repos):
    import os, subprocess, sys
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "inventory", "--json"], env=env,
                       capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert {x["repo"] for x in data["libraries"]} == {"api", "web", "worker"} and data["vulns"] is None
    assert (kit.root / "docs" / "overview" / "libraries.md").is_file()
    assert "libraries in 3 repos" in r.stderr          # --json: what it is doing goes to stderr, stdout stays JSON


def test_the_portal_reads_it_and_refreshes_it(kit, repos):
    import time
    from lib import serve
    first = serve.api_inventory()
    assert first["libraries"] and first["vulns"] is None and not (kit.root / "docs" / ".work" / "inventory.json").exists()
    job = serve.inventory_job({"cves": False})
    for _ in range(200):
        if serve.JOBS[job["id"]]["status"] != "running":
            break
        time.sleep(0.05)
    assert serve.JOBS[job["id"]]["status"] == "done"
    assert serve.api_inventory()["libraries"] == repos.load()["libraries"]


def test_the_libraries_tldr_counts_and_drift(kit, repos):
    other = dict(PACKAGE, name="admin", dependencies={"lodash": "4.17.21"}, devDependencies={})
    (kit.ws / "api" / "package.json").write_text(json.dumps(other), encoding="utf-8")
    result = repos.scan()
    text = repos.render(result)
    n, d = len(result["libraries"]), len({r["name"] for r in result["libraries"] if r["drift"]})
    assert d >= 1 and f"> **TL;DR:** {n} direct dependencies across 3 repos; " in text
    assert text.split(":::details How this page is made")[0].count("with known vulnerabilities") == 0
    assert "camaron inventory --cves" in text.split(":::details How this page is made")[1]
    assert text.rstrip().endswith(":::")


def test_the_libraries_tldr_counts_vulnerabilities_and_no_manifests(kit, repos):
    result = repos.scan()
    result["vulns"] = []
    result["libraries"][0]["vulns"] = [{"id": "X", "cve": "CVE-1", "severity": "HIGH", "fixed": None}]
    assert "; 1 library with known vulnerabilities." in repos.render(result)
    assert "> **TL;DR:** no direct dependencies across 3 repos." in repos.render({"libraries": []})   # the workspace's


def test_the_libraries_tldr_counts_every_workspace_repo(kit, repos):
    result = repos.scan()
    result["libraries"] = [r for r in result["libraries"] if r["repo"] == "api"]
    assert "> **TL;DR:** " in repos.render(result) and " across 3 repos" in repos.render(result)


def test_finding_vulnerabilities_is_not_a_failure_unless_asked(kit, repos):
    """A scan that found vulnerabilities did its job (the desktop app showed it as failed); CI asks to fail with
    --fail-on high|critical, and then the known findings decide, from this scan or the last one."""
    import os, subprocess, sys
    repos.run(log=lambda _: None)
    data = repos.load()
    for r in data["libraries"]:
        if (r["repo"], r["name"]) == ("web", "axios"):
            r["vulns"] = [{"id": "GHSA-x", "cve": "CVE-1", "summary": "", "severity": "high", "score": 7.5, "fixed": "1.6.3"}]
    data["vulns"] = {"scanned": 3, "failed": [], "online": False, "vulnerable": 1, "at": "2026-10-27T10:00:00+00:00"}
    (kit.root / "docs" / ".work" / "inventory.json").write_text(json.dumps(data), encoding="utf-8")
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    run = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "inventory", "--json", *a],  # noqa: E731
                                    env=env, capture_output=True, text=True, encoding="utf-8", cwd=kit.ws).returncode
    assert run() == 0
    assert run("--fail-on", "high") == 1
    assert run("--fail-on", "critical") == 0
