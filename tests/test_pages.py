"""Pages from the code (no AI): the facts about each repo and the `repos` block of cards the project home carries."""
from __future__ import annotations

import importlib

import pytest

OPENAPI = """openapi: 3.0.1
info: {title: api, version: '1'}
paths:
  /pets:
    get: {summary: List pets}
    post: {operationId: addPet}
  /pets/{id}:
    delete: {summary: Delete a pet}
"""
SQL = "CREATE TABLE pets (id int primary key, name text);\nCREATE TABLE owners (id int primary key);\n"


@pytest.fixture
def pg(kit):
    from fixtures.builder import rmtree

    def put(repo, rel, text):
        f = kit.ws / repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return f
    return type("PG", (), {"kit": kit, "put": staticmethod(put), "rmtree": staticmethod(rmtree),
                           "mod": importlib.import_module("lib.pages"), "gb": importlib.import_module("lib.genblocks")})


def test_count_says_zero_plainly(pg):
    assert pg.mod.count(0, "endpoint") == "no endpoints"
    assert pg.mod.count(1, "endpoint") == "1 endpoint" and pg.mod.count(35, "endpoint") == "35 endpoints"
    assert pg.mod.count(1, "table") == "1 table" and pg.mod.count(9, "table") == "9 tables"
    assert pg.mod.count(3, "direct dependency", "direct dependencies") == "3 direct dependencies"
    assert pg.mod.count(0, "dependency", "dependencies") == "no dependencies"


def test_facts_count_what_the_code_states(pg):
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)            # 3 operations, one path twice in two files
    pg.put("api", "src/main/resources/openapi-v2.yaml", OPENAPI.split("  /pets/{id}")[0])
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)   # 2 tables
    pg.put("api", "src/main/resources/application.properties", "spring.datasource.url=jdbc:postgresql://localhost:5432/pets\n")
    pg.put("web", "src/client.js", "export const pets = () => fetch('http://api:8080/pets');\n")
    facts = pg.mod.facts()
    f = facts["repos"]["api"]
    assert (f["endpoints"], f["tables"], f["engines"]) == (3, 2, ["PostgreSQL"])
    assert f["publishes"] == [] and f["calls"] == ["worker"]             # the fixture's Api.java mentions worker
    assert list(facts["repos"]) == ["api", "web", "worker"] and facts["project"] == "demo"
    assert facts["repos"]["web"]["calls"] == ["api"] and facts["repos"]["web"]["endpoints"] == 0
    assert facts["dependencies"] >= 1
    assert "api:src/main/resources/db/migration/V1__init.sql" in facts["sources"]
    assert "api:src/main/resources/openapi.yaml" in facts["sources"]
    assert not [x for x in facts["sources"] if x.startswith("api:api:") or "#" in x]


def test_facts_list_topics_and_scan_once(pg, monkeypatch):
    pg.put("api", "pom.xml", "<project><artifactId>api</artifactId><dependency>spring-kafka</dependency></project>\n")
    pg.put("api", "src/Events.java", 'class E { @KafkaListener(topics = "pet-created") void on(String m) {}\n'
                                     '  void s() { kafkaTemplate.send("visit-booked", m); } }\n')
    calls, real = [], pg.mod.diagrams.quickarch.scan
    monkeypatch.setattr(pg.mod.diagrams.quickarch, "scan", lambda: calls.append(1) or real())
    memo = {}
    f = pg.mod.facts(memo)["repos"]["api"]
    assert (f["publishes"], f["consumes"]) == (["visit-booked"], ["pet-created"])
    assert pg.mod.facts(memo) is pg.mod.facts(memo) and len(calls) == 1


def test_the_repos_block_has_one_card_per_repo(pg):
    body, sources = pg.mod.repos_block()
    lines = body.splitlines()
    assert lines[0].startswith("- [api](repos/api/index.md): ") and len(lines) == 3
    assert "no endpoints" in lines[1] and "no tables" in lines[1] and "no topics" in lines[1]
    assert lines[1].startswith("- [web](repos/web/index.md): ") and sources


def test_a_repos_block_refreshes_through_genblocks(pg):
    page = pg.kit.root / "docs" / "index.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# demo\n\n" + pg.gb.block("repos", "_system", "old") + "\n", encoding="utf-8")
    pg.gb.refresh()
    assert "repos/web/index.md" in page.read_text(encoding="utf-8")
    assert "repos" in pg.gb.PAGE_KINDS and "repos" not in pg.gb.KINDS
    states = [s for _m, s, _b in pg.gb.states(page.read_text(encoding="utf-8"), pg.gb.Scanner())]
    assert states == ["current"]


def test_the_repos_block_is_unknown_when_a_repo_is_missing(pg):
    pg.rmtree(pg.kit.ws / "worker")
    assert pg.mod.repos_block() is None
    states = [s for _m, s, _b in pg.gb.states(pg.gb.block("repos", "_system", "x"), pg.gb.Scanner())]
    assert states == ["unknown"]
    assert pg.gb.render("repos", "api", pg.kit.ws / "api") is None
