"""Diagrams from the code (no AI): `states` blocks read from status enums in Java, Kotlin, TypeScript, Python, C#, Go and
SQL. A diagram shows the states only, never a transition: those wait for a proposal."""
from __future__ import annotations

import importlib

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
