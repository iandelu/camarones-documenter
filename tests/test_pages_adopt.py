"""`camaron pages --adopt`: an old project's generated blocks move into the new pages and its emptied pages go."""
from __future__ import annotations

import importlib, json, re

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
    assert sorted(out["kept"]) == ["docs/data/api.md: has text a person or an agent wrote",
                                   "docs/repos/web/reference.md: owned by a person"]


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
