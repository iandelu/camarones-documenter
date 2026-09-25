"""Stack + tooling radar: a static, offline scan of the repos for the tools the team already uses (no AI, no network)."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest

from conftest import KIT_DIR

TOOLING = {
    "api": {
        "pom.xml": ("<project><artifactId>api</artifactId><properties><java.version>21</java.version></properties>"
                    "<dependencies><dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
                    "<dependency><artifactId>springdoc-openapi-starter-webmvc-ui</artifactId></dependency>"
                    "<dependency><artifactId>testcontainers</artifactId></dependency></dependencies>"
                    "<build><plugins><plugin><artifactId>maven-checkstyle-plugin</artifactId></plugin>"
                    "<plugin><artifactId>sonar-maven-plugin</artifactId></plugin></plugins></build></project>\n"),
        "catalog-info.yaml": ("apiVersion: backstage.io/v1alpha1\nkind: Component\nmetadata:\n  name: api\n"
                              "spec:\n  type: service\n  owner: team-pets\n  system: petclinic\n  lifecycle: production\n"),
        "sonar-project.properties": "sonar.projectKey=acme_api\nsonar.host.url=https://sonar.acme.test\n",
        "src/main/resources/openapi.yaml": "openapi: 3.0.0\n",
        "Dockerfile": "FROM eclipse-temurin:21\n",
        "mvnw": "#!/bin/sh\n",
        "deploy/app.yaml": "apiVersion: argoproj.io/v1alpha1\nkind: Application\n",
        ".gitlab-ci.yml": "test:\n  script: mvn verify\n",
    },
    "web": {
        "package.json": ('{"name": "web", "dependencies": {"react": "18.0.0", "@mui/material": "5.0.0"},'
                         ' "devDependencies": {"eslint": "9.0.0", "@storybook/react": "8.0.0", "vitest": "1.0.0"}}\n'),
        ".storybook/main.js": "export default {}\n",
        "eslint.config.js": "export default []\n",
        ".github/workflows/ci.yml": "on: push\n",
    },
}


def add_files(kit, files: dict[str, dict[str, str]]) -> None:
    for repo, tree in files.items():
        for rel, text in tree.items():
            f = kit.ws / repo / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def radar(kit):
    import importlib
    kit.radar = importlib.import_module("lib.radar")
    return kit


def tool(result: dict, repo: str, tid: str) -> dict:
    found = {t["id"]: t for t in result[repo]["tools"]}
    assert tid in found, f"{tid} not detected in {repo}: {sorted(found)}"
    return found[tid]


# ---------- characterization: the first-look stack guess the radar reuses ----------
def test_quickarch_stack_on_the_fixture_repos(kit):
    tech = {n: r["tech"] for n, r in kit.quickarch.scan()["repos"].items()}
    assert tech == {"api": "Java", "web": "Node.js · React", "worker": "Python"}


# ---------- detection ----------
def test_plain_repos_have_a_stack_and_few_tools(radar):
    res = radar.radar.scan()
    assert res["api"]["stack"] == "Java" and res["worker"]["stack"] == "Python"
    assert "backstage" not in {t["id"] for t in res["api"]["tools"]}


def test_detects_the_tools_the_team_already_uses(radar):
    add_files(radar, TOOLING)
    res = radar.radar.scan()
    assert res["api"]["stack"] == "Java 21 · Spring Boot"
    for tid in ("backstage", "sonar", "checkstyle", "openapi", "springdoc", "testcontainers", "docker",
                "maven-wrapper", "argocd", "gitlab-ci"):
        tool(res, "api", tid)
    for tid in ("storybook", "mui", "eslint", "vitest", "github-actions"):
        tool(res, "web", tid)
    assert tool(res, "api", "openapi")["evidence"] == ["api:src/main/resources/openapi.yaml"]
    assert tool(res, "web", "storybook")["evidence"][0] in ("web:.storybook", "web:package.json")


def test_reads_backstage_and_sonar_metadata(radar):
    add_files(radar, TOOLING)
    res = radar.radar.scan()
    assert tool(res, "api", "backstage")["info"] == {"name": "api", "type": "service", "owner": "team-pets",
                                                      "system": "petclinic", "lifecycle": "production"}
    assert tool(res, "api", "sonar")["info"]["link"] == "https://sonar.acme.test/dashboard?id=acme_api"


def test_framework_names_in_vendored_code_do_not_change_the_stack(radar):
    add_files(radar, {"web": {"docs/js/libs/vis.min.js": 'x = {"next": 1, "vue": 2}\n'}})    # seen in PetClinic Angular
    assert radar.radar.scan()["web"]["stack"] == "Node.js · React"


def test_sonar_configured_in_the_build_file(radar):
    add_files(radar, {"api": {"pom.xml": ("<project><properties><sonar.organization>acme</sonar.organization>"
                                          "<sonar.host.url>https://sonarcloud.io</sonar.host.url></properties></project>\n")},
                      "web": {"build.gradle": 'sonar {\n  properties {\n    property "sonar.projectKey", "acme_web"\n'
                                              '    property "sonar.organization", "acme"\n  }\n}\n'}})
    res = radar.radar.scan()
    assert tool(res, "api", "sonar")["info"] == {"organization": "acme",
                                                  "link": "https://sonarcloud.io/organizations/acme/projects"}
    assert tool(res, "web", "sonar")["info"]["link"] == "https://sonarcloud.io/dashboard?id=acme_web"


def test_broken_catalog_file_does_not_stop_the_scan(radar):
    add_files(radar, {"api": {"catalog-info.yaml": "metadata: [unclosed\n"}})
    assert tool(radar.radar.scan(), "api", "backstage")["info"] == {}


def test_build_output_and_dependencies_are_ignored(radar):
    add_files(radar, {"web": {"node_modules/x/.storybook/main.js": "", "node_modules/x/Dockerfile": ""}})
    ids = {t["id"] for t in radar.radar.scan()["web"]["tools"]}
    assert "storybook" not in ids and "docker" not in ids


# ---------- page ----------
def test_page_is_a_valid_draft_with_resolvable_sources(radar):
    add_files(radar, TOOLING)
    written = radar.radar.run()
    page = radar.docs.DOCS / "overview" / "tooling.md"
    assert written == page and page.exists()
    fm, body = radar.docs.split_fm(page.read_text(encoding="utf-8"))
    assert fm["type"] == "overview" and fm["x-owner"] == "ai" and "x-confirmed" not in fm
    assert "api:catalog-info.yaml" in fm["x-sources"]
    assert "team-pets" in body and "https://sonar.acme.test/dashboard?id=acme_api" in body
    errors, _ = radar.docs.check()
    assert not [e for e in errors if "tooling.md" in e]


def test_removed_tool_shows_as_orphan_until_rescanned(radar):
    add_files(radar, TOOLING)
    radar.radar.run()
    (radar.ws / "api" / "sonar-project.properties").unlink()
    errors, _ = radar.docs.check()
    assert any("tooling.md" in e and "sonar-project.properties" in e for e in errors)
    radar.radar.run()
    errors, _ = radar.docs.check()
    assert not [e for e in errors if "tooling.md" in e]


def test_rescan_keeps_a_human_confirmation_and_a_human_owned_page(radar):
    radar.radar.run()
    page = radar.docs.DOCS / "overview" / "tooling.md"
    radar.docs.confirm([str(page)], by="ana")
    radar.radar.run()                                                            # same repos → still confirmed
    assert radar.docs.doc_status("overview/tooling.md", page, [])["trust"] == "confirmed"
    add_files(radar, TOOLING)
    radar.radar.run()                                                            # new tools → the human re-checks
    assert radar.docs.doc_status("overview/tooling.md", page, [])["trust"] == "needs-reconfirm"
    fm, body = radar.docs.split_fm(page.read_text(encoding="utf-8"))
    page.write_text(radar.docs.join_fm({**fm, "x-owner": "human"}, body + "\nHand notes.\n"), encoding="utf-8")
    radar.radar.run()
    assert "Hand notes." in page.read_text(encoding="utf-8")


# ---------- stack override (workspace.yaml repos[i].stack) ----------
def test_stack_override_wins_and_can_be_reset(radar):
    radar.radar.set_stack("api", "Java 21 · Spring Boot 3")
    assert radar.docs.workspace()["repos"][0]["stack"] == "Java 21 · Spring Boot 3"
    res = radar.radar.scan()
    assert res["api"]["stack"] == "Java 21 · Spring Boot 3" and res["api"]["detected_stack"] == "Java"
    assert radar.quickarch.scan()["repos"]["api"]["tech"] == "Java 21 · Spring Boot 3"   # C4 draft agrees
    radar.radar.set_stack("api", None)
    assert "stack" not in radar.docs.workspace()["repos"][0]
    assert radar.radar.scan()["api"]["stack"] == "Java"


def test_unknown_repo_is_rejected(radar):
    with pytest.raises(ValueError):
        radar.radar.set_stack("nope", "Go")


# ---------- CLI ----------
def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


def test_cli_radar_json_and_stack(radar):
    add_files(radar, TOOLING)
    r = cli(radar, "stack", "web", "TypeScript · React 18")
    assert r.returncode == 0, r.stdout + r.stderr
    r = cli(radar, "radar", "--json")
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data["web"]["stack"] == "TypeScript · React 18"
    assert "backstage" in {t["id"] for t in data["api"]["tools"]}
    assert (radar.docs.DOCS / "overview" / "tooling.md").exists()
    r = cli(radar, "stack", "web", "--reset")
    assert r.returncode == 0 and "stack" not in radar.docs.workspace()["repos"][1]
    r = cli(radar, "stack", "nope", "Go")
    assert r.returncode != 0
