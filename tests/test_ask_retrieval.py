"""Ask and search find what a question means, not only its exact words: a generic term finds the products that
implement it (database → PostgreSQL), Spanish questions find English pages, and the kit's own guides never push a
project page out of the answer unless the question is about the kit."""
from __future__ import annotations

from test_mcp_resources import write

FIRST_LOOK = """---
title: Architecture — first look
---
# Architecture — first look

## Detected relations

- spring-petclinic-rest → PostgreSQL:petclinic: reads/writes
- spring-petclinic-rest → MySQL:petclinic: reads/writes
"""

TOOLING = """---
title: Stack and tooling
---
# Stack and tooling

Each repo's stack and the tools the team already uses: Maven, Docker Compose, GitHub Actions.
"""

TUTORIAL = """---
type: guide
title: Tutorial — Camarón, the project docs wizard
---
# Tutorial

## CI
Run `camaron pr fresh <repo> --base main` in CI; the portal shows the result. The data base of the portal is git.
Use the portal to read, edit and review; the wizard uses the plan.
"""


def pages(kit):
    write(kit, "architecture/first-look.md", FIRST_LOOK, confirm=False)
    write(kit, "overview/tooling.md", TOOLING, confirm=False)
    write(kit, "guides/tutorial.md", TUTORIAL, confirm=False)


def test_a_generic_term_finds_the_products_that_implement_it(kit):
    pages(kit)
    assert kit.docs.search("what database does it use")[0]["path"] == "architecture/first-look.md"


def test_a_spanish_question_finds_an_english_page(kit):
    pages(kit)
    assert kit.docs.search("qué base de datos usa")[0]["path"] == "architecture/first-look.md"


def test_the_kit_guides_never_outrank_a_project_page(kit):
    pages(kit)
    hits = kit.docs.search("how do I use the portal in CI with maven")
    assert hits[0]["path"] == "overview/tooling.md"
    assert [h["path"] for h in hits].index("guides/tutorial.md") > 0


def test_a_question_about_the_kit_still_finds_its_guide(kit):
    pages(kit)
    assert kit.docs.search("camaron portal ci")[0]["path"] == "guides/tutorial.md"


def test_exact_words_still_rank_above_their_expansions(kit):
    pages(kit)
    write(kit, "data/postgres.md", "---\ntitle: Orders store\n---\n# Orders store\n\nThe database of orders.\n",
          confirm=False)
    assert kit.docs.search("database")[0]["path"] == "data/postgres.md"


def test_ask_answers_with_the_first_look_section(kit):
    pages(kit)
    from lib import serve
    first = serve.api_ask("which database does it use?")["sections"][0]
    assert first["cite"] == "architecture/first-look.md#detected-relations"


def test_a_whole_page_hit_does_not_repeat_its_tldr(kit):
    write(kit, "overview/tooling.md", TOOLING.replace("# Stack and tooling\n", "# Stack and tooling\n\n"
                                                      "> **TL;DR:** What each repo is built with.\n"), confirm=False)
    from lib import serve
    hit = serve.api_ask("maven docker")["sections"][0]
    assert hit["tldr"] == "> **TL;DR:** What each repo is built with."
    assert "TL;DR" not in hit["text"] and "Maven" in hit["text"]


def test_the_first_look_cites_what_it_read_so_agents_may_use_it(kit, monkeypatch):
    conf = kit.ws / "api" / "src" / "main" / "resources" / "application.properties"
    conf.parent.mkdir(parents=True)
    conf.write_text("spring.datasource.url=jdbc:postgresql://localhost:5432/petclinic\n", encoding="utf-8")
    from lib import quickarch, serve
    monkeypatch.setattr(quickarch, "which", lambda name: None)                     # no LikeC4 build in tests
    quickarch.save(quickarch.draft(log=lambda _: None))
    fm = kit.docs.split_fm((kit.root / "docs" / "architecture" / "first-look.md").read_text(encoding="utf-8"))[0]
    assert "api:src/main/resources/application.properties" in fm["x-sources"] and "api:pom.xml" in fm["x-sources"]
    assert fm["x-sources"] == sorted(fm["x-sources"])
    hit = serve.api_ask("which database does it use?")["sections"][0]
    assert hit["cite"].startswith("architecture/first-look.md") and not hit["withheld_for_agents"]
