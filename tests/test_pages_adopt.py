"""`camaron pages --adopt`: an old project's generated blocks move into the new pages and its emptied pages go."""
from __future__ import annotations

import importlib, json, pathlib, re

import pytest

from fixtures.builder import snapshot
from test_pages import OPENAPI, ORDER, PUBLISHER, SQL, cli, pg  # noqa: F401  (pg: the fixture, reused)

PROPS = "server.port=${PORT:8080}\nspring.datasource.url=${DB_URL:jdbc:postgresql://localhost:5432/pets}\n"


@pytest.fixture
def old_project(pg, monkeypatch):  # noqa: F811
    """A 4.x project: code with an OpenAPI file, a status enum, a SQL migration, a publisher and environment variables,
    documented by the 4.x writers (reference, diagram and data pages, the first look; LikeC4 off)."""
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)
    pg.put("api", "src/main/java/demo/Pub.java", PUBLISHER)
    pg.put("api", "src/main/resources/application.properties", PROPS)
    quickarch = importlib.import_module("lib.quickarch")
    monkeypatch.setattr(quickarch, "which", lambda _n: None)
    monkeypatch.setattr(pg.kit.quality, "which", lambda _n: None)               # no mermaid-cli, no gitleaks
    monkeypatch.setattr(pg.kit.quality.binaries, "bin_path", lambda _n: None)
    pg.gb.write_reference()
    pg.mod.diagrams.write_pages()
    pg.mod.schemas.write_pages(log=lambda _: None)
    quickarch.save(quickarch.draft(log=lambda _: None))
    assert pg.mod.layout() == "old"
    return pg


def doc(fx, rel):
    return fx.kit.root / "docs" / rel


def _block(fx, rel, pick):
    text = doc(fx, rel).read_text(encoding="utf-8")
    return text, next(b for b in fx.gb.BLOCK_RE.finditer(text) if pick(b))


def _swap(fx, rel, text, old, new):
    doc(fx, rel).write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return new


def confirm(fx, rel, id):
    """Confirm the block `id` of `rel` as a person would (`confirmed=<its sha> by=ana`); returns the new block text."""
    text, m = _block(fx, rel, lambda b: b["id"] == id)
    return _swap(fx, rel, text, m[0], fx.gb.block(m["kind"], m["repo"], m["body"], id=id, confirmed=m["sha"], by="ana"))


def hand_edit_table(fx, rel, kind):
    """Append a row inside the `kind` block of `rel` (a hand edit: its sha no longer matches); returns the block."""
    text, m = _block(fx, rel, lambda b: b["kind"] == kind)
    close = f"<!-- /generated:{kind} -->"
    return _swap(fx, rel, text, m[0], m[0].replace(close, "| `ADDED_BY_HAND` | yes | ask ops |\n" + close))


def add_paragraph(fx, rel, text):
    """`text` as a paragraph before the last `## ` heading of `rel`."""
    page = doc(fx, rel).read_text(encoding="utf-8")
    at = page.rindex("\n## ") + 1
    doc(fx, rel).write_text(page[:at] + text + "\n\n" + page[at:], encoding="utf-8", newline="\n")


def make_human(fx, rel):
    fm, body = fx.kit.docs.split_fm(doc(fx, rel).read_text(encoding="utf-8"))
    doc(fx, rel).write_text(fx.kit.docs.join_fm({**fm, "x-owner": "human"}, body), encoding="utf-8", newline="\n")


def run_check(fx):
    """The issue strings of the project's quality check (its errors: what makes `camaron check` fail)."""
    return fx.kit.docs.check()[0]


def pages(fx):
    """The docs pages as bytes (`snapshot` without the kit's caches under dot folders and dot files)."""
    return {k: v for k, v in snapshot(fx.kit.root / "docs").items() if not re.match(r"(.*/)?\.", k)}


DIFFERS = "differs from what this kit writes (text a person or an agent added, or an older kit's wording)"
OLD = ("repos/api/reference.md", "repos/api/diagrams.md", "data/api.md", "architecture/system-map.md",
       "architecture/first-look.md")


def test_adopt_moves_every_block_and_deletes_the_emptied_pages(old_project):
    out = old_project.mod.adopt()
    docs_dir = old_project.kit.root / "docs"
    for rel in OLD:
        assert not (docs_dir / rel).exists() and f"docs/{rel}" in out["deleted"]
    api = (docs_dir / "repos" / "api" / "index.md").read_text(encoding="utf-8")
    for kind in ("endpoints-map", "endpoints", "schema", "states", "topics", "env", "commands"):
        assert f"<!-- generated:{kind} repo=api" in api
    assert old_project.mod.layout() == "new"
    assert set(out) == {"moved", "deleted", "kept", "relinked", "links", "translations"}
    assert out["kept"] == [] and out["moved"] == []                              # every block was fresh: drawn again


def test_adopt_keeps_a_confirmed_and_an_edited_block_verbatim(old_project):
    confirmed = confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    edited = hand_edit_table(old_project, "repos/api/reference.md", "env")
    out = old_project.mod.adopt()
    api = (old_project.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")
    assert api.count(confirmed) == 1 and api.count(edited) == 1
    assert sorted(out["moved"]) == ["env api → docs/repos/api/index.md", "states api OrderStatus → docs/repos/api/index.md"]
    assert api.index("## What it needs to run") < api.index(":::details Environment variables\n" + edited)


def test_adopt_leaves_a_page_with_prose_and_a_human_page(old_project):
    add_paragraph(old_project, "data/api.md", "Pets are never deleted, only archived.")
    make_human(old_project, "repos/web/reference.md")
    out = old_project.mod.adopt()
    docs_dir = old_project.kit.root / "docs"
    assert "archived" in (docs_dir / "data" / "api.md").read_text(encoding="utf-8")
    assert (docs_dir / "repos" / "web" / "reference.md").exists()
    assert any(k.startswith("docs/data/api.md") for k in out["kept"])
    assert "generated:schema repo=api" not in (docs_dir / "repos" / "api" / "index.md").read_text(encoding="utf-8")
    assert sorted(out["kept"]) == [f"docs/data/api.md: {DIFFERS}", "docs/repos/web/reference.md: owned by a person"]


def test_adopt_twice_changes_nothing(old_project):
    old_project.mod.adopt()
    before = snapshot(old_project.kit.root / "docs")
    out = old_project.mod.adopt()
    assert snapshot(old_project.kit.root / "docs") == before and out["moved"] == out["deleted"] == []


def test_adopt_twice_with_kept_and_carried_blocks_changes_nothing(old_project):
    confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    add_paragraph(old_project, "data/api.md", "Pets are never deleted, only archived.")
    old_project.mod.adopt()
    before = pages(old_project)
    out = old_project.mod.adopt()
    assert pages(old_project) == before and out["moved"] == out["deleted"] == []
    assert old_project.mod.write() == []


def test_adopt_on_a_new_project_is_a_no_op(pg):  # noqa: F811
    pg.mod.write()
    assert pg.mod.adopt()["deleted"] == []


def test_adopt_keeps_a_block_the_new_pages_have_no_place_for(old_project):
    rel = "repos/api/reference.md"
    text = doc(old_project, rel).read_text(encoding="utf-8")
    doc(old_project, rel).write_text(text + "\n" + old_project.gb.block("future-kind", "api", "x") + "\n",
                                     encoding="utf-8", newline="\n")
    out = old_project.mod.adopt()
    assert doc(old_project, rel).read_text(encoding="utf-8") == text + "\n" + old_project.gb.block("future-kind", "api", "x") + "\n"
    assert f"docs/{rel}: has a block the new pages have no place for" in out["kept"]
    api = doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")
    assert "generated:env repo=api" not in api                                   # it still lives in the kept page


def test_adopt_with_a_repo_missing_changes_nothing(old_project):
    old_project.rmtree(old_project.kit.ws / "worker")
    before = snapshot(old_project.kit.root / "docs")
    out = old_project.mod.adopt()
    assert snapshot(old_project.kit.root / "docs") == before and out["deleted"] == []
    assert "docs/repos/api/reference.md: not every repo is on this machine" in out["kept"]
    assert len(out["kept"]) == len(old_project.mod.old_pages())


def test_adopt_deletes_nothing_when_writing_fails(old_project, monkeypatch):
    monkeypatch.setattr(old_project.mod, "_write_new", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        old_project.mod.adopt()
    assert all(doc(old_project, rel).exists() for rel in OLD)


def test_the_adopted_pages_pass_check(old_project):
    for rel in ("overview/tooling.md", "overview/libraries.md", "guides/tutorial.md"):  # what the new pages link to
        doc(old_project, rel).parent.mkdir(parents=True, exist_ok=True)
        doc(old_project, rel).write_text("---\ntitle: T\ndescription: d\ntype: guide\n---\n# T\n", encoding="utf-8")
    old_project.mod.adopt()
    assert [i for i in run_check(old_project) if "index.md" in i or "messaging.md" in i] == []


def test_pages_adopt_on_the_command_line(old_project):
    out = json.loads(cli(old_project, "pages", "--adopt", "--json").stdout)
    assert "docs/repos/api/reference.md" in out["deleted"] and out["relinked"] == out["links"] == out["translations"] == []
    assert old_project.mod.layout() == "new"


# ---------- fix round 1: drafts, a person's home, gone blocks, two copies, a failure ----------
AGENT_HOME = ("---\ntitle: demo\ntype: overview\nx-owner: ai\n---\n# demo\n\n> **TL;DR:** demo sells pets.\n\n"
              "The team ships every Friday.\n\n## Domain\n\nPets and owners.\n")


def write_doc(fx, rel, text):
    doc(fx, rel).parent.mkdir(parents=True, exist_ok=True)
    doc(fx, rel).write_text(text, encoding="utf-8", newline="\n")
    return doc(fx, rel)


def test_adopt_brings_the_blocks_into_an_agents_home(old_project):
    write_doc(old_project, "index.md", AGENT_HOME)
    out = old_project.mod.adopt()
    text = doc(old_project, "index.md").read_text(encoding="utf-8")
    assert "> **TL;DR:** demo sells pets.\n\n:::cards\n<!-- generated:repos repo=_system" in text
    assert "generated:context repo=_system" in text and "The team ships every Friday.\n\n## Domain\n\nPets and owners." in text
    assert "docs/architecture/system-map.md" in out["deleted"] and old_project.mod.layout() == "new"
    fm = old_project.kit.docs.split_fm(text)[0]
    assert fm["x-owner"] == "ai" and fm["x-sources"] and "x-generated" not in fm
    assert old_project.mod.adopt()["moved"] == [] and doc(old_project, "index.md").read_text(encoding="utf-8") == text


def test_adopt_brings_the_blocks_into_an_agents_repo_page(old_project):
    write_doc(old_project, "repos/api/index.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\nOur notes on the api.\n")
    out = old_project.mod.adopt()
    text = doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")
    assert "Our notes on the api." in text and "docs/repos/api/reference.md" in out["deleted"]
    for kind in ("endpoints-map", "endpoints", "states", "env"):
        assert f"<!-- generated:{kind} repo=api" in text


def test_adopt_with_a_persons_home_changes_nothing(old_project):
    write_doc(old_project, "index.md", AGENT_HOME.replace("x-owner: ai", "x-owner: human"))
    before = pages(old_project)
    out = old_project.mod.adopt()
    assert pages(old_project) == before and out["deleted"] == [] and out["moved"] == []
    reason = "docs/index.md is a person's page (x-owner: human): add the cards by hand, or set x-owner: ai and run --adopt again"
    assert sorted(out["kept"]) == sorted(f"docs/{rel}: {reason}" for rel in (*OLD, "repos/web/reference.md",
                                                                               "repos/worker/reference.md"))


def test_adopt_carries_a_confirmed_block_whose_source_left_the_code(old_project):
    confirmed = confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    (old_project.kit.ws / "api" / "src" / "main" / "java" / "demo" / "OrderStatus.java").unlink()
    out = old_project.mod.adopt()
    assert doc(old_project, "repos/api/index.md").read_text(encoding="utf-8").count(confirmed) == 1
    assert "docs/repos/api/diagrams.md" in out["deleted"] and "states api OrderStatus → docs/repos/api/index.md" in out["moved"]


def test_adopt_carries_a_hand_edited_block_whose_source_left_the_code(old_project):
    text, m = _block(old_project, "repos/api/diagrams.md", lambda b: b["id"] == "OrderStatus")
    edited = _swap(old_project, "repos/api/diagrams.md", text, m[0], m[0].replace("SHIPPED", "SHIPPED_BY_HAND"))
    (old_project.kit.ws / "api" / "src" / "main" / "java" / "demo" / "OrderStatus.java").unlink()
    out = old_project.mod.adopt()
    assert doc(old_project, "repos/api/index.md").read_text(encoding="utf-8").count(edited) == 1
    assert "docs/repos/api/diagrams.md" in out["deleted"]


def test_adopt_drops_an_unconfirmed_gone_block(old_project):
    (old_project.kit.ws / "api" / "src" / "main" / "java" / "demo" / "OrderStatus.java").unlink()
    out = old_project.mod.adopt()
    assert "docs/repos/api/diagrams.md" in out["deleted"] and out["moved"] == []
    assert "OrderStatus" not in doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")


def test_adopt_keeps_two_pages_with_different_copies_of_a_block(old_project):
    edited = hand_edit_table(old_project, "repos/api/reference.md", "env")
    _text, m = _block(old_project, "repos/api/reference.md", lambda b: b["kind"] == "env")
    other = old_project.gb.block("env", "api", m["body"].replace("ADDED_BY_HAND", "OTHER_HAND"))
    diagrams_md = doc(old_project, "repos/api/diagrams.md").read_text(encoding="utf-8")
    write_doc(old_project, "repos/api/diagrams.md", diagrams_md + "\n" + other.replace("sha=", "sha=0") + "\n")
    out = old_project.mod.adopt()
    reason = "another old page holds a different copy of the same block"
    assert {f"docs/repos/api/reference.md: {reason}", f"docs/repos/api/diagrams.md: {reason}"} <= set(out["kept"])
    assert doc(old_project, "repos/api/reference.md").read_text(encoding="utf-8").count(edited) == 1
    assert "generated:env repo=api" not in doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")


def test_adopt_deletes_nothing_when_writing_a_carried_block_fails(old_project, monkeypatch):
    confirm(old_project, "repos/api/diagrams.md", "OrderStatus")                     # → docs/repos/api/index.md
    confirm(old_project, "architecture/system-map.md", None)                         # the context map → docs/index.md
    real_write_new, real_write_text, calls = old_project.mod._write_new, pathlib.Path.write_text, []

    def failing(self, *a, **k):
        calls.append(self)
        if len(calls) == 2:
            raise OSError("disk full")
        return real_write_text(self, *a, **k)

    def write_new(*a, **k):
        written = real_write_new(*a, **k)
        monkeypatch.setattr(pathlib.Path, "write_text", failing)
        return written
    monkeypatch.setattr(old_project.mod, "_write_new", write_new)
    with pytest.raises(OSError):
        old_project.mod.adopt()
    monkeypatch.undo()
    assert len(calls) == 2 and all(doc(old_project, rel).exists() for rel in OLD)


# ---------- fix round 2: a person's page is never written; no x-owner is a person's; a target that never came ----------
def test_adopt_never_writes_a_persons_page_holding_another_copy(old_project):
    _text, m = _block(old_project, "repos/api/diagrams.md", lambda b: b["id"] == "OrderStatus")
    write_doc(old_project, "repos/api/index.md", "---\ntitle: api\nx-owner: human\n---\n# api\n\n## Lifecycles\n\n"
              + m[0].replace("SHIPPED", "SHIPPED_OURS") + "\n")
    human = doc(old_project, "repos/api/index.md").read_bytes()
    confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    diagrams_md = doc(old_project, "repos/api/diagrams.md").read_bytes()
    out = old_project.mod.adopt()
    assert doc(old_project, "repos/api/index.md").read_bytes() == human
    assert doc(old_project, "repos/api/diagrams.md").read_bytes() == diagrams_md
    assert ("docs/repos/api/diagrams.md: docs/repos/api/index.md is a person's page and holds a different copy of "
            "states api OrderStatus") in out["kept"]


def test_adopt_lets_go_of_a_block_a_persons_page_holds_identically(old_project):
    confirmed = confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    _text, endpoints = _block(old_project, "repos/api/diagrams.md", lambda b: b["kind"] == "endpoints-map")
    write_doc(old_project, "repos/api/index.md", "---\ntitle: api\nx-owner: human\n---\n# api\n\n" + endpoints[0]
              + "\n\n" + confirmed + "\n")
    human = doc(old_project, "repos/api/index.md").read_bytes()
    out = old_project.mod.adopt()
    assert doc(old_project, "repos/api/index.md").read_bytes() == human
    assert "docs/repos/api/diagrams.md" in out["deleted"] and out["moved"] == []
    assert any(k.startswith("docs/repos/api/reference.md: docs/repos/api/index.md is a person's page") for k in out["kept"])


def test_a_confirmed_home_says_how_to_proceed(old_project):
    write_doc(old_project, "index.md", AGENT_HOME.replace("x-owner: ai", "x-owner: ai\nx-confirmed:\n  by: ana"))
    out = old_project.mod.adopt()
    assert out["deleted"] == [] and out["kept"][0].endswith(
        "docs/index.md is a person's page (x-confirmed): add the cards by hand, or remove x-confirmed and run --adopt again")


def test_a_home_with_no_owner_is_an_agents(old_project):
    """The 4.x skeletons never set x-owner, and the kit reads a missing owner as `ai` (`doc_status`)."""
    write_doc(old_project, "index.md", AGENT_HOME.replace("x-owner: ai\n", ""))
    out = old_project.mod.adopt()
    text = doc(old_project, "index.md").read_text(encoding="utf-8")
    assert "> **TL;DR:** demo sells pets.\n\n:::cards\n<!-- generated:repos repo=_system" in text
    assert "The team ships every Friday." in text and "docs/architecture/system-map.md" in out["deleted"]
    assert "x-owner" not in old_project.kit.docs.split_fm(text)[0]


def test_adopt_keeps_an_old_page_a_person_confirmed(old_project):
    f = doc(old_project, "repos/api/reference.md")
    fm, body = old_project.kit.docs.split_fm(f.read_text(encoding="utf-8"))
    f.write_text(old_project.kit.docs.join_fm({**fm, "x-confirmed": {"by": "ana", "at": "2026-10-01", "body_sha": "x"}}, body),
                 encoding="utf-8", newline="\n")
    before = f.read_bytes()
    out = old_project.mod.adopt()
    assert f.read_bytes() == before and "docs/repos/api/reference.md: confirmed by a person" in out["kept"]
    assert "generated:env repo=api" not in doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")


def test_adopt_keeps_a_page_with_a_persons_copy_of_a_block_row(old_project):
    rel = "repos/api/reference.md"
    _text, m = _block(old_project, rel, lambda b: b["kind"] == "env")
    add_paragraph(old_project, rel, next(line for line in m["body"].splitlines() if line.startswith("| `")))
    out = old_project.mod.adopt()
    assert doc(old_project, rel).exists() and f"docs/{rel}: {DIFFERS}" in out["kept"]


@pytest.mark.parametrize("rel", OLD)
def test_adopt_takes_an_older_kits_tldr_line(old_project, rel):
    """Every old page type: a TL;DR line in other words is still the kit's, the lines under it are the kit's today."""
    text = doc(old_project, rel).read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("> **TL;DR:**"))
    doc(old_project, rel).write_text(text.replace(line, "> **TL;DR:** an older kit's words."), encoding="utf-8",
                                     newline="\n")
    assert f"docs/{rel}" in old_project.mod.adopt()["deleted"]


def test_adopt_keeps_a_page_with_a_line_under_its_tldr(old_project):
    rel = "repos/api/reference.md"
    text = doc(old_project, rel).read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("> **TL;DR:**"))
    doc(old_project, rel).write_text(text.replace(line, line + "\n> Never restart it during business hours."),
                                     encoding="utf-8", newline="\n")
    out = old_project.mod.adopt()
    assert doc(old_project, rel).exists() and f"docs/{rel}: {DIFFERS}" in out["kept"]


def test_adopt_keeps_a_page_whose_carried_blocks_target_never_came(old_project, monkeypatch):
    confirm(old_project, "architecture/system-map.md", "orders")                    # a messaging block → messaging.md
    monkeypatch.setattr(old_project.mod, "messaging_page", lambda memo, skip=frozenset(): None)
    out = old_project.mod.adopt()
    assert not doc(old_project, "architecture/messaging.md").exists()
    assert "docs/architecture/system-map.md: some of its blocks have no other home" in out["kept"]
    assert doc(old_project, "architecture/system-map.md").exists()


# ---------- task 6: links to the removed pages ----------
def test_adopt_relinks_and_check_has_no_broken_link(old_project):
    brief = write_doc(old_project, "repos/api/brief.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\n"
                      "> **TL;DR:** The API.\n\nSee [the reference](reference.md#http-endpoints).\n")
    confirmed = write_doc(old_project, "overview/system.md", "---\ntitle: System\nx-confirmed:\n  by: ana\n  at: 2026-10-01\n---\n"
                          "# System\n\n> **TL;DR:** x.\n\nSee [the map](../architecture/system-map.md).\n")
    out = old_project.mod.adopt()
    assert "[the reference](index.md)" in doc(old_project, "repos/api/brief.md").read_text(encoding="utf-8")
    assert "docs/repos/api/brief.md" in out["relinked"] and "docs/overview/system.md" in out["links"]
    assert "../architecture/system-map.md" in doc(old_project, "overview/system.md").read_text(encoding="utf-8")
    broken = [i for i in run_check(old_project) if "repos/api/brief.md" in i and "link" in i.lower()]
    assert broken == []


def test_adopt_lists_the_translations_of_removed_pages(old_project):
    write_doc(old_project, "i18n/es/repos/api/reference.md", "---\nx-translation-of: repos/api/reference.md\n---\n# api\n")
    out = old_project.mod.adopt()
    assert "docs/i18n/es/repos/api/reference.md" in out["translations"]
    assert doc(old_project, "i18n/es/repos/api/reference.md").exists()


def test_adopt_relinks_only_the_target_and_only_outside_code(old_project):
    text = ("---\ntitle: Notes\nx-generated: true\nx-owner: ai\ndescription: 'keep  this'\n---\n# Notes\n\n"
            "Read [the *data*](../../data/api.md#tables) and [the map][map], not `[x](reference.md)`.\n"
            "A [site](https://example.com/reference.md) and [other](../web/reference.md \"web\") stay or move.\n\n"
            "```\n[in a fence](reference.md)\n```\n\n[map]: ../../architecture/system-map.md#top\n"
            "[first]: <../../architecture/first-look.md>\n")
    write_doc(old_project, "repos/api/notes.md", text)
    out = old_project.mod.adopt()
    assert out["relinked"] == ["docs/repos/api/notes.md"]
    assert doc(old_project, "repos/api/notes.md").read_text(encoding="utf-8") == (
        text.replace("(../../data/api.md#tables)", "(index.md)").replace("(../web/reference.md ", "(../web/index.md ")
        .replace("[map]: ../../architecture/system-map.md#top", "[map]: ../../index.md")
        .replace("<../../architecture/first-look.md>", "<../../index.md>"))


def test_adopt_leaves_links_to_pages_it_kept(old_project):
    make_human(old_project, "repos/web/reference.md")
    write_doc(old_project, "guides/api.md", "---\ntitle: G\nx-owner: ai\n---\n# G\n\n[web](../repos/web/reference.md) and "
              "[api](../repos/api/reference.md)\n")
    out = old_project.mod.adopt()
    assert "(../repos/web/reference.md) and [api](../repos/api/index.md)" in doc(old_project, "guides/api.md").read_text(
        encoding="utf-8")
    assert out["relinked"] == ["docs/guides/api.md"]


def test_adopt_relinks_a_page_without_owner(old_project):
    write_doc(old_project, "guides/mine.md", "---\ntitle: Mine\n---\n# Mine\n\n[ref](../repos/api/reference.md)\n")
    out = old_project.mod.adopt()
    assert out["relinked"] == ["docs/guides/mine.md"] and out["links"] == []
    assert "[ref](../repos/api/index.md)" in doc(old_project, "guides/mine.md").read_text(encoding="utf-8")


def test_adopt_lists_a_persons_page_with_a_link(old_project):
    write_doc(old_project, "guides/mine.md", "---\ntitle: Mine\nx-owner: human\n---\n# Mine\n\n"
              "[ref](../repos/api/reference.md)\n")
    out = old_project.mod.adopt()
    assert out["links"] == ["docs/guides/mine.md"] and out["relinked"] == []


# A brief and a home as an agent wrote them from the 4.x skeletons (`repo-brief.md`, `overview.md`): no x-owner.
BRIEF_4X = ("---\ntype: overview\ntitle: api brief\ndescription: What api does, its stack, how to build, test and run it, "
            "and the interfaces and data it owns.\ntags: [api]\nx-sources:\n  - api:README.md\n---\n# api\n\n"
            "> **TL;DR:** The pets API, in Spring Boot; run it with Maven.\n\n## Build, test and run\n\n"
            "Run `./mvnw spring-boot:run`.\n\n## Interfaces\n\nThe full lists of endpoints, topics and env vars are in "
            "[api reference](reference.md), generated from the code.\n\n## Data owned\n\nThe pets tables.\n")
HOME_4X = ("---\ntype: overview\ntitle: demo\ndescription: What the system is for, who uses it, and which repos make it "
           "up, for someone who has never seen it.\ntags: [overview]\nx-sources:\n  - api:README.md\n---\n# demo\n\n"
           "> **TL;DR:** demo sells pets, through api and web.\n\n## What it does\n\nSells pets. The map is in "
           "[the system map](architecture/system-map.md).\n\n## Repos\n\n| Repo | Role | Stack |\n|---|---|---|\n"
           "| `api` | the API | Spring Boot |\n")


def test_adopt_on_the_4x_brief_and_home_leaves_no_broken_link(old_project):
    for rel in ("overview/tooling.md", "overview/libraries.md", "guides/tutorial.md"):  # what the new pages link to
        write_doc(old_project, rel, "---\ntitle: T\ndescription: d\ntype: guide\n---\n# T\n")
    write_doc(old_project, "repos/api/brief.md", BRIEF_4X)
    write_doc(old_project, "index.md", HOME_4X)
    out = old_project.mod.adopt()
    brief, home = (doc(old_project, rel).read_text(encoding="utf-8") for rel in ("repos/api/brief.md", "index.md"))
    assert "[api reference](index.md)" in brief and "[the system map](index.md)" in home
    assert "> **TL;DR:** demo sells pets, through api and web.\n\n:::cards\n<!-- generated:repos repo=_system" in home
    assert {"docs/repos/api/reference.md", "docs/architecture/system-map.md"} <= set(out["deleted"])
    assert {"docs/repos/api/brief.md", "docs/index.md"} <= set(out["relinked"]) and out["links"] == []
    assert [i for i in run_check(old_project) if "link" in i.lower()] == []


def test_relink_lists_a_page_it_cannot_write(old_project, monkeypatch):
    page = write_doc(old_project, "guides/locked.md", "---\ntitle: x\nx-owner: ai\n---\n# x\n\n"
                     "[r](../repos/api/reference.md)\n")
    write_doc(old_project, "repos/api/index.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n")    # the page that took over
    real = pathlib.Path.write_bytes
    monkeypatch.setattr(pathlib.Path, "write_bytes", lambda self, data: (_ for _ in ()).throw(PermissionError("locked"))
                        if self.name == "locked.md" else real(self, data))
    relinked, left = old_project.mod._relink({"repos/api/reference.md"})
    assert left == ["docs/guides/locked.md"] and relinked == [] and "reference.md" in page.read_text(encoding="utf-8")


def test_adopt_regenerates_llms_txt(old_project):
    old_project.kit.docs.llms()
    assert "reference.md" in doc(old_project, "llms.txt").read_text(encoding="utf-8")
    old_project.mod.adopt()
    text = doc(old_project, "llms.txt").read_text(encoding="utf-8")
    assert "reference.md" not in text and "repos/api/index.md" in text


def test_adopt_logs_an_llms_txt_failure(old_project, monkeypatch):
    monkeypatch.setattr(old_project.kit.docs, "llms", lambda: (_ for _ in ()).throw(RuntimeError("no llms today")))
    logs = []
    out = old_project.mod.adopt(log=logs.append)
    assert "docs/repos/api/reference.md" in out["deleted"] and any("no llms today" in line for line in logs)


def test_the_first_look_page_is_written_with_lf(old_project):
    assert b"\r\n" not in doc(old_project, "architecture/first-look.md").read_bytes()


def test_adopt_twice_relinks_nothing_more(old_project):
    write_doc(old_project, "repos/api/brief.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\n[r](reference.md)\n")
    old_project.mod.adopt()
    before = pages(old_project)
    out = old_project.mod.adopt()
    assert pages(old_project) == before and out["relinked"] == out["links"] == out["translations"] == []


def test_pages_adopt_prints_one_line_per_relinked_page(old_project):
    write_doc(old_project, "repos/api/brief.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\n[r](reference.md)\n")
    write_doc(old_project, "guides/mine.md", "---\ntitle: Mine\n---\n# Mine\n\n[ref](../repos/api/reference.md)\n")
    write_doc(old_project, "i18n/es/repos/api/reference.md", "---\nx-translation-of: repos/api/reference.md\n---\n# api\n")
    out = cli(old_project, "pages", "--adopt").stdout
    assert "relinked docs/repos/api/brief.md" in out and "docs/guides/mine.md" in out
    assert "docs/i18n/es/repos/api/reference.md" in out


# ---------- task 6, fix round 1: pages adopt filled, links inside blocks, pages that do not decode ----------
def test_adopt_relinks_the_prose_of_an_agents_home_it_filled(old_project):
    write_doc(old_project, "index.md", AGENT_HOME.replace("Pets and owners.", "Pets and owners, see [the reference]"
              "(repos/api/reference.md#http-endpoints) and [the map](architecture/system-map.md)."))
    out = old_project.mod.adopt()
    text = doc(old_project, "index.md").read_text(encoding="utf-8")
    assert "[the reference](repos/api/index.md) and [the map](index.md)" in text and "docs/index.md" in out["relinked"]
    assert "generated:repos repo=_system" in text                                # adopt did fill it


def test_adopt_relinks_the_prose_of_an_agents_repo_page_it_filled(old_project):
    write_doc(old_project, "repos/api/index.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\nSee [the diagrams](diagrams.md).\n")
    out = old_project.mod.adopt()
    text = doc(old_project, "repos/api/index.md").read_text(encoding="utf-8")
    assert "[the diagrams](index.md)" in text and "generated:env repo=api" in text
    assert "docs/repos/api/index.md" in out["relinked"]


def test_adopt_lists_the_link_on_a_persons_home_it_could_not_fill_nor_fix(old_project):
    write_doc(old_project, "index.md", AGENT_HOME.replace("x-owner: ai", "x-owner: human") + "\n[r](repos/api/reference.md)\n")
    out = old_project.mod.adopt()                                                # nothing is deleted: the home is closed
    assert out["deleted"] == [] and out["links"] == []


def test_adopt_never_edits_a_generated_block(old_project):
    page = write_doc(old_project, "guides/blocks.md", "---\ntitle: B\nx-owner: ai\n---\n# B\n\n"
                     + old_project.gb.block("future-kind", "api", "[r](../repos/api/reference.md)") + "\n")
    before = page.read_bytes()
    out = old_project.mod.adopt()
    assert page.read_bytes() == before and "docs/guides/blocks.md" not in out["relinked"] + out["links"]



def test_relink_lists_a_page_that_is_not_utf8_and_has_such_a_link(old_project):
    """`docs.collect` cannot read such a page, so `adopt` never gets here with one: `_relink` is called as it is."""
    page, other = doc(old_project, "guides/latin.md"), doc(old_project, "guides/latin2.md")
    page.parent.mkdir(parents=True, exist_ok=True)
    head = b"---\ntitle: x\nx-owner: ai\n---\n# x\n\n"
    page.write_bytes(head + b"[r](../repos/api/reference.md) caf\xe9\n")
    other.write_bytes(head + b"no link caf\xe9\n")
    before = page.read_bytes()
    relinked, left = old_project.mod._relink({"repos/api/reference.md"})
    assert left == ["docs/guides/latin.md"] and relinked == [] and page.read_bytes() == before
