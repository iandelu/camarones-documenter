"""Diagrams from the code (no AI): `states` blocks read from status enums in Java, Kotlin, TypeScript, Python, C#, Go and
SQL. A diagram shows the states only, never a transition: those wait for a proposal."""
from __future__ import annotations

import importlib
import re

import pytest


@pytest.fixture
def dg(kit):
    def put(repo, rel, text):
        f = kit.ws / repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return f
    return type("DG", (), {"kit": kit, "put": staticmethod(put), "mod": importlib.import_module("lib.diagrams"),
                           "gb": importlib.import_module("lib.genblocks")})


def enums(dg, repo="api"):
    return {e["id"]: e for e in dg.mod.status_enums(repo, dg.kit.ws / repo)}


ORDER = "package demo;\n\npublic enum OrderStatus { PENDING, PAID(\"p\"), SHIPPED; private final String c; }\n"


def test_java_enum_lists_constants_not_fields(dg):
    dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    got = dg.mod.status_enums("api", dg.kit.ws / "api")
    assert [(e["id"], e["states"]) for e in got] == [("OrderStatus", ["PENDING", "PAID", "SHIPPED"])]
    assert got[0]["source"] == "api:src/main/java/demo/OrderStatus.java#L3"


def test_kotlin_enum_with_constructor(dg):
    dg.put("api", "src/PetState.kt", "enum class PetState(val x: Int) { NEW(1), ADOPTED(2) }\n")
    assert enums(dg)["PetState"]["states"] == ["NEW", "ADOPTED"]


def test_typescript_enum_with_values(dg):
    dg.put("web", "src/visit.ts", "export enum VisitPhase { Booked = 'b', Done = 'd' }\n")
    assert enums(dg, "web")["VisitPhase"]["states"] == ["Booked", "Done"]


def test_python_enum_class(dg):
    dg.put("api", "app/models.py", 'class InvoiceStatus(str, Enum):\n    OPEN = "open"\n    CLOSED = "closed"\n\n'
                                   "    def label(self):\n        x = 1\n        return self.value\n\nDEFAULT = 1\n")
    assert enums(dg)["InvoiceStatus"]["states"] == ["OPEN", "CLOSED"]


def test_csharp_enum(dg):
    dg.put("api", "Jobs.cs", "public enum JobStage { Queued, Running }\n")
    assert enums(dg)["JobStage"]["states"] == ["Queued", "Running"]


def test_go_iota_const_block(dg):
    dg.put("api", "run.go", "package run\n\ntype RunStatus int\n\nconst (\n\tRunPending RunStatus = iota\n\tRunDone\n)\n")
    assert enums(dg)["RunStatus"]["states"] == ["RunPending", "RunDone"]


def test_sql_check_in_on_a_status_column(dg):
    dg.put("api", "db/migration/V1__orders.sql",
           "CREATE TABLE orders (id int, status varchar(9) CHECK (status IN ('NEW','PAID')));\n")
    got = enums(dg)["orders_status"]
    assert got["states"] == ["NEW", "PAID"] and got["source"].startswith("api:db/migration/V1__orders.sql")


def test_an_enum_not_about_state_is_ignored(dg):
    dg.put("api", "Color.java", "public enum Color { RED }\n")
    assert dg.mod.status_enums("api", dg.kit.ws / "api") == []
    assert dg.mod.ids("states", "api") == []


def test_ids_follow_declaration_order(dg):
    dg.put("api", "A.java", "enum ZetaState { A, B }\n")
    dg.put("api", "B.java", "enum AlphaPhase { C, D }\n")
    assert dg.mod.ids("states", "api") == ["ZetaState", "AlphaPhase"]


def test_states_block_has_states_and_no_transition(dg):
    dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    body, sources = dg.mod.render("states", "api", "OrderStatus")
    assert "```mermaid" in body and "stateDiagram-v2" in body
    assert all(s in body for s in ("PENDING", "PAID", "SHIPPED"))
    assert "note right of PENDING : transitions: waiting for a proposal" in body
    assert "-->" not in body
    assert body.startswith("**`OrderStatus`** · `api:src/main/java/demo/OrderStatus.java`")
    assert sources == ["api:src/main/java/demo/OrderStatus.java"]


def test_a_state_with_spaces_gets_a_valid_node(dg):
    dg.put("api", "db/V1__t.sql", "CREATE TABLE t (state text CHECK (state IN ('IN PROGRESS','DONE')));\n")
    body, _ = dg.mod.render("states", "api", "t_state")
    assert 'state "IN PROGRESS" as IN_PROGRESS' in body and "\n    DONE\n" in body


def test_more_than_25_states_keeps_25_and_says_how_many_more(dg):
    dg.put("api", "Big.java", "enum BigStatus { " + ", ".join(f"S{i}" for i in range(30)) + " }\n")
    body, _ = dg.mod.render("states", "api", "BigStatus")
    mermaid = body.split("```mermaid")[1]
    assert sum(1 for ln in mermaid.splitlines() if ln.strip() in {f"S{i}" for i in range(30)}) == 25
    assert "note right of S0 : 5 more states in Big.java" in body and "S25" not in body


def test_render_of_a_gone_enum_is_none(dg):
    dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    assert dg.mod.render("states", "api", "Nope") is None
    assert dg.mod.render("states", "ghost-repo", "OrderStatus") is None


def test_genblocks_delegates_diagram_kinds_even_without_a_folder(dg):
    dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    assert "states" in dg.gb.DIAGRAM_KINDS and "states" not in dg.gb.KINDS
    assert dg.gb.render("states", "api", dg.kit.ws / "api", "OrderStatus") == dg.mod.render("states", "api", "OrderStatus")
    assert dg.gb.render("states", "_system", None, "x") is None


def test_a_states_block_refreshes_and_goes_stale_with_the_code(dg):
    f = dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    body, _ = dg.mod.render("states", "api", "OrderStatus")
    text = dg.gb.block("states", "api", body, id="OrderStatus")
    scan = dg.gb.Scanner()
    assert [s for _, s, _ in dg.gb.states(text, scan)] == ["current"]
    f.write_text(ORDER.replace("SHIPPED", "SHIPPED, LOST"), encoding="utf-8")
    assert [s for _, s, _ in dg.gb.states(text, dg.gb.Scanner())] == ["stale"]
    f.unlink()
    assert [s for _, s, _ in dg.gb.states(text, dg.gb.Scanner())] == ["unknown"]


@pytest.mark.parametrize("base", ["IntEnum", "StrEnum", "IntFlag", "enum.Enum"])
def test_python_enum_subclasses_are_detected(dg, base):
    dg.put("api", "app/jobs.py", f"class JobStatus({base}):\n    QUEUED = 1\n    DONE = 2\n")
    assert enums(dg)["JobStatus"]["states"] == ["QUEUED", "DONE"]


def test_slashes_inside_a_string_do_not_cut_the_list(dg):
    dg.put("api", "EnvState.java", 'enum EnvState { PROD("https://a.com"), TEST("https://t.com"), DEV("x"); }\n')
    assert enums(dg)["EnvState"]["states"] == ["PROD", "TEST", "DEV"]


def test_an_escaped_quote_inside_a_string_does_not_cut_the_list(dg):
    dg.put("api", "AStatus.java", 'enum AStatus { A("x\\"y"), B, C }\n')
    assert enums(dg)["AStatus"]["states"] == ["A", "B", "C"]


def test_comments_are_still_ignored_and_line_numbers_kept(dg):
    dg.put("api", "Doc.java", "/* the states\n   enum FakeState { X } */\n// enum OtherState { Y }\n"
                              'enum RealState { A("//"), /* skip */ B } // end\n')
    got = enums(dg)
    assert list(got) == ["RealState"] and got["RealState"]["states"] == ["A", "B"] and got["RealState"]["source"].endswith("#L4")


def test_a_state_named_like_a_mermaid_keyword_gets_an_aliased_id(dg):
    dg.put("api", "app/run.py", 'class RunState(Enum):\n    start = "s"\n    end = "e"\n    state = "x"\n    note = "n"\n')
    body, _ = dg.mod.render("states", "api", "RunState")
    lines = [ln.strip() for ln in body.splitlines()]
    assert 'state "end" as end_' in lines and 'state "state" as state_' in lines and 'state "note" as note_' in lines
    assert "start" in lines and not {"end", "state", "note"} & set(lines)


# ---------- endpoints-map ----------
OPENAPI = """openapi: 3.0.1
info: {title: api, version: '1'}
paths:
  /pets:
    get: {summary: List pets, operationId: listPets}
    post: {operationId: addPet}
  /pets/{id}:
    delete: {summary: Delete a pet}
"""
LISTENER = """package demo;

public class Events {
    @KafkaListener(topics = "pet-created")
    public void on(String m) {}

    void send() { kafkaTemplate.send("visit-booked", m); }
}
"""
APP_YML = "spring:\n  datasource:\n    url: jdbc:postgresql://${DB_HOST:localhost}/pets\n"


def api_repo(dg, openapi=OPENAPI):
    dg.put("api", "pom.xml", "<project><artifactId>api</artifactId><parent>spring-boot</parent></project>\n")
    dg.put("api", "src/main/resources/application.yml", APP_YML)
    dg.put("api", "src/main/resources/openapi.yml", openapi)
    dg.put("api", "src/main/java/demo/Events.java", LISTENER)


def mermaid(body):
    return body.split("```mermaid\n")[1].split("```")[0]


def node_ids(body):
    """Distinct node ids defined in a flowchart body: the first token of every `id[...]`, `id[(...)]`, `id([...])` line."""
    return {m.group(1) for ln in mermaid(body).splitlines() if (m := re.match(r"\s+(\w+)(?:\[|\(\[)", ln))}


def openapi_of(paths):
    return "openapi: 3.0.1\ninfo: {title: api, version: '1'}\npaths:\n" + "".join(
        f"  {p}:\n    get: {{operationId: op{i}}}\n" for i, p in enumerate(paths))


def test_endpoints_map_groups_by_resource_and_shows_dependencies(dg):
    api_repo(dg)
    assert dg.mod.ids("endpoints-map", "api") == [None]
    body, sources = dg.mod.render("endpoints-map", "api", None)
    code = mermaid(body)
    assert code.startswith("flowchart LR") and code.count("subgraph ") == 1
    assert 'subgraph pets["/pets"]' in code
    assert '["GET /pets"]' in code and '["DELETE /pets/{id}"]' in code
    assert '[("PostgreSQL' in code                                          # the datastore, as a cylinder
    assert 'visit_booked(["visit-booked"])' in code and 'api -->|"publishes"| visit_booked' in code
    assert 'pet_created(["pet-created"])' in code and 'pet_created -->|"consumes"| api' in code
    assert "api:src/main/resources/openapi.yml" in sources and "api:src/main/java/demo/Events.java" in sources
    assert all("#" not in s for s in sources)


def test_endpoints_map_shows_the_repos_it_calls(dg):
    api_repo(dg)
    dg.put("web", "package.json", '{"name": "web"}\n')
    dg.put("api", "src/main/resources/application.yml", APP_YML + "web:\n  url: http://web:4200/\n")
    body, _ = dg.mod.render("endpoints-map", "api", None)
    code = mermaid(body)
    assert 'web["web"]' in code and 'api -->|"calls (HTTP)"| web' in code


def test_path_params_and_special_labels_are_quoted(dg):
    api_repo(dg, openapi_of(['/pets/{id}', '/we"ird[x]<b>']))
    body, _ = dg.mod.render("endpoints-map", "api", None)
    labels = [ln.strip() for ln in mermaid(body).splitlines() if "GET /" in ln]
    assert len(labels) == 2 and all(re.fullmatch(r'\w+\["GET [^"]*"\]', ln) for ln in labels)
    assert any("we#quot;ird[x]#lt;b#gt;" in ln for ln in labels) and not any('we"ird' in ln for ln in labels)


def test_a_big_map_is_split_by_resource(dg):
    api_repo(dg, openapi_of([f"/{g}/{i}" for g in ("pets", "owners", "vets") for i in range(10)]))
    assert dg.mod.ids("endpoints-map", "api") == ["pets", "owners", "vets"]
    for group in ("pets", "owners", "vets"):
        body, sources = dg.mod.render("endpoints-map", "api", group)
        assert len(node_ids(body)) <= 25 and f"/{group}/3" in body
        assert sum(g in body for g in ("/pets/", "/owners/", "/vets/")) == 1
    assert dg.mod.render("endpoints-map", "api", None) is None and dg.mod.render("endpoints-map", "api", "cats") is None


def test_a_group_over_the_limit_is_chunked(dg):
    api_repo(dg, openapi_of([f"/pets/{i}" for i in range(40)]))
    got = dg.mod.ids("endpoints-map", "api")
    assert got[:2] == ["pets", "pets-2"] and len(got) == len(set(got)) >= 2
    seen = set()
    for i in got:
        body, _ = dg.mod.render("endpoints-map", "api", i)
        assert len(node_ids(body)) <= 25
        seen |= set(re.findall(r"GET (/pets/\d+)", body))
    assert len(seen) == 40


def test_a_repo_without_endpoints_has_no_map(dg):
    api_repo(dg)
    dg.put("web", "package.json", '{"name": "web"}\n')
    assert dg.mod.ids("endpoints-map", "web") == [] and dg.mod.render("endpoints-map", "web", None) is None
    assert dg.mod.ids("endpoints-map", "ghost-repo") == []


def test_render_scans_the_architecture_once(dg, monkeypatch):
    api_repo(dg)
    calls = []
    real = dg.mod.quickarch.scan
    monkeypatch.setattr(dg.mod.quickarch, "scan", lambda: calls.append(1) or real())
    dg.mod.render("endpoints-map", "api", None)
    assert len(calls) == 1


def test_an_endpoints_map_block_refreshes_through_genblocks(dg):
    api_repo(dg)
    body, sources = dg.mod.render("endpoints-map", "api", None)
    assert dg.gb.render("endpoints-map", "api", dg.kit.ws / "api") == (body, sources)
    text = dg.gb.block("endpoints-map", "api", body)
    assert [s for _, s, _ in dg.gb.states(text, dg.gb.Scanner())] == ["current"]


# ---------- context and messaging (system-wide) ----------
SYSTEM = "_system"
KAFKA_POM = "<project><artifactId>api</artifactId><parent>spring-boot</parent><dependency>spring-kafka</dependency></project>\n"


def system_repos(dg):
    """api (PostgreSQL, Kafka: publishes visit-booked, consumes pet-created) and web calling api over HTTP."""
    api_repo(dg)
    dg.put("api", "pom.xml", KAFKA_POM)
    dg.put("web", "package.json", '{"name": "web"}\n')
    dg.put("web", "src/client.js", 'export const pets = () => fetch("http://api:8080/pets");\n')


def add_repos(dg, n):
    ws = dg.kit.docs.workspace()
    for i in range(n):
        dg.put(f"svc{i}", "package.json", f'{{"name": "svc{i}"}}\n')
        ws["repos"].append({"name": f"svc{i}", "kind": "service", "branch": "main"})
    dg.kit.docs.save_workspace(ws)


def test_context_map_draws_repos_stores_and_calls(dg):
    system_repos(dg)
    assert dg.mod.ids("context", SYSTEM) == [None]
    body, sources = dg.mod.render("context", SYSTEM, None)
    code = mermaid(body)
    assert code.startswith("flowchart")
    assert 'api["api"]' in code and 'web["web"]' in code
    assert '[("PostgreSQL' in code and 'Kafka(["Kafka"])' in code
    assert 'web -->|"calls (HTTP)"| api' in code and '-->|"reads/writes"|' in code
    assert 'api -->|"publishes visit-booked"| Kafka' in code
    assert sources and set(sources) <= dg.mod.quickarch.scan()["sources"]


def test_a_crowded_context_folds_external_systems(dg):
    system_repos(dg)
    add_repos(dg, 17)                                                      # 3 + 17 repos, a database, a broker
    idps = ("keycloak", "auth0", "cognito", "firebase_auth", "okta")       # the five labels quickarch.IDP_HINTS knows
    dg.put("svc0", "src/auth.js", "// " + " ".join(idps) + "\n")
    assert len(dg.mod.quickarch.scan()["idps"]) == 5
    body, _ = dg.mod.render("context", SYSTEM, None)
    assert len(node_ids(body)) <= 25
    assert len(re.findall(r'\["External', mermaid(body))) == 1
    assert "5 identity providers folded into External" in body and "Okta" in body and 'Auth0["Auth0"]' not in body
    assert "not drawn" not in body and "svc16" in body                     # folding was enough: no repo left out


def test_a_context_still_too_big_leaves_out_the_least_connected(dg):
    system_repos(dg)
    add_repos(dg, 30)
    body, _ = dg.mod.render("context", SYSTEM, None)
    assert len(node_ids(body)) <= 25 and 'api["api"]' in mermaid(body) and "less connected elements not drawn" in body


def test_context_needs_a_repo_and_only_exists_for_the_system(dg):
    system_repos(dg)
    assert dg.mod.ids("context", "api") == [] and dg.mod.render("context", "api", None) is None
    assert dg.mod.render("context", SYSTEM, "x") is None
    ws = dg.kit.docs.workspace()
    ws["repos"] = []
    dg.kit.docs.save_workspace(ws)
    assert dg.mod.ids("context", SYSTEM) == [] and dg.mod.render("context", SYSTEM, None) is None


def test_messaging_has_one_sequence_per_topic(dg):
    system_repos(dg)
    assert dg.mod.ids("messaging", SYSTEM) == ["pet-created", "visit-booked"]
    body, sources = dg.mod.render("messaging", SYSTEM, "visit-booked")
    assert "sequenceDiagram" in body and "api->>Kafka: publish visit-booked" in body and "deliver visit-booked" not in body
    assert sources == ["api:src/main/java/demo/Events.java"]
    body, _ = dg.mod.render("messaging", SYSTEM, "pet-created")
    assert "Kafka-->>api: deliver pet-created" in body and "publish pet-created" not in body
    assert dg.mod.render("messaging", SYSTEM, "gone") is None and dg.mod.render("messaging", SYSTEM, None) is None
    assert dg.mod.ids("messaging", "api") == [] and dg.mod.render("messaging", "api", "pet-created") is None


def test_a_topic_published_and_consumed_is_one_diagram_with_one_broker(dg):
    system_repos(dg)
    dg.put("web", "src/Bus.java", 'class Bus { @KafkaListener(topics = "visit-booked") void on(String m) {} }\n')
    dg.put("web", "src/Bus2.java", 'class Bus2 { void f() { kafkaTemplate.send("visit-booked", m); } }\n')
    assert dg.mod.ids("messaging", SYSTEM).count("visit-booked") == 1
    code = mermaid(dg.mod.render("messaging", SYSTEM, "visit-booked")[0])
    assert code.count("participant Kafka") == 1 and code.count("participant web") == 1
    assert "web->>Kafka: publish visit-booked" in code and "Kafka-->>web: deliver visit-booked" in code
    assert "api->>Kafka: publish visit-booked" in code


def test_two_brokers_share_the_name_broker(dg):
    system_repos(dg)
    dg.put("web", "package.json", '{"name": "web", "dependencies": {"amqplib": "1"}}\n')
    dg.put("web", "src/bus.js", "channel.publish('visit-booked', x)\n")
    body, _ = dg.mod.render("messaging", SYSTEM, "visit-booked")
    assert "web->>Broker: publish visit-booked" in body and "api->>Broker: publish visit-booked" in body
    assert "Kafka" not in mermaid(body)


def test_a_hyphenated_repo_gets_an_aliased_participant(dg):
    ws = dg.kit.docs.workspace()
    ws["repos"].append({"name": "pet-api", "kind": "service", "branch": "main"})
    dg.kit.docs.save_workspace(ws)
    dg.put("pet-api", "src/Bus.java", 'class Bus { void f() { kafkaTemplate.send("pet-created", m); } }\n')
    code = mermaid(dg.mod.render("messaging", SYSTEM, "pet-created")[0])
    assert "participant pet_api as pet-api" in code and "pet_api->>Broker: publish pet-created" in code


def test_sequence_keywords_as_repo_names_get_safe_participants(dg):
    ws = dg.kit.docs.workspace()
    for name in ("loop", "alt"):
        ws["repos"].append({"name": name, "kind": "service", "branch": "main"})
    dg.kit.docs.save_workspace(ws)
    dg.put("loop", "src/Bus.java", 'class Bus { void f() { kafkaTemplate.send("pet-created", m); } }\n')
    dg.put("alt", "src/Sub.java", 'class Sub { @KafkaListener(topics = "pet-created") void on(String m) {} }\n')
    code = mermaid(dg.mod.render("messaging", SYSTEM, "pet-created")[0])
    assert "participant loop_ as loop" in code and "participant alt_ as alt" in code
    assert "loop_->>Broker: publish pet-created" in code and "Broker-->>alt_: deliver pet-created" in code
    assert not re.search(r"^\s*(loop|alt)->>", code, re.M)


def test_a_context_that_just_fits_keeps_every_repo_and_adds_no_external(dg):
    add_repos(dg, 21)                                                      # 3 + 21 repos, plus one identity provider = 25
    dg.put("svc0", "src/auth.js", "// okta\n")
    body, _ = dg.mod.render("context", SYSTEM, None)
    assert len(node_ids(body)) == 25 and 'Okta["Okta"]' in mermaid(body)
    assert all(f'svc{i}["svc{i}"]' in mermaid(body) for i in range(21))
    assert "External" not in body and "not drawn" not in body


def test_a_single_identity_provider_is_never_folded(dg):
    add_repos(dg, 22)                                                      # 25 repos + 1 provider: a fold would not save a node
    dg.put("svc0", "src/auth.js", "// okta\n")
    body, _ = dg.mod.render("context", SYSTEM, None)
    assert len(node_ids(body)) <= 25 and 'Okta["Okta"]' in mermaid(body) and "External" not in body
    assert "1 less connected elements not drawn" in body


def test_no_topics_no_messaging(dg):
    dg.put("web", "package.json", '{"name": "web"}\n')
    assert dg.mod.ids("messaging", SYSTEM) == []
    assert dg.mod.render("messaging", SYSTEM, "pet-created") is None


def test_messaging_and_context_scan_the_architecture_once(dg, monkeypatch):
    system_repos(dg)
    calls = []
    real = dg.mod.quickarch.scan
    monkeypatch.setattr(dg.mod.quickarch, "scan", lambda: calls.append(1) or real())
    dg.mod.render("context", SYSTEM, None)
    assert len(calls) == 1
    calls.clear()
    dg.mod.render("messaging", SYSTEM, "visit-booked")
    assert len(calls) == 1
    calls.clear()
    dg.mod.ids("messaging", SYSTEM)
    assert not calls                                                       # topic names need no architecture scan


def test_system_blocks_refresh_through_genblocks(dg):
    system_repos(dg)
    for kind, id in (("context", None), ("messaging", "visit-booked")):
        body, sources = dg.mod.render(kind, SYSTEM, id)
        assert dg.gb.render(kind, SYSTEM, None, id) == (body, sources)


# ---- pages, `camaron diagrams`, install hooks ------------------------------------------------------------------------

def pages_repo(dg):
    """api: endpoints, a datastore, topics and one status enum; web: nothing to draw."""
    system_repos(dg)
    dg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)


def page_text(dg, rel):
    return (dg.kit.root / "docs" / rel).read_text(encoding="utf-8")


def keys(text):
    heads = re.findall(r"<!-- generated:([\w-]+) repo=([\w.\-]+)(?: id=([\w.\-]+))?", text)
    return [(k, r, i or None) for k, r, i in heads]


def test_write_pages_creates_the_system_map_and_repo_pages(dg):
    pages_repo(dg)
    written = dg.mod.write_pages()
    assert sorted(written) == ["docs/architecture/system-map.md", "docs/repos/api/diagrams.md"]
    for rel, h1 in (("architecture/system-map.md", "# System map"), ("repos/api/diagrams.md", "# api diagrams")):
        fm, body = dg.kit.docs.split_fm(page_text(dg, rel))
        assert fm["x-generated"] is True and fm["x-owner"] == "ai" and fm["type"] == "overview" and fm["x-sources"]
        assert h1 in body and "> **TL;DR:**" in body and "no AI" in body and "camaron diagrams" in body
    system = page_text(dg, "architecture/system-map.md")
    assert system.index("## Context map") < system.index("## Messaging")
    assert keys(system) == [("context", SYSTEM, None), ("messaging", SYSTEM, "pet-created"), ("messaging", SYSTEM, "visit-booked")]
    repo = page_text(dg, "repos/api/diagrams.md")
    assert repo.index("## Endpoints") < repo.index("## Lifecycles")
    assert keys(repo) == [("endpoints-map", "api", None), ("states", "api", "OrderStatus")]
    assert "id=" not in re.search(r"<!-- generated:context[^>]*-->", system)[0]


def test_no_page_without_diagrams(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    assert not (dg.kit.root / "docs" / "repos" / "web" / "diagrams.md").exists()


def test_nothing_to_draw_writes_nothing(dg):
    ws = dg.kit.docs.workspace()
    ws["repos"] = []
    dg.kit.docs.save_workspace(ws)
    assert dg.mod.write_pages() == []
    assert not (dg.kit.root / "docs" / "architecture" / "system-map.md").exists()


def test_a_second_run_changes_nothing(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    files = [dg.kit.root / "docs" / "architecture" / "system-map.md", dg.kit.root / "docs" / "repos" / "api" / "diagrams.md"]
    before = [f.read_bytes() for f in files]
    assert dg.mod.write_pages() == []
    assert [f.read_bytes() for f in files] == before


def test_a_new_enum_is_added_to_an_existing_page(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    before = page_text(dg, "repos/api/diagrams.md")
    dg.put("api", "src/main/java/demo/PetState.java", "enum PetState { NEW, ADOPTED }\n")
    assert dg.mod.write_pages() == ["docs/repos/api/diagrams.md"]
    after = page_text(dg, "repos/api/diagrams.md")
    assert keys(after) == [("endpoints-map", "api", None), ("states", "api", "OrderStatus"), ("states", "api", "PetState")]
    assert after.index("id=PetState") > after.index("## Lifecycles")
    assert all(m[0] in after for m in dg.gb.BLOCK_RE.finditer(before))     # the rest is byte for byte what it was


def test_a_moved_block_is_not_written_twice(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    f = dg.kit.root / "docs" / "repos" / "api" / "diagrams.md"
    text = f.read_text(encoding="utf-8")
    moved = next(m for m in dg.gb.BLOCK_RE.finditer(text) if m["id"] == "OrderStatus")
    f.write_text(text.replace(moved[0], ""), encoding="utf-8")
    flow = dg.kit.root / "docs" / "flows" / "checkout.md"
    flow.parent.mkdir(parents=True, exist_ok=True)
    flow.write_text("---\ntitle: Checkout\n---\n# Checkout\n\n" + moved[0] + "\n", encoding="utf-8")
    dg.mod.write_pages()
    assert "id=OrderStatus" not in f.read_text(encoding="utf-8")
    assert "id=OrderStatus" in flow.read_text(encoding="utf-8")
    dg.put("api", "src/main/java/demo/OrderStatus.java", "enum OrderStatus { PENDING, PAID, SHIPPED, LOST }\n")
    dg.gb.refresh()
    assert "LOST" in flow.read_text(encoding="utf-8")
    assert "id=OrderStatus" not in f.read_text(encoding="utf-8")


def test_a_fresh_page_skips_a_block_that_lives_elsewhere(dg):
    pages_repo(dg)
    flow = dg.kit.root / "docs" / "flows" / "checkout.md"
    flow.parent.mkdir(parents=True, exist_ok=True)
    flow.write_text("---\ntitle: Checkout\n---\n# Checkout\n\n" + dg.gb.block("states", "api", "x", id="OrderStatus") + "\n",
                    encoding="utf-8")
    dg.mod.write_pages()
    assert keys(page_text(dg, "repos/api/diagrams.md")) == [("endpoints-map", "api", None)]


def confirm(dg, f, id):
    """Replace the `states` block `id` in page `f` by one a person confirmed against the code as it is now."""
    text = f.read_text(encoding="utf-8")
    m = next(m for m in dg.gb.BLOCK_RE.finditer(text) if m["id"] == id)
    kept = dg.gb.block("states", "api", "accepted by a person", id=id, by="ana",
                       confirmed=dg.gb.sha(dg.gb.render("states", "api", dg.kit.ws / "api", id)[0]))
    f.write_text(text.replace(m[0], kept), encoding="utf-8", newline="\n")
    return kept


def test_a_gone_enum_leaves_the_page_unless_confirmed(dg):
    pages_repo(dg)
    dg.put("api", "src/main/java/demo/PetState.java", "enum PetState { NEW, ADOPTED }\n")
    dg.mod.write_pages()
    f = dg.kit.root / "docs" / "repos" / "api" / "diagrams.md"
    kept = confirm(dg, f, "PetState")
    (dg.kit.ws / "api" / "src/main/java/demo/OrderStatus.java").unlink()
    (dg.kit.ws / "api" / "src/main/java/demo/PetState.java").unlink()
    dg.mod.write_pages()
    text = f.read_text(encoding="utf-8")
    assert keys(text) == [("endpoints-map", "api", None), ("states", "api", "PetState")] and kept in text
    _, issues = dg.gb.check(dg.kit.docs.collect())
    assert any("diagrams.md" in i for i in issues)


def test_a_confirmed_block_that_is_still_valid_is_kept_verbatim(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    f = dg.kit.root / "docs" / "repos" / "api" / "diagrams.md"
    kept = confirm(dg, f, "OrderStatus")
    dg.mod.write_pages()
    assert f.read_text(encoding="utf-8").count(kept) == 1


def test_a_page_a_person_owns_is_not_touched(dg):
    pages_repo(dg)
    dg.mod.write_pages()
    f = dg.kit.root / "docs" / "repos" / "api" / "diagrams.md"
    f.write_text(f.read_text(encoding="utf-8").replace("x-owner: ai", "x-owner: human"), encoding="utf-8", newline="\n")
    before = f.read_bytes()
    dg.put("api", "src/main/java/demo/PetState.java", "enum PetState { NEW, ADOPTED }\n")
    (dg.kit.ws / "api" / "src/main/java/demo/OrderStatus.java").unlink()
    assert "docs/repos/api/diagrams.md" not in dg.mod.write_pages()
    assert f.read_bytes() == before


def test_the_diagrams_command(dg):
    import json, os, subprocess, sys
    pages_repo(dg)
    env = {**os.environ, "CAMARONES_ROOT": str(dg.kit.root)}
    run = lambda *a: subprocess.run([sys.executable, str(dg.kit.kit_dir / "camarones.py"), "diagrams", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    out = json.loads(run("--json").stdout)
    assert "docs/architecture/system-map.md" in out["written"] and "docs/repos/api/diagrams.md" in out["written"]
    assert run().returncode == 0


def test_install_scan_draws_the_diagrams(dg):
    pages_repo(dg)
    dg.kit.wizard.scan_repos(log=lambda _: None)
    assert (dg.kit.root / "docs" / "architecture" / "system-map.md").exists()
    assert (dg.kit.root / "docs" / "repos" / "api" / "diagrams.md").exists()


def test_first_look_draws_the_diagrams(dg, monkeypatch):
    pages_repo(dg)
    serve = importlib.import_module("lib.serve")
    monkeypatch.setattr(serve.env, "which", lambda _n: None)
    logs = []
    assert serve.first_look(log=logs.append)
    assert (dg.kit.root / "docs" / "architecture" / "system-map.md").exists()
    assert "architecture/system-map.md" in logs[-1]
