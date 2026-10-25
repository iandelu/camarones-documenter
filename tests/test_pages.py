"""Pages from the code (no AI): the facts about each repo and the `repos` block of cards the project home carries."""
from __future__ import annotations

import importlib, json, os, shutil, subprocess, sys

import pytest

from fixtures.builder import seed_old_layout

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
        f.write_text(text, encoding="utf-8", newline="\n")
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
    page.write_text("# demo\n\n" + pg.gb.block("repos", "_system", "old") + "\n", encoding="utf-8", newline="\n")
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


# ---------- layout and the three pages ----------
ORDER = "package demo;\n\npublic enum OrderStatus { PENDING, PAID(\"p\"), SHIPPED; private final String c; }\n"
PUBLISHER = 'class Pub { void f() { kafkaTemplate.send("orders", m); } }\n'


def write_doc(pg, rel, text):
    f = pg.kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


def test_a_fresh_project_is_new_layout(pg):
    assert pg.mod.layout() == "new"


@pytest.mark.parametrize("rel", ["repos/api/reference.md", "repos/api/diagrams.md", "architecture/first-look.md",
                                 "architecture/system-map.md"])
def test_any_old_page_makes_the_layout_old(pg, rel):
    write_doc(pg, rel, "# old\n")
    assert pg.mod.layout() == "old"


def test_a_generated_data_page_is_an_old_page_but_a_hand_written_one_is_not(pg):
    write_doc(pg, "data/api.md", "---\ntitle: api data\n---\n# api data\n")      # no x-generated
    assert pg.mod.layout() == "new" and pg.mod.old_pages() == []
    write_doc(pg, "data/api.md", "---\ntitle: api data\nx-generated: true\n---\n# api data\n")
    write_doc(pg, "data/elsewhere.md", "---\nx-generated: true\n---\n# not a workspace repo\n")
    assert [p.name for p in pg.mod.old_pages()] == ["api.md"] and pg.mod.layout() == "old"


def test_the_home_with_cards_wins_over_a_kept_old_page(pg):
    write_doc(pg, "repos/api/reference.md", "# old\n")
    write_doc(pg, "index.md", "# demo\n\n" + pg.gb.block("repos", "_system", "x") + "\n")
    assert pg.mod.layout() == "new"


def test_the_home_says_the_facts_and_zero_counts(pg):
    write_doc(pg, "overview/tooling.md", "# Tooling\n")
    text = pg.mod.home_page({})
    assert "> **TL;DR:** demo has 3 repos (" in text and "no message topics" in text
    assert "\n:::cards\n<!-- generated:repos repo=_system" in text and "## Context map" in text
    assert "architecture/messaging.md" not in text                              # no topics: no link
    assert text.rstrip().endswith(":::") and text.index("## More") < text.index(":::details How this page is made")
    assert "[the tutorial](guides/tutorial.md)" in text and "(overview/tooling.md)" in text


def test_the_home_links_the_messaging_page_when_there_are_topics(pg):
    pg.put("api", "src/main/java/demo/Pub.java", PUBLISHER)
    assert "architecture/messaging.md" not in pg.mod.home_page({})              # not written yet: no link
    write_doc(pg, "architecture/messaging.md", pg.mod.messaging_page({}))
    text = pg.mod.home_page({})
    assert "- [Messaging](architecture/messaging.md)" in text and "1 message topic," in text


def test_the_home_links_only_pages_that_exist(pg):
    write_doc(pg, "overview/libraries.md", "# Libraries\n")
    write_doc(pg, "architecture/messaging.md", "# Messaging\n")                 # no topics: still no link
    text = pg.mod.home_page({})
    assert "(overview/libraries.md)" in text and "overview/tooling.md" not in text
    assert "architecture/messaging.md" not in text


def test_the_home_is_unknown_when_a_repo_is_missing(pg):
    pg.rmtree(pg.kit.ws / "worker")
    assert pg.mod.home_page({}) is None


def test_the_repo_page_puts_diagrams_first_and_tables_folded(pg):
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    text = pg.mod.repo_page("api", {})
    order = [text.index(h) for h in ("## What it exposes", "generated:endpoints-map", ":::details Endpoints",
                                     "generated:endpoints ", "## Lifecycles", "## What it needs to run",
                                     ":::details Commands", ":::details How this page is made")]
    assert order == sorted(order)
    assert "## Data" not in text and "## Messages" not in text                  # nothing to show: no section
    assert "[the tutorial](../../guides/tutorial.md)" in text and "tags:\n- api\n" in text


def test_an_empty_repo_says_what_it_lacks(pg):
    text = pg.mod.repo_page("worker", {})
    assert "no endpoints" in text and "no tables" in text and "publishes and consumes no messages" in text
    assert "## What it exposes" not in text


def test_a_repo_not_here_has_no_page(pg):
    pg.rmtree(pg.kit.ws / "worker")
    assert pg.mod.repo_page("worker", {}) is None and pg.mod.repo_page("nope", {}) is None


def test_a_skipped_key_is_not_drawn_again(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    assert "OrderStatus" in pg.mod.repo_page("api", {})
    assert "OrderStatus" not in pg.mod.repo_page("api", {}, skip={("states", "api", "OrderStatus")})


def test_the_repo_tldr_phrases(pg):
    f = {"kind": "service", "stack": "Spring Boot", "endpoints": 3, "tables": 9, "engines": ["PostgreSQL", "MySQL"],
         "publishes": ["a", "b"], "consumes": ["c"], "calls": ["web", "worker"]}
    assert pg.mod.repo_tldr("api", f) == ("`api` is a Spring Boot service: 3 endpoints, 9 tables in its PostgreSQL and "
                                          "MySQL databases; it publishes 2 topics and consumes 1; it calls web and worker.")
    g = {**f, "kind": "webapp", "tables": 1, "engines": ["PostgreSQL"], "publishes": [], "calls": []}
    assert pg.mod.repo_tldr("web", g) == ("`web` is a Spring Boot web app: 3 endpoints, 1 table in its PostgreSQL database; "
                                          "it consumes 1 topic; it calls no other repo.")
    h = {**f, "kind": "infra", "tables": 4, "engines": [], "consumes": [], "publishes": ["a"], "endpoints": 0}
    assert "infrastructure repo: no endpoints, 4 tables; it publishes 1 topic;" in pg.mod.repo_tldr("ci", h)
    assert pg.mod.repo_tldr("x", {**f, "tables": 0, "publishes": [], "consumes": []}).count("no tables; it publishes and "
                                                                                          "consumes no messages") == 1


def test_the_messaging_page_exists_only_with_topics(pg):
    assert pg.mod.messaging_page({}) is None
    pg.put("api", "src/main/java/demo/Pub.java", PUBLISHER)
    text = pg.mod.messaging_page({})
    assert "generated:messaging repo=_system id=orders" in text and "## Messaging" in text
    assert "[the tutorial](../guides/tutorial.md)" in text
    assert pg.mod.messaging_page({}, skip={("messaging", "_system", "orders")}) is None


def test_the_pages_list_the_sources_of_their_blocks_once(pg):
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    fm = pg.kit.docs.split_fm(pg.mod.repo_page("api", {}))[0]
    assert "api:src/main/resources/openapi.yaml" in fm["x-sources"] and len(fm["x-sources"]) == len(set(fm["x-sources"]))
    assert (fm["type"], fm["x-owner"], fm["x-generated"]) == ("overview", "ai", True)


def test_a_page_scans_the_code_once(pg, monkeypatch):
    calls, real = [], pg.mod.diagrams.quickarch.scan
    monkeypatch.setattr(pg.mod.diagrams.quickarch, "scan", lambda: calls.append(1) or real())
    memo = {}
    pg.mod.home_page(memo)
    pg.mod.repo_page("api", memo)
    pg.mod.messaging_page(memo)
    assert len(calls) == 1


def test_the_generated_pages_pass_check(pg, monkeypatch):
    monkeypatch.setattr(pg.kit.quality, "which", lambda name: None)             # no mermaid-cli, no gitleaks
    monkeypatch.setattr(pg.kit.quality.binaries, "bin_path", lambda name: None)
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.put("api", "src/main/java/demo/Pub.java", PUBLISHER)
    for rel in ("overview/tooling.md", "overview/libraries.md", "guides/tutorial.md"):   # the pages the links point to
        write_doc(pg, rel, "---\ntitle: T\ndescription: d\ntype: guide\n---\n# T\n")
    memo = {}
    write_doc(pg, "architecture/messaging.md", pg.mod.messaging_page(memo))
    pages = [("index.md", pg.mod.home_page(memo))]
    pages += [(f"repos/{r}/index.md", pg.mod.repo_page(r, memo)) for r in ("api", "web", "worker")]
    for rel, text in pages:
        write_doc(pg, rel, text)
    assert "(architecture/messaging.md)" in pages[0][1] and "(overview/tooling.md)" in pages[0][1]
    errors, _warns = pg.kit.docs.check()
    assert [e for e in errors if "index.md" in e or "messaging.md" in e] == []


# ---------- writing the pages ----------
def confirm(pg, page, id):
    """Confirm the block `id` of `page` as a person would (`confirmed=<its sha> by=ana`); returns the new block text."""
    text = page.read_text(encoding="utf-8")
    m = next(b for b in pg.gb.BLOCK_RE.finditer(text) if b["id"] == id)
    new = pg.gb.block(m["kind"], m["repo"], m["body"], id=id, confirmed=m["sha"], by="ana")
    page.write_text(text.replace(m[0], new), encoding="utf-8", newline="\n")
    return new


def test_write_creates_the_home_and_a_page_per_repo(pg):
    written = pg.mod.write()
    assert set(written) == {"docs/index.md", "docs/repos/api/index.md", "docs/repos/web/index.md", "docs/repos/worker/index.md"}
    assert pg.mod.write() == []                                                    # idempotent


def test_write_in_the_old_layout_is_2a(pg):
    write_doc(pg, "architecture/first-look.md", "# old\n")
    pg.mod.write()
    assert not (pg.kit.root / "docs" / "index.md").exists()
    assert (pg.kit.root / "docs" / "architecture" / "system-map.md").exists()


def test_a_confirmed_block_survives_a_rewrite(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    confirmed = confirm(pg, page, "OrderStatus")                                   # helper: sets confirmed= and by=
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER.replace("SHIPPED", "SHIPPED, LOST"))
    pg.mod.write()
    assert page.read_text(encoding="utf-8").count(confirmed) == 1


def test_a_confirmed_page_is_settled_after_one_write(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    confirm(pg, pg.kit.root / "docs" / "repos" / "api" / "index.md", "OrderStatus")
    assert pg.mod.write() == []


def test_a_hand_edited_block_survives_a_rewrite(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    page.write_text(page.read_text(encoding="utf-8").replace("    SHIPPED\n", "    SHIPPED\n    LOST_BY_HAND\n"),
                    encoding="utf-8", newline="\n")
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER.replace("SHIPPED", "SHIPPED, RETURNED"))
    pg.mod.write()
    text = page.read_text(encoding="utf-8")
    assert text.count("LOST_BY_HAND") == 1 and "RETURNED" not in text


def test_a_block_moved_to_another_repo_page_stays_there(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    api, web = (pg.kit.root / "docs" / "repos" / r / "index.md" for r in ("api", "web"))
    text = api.read_text(encoding="utf-8")
    m = next(b for b in pg.gb.BLOCK_RE.finditer(text) if b["id"] == "OrderStatus")
    api.write_text(text.replace(m[0], ""), encoding="utf-8", newline="\n")
    web.write_text(web.read_text(encoding="utf-8").replace(":::details How", m[0] + "\n\n:::details How"),
                   encoding="utf-8", newline="\n")
    pg.mod.write()
    assert web.read_text(encoding="utf-8").count(m[0]) == 1 and "OrderStatus" not in api.read_text(encoding="utf-8")
    assert pg.mod.write() == []


def test_a_persons_title_survives_a_rewrite(pg):
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    page.write_text(page.read_text(encoding="utf-8").replace("title: api", "title: The API\nx-team: pets"),
                    encoding="utf-8", newline="\n")
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    fm = pg.kit.docs.split_fm(page.read_text(encoding="utf-8"))[0]
    assert (fm["title"], fm["x-team"]) == ("The API", "pets")
    assert "api:src/main/java/demo/OrderStatus.java" in fm["x-sources"]


def test_prose_in_a_kit_page_is_kept(pg):
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    page.write_text(page.read_text(encoding="utf-8").replace("## What it needs to run",
                    "The team runs it behind nginx.\n\n## What it needs to run"), encoding="utf-8", newline="\n")
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    text = page.read_text(encoding="utf-8")
    assert "behind nginx" in text and "generated:states repo=api id=OrderStatus" in text


def test_a_block_moved_elsewhere_is_not_written_twice(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    write_doc(pg, "flows/checkout.md", "---\ntitle: Checkout\n---\n# Checkout\n\n"
              + pg.gb.block("states", "api", "x", id="OrderStatus") + "\n")
    pg.mod.write()
    assert "OrderStatus" not in (pg.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")


def test_a_partial_clone_leaves_the_home_alone(pg):
    pg.mod.write()
    home = (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8")
    pg.rmtree(pg.kit.ws / "worker")
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.mod.write()
    assert (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8") == home
    assert "generated:endpoints-map" in (pg.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")


def test_a_human_page_is_never_written(pg):
    write_doc(pg, "index.md", "---\ntitle: Home\nx-owner: human\n---\n# Home\n")
    pg.mod.write()
    assert (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8").endswith("# Home\n")


def test_a_page_the_kit_did_not_write_is_left_alone(pg):
    write_doc(pg, "repos/api/index.md", "---\ntitle: api\n---\n# api\n\nOur notes.\n")
    logs = []
    assert "docs/repos/api/index.md" not in pg.mod.write(logs.append)
    assert any("was not written by the kit" in line for line in logs)


def test_prose_keeps_the_tldr_and_folds_a_new_table(pg):
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    text = page.read_text(encoding="utf-8")
    tldr = next(line for line in text.splitlines() if line.startswith("> **TL;DR:**"))
    page.write_text(text.replace(tldr, "> **TL;DR:** the api, as we see it.\n\nA note of ours."), encoding="utf-8", newline="\n")
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    logs = []
    pg.mod.write(logs.append)
    text = page.read_text(encoding="utf-8")
    assert "as we see it" in text and "A note of ours." in text
    assert ":::details Endpoints\n<!-- generated:endpoints repo=api" in text
    assert text.index("generated:endpoints-map") < text.index(":::details Endpoints") < text.index(":::details How this")
    assert any("has text a person or an agent wrote, only its blocks" in line for line in logs)
    assert "api:src/main/resources/openapi.yaml" in pg.kit.docs.split_fm(text)[0]["x-sources"]


def test_a_confirmed_kit_page_only_gets_its_blocks(pg):
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    text = page.read_text(encoding="utf-8")
    page.write_text(text.replace("x-generated: true", "x-generated: true\nx-confirmed:\n  body_sha: abc\n  by: ana"),
                    encoding="utf-8", newline="\n")
    tldr = next(line for line in text.splitlines() if line.startswith("> **TL;DR:**"))
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)                    # the TL;DR's facts change
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    logs = []
    pg.mod.write(logs.append)
    text = page.read_text(encoding="utf-8")
    assert pg.kit.docs.split_fm(text)[0]["x-confirmed"] == {"body_sha": "abc", "by": "ana"} and "id=OrderStatus" in text
    assert tldr in text and "generated:endpoints-map repo=api" in text            # the TL;DR a person confirmed stays
    assert any("confirmed by a person" in line and "only its blocks" in line for line in logs)


def test_kit_only_allows_kit_lines_only(pg):
    """The TL;DR line is the kit's by its place; a line under it is the kit's only when the kit writes it (an older
    kit's two-line TL;DR whose second line the kit still writes, as `reference.md` and `first-look.md` do)."""
    fresh = ("---\ntitle: a\n---\n# a\n\n> **TL;DR:** x\n> over two lines.\n\n:::details Commands\nRead from the code.\n"
             ":::\n")
    blk = pg.gb.block("env", "api", "| a |\n|---|")
    old = (f"---\ntitle: b\n---\n# b\n\n> **TL;DR:** an older kit's words\n> over two lines.\n\n"
           f"## Run\n\n:::details Commands\n{blk}\n:::\n\n- [Libraries](../../overview/libraries.md)\nRead from the code.\n")
    assert pg.mod.kit_only(old, fresh)
    assert not pg.mod.kit_only(old, fresh.replace("> over two lines.\n", ""))  # an older kit's line the kit lost: kept
    assert not pg.mod.kit_only("# a\n\nThe team runs it behind nginx.\n", fresh)
    assert not pg.mod.kit_only("# a\n\n- [x](y) and more\n", fresh)


def test_kit_only_keeps_a_note_right_under_the_tldr(pg):
    fresh = "# a\n\n> **TL;DR:** x\n\n## Run\n"
    assert not pg.mod.kit_only("# a\n\n> **TL;DR:** x\n> Never restart it during business hours.\n\n## Run\n", fresh)
    assert pg.mod.kit_only("# a\n\n> **TL;DR:** older words\n\n## Run\n", fresh)


def test_kit_only_reads_the_kit_lines_outside_its_blocks_and_frontmatter(pg):
    row = "| `DB_URL` | yes | ask ops |"
    blk = pg.gb.block("env", "api", f"| Variable | Required | Default |\n|---|---|---|\n{row}")
    fresh = f"---\ntitle: a\n---\n# a\n\n> **TL;DR:** x\n\n## Run\n\n{blk}\n"
    assert pg.mod.kit_only(f"# a\n\n> **TL;DR:** x\n\n## Run\n\n{blk}\n", fresh)
    assert not pg.mod.kit_only(f"# a\n\n> **TL;DR:** x\n\n## Run\n\n{blk}\n\n{row}\n", fresh)   # a person's copy
    assert not pg.mod.kit_only("# a\n\n> **TL;DR:** x\n\ntitle: a\n", fresh)


@pytest.mark.parametrize("line", ["> Never restart it during business hours.", "- [Runbook](https://wiki/x): restart steps",
                                  "- [Libraries](overview/libraries.md): ours", "#1 rule: never restart on Fridays",
                                  ":::tip Restart only at night"])
def test_kit_only_keeps_a_persons_lines(pg, line):
    fresh = "# a\n\n> **TL;DR:** x\n\n## Run\n"
    assert not pg.mod.kit_only(f"# a\n\n> **TL;DR:** x\n\n## Run\n\n{line}\n", fresh)


def test_place_puts_a_block_in_its_section(pg):
    how = ":::details How this page is made\nx\n:::\n"
    env = pg.gb.block("env", "api", "| a |")
    body = pg.mod.place(f"# api\n\n## What it needs to run\n\n:::details Commands\nc\n:::\n\n{how}", env, ("env", "api", None))
    assert body.index("## What it needs") < body.index(":::details Environment variables\n" + env + "\n:::") < body.index(how)
    env2 = pg.gb.block("env", "api", "| b |")
    assert pg.mod.place(body, env2, ("env", "api", None)) == body.replace(env, env2)
    states = pg.gb.block("states", "api", "s", id="S")
    body = pg.mod.place(body, states, ("states", "api", "S"))
    assert body.index(f"## Lifecycles\n\n{states}") < body.index(how) and body.endswith(how)


def test_a_table_gone_from_a_page_with_prose_takes_its_fold(pg):
    env = pg.put("api", "src/main/resources/application.properties", "db.url=${DB_URL:jdbc:h2:mem}\n")
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    page.write_text(page.read_text(encoding="utf-8").replace("## What it needs to run",
                    "## What it needs to run\n\nAsk ops for the database."), encoding="utf-8", newline="\n")
    assert ":::details Environment variables" in page.read_text(encoding="utf-8")
    env.unlink()
    pg.mod.write()
    text = page.read_text(encoding="utf-8")
    assert ":::details Environment variables" not in text and "\n\n\n" not in text
    assert "Ask ops for the database.\n\n:::details Commands\n" in text


# ---------- the commands, the install and the first look use the layout ----------
def cli(pg, *args):
    """`camarones.py ARGS` on the fixture project, with a PATH that hides LikeC4 (no real C4 build in tests)."""
    likec4 = shutil.which("likec4")
    hidden = os.path.normcase(os.path.dirname(likec4)) if likec4 else None
    path = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                           if not hidden or os.path.normcase(d.strip().strip('"')) != hidden)
    env = {**os.environ, "CAMARONES_ROOT": str(pg.kit.root), "PATH": path}
    return subprocess.run([sys.executable, str(pg.kit.kit_dir / "camarones.py"), *args], env=env, capture_output=True,
                          text=True, encoding="utf-8")


def test_install_writes_the_new_pages(pg):
    pg.kit.wizard.scan_repos(log=lambda _: None)
    docs_dir = pg.kit.root / "docs"
    assert (docs_dir / "index.md").exists() and (docs_dir / "repos" / "api" / "index.md").exists()
    assert not (docs_dir / "repos" / "api" / "reference.md").exists()
    assert not (docs_dir / "architecture" / "system-map.md").exists()


def test_install_in_the_old_layout_is_unchanged(pg):
    seed_old_layout(pg.kit.root)
    pg.kit.wizard.scan_repos(log=lambda _: None)
    assert (pg.kit.root / "docs" / "repos" / "api" / "reference.md").exists()


def test_install_survives_a_pages_failure(pg, monkeypatch):
    monkeypatch.setattr(pg.mod, "write", lambda log=None: (_ for _ in ()).throw(RuntimeError("no pages today")))
    logs = []
    pg.kit.wizard.scan_repos(log=logs.append)
    assert (pg.kit.root / "docs" / "overview" / "tooling.md").exists()
    assert any("pages skipped" in l and "no pages today" in l for l in logs)


def test_first_look_writes_the_home_not_first_look_md(pg, monkeypatch):
    serve = importlib.import_module("lib.serve")
    monkeypatch.setattr(serve.env, "which", lambda _n: None)
    monkeypatch.setattr(importlib.import_module("lib.quickarch"), "which", lambda _n: None)   # no LikeC4 in tests
    logs = []
    assert serve.first_look(log=logs.append)
    docs_dir = pg.kit.root / "docs"
    assert (docs_dir / "index.md").exists() and (docs_dir / "architecture" / "model.c4").exists()
    assert not (docs_dir / "architecture" / "first-look.md").exists() and "index.md" in logs[-1]


def test_old_commands_do_not_write_old_pages_in_the_new_layout(pg):
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)
    for args in (("blocks",), ("schemas",), ("arch-draft", "--save")):
        assert cli(pg, *args).returncode == 0
    importlib.import_module("lib.serve").schemas_write()
    assert pg.mod.old_pages() == [] and pg.mod.layout() == "new"


def test_pages_and_its_alias(pg):
    out = json.loads(cli(pg, "pages", "--json").stdout)
    assert out["layout"] == "new" and "docs/index.md" in out["written"]
    assert cli(pg, "diagrams", "--json").returncode == 0 and cli(pg, "diagrams", "--adopt").returncode != 0


def test_the_data_view_links_the_repo_page(pg):
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)
    pg.mod.write()
    rows = importlib.import_module("lib.serve").api_schemas()["repos"]
    assert next(r for r in rows if r["repo"] == "api")["page"] == "repos/api/index.md"


def test_blocks_says_only_what_it_refreshed_in_the_new_layout(pg):
    out = cli(pg, "blocks").stdout
    assert "page(s) refreshed" in out and "reference page" not in out
    seed_old_layout(pg.kit.root)
    assert "reference page(s) created" in cli(pg, "blocks").stdout           # the older layout still says it
