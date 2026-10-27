"""*Candidatas* (`adr_pack.candidates`): the decisions the code already took that no ADR covers, found without a model
from the library inventory, the C4 model and the deployment sources. A source that is missing or broken leaves its
share out; a fresh project has none."""
from __future__ import annotations

import importlib

import pytest

ROW = dict(ecosystem="maven", version="1", declared="1", language="java", scope="runtime")
MODEL = """model {
  db = container 'Database' {
    technology '%s'
    metadata { repo 'api' }
  }
}
"""


@pytest.fixture
def adr_pack(kit):
    return importlib.import_module("lib.adr_pack")


def lib(repo, name, category, source=None, **more):
    return {**ROW, "repo": repo, "name": name, "category": category, "source": source or f"{repo}:pom.xml", **more}


def seed_inventory(rows):
    from lib.common import WORK, save_json
    save_json(WORK / "inventory.json", {"libraries": rows})


def write(kit, rel, text):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")


def decide(kit, name, text):
    write(kit, f"decisions/{name}.md", text)


def keys(adr_pack):
    return [c["key"] for c in adr_pack.candidates()]


def test_terms(adr_pack):
    assert adr_pack.term("org.springframework.boot:spring-boot-starter-data-jpa") == "data-jpa"
    assert adr_pack.term("org.postgresql:postgresql") == "postgresql" and adr_pack.term("@nestjs/core") == "core"


def test_a_term_is_the_bare_artifact_in_lower_case(adr_pack):
    assert adr_pack.term("org.springframework.kafka:spring-kafka") == "kafka"
    assert adr_pack.term("github.com/jackc/pgx") == "pgx"
    assert adr_pack.term("Redis") == "redis"
    assert adr_pack.term("spring-") == "spring-"                   # nothing left to name: the artifact stays
    assert adr_pack.term("") == ""


def test_candidates_group_repos_and_skip_tests_and_covered_ones(adr_pack, kit):
    seed_inventory([
        lib("api", "org.postgresql:postgresql", "data"),
        lib("web", "org.postgresql:postgresql", "data"),
        lib("api", "junit", "testing"),
        lib("api", "kafka-clients", "messaging", scope="test"),
        lib("api", "spring-boot-starter-security", "security")])
    got = adr_pack.candidates()
    assert [(c["key"], c["repos"]) for c in got] == [("data:postgresql", ["api", "web"]), ("security:security", ["api"])]
    assert got[0]["manifests"] == ["api:pom.xml", "web:pom.xml"]
    decide(kit, "0001-db", "---\ntitle: 0001 — Why PostgreSQL\n---\n# 0001 — Why PostgreSQL\n")
    assert keys(adr_pack) == ["security:security"]


def test_a_row_says_what_the_app_shows(adr_pack):
    seed_inventory([lib("api", "org.postgresql:postgresql", "data")])
    assert adr_pack.candidates() == [{"key": "data:postgresql", "label": "postgresql", "category": "data",
                                      "repos": ["api"], "manifests": ["api:pom.xml"]}]


def test_only_runtime_rows_of_the_decision_categories_count(adr_pack):
    seed_inventory([lib("api", "lombok", "tooling"), lib("api", "h2", "data", scope="dev"),
                    lib("api", "jedis", "cache", scope="runtime"), lib("api", "spring-boot-starter-web", "framework"),
                    lib("api", "kafka-clients", "messaging", scope="test"), lib("api", "slf4j", "logging")])
    assert keys(adr_pack) == ["cache:jedis", "framework:web"]


def test_the_manifest_is_read_from_the_row_source_or_the_repo_and_manifest(adr_pack):
    seed_inventory([
        lib("api", "org.postgresql:postgresql", "data", source="api:services/orders/pom.xml"),
        lib("api", "org.postgresql:postgresql", "data", source="api:pom.xml"),
        {**ROW, "repo": "web", "name": "org.postgresql:postgresql", "category": "data", "manifest": "pom.xml"},
        {**ROW, "repo": "worker", "name": "org.postgresql:postgresql", "category": "data"}])
    (row,) = adr_pack.candidates()
    assert row["repos"] == ["api", "web", "worker"]
    assert row["manifests"] == ["api:pom.xml", "api:services/orders/pom.xml", "web:pom.xml"]


def test_the_same_term_in_two_categories_is_two_decisions(adr_pack):
    seed_inventory([lib("api", "jedis", "cache"), lib("api", "spring-data-redis", "data"),
                    lib("api", "spring-boot-starter-data-redis", "cache")])
    assert keys(adr_pack) == ["cache:data-redis", "cache:jedis", "data:data-redis"]


# ---------- coverage: an ADR's title, tags or TL;DR ----------
def test_a_tag_or_a_tldr_covers_a_candidate(adr_pack, kit):
    seed_inventory([lib("api", "kafka-clients", "messaging"), lib("api", "jedis", "cache"),
                    lib("api", "org.postgresql:postgresql", "data"), lib("api", "spring-boot-starter-security", "security")])
    assert keys(adr_pack) == ["cache:jedis", "data:postgresql", "messaging:kafka-clients", "security:security"]
    decide(kit, "0001-events", "---\ntags: [Messaging, kafka-clients]\n---\n# 0001 — Events\n")
    decide(kit, "0002-cache", "---\ntags: jedis, perf\n---\n# 0002 — Speed\n")
    decide(kit, "0003-data", "# 0003 — Storage\n\n> **TL;DR:** We keep PostgreSQL as the system of record.\n")
    assert keys(adr_pack) == ["security:security"]


def test_coverage_is_by_whole_words_and_ignores_case_and_separators(adr_pack, kit):
    seed_inventory([lib("api", "spring-boot-starter-web", "framework"), lib("api", "spring-boot-starter-data-jpa", "data"),
                    lib("api", "org.postgresql:postgresql", "data")])
    decide(kit, "0001-hooks", "# 0001 — Webhooks and postgres\n")
    assert keys(adr_pack) == ["data:data-jpa", "data:postgresql", "framework:web"]
    decide(kit, "0002-orm", "# 0002 — Persistence with Spring Data JPA\n")
    assert keys(adr_pack) == ["data:postgresql", "framework:web"]
    decide(kit, "0003-db", "# 0003 — Why POSTGRESQL\n")
    assert keys(adr_pack) == ["framework:web"]


def test_an_adr_in_progress_covers_its_candidate(adr_pack, kit):
    seed_inventory([lib("api", "org.postgresql:postgresql", "data")])
    adr = importlib.import_module("lib.adr")
    adr.new({"title": "Why PostgreSQL?", "kind": "retro"})
    assert keys(adr_pack) == []


def test_a_rejected_or_superseded_adr_still_covers(adr_pack, kit):
    seed_inventory([lib("api", "org.postgresql:postgresql", "data")])
    decide(kit, "0001-db", "# 0001 — PostgreSQL\n\n## Status\n\nRejected (2026-01-02): too heavy\n")
    assert keys(adr_pack) == []


# ---------- deployment sources ----------
def test_deployment_sources_are_candidates(adr_pack, kit):
    (kit.ws / "api" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    assert ("deploy:docker-compose", ["api:docker-compose.yml"]) in [(c["key"], c["manifests"]) for c in adr_pack.candidates()]


def test_compose_files_at_a_repo_root_and_charts_up_to_three_folders_deep(adr_pack, kit):
    files = {"api/docker-compose.yml": "", "api/docker-compose.prod.yaml": "", "web/compose.yaml": "",
             "web/Compose.override.yml": "", "worker/src/docker-compose.yml": "", "worker/compose.txt": "",
             "api/deploy/helm/orders/Chart.yaml": "name: orders\n", "web/chart/Chart.yaml": "",
             "worker/a/b/c/d/Chart.yaml": "", "api/node_modules/dep/Chart.yaml": ""}
    for rel, text in files.items():
        f = kit.ws / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    got = {c["key"]: c for c in adr_pack.candidates()}
    assert sorted(got) == ["deploy:docker-compose", "deploy:helm"]
    assert got["deploy:docker-compose"]["label"] == "Docker Compose" and got["deploy:helm"]["label"] == "Helm"
    assert got["deploy:docker-compose"]["category"] == "deploy"
    assert got["deploy:docker-compose"]["repos"] == ["api", "web"]
    assert got["deploy:docker-compose"]["manifests"] == ["api:docker-compose.prod.yaml", "api:docker-compose.yml",
                                                         "web:Compose.override.yml", "web:compose.yaml"]
    assert got["deploy:helm"]["repos"] == ["api", "web"]
    assert got["deploy:helm"]["manifests"] == ["api:deploy/helm/orders/Chart.yaml", "web:chart/Chart.yaml"]


def test_an_adr_about_compose_or_helm_covers_them(adr_pack, kit):
    (kit.ws / "api" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (kit.ws / "api" / "Chart.yaml").write_text("name: api\n", encoding="utf-8")
    decide(kit, "0001-run", "# 0001 — Run locally with Docker Compose\n")
    assert keys(adr_pack) == ["deploy:helm"]


# ---------- C4 technologies ----------
def test_a_c4_technology_is_a_candidate(adr_pack, kit):
    write(kit, "architecture/model.c4", MODEL % "PostgreSQL")
    assert [(c["key"], c["repos"]) for c in adr_pack.candidates()] == [("c4:postgresql", ["api"])]
    (row,) = adr_pack.candidates()
    assert row["label"] == "PostgreSQL" and row["category"] == "c4" and row["manifests"] == []


def test_a_c4_technology_next_to_an_inventory_row_is_one_candidate(adr_pack, kit):
    write(kit, "architecture/model.c4", MODEL % "PostgreSQL")
    seed_inventory([lib("web", "org.postgresql:postgresql", "data")])
    got = adr_pack.candidates()
    assert [(c["key"], c["repos"]) for c in got] == [("data:postgresql", ["api", "web"])]
    assert got[0]["manifests"] == ["web:pom.xml"]


def test_a_c4_technology_with_several_names_gives_one_candidate_each(adr_pack, kit):
    write(kit, "architecture/model.c4", MODEL % "Spring Data JPA · Kafka / Avro")
    seed_inventory([lib("api", "spring-boot-starter-data-jpa", "data")])
    assert [(c["key"], c["repos"]) for c in adr_pack.candidates()] == [
        ("c4:avro", ["api"]), ("c4:kafka", ["api"]), ("data:data-jpa", ["api"])]


def test_a_c4_technology_without_a_repo_is_still_a_decision(adr_pack, kit):
    write(kit, "architecture/model.c4", "model {\n  db = container 'DB' {\n    technology 'Redis'\n  }\n}\n")
    assert [(c["key"], c["repos"]) for c in adr_pack.candidates()] == [("c4:redis", [])]


def test_a_covered_c4_technology_is_left_out(adr_pack, kit):
    write(kit, "architecture/model.c4", MODEL % "PostgreSQL")
    decide(kit, "0001-db", "---\ntags: [postgresql]\n---\n# 0001 — The database\n")
    assert adr_pack.candidates() == []


# ---------- order and failure ----------
def test_rows_are_sorted_by_category_then_label(adr_pack, kit):
    (kit.ws / "api" / "Chart.yaml").write_text("name: api\n", encoding="utf-8")
    write(kit, "architecture/model.c4", MODEL % "Zookeeper")
    seed_inventory([lib("api", "spring-boot-starter-security", "security"), lib("api", "kafka-clients", "messaging"),
                    lib("api", "org.postgresql:postgresql", "data"), lib("api", "jedis", "cache"),
                    lib("api", "mysql-connector-j", "data")])
    assert keys(adr_pack) == ["c4:zookeeper", "cache:jedis", "data:mysql-connector-j", "data:postgresql",
                              "deploy:helm", "messaging:kafka-clients", "security:security"]


def test_a_fresh_project_has_no_candidates_and_no_error(adr_pack):
    assert adr_pack.candidates() == []


def test_a_broken_source_leaves_the_others(adr_pack, kit):
    from lib.common import WORK
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "inventory.json").write_text("{not json", encoding="utf-8")
    write(kit, "architecture/model.c4", MODEL % "PostgreSQL")
    assert keys(adr_pack) == ["c4:postgresql"]
    (WORK / "inventory.json").write_text('{"libraries": ["x", 3, null, {"repo": "api"}]}', encoding="utf-8")
    assert keys(adr_pack) == ["c4:postgresql"]


def test_a_source_that_fails_leaves_the_others(adr_pack, kit, monkeypatch):
    (kit.ws / "api" / "Chart.yaml").write_text("name: api\n", encoding="utf-8")
    write(kit, "architecture/model.c4", MODEL % "PostgreSQL")
    seed_inventory([lib("api", "kafka-clients", "messaging")])

    def boom(*_):
        raise RuntimeError("broken")

    monkeypatch.setattr(adr_pack.c4edit, "index", boom)
    assert keys(adr_pack) == ["deploy:helm", "messaging:kafka-clients"]
    monkeypatch.setattr(adr_pack.inventory, "load", boom)
    assert keys(adr_pack) == ["deploy:helm"]
    monkeypatch.setattr(adr_pack.adr, "list_adrs", boom)
    assert keys(adr_pack) == ["deploy:helm"]


def test_a_repo_that_is_not_on_disk_is_skipped(adr_pack, kit):
    import shutil
    shutil.rmtree(kit.ws / "web")
    (kit.ws / "api" / "compose.yml").write_text("", encoding="utf-8")
    assert [(c["key"], c["repos"]) for c in adr_pack.candidates()] == [("deploy:docker-compose", ["api"])]
