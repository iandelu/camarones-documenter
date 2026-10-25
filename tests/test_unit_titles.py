"""Plan units' titles in the reader's language (4.55). plan.yaml keeps the English title the kit wrote (3.x and 4.x
plans stay as they are, byte for byte); what people see is localized when it is read: while a unit's title is still
its type's English template (lib/pipelines/units.yaml `title`), the Spanish one (`title_es`) is shown in Spanish. A
title a person or `plan add` chose is shown as written. The server takes the UI's language (?lang=), else the one
picked on this machine (~/.camarones.json, Spanish by default); the wizard uses its own."""
from __future__ import annotations

import io, json, string, threading, urllib.request
from http.server import ThreadingHTTPServer

import pytest
import yaml
from rich.console import Console

TOKEN = "titles-tok"


def fields(tpl: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(tpl) if f}


def unit(kit, uid):
    return kit.plan.get(kit.plan.load(), uid)


# ---------- the templates ----------
def test_every_unit_type_has_its_title_in_es_and_en(kit):
    from lib.harness import pipeline
    for type_, t in pipeline.types().items():
        assert t.get("title") and t.get("title_es"), type_
        assert t["title_es"] != t["title"], type_                       # written in Spanish, not copied
        assert fields(t["title_es"]) == fields(t["title"]), type_       # the same {repo} / {slug} filled in


def test_the_stored_titles_stay_english(kit):
    """blueprint() and sync() write the English template, as every kit before did: a plan written now opens the same
    with an older kit, and `plan sync` never flips a title between languages."""
    data = kit.plan.sync()
    disc = kit.plan.get(data, "discovery:api")
    assert disc["title"] == "Discovery of api"
    stored = yaml.safe_load(kit.plan.PLAN.read_text(encoding="utf-8"))["units"]
    assert next(u["title"] for u in stored if u["id"] == "discovery:api") == "Discovery of api"


# ---------- plan.title ----------
def test_a_kit_unit_reads_in_spanish_and_english(kit):
    kit.plan.sync()
    disc = unit(kit, "discovery:api")
    assert kit.plan.title(disc, "es") == "Descubrimiento de api"
    assert kit.plan.title(disc, "en") == "Discovery of api"
    assert kit.plan.title(unit(kit, "interview-context"), "es").startswith("Entrevista 1: ")


def test_a_language_the_kit_does_not_speak_reads_in_english(kit):
    kit.plan.sync()
    assert kit.plan.title(unit(kit, "discovery:api"), "fr") == "Discovery of api"


def test_a_title_someone_wrote_stays_as_written(kit):
    kit.plan.sync()
    kit.plan.add("flow:checkout", "Checkout: from the cart to a paid order")
    assert kit.plan.title(unit(kit, "flow:checkout"), "es") == "Checkout: from the cart to a paid order"
    edited = {**unit(kit, "discovery:api"), "title": "Discovery of the API gateway"}       # changed by hand
    assert kit.plan.title(edited, "es") == "Discovery of the API gateway"


def test_units_the_kit_adds_while_working_read_in_spanish(kit):
    from lib.harness import evals
    kit.plan.sync()
    kit.plan.add("flow:checkout", "Flow: checkout")                       # what the flows catalog writes
    kit.plan.add("security-review", kit.plan.TYPES["security-review"][2], "security-review", [])   # the wizard's extra
    kit.plan.ensure("integrate:discovery:api", "integrate",
                    title="Integrate discovery:api: resolve it against the main docs")      # harness/integrate.py
    evals.draft_unit()
    kit.plan.ensure("review-fixes", "review-fixes")
    es = {u["id"]: kit.plan.title(u, "es") for u in kit.plan.load()["units"]}
    assert es["flow:checkout"] == "Flujo: checkout"
    assert es["security-review"].startswith("[beta] Revisión de seguridad")
    assert es["integrate:discovery:api"].startswith("Integrar discovery:api: ")
    assert es["eval-questions"].startswith("Preguntas de oro: ")
    assert es["review-fixes"].startswith("Aplicar ")


def test_a_unit_of_an_unknown_type_keeps_its_title(kit):
    assert kit.plan.title({"id": "x", "type": "gone-type", "title": "Old work"}, "es") == "Old work"
    assert kit.plan.title({"id": "x", "title": "No type at all"}, "es") == "No type at all"


def test_the_next_step_speaks_the_language_asked(kit):
    kit.plan.sync()
    assert kit.plan.next_step()["unit"]["title"] == unit(kit, "setup")["title"]           # English, as before
    assert kit.plan.next_step(lang="es")["unit"]["title"].startswith("Entorno listo")


# ---------- a plan from an older kit ----------
OLD_PLAN = """\
# Camarón work plan — one unit per agent session. Managed by the camarones CLI.
version: 1
units:
- id: setup
  type: setup
  phase: 0
  runner: wizard
  title: Environment ready (tools, repos, agent wiring)
  status: done
  deps: []
  repo: null
  notes: ''
  updated: '2025-03-02T10:00:00'
- id: discovery:api
  type: discovery
  phase: 1
  runner: agent
  title: Discovery of api
  status: todo
  deps:
  - setup
  repo: api
  notes: ''
  updated: null
- id: flow:checkout
  type: flow
  phase: 5
  runner: agent
  title: Checkout, end to end
  status: todo
  deps: []
  repo: null
  notes: ''
  updated: null
- id: legacy-step
  type: legacy-step
  phase: 3
  runner: agent
  title: A unit type this kit no longer has
  status: todo
  deps: []
  repo: null
  notes: ''
  updated: null
"""


@pytest.fixture
def old_plan(kit):
    kit.plan.PLAN.parent.mkdir(parents=True, exist_ok=True)
    kit.plan.PLAN.write_bytes(OLD_PLAN.encode("utf-8"))
    return kit.plan.PLAN


def test_an_older_plan_is_localized_without_being_rewritten(kit, old_plan):
    before = old_plan.read_bytes()
    units = {u["id"]: u["title"] for u in kit.serve.api_pipeline("es")["units"]}
    assert units == {"setup": "Entorno listo (herramientas, repos y agentes conectados)",
                     "discovery:api": "Descubrimiento de api", "flow:checkout": "Checkout, end to end",
                     "legacy-step": "A unit type this kit no longer has"}
    assert kit.serve.app_summary("es")["step"]["unit"]["title"] == "Descubrimiento de api"
    assert old_plan.read_bytes() == before


# ---------- the server ----------
@pytest.fixture
def server(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    req = urllib.request.Request(url, headers={"X-Camaron-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def disc_title(body):
    return next(u["title"] for u in body["units"] if u["id"] == "discovery:api")


def test_the_pipeline_speaks_the_language_of_the_ui_that_asks(kit, server):
    kit.plan.sync()
    assert disc_title(get(server + "/api/pipeline?lang=es")) == "Descubrimiento de api"
    assert disc_title(get(server + "/api/pipeline?lang=en")) == "Discovery of api"


def test_without_a_language_the_machine_setting_decides(kit, server):
    kit.plan.sync()
    assert disc_title(get(server + "/api/pipeline")) == "Descubrimiento de api"           # nothing chosen: Spanish
    kit.common.save_json(kit.common.PREFS, {"lang": "en"})
    assert disc_title(get(server + "/api/pipeline")) == "Discovery of api"
    kit.common.save_json(kit.common.PREFS, {"lang": "es"})
    assert disc_title(get(server + "/api/pipeline?lang=xx")) == "Descubrimiento de api"   # not a UI language


def test_the_app_summary_speaks_the_language_asked(kit, server):
    kit.plan.sync()
    kit.plan.set_status("setup", "done")
    assert get(server + "/api/app/summary?lang=es")["step"]["unit"]["title"] == "Descubrimiento de api"
    assert get(server + "/api/app/summary?lang=en")["step"]["unit"]["title"] == "Discovery of api"


def test_reading_never_writes_the_plan(kit, server):
    kit.plan.sync()
    before = kit.plan.PLAN.read_bytes()
    for path in ("/api/pipeline?lang=es", "/api/pipeline?lang=en", "/api/app/summary?lang=es", "/api/pipeline"):
        get(server + path)
    assert kit.plan.PLAN.read_bytes() == before


# ---------- the wizard ----------
def text(renderable) -> str:
    c = Console(file=io.StringIO(), width=240, color_system=None)
    c.print(renderable)
    return c.file.getvalue()


@pytest.mark.parametrize("lang,shown", [("es", "Descubrimiento de api"), ("en", "Discovery of api")])
def test_the_wizard_shows_the_titles_in_its_language(kit, lang, shown):
    data = kit.plan.sync()
    w = kit.wizard.W()
    w.lang = lang
    assert w.unit_label(kit.plan.get(data, "discovery:api"), data) == f"discovery:api — {shown}"
    assert shown in text(w.board())
