"""Generated blocks (R24 / X3): env vars, commands, endpoints and topics read from the repos' sources of truth, no AI.
A block is `<!-- generated:<kind> repo=<repo> sha=<hash> -->…<!-- /generated:<kind> -->`; the hash tells a hand edit
(kept, flagged by check) from a block the code has moved past (refreshed)."""
from __future__ import annotations

import pytest

APP_YML = """server:
  port: ${PORT:8080}
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}/pets
    password: ${DB_PASSWORD:secret123}
"""
OPENAPI = """openapi: 3.0.1
info: {title: api, version: '1'}
paths:
  /pets:
    get: {summary: List pets, operationId: listPets}
    post: {operationId: addPet}
  /pets/{id}:
    delete: {summary: Delete a pet}
"""
CONTROLLER = """package demo;

@RestController
@RequestMapping("/api/owners")
public class OwnerController {
    @GetMapping
    public List<Owner> all() { return null; }

    @PostMapping(value = "/{id}/pets")
    public Pet add() { return null; }
}
"""
LISTENER = """package demo;

public class Events {
    @KafkaListener(topics = "pet-created")
    public void on(String m) {}

    void send() { kafkaTemplate.send("visit-booked", m); }
}
"""
PACKAGE = '{"name": "web", "scripts": {"start": "ng serve", "test": "ng test --watch=false"}}\n'


def put(kit, repo, rel, text):
    f = kit.ws / repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


@pytest.fixture
def gb(kit):
    import importlib
    put(kit, "api", "mvnw", "#!/bin/sh\n")
    put(kit, "api", "pom.xml", "<project><artifactId>api</artifactId><parent>spring-boot</parent></project>\n")
    put(kit, "api", "src/main/resources/application.yml", APP_YML)
    put(kit, "api", "src/main/resources/openapi.yml", OPENAPI)
    put(kit, "api", "src/main/java/demo/Events.java", LISTENER)
    put(kit, "api", ".env.example", "API_KEY=\nLOG_LEVEL=info\n")
    put(kit, "web", "package.json", PACKAGE)
    return importlib.import_module("lib.genblocks")


def test_env_vars_come_from_config_placeholders_and_env_examples(kit, gb):
    rows = {r["name"]: r for r in gb.env_rows("api", kit.ws / "api")}
    assert rows["PORT"]["default"] == "8080" and rows["DB_HOST"]["default"] == "localhost"
    assert rows["PORT"]["source"] == "api:src/main/resources/application.yml#L2"
    assert rows["DB_PASSWORD"]["default"] == "(hidden)"                       # never copy secret-looking defaults
    assert rows["LOG_LEVEL"]["default"] == "info" and rows["API_KEY"]["default"] == ""


def test_angular_environment_files_count_as_config(kit, gb):
    put(kit, "web", "src/environments/environment.ts",
        "export const environment = {\n  production: false,\n  REST_API_URL: 'http://localhost:9966/api/'\n};\n")
    put(kit, "web", "src/environments/environment.prod.ts",
        "export const environment = {\n  production: true,\n  REST_API_URL: 'https://pets.example/api/'\n};\n")
    rows = {r["name"]: r for r in gb.env_rows("web", kit.ws / "web")}
    assert rows["REST_API_URL"]["default"] == "http://localhost:9966/api/"          # the base file wins over profiles
    assert rows["production"]["source"] == "web:src/environments/environment.ts#L2"


def test_hidden_defaults_are_not_shown_as_code(kit, gb):
    body, _ = gb.render("env", "api", kit.ws / "api")
    assert "| `DB_PASSWORD` | (hidden) |" in body


def test_commands_come_from_the_build_tools(kit, gb):
    api = {r["command"] for r in gb.command_rows("api", kit.ws / "api")}
    assert {"./mvnw spring-boot:run", "./mvnw test", "./mvnw package"} <= api
    web = {r["command"]: r["what"] for r in gb.command_rows("web", kit.ws / "web")}
    assert web["npm run test"] == "`ng test --watch=false`"


def test_endpoints_come_from_openapi_first(kit, gb):
    rows = [(r["method"], r["path"], r["what"]) for r in gb.endpoint_rows("api", kit.ws / "api")]
    assert rows == [("GET", "/pets", "List pets"), ("POST", "/pets", "addPet"), ("DELETE", "/pets/{id}", "Delete a pet")]


def test_without_openapi_endpoints_come_from_spring_annotations(kit, gb):
    (kit.ws / "api" / "src/main/resources/openapi.yml").unlink()
    put(kit, "api", "src/main/java/demo/OwnerController.java", CONTROLLER)
    rows = [(r["method"], r["path"], r["source"]) for r in gb.endpoint_rows("api", kit.ws / "api")]
    assert rows == [("GET", "/api/owners", "api:src/main/java/demo/OwnerController.java#L6"),
                    ("POST", "/api/owners/{id}/pets", "api:src/main/java/demo/OwnerController.java#L9")]


def test_topics_say_who_publishes_and_who_consumes(kit, gb):
    rows = {(r["topic"], r["direction"]) for r in gb.topic_rows("api", kit.ws / "api")}
    assert rows == {("pet-created", "consumes"), ("visit-booked", "publishes")}


def test_write_creates_a_reference_page_per_repo(kit, gb):
    written = gb.write_reference()
    assert "docs/repos/api/reference.md" in written
    text = (kit.root / "docs" / "repos" / "api" / "reference.md").read_text(encoding="utf-8")
    assert "<!-- generated:env repo=api sha=" in text and "`DB_HOST`" in text and "`./mvnw test`" in text
    fm, _ = kit.docs.split_fm(text)
    assert "api:src/main/resources/openapi.yml" in fm["x-sources"] and fm["x-generated"] is True
    _, warns = kit.quality.check_structure(kit.docs.collect())
    assert not [w for w in warns if "reference.md" in w]


def test_refresh_follows_the_code_and_keeps_the_rest_of_the_page(kit, gb):
    gb.write_reference()
    page = kit.root / "docs" / "repos" / "api" / "reference.md"
    page.write_text(page.read_text(encoding="utf-8") + "\nA note a person added.\n", encoding="utf-8")
    put(kit, "api", "src/main/resources/application.yml", APP_YML + "  cache: ${CACHE_TTL:60}\n")
    assert gb.refresh()["updated"] == ["docs/repos/api/reference.md"]
    text = page.read_text(encoding="utf-8")
    assert "`CACHE_TTL`" in text and "A note a person added." in text
    assert gb.refresh()["updated"] == []                                       # idempotent


def test_a_block_embedded_in_any_page_is_filled(kit, gb):
    f = kit.root / "docs" / "repos" / "api" / "brief.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: api\n---\n# api\n\n## Build\n\n<!-- generated:commands repo=api -->\n"
                 "<!-- /generated:commands -->\n", encoding="utf-8")
    gb.refresh()
    assert "`./mvnw spring-boot:run`" in f.read_text(encoding="utf-8")


def test_a_hand_edit_is_kept_and_flagged(kit, gb):
    gb.write_reference()
    page = kit.root / "docs" / "repos" / "api" / "reference.md"
    page.write_text(page.read_text(encoding="utf-8").replace("`DB_HOST`", "`DATABASE_HOST`"), encoding="utf-8")
    put(kit, "api", "src/main/resources/application.yml", APP_YML + "  cache: ${CACHE_TTL:60}\n")
    r = gb.refresh()
    assert r["updated"] == [] and r["edited"] == ["docs/repos/api/reference.md (env, api)"]
    assert "`DATABASE_HOST`" in page.read_text(encoding="utf-8")
    _, warns = kit.docs.check()
    assert any("reference.md" in w and "edited by hand" in w for w in warns)
    assert gb.refresh(force=True)["updated"] == ["docs/repos/api/reference.md"]
    assert "`DATABASE_HOST`" not in page.read_text(encoding="utf-8")


def test_check_warns_when_the_code_moved_past_a_block(kit, gb):
    gb.write_reference()
    put(kit, "api", "src/main/resources/application.yml", APP_YML + "  cache: ${CACHE_TTL:60}\n")
    _, warns = kit.docs.check()
    assert any("reference.md" in w and "out of date" in w and "blocks" in w for w in warns)


def test_pages_a_person_owns_are_never_rewritten(kit, gb):
    f = kit.root / "docs" / "ops.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    text = ("---\ntitle: ops\nx-owner: human\n---\n# Ops\n\n<!-- generated:commands repo=api -->\n"
            "<!-- /generated:commands -->\n")
    f.write_text(text, encoding="utf-8")
    assert gb.refresh(force=True)["updated"] == [] and f.read_text(encoding="utf-8") == text


def test_an_existing_reference_page_is_not_recreated(kit, gb):
    gb.write_reference()
    assert gb.write_reference() == []


def test_the_blocks_command(kit, gb):
    import json, os, subprocess, sys
    from fixtures.builder import seed_old_layout
    seed_old_layout(kit.root)                                                  # reference.md is the old layout's
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    run = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "blocks", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    out = json.loads(run("--json").stdout)
    assert "docs/repos/api/reference.md" in out["created"]
    assert run().returncode == 0


def test_the_wizard_stack_step_writes_the_reference_pages(kit, gb):
    from fixtures.builder import seed_old_layout
    seed_old_layout(kit.root)                                                  # reference.md is the old layout's
    kit.wizard.scan_repos(log=lambda _: None)
    assert (kit.root / "docs" / "repos" / "web" / "reference.md").exists()
    assert (kit.root / "docs" / "overview" / "tooling.md").exists()


def test_a_page_that_only_quotes_the_marker_syntax_is_not_reported(kit, gb):
    f = kit.root / "docs" / "guides" / "how.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: how\nx-owner: human\n---\n# How\n\nUse `<!-- generated:<kind> repo=<repo> -->`.\n",
                 encoding="utf-8")
    assert gb.refresh()["human"] == []


def _confirmed_page(kit, gb):
    """A page with an `endpoints` block a person confirmed against the code as it is now."""
    fresh = gb.render("endpoints", "api", kit.ws / "api")[0]
    f = kit.root / "docs" / "repos" / "api" / "api-diagram.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: api\n---\n# api\n\n" + gb.block("endpoints", "api", "accepted by a person",
                                                           confirmed=gb.sha(fresh), by="ana") + "\n", encoding="utf-8")
    return f


def test_a_block_keeps_its_id_and_confirmation(kit, gb):
    text = gb.block("endpoints", "api", "body", id="pets", confirmed="abc", by="ana")
    assert text.startswith("<!-- generated:endpoints repo=api id=pets confirmed=abc by=ana sha=")
    m = gb.BLOCK_RE.search(text)
    assert (m["id"], m["confirmed"], m["by"]) == ("pets", "abc", "ana")


def test_an_old_block_without_new_attributes_reads_as_before(kit, gb):
    body = gb.render("endpoints", "api", kit.ws / "api")[0]
    text = f"<!-- generated:endpoints repo=api sha={gb.sha(body)} -->\n{body}\n<!-- /generated:endpoints -->"
    (m, state, _), = gb.states(text, gb.Scanner())
    assert state == "current" and m["id"] is None and m["confirmed"] is None and m["by"] is None


def test_a_confirmed_block_survives_refresh_even_forced(kit, gb):
    f = _confirmed_page(kit, gb)
    before = f.read_bytes()
    assert gb.refresh(force=True)["updated"] == [] and f.read_bytes() == before
    assert [s for _, s, _ in gb.states(f.read_text(encoding="utf-8"), gb.Scanner())] == ["confirmed"]


def test_the_code_moving_past_a_confirmed_block_is_reported(kit, gb):
    f = _confirmed_page(kit, gb)
    put(kit, "api", "src/main/resources/openapi.yml", OPENAPI + "  /owners:\n    get: {summary: List owners}\n")
    before = f.read_bytes()
    assert [s for _, s, _ in gb.states(f.read_text(encoding="utf-8"), gb.Scanner())] == ["confirmed-stale"]
    issues = gb.check(kit.docs.collect())[1]
    assert len(issues) == 1 and "the code changed since this diagram was confirmed" in issues[0]
    assert gb.refresh(force=True)["updated"] == [] and f.read_bytes() == before


# ---- the opening marker, written by hand --------------------------------------------------------------------------

def _one(gb, marker, body="body"):
    return list(gb.BLOCK_RE.finditer(f"# P\n\n{marker}\n{body}\n<!-- /generated:endpoints -->\n"))


def test_marker_attributes_are_read_in_any_order(kit, gb):
    (m,) = _one(gb, "<!-- generated:endpoints sha=abc123 by=ana confirmed=def456 id=pets repo=api -->")
    assert (m["kind"], m["repo"], m["id"], m["confirmed"], m["by"], m["sha"]) == ("endpoints", "api", "pets", "def456", "ana", "abc123")
    assert m["body"] == "body\n" and m[0].startswith("<!-- generated:endpoints sha=")


@pytest.mark.parametrize("by", ['"Ana López"', "Ana López"])
def test_a_name_with_spaces_is_read_whole(kit, gb, by):
    (m,) = _one(gb, f"<!-- generated:endpoints repo=api confirmed=3fa1c2d4e5f6 by={by} sha=abc123 -->")
    assert m["by"] == "Ana López" and m["sha"] == "abc123" and m["confirmed"] == "3fa1c2d4e5f6"


def test_a_marker_without_repo_is_not_a_block(kit, gb):
    assert _one(gb, "<!-- generated:endpoints sha=abc123 -->") == []
    assert _one(gb, "<!-- generated:endpoints repo=a/b sha=abc123 -->") == []
    assert _one(gb, "<!-- generated:endpoints repo=api repo=web -->") == []
    assert _one(gb, " <!-- generated:endpoints repo=api -->") == []            # a marker starts its line, like the portal's
    (m,) = _one(gb, "<!-- generated:endpoints repo=api id=X confirmed=3fa1c2… by=ana sha=abc -->")
    assert m["confirmed"] == "3fa1c2…"                                          # a pasted placeholder still reads


def test_block_still_writes_the_canonical_order(kit, gb):
    text = gb.block("endpoints", "api", "b", id="pets", confirmed="abc", by="Ana López")
    assert text.startswith('<!-- generated:endpoints repo=api id=pets confirmed=abc by="Ana López" sha=')
    assert gb.BLOCK_RE.search(text)["by"] == "Ana López"


def test_check_flags_a_marker_it_cannot_read(kit, gb):
    f = kit.root / "docs" / "notes.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: notes\n---\n# Notes\n\n<!-- generated:endpoints sha=abc -->\nx\n<!-- /generated:endpoints -->\n\n"
                 "Quoted: `<!-- generated:endpoints sha=abc -->`\n\n```md\n<!-- generated:env -->\n```\n\n"
                 "`<!-- generated:env -->` too.\n", encoding="utf-8", newline="\n")
    _, warns = gb.check(kit.docs.collect())
    bad = [w for w in warns if "notes.md" in w]
    assert len(bad) == 1 and "line 6" in bad[0] and "cannot be read" in bad[0]


def test_a_page_that_quotes_the_syntax_in_a_fence_is_not_flagged(kit, gb):
    f = kit.root / "docs" / "guide.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: guide\n---\n# Guide\n\n~~~\n<!-- generated:<kind> repo=<repo> -->\n~~~\n", encoding="utf-8")
    assert not [w for w in gb.check(kit.docs.collect())[1] if "guide.md" in w]
