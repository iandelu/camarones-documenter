"""Optional AI suggestions for the story wizard: off by default, one headless call to the runner routed for bounded work
(like Ask's AI answer), wording / criteria / subtask ideas only. An invented file never survives, and nothing here
decides footprints, dependencies, waves or the verdict."""
from __future__ import annotations

import json, sys

import pytest

from test_portal_kanban import PORTAL, call, server  # noqa: F401 — the portal server fixture
from test_portal_stories import get, ops, post, story, world  # noqa: F401 — fixtures and helpers

REAL = "api:api-core/src/main/java/demo/shop/orders/OrderService.java"
INVENTED = "api:api-core/src/main/java/demo/shop/orders/Nope.java"

SUGGESTER = r'''
import json, os, sys
open(os.environ["ASK_LOG"], "w", encoding="utf-8").write(sys.argv[1])
open(os.environ["ASK_LOG"] + ".cwd", "w", encoding="utf-8").write(json.dumps([os.getcwd(), sys.argv[2:]]))
if os.environ.get("ASK_SLEEP"):
    import time; time.sleep(float(os.environ["ASK_SLEEP"]))
print("thinking…")
if os.environ.get("ASK_BROKEN"):
    print('{"tasks": [ this is not json')
    sys.exit(0)
print(os.environ["SUGGEST_JSON"])
'''


@pytest.fixture
def suggester(world, tmp_path, monkeypatch):  # noqa: F811
    """A fake bounded runner that prints `$SUGGEST_JSON`; returns the file it logs its prompt to. AI stays off."""
    script = tmp_path / "suggester.py"
    script.write_text(SUGGESTER, encoding="utf-8")
    log = tmp_path / "prompt.txt"
    monkeypatch.setenv("ASK_LOG", str(log))
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "{prompt}", "{model}"]}},
                      "routing": {"bounded": ["fake"]}})
    return log


def turn_on(kit, **extra):
    ws = kit.docs.workspace()
    ws["stories"] = {"ai": True, **extra}
    kit.docs.save_workspace(ws)


def reply(monkeypatch, **obj):
    monkeypatch.setenv("SUGGEST_JSON", json.dumps(obj))


def a_story(**kw):
    return {"id": None, "as_": "responsable de pedidos", "want": "cobrar los pedidos con tarjeta",
            "so": "no perder ventas", "criteria": [], "touches": [REAL], "epic": None, "priority": None, **kw}


# ── off by default ───────────────────────────────────────────────────────────────────────────────────────────────

def test_it_is_off_by_default_and_never_calls_the_runner(world, suggester):
    from lib import stories_ai
    assert stories_ai.enabled() is False                                  # a runner is configured, the switch is not
    with pytest.raises(RuntimeError, match=r"AI suggestions are off: set stories: \{ai: true\} in workspace.yaml"):
        stories_ai.suggest(a_story(), what="tasks", lang="en")
    assert not suggester.exists()                                         # the fake runner never ran


@pytest.mark.parametrize("value", [False, "true", 1, None, "yes"])
def test_only_a_true_switch_turns_it_on(world, suggester, value):
    from lib import stories_ai
    ws = world.docs.workspace(); ws["stories"] = {"ai": value}; world.docs.save_workspace(ws)
    assert stories_ai.enabled() is False


def test_on_without_a_runner_is_not_available(world, tmp_path):
    from lib import stories_ai
    from lib.common import PREFS, save_json
    save_json(PREFS, {"routing": {"bounded": ["nonexistent-runner"]}})
    turn_on(world)
    assert stories_ai.enabled() is False
    with pytest.raises(RuntimeError, match="no runner for bounded work"):
        stories_ai.suggest(a_story(), what="tasks", lang="en")


def test_enabled_does_not_run_anything(world, suggester):
    from lib import stories_ai
    turn_on(world)
    assert stories_ai.enabled() is True and stories_ai.runner() == "fake"
    assert not suggester.exists()


# ── what comes back ──────────────────────────────────────────────────────────────────────────────────────────────

def test_tasks_keep_real_files_only(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    reply(monkeypatch, tasks=[{"title": "Cobrar con tarjeta", "touches": [REAL, INVENTED, "no-colon", 7]},
                              {"title": "Avisar al cliente", "touches": []},
                              {"title": "   ", "touches": [REAL]}, "not an object", {"touches": [REAL]}])
    r = stories_ai.suggest(a_story(), what="tasks", lang="es")
    assert r["tasks"] == [{"title": "Cobrar con tarjeta", "touches": [REAL]},
                          {"title": "Avisar al cliente", "touches": []}]
    assert r["rewrite"] is None and r["criteria"] == [] and r["missing"] == []
    assert r["runner"] == "fake" and "seconds" in r and "model" in r


def test_tasks_are_capped_trimmed_and_deduplicated(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    titles = ["Tarea %d" % i for i in range(12)]
    reply(monkeypatch, tasks=[{"title": "Ya estaba", "touches": []}, {"title": "x" * 300, "touches": []},
                              {"title": titles[0], "touches": []}, {"title": "tarea 0", "touches": []}]
          + [{"title": t, "touches": []} for t in titles[1:]])
    r = stories_ai.suggest(a_story(), what="tasks", exclude=["  ya   ESTABA "], lang="es")
    got = [t["title"] for t in r["tasks"]]
    assert len(got) == 8 and "Ya estaba" not in got
    assert len(got[0]) <= 120 and got[0].startswith("xxx")
    assert got.count("Tarea 0") == 1 and got[1] == "Tarea 0"             # "tarea 0" duplicated "Tarea 0": the first stays


def test_criteria_are_text_deduplicated_and_capped(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    reply(monkeypatch, criteria=["Dado un pedido, cuando pago, entonces veo el recibo", "  ", 4, "Ya estaba",
                                 "Dado un pedido, cuando pago, entonces veo el recibo"] + [f"Criterio {i}" for i in range(12)])
    r = stories_ai.suggest(a_story(), what="criteria", exclude=["ya estaba"], lang="es")
    assert r["criteria"][0] == "Dado un pedido, cuando pago, entonces veo el recibo"
    assert "Ya estaba" not in r["criteria"] and len(r["criteria"]) == 8 and len(set(r["criteria"])) == 8
    assert r["tasks"] == [] and r["rewrite"] is None and r["missing"] == []


def test_a_rewrite_needs_all_three_clauses(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    reply(monkeypatch, rewrite={"as": " quien gestiona los pedidos ", "want": "pagar con tarjeta.", "so": "vender más"})
    r = stories_ai.suggest(a_story(), what="rewrite", lang="es")
    assert r["rewrite"] == {"as_": "quien gestiona los pedidos", "want": "pagar con tarjeta", "so": "vender más"}
    reply(monkeypatch, rewrite={"as": "quien gestiona los pedidos", "want": "pagar con tarjeta", "so": ""})
    r = stories_ai.suggest(a_story(), what="rewrite", lang="es")
    assert r["rewrite"] is None and r["missing"] == ["rewrite"]


def test_broken_json_lists_what_is_missing(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    monkeypatch.setenv("ASK_BROKEN", "1")
    for what, key in (("tasks", "tasks"), ("criteria", "criteria"), ("rewrite", "rewrite")):
        r = stories_ai.suggest(a_story(), what=what, lang="en")
        assert r["missing"] == [key] and r["tasks"] == [] and r["criteria"] == [] and r["rewrite"] is None
    reply(monkeypatch, other=1)
    monkeypatch.delenv("ASK_BROKEN")
    assert stories_ai.suggest(a_story(), what="tasks", lang="en")["missing"] == ["tasks"]


def test_a_bad_part_is_a_value_error_before_any_call(world, suggester):
    from lib import stories_ai
    turn_on(world)
    with pytest.raises(ValueError, match="what"):
        stories_ai.suggest(a_story(), what="verdict", lang="en")        # type: ignore[arg-type]
    assert not suggester.exists()


# ── the call itself ──────────────────────────────────────────────────────────────────────────────────────────────

def test_the_prompt_is_one_line_in_the_project_language_and_the_model_runs_in_an_empty_folder(world, suggester, monkeypatch):
    from pathlib import Path
    from lib import stories_ai
    turn_on(world)
    reply(monkeypatch, criteria=["Dado un pedido, cuando pago, entonces veo el recibo"])
    stories_ai.suggest(a_story(), what="criteria", exclude=["Ya estaba"], lang="es")
    prompt = suggester.read_text(encoding="utf-8")
    assert "\n" not in prompt and "cobrar los pedidos con tarjeta" in prompt and "Spanish" in prompt
    assert "criteria" in prompt and "Ya estaba" in prompt
    assert "Reply with one JSON object on the last line" in prompt
    cwd, args = json.loads(suggester.with_name("prompt.txt.cwd").read_text(encoding="utf-8"))
    assert not Path(cwd).resolve().is_relative_to(world.common.WORKSPACE.resolve())
    assert args == [""]                                                  # fake runner: no cheap default
    stories_ai.suggest(a_story(), what="criteria", lang="en")
    assert "English" in suggester.read_text(encoding="utf-8")


def test_only_the_asked_part_is_requested(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    reply(monkeypatch, tasks=[])
    stories_ai.suggest(a_story(), what="tasks", lang="en")
    prompt = suggester.read_text(encoding="utf-8")
    assert '"tasks"' in prompt and '"criteria"' not in prompt and '"rewrite"' not in prompt
    assert REAL in prompt                                                # the files the story already touches


def test_the_cheap_model_and_the_workspace_override(world):
    from lib import stories_ai
    assert stories_ai.model("claude") == "haiku" and stories_ai.model("claude:opus") is None
    turn_on(world, model="sonnet")
    assert stories_ai.model("claude") == "sonnet" and stories_ai.model("fake") == "sonnet"


def test_a_slow_model_gives_a_readable_error(world, suggester, monkeypatch):
    from lib import stories_ai
    turn_on(world)
    monkeypatch.setattr(stories_ai, "TIMEOUT", 1)
    monkeypatch.setenv("ASK_SLEEP", "5")
    with pytest.raises(RuntimeError, match="1 s"):
        stories_ai.suggest(a_story(), what="tasks", lang="en")


def test_usage_is_recorded_for_people(world, suggester, monkeypatch):
    from lib import stories_ai, usage
    turn_on(world)
    seen = []
    monkeypatch.setattr(usage, "record", lambda event, **kw: seen.append((event, kw)))
    reply(monkeypatch, tasks=[{"title": "Una", "touches": []}])
    stories_ai.suggest(a_story(), what="tasks", lang="en")
    reply(monkeypatch, tasks=[])
    stories_ai.suggest(a_story(), what="tasks", lang="en")
    seen = [s for s in seen if s[0] == "stories:suggest"]                 # Ask's retrieval counts its own use apart
    assert seen == [("stories:suggest", {"channel": "human", "hit": True}),
                    ("stories:suggest", {"channel": "human", "hit": False})]


# ── over HTTP ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_list_says_whether_ai_is_available(world, suggester, server):  # noqa: F811
    assert get(server, "/api/stories")[1]["ai"] == {"available": False, "runner": None, "model": None}
    turn_on(world)
    assert get(server, "/api/stories")[1]["ai"] == {"available": True, "runner": "fake", "model": None}
    assert not suggester.exists()


def test_suggest_over_http(world, suggester, server, monkeypatch):  # noqa: F811
    turn_on(world)
    reply(monkeypatch, tasks=[{"title": "Cobrar con tarjeta", "touches": [REAL, INVENTED]}])
    code, b = post(server, "/api/stories/suggest", {**story(), "what": "tasks", "lang": "es"}, token=PORTAL)
    assert code == 200 and b["tasks"] == [{"title": "Cobrar con tarjeta", "touches": [REAL]}]
    assert b["runner"] == "fake"


def test_suggest_needs_the_token_and_does_not_call_the_runner(world, suggester, server, monkeypatch):  # noqa: F811
    turn_on(world)
    reply(monkeypatch, tasks=[])
    code, b = post(server, "/api/stories/suggest", {**story(), "what": "tasks"})
    assert code == 403 and b["token"] is True and "error" in b
    assert post(server, "/api/stories/suggest", {**story(), "what": "tasks"}, token="nope")[0] == 403
    assert not suggester.exists()


def test_suggest_while_off_is_a_503(world, suggester, server):  # noqa: F811
    code, b = post(server, "/api/stories/suggest", {**story(), "what": "tasks"}, token=PORTAL)
    assert code == 503 and "AI suggestions are off" in b["error"]
    assert not suggester.exists()


def test_a_timeout_is_a_503(world, suggester, server, monkeypatch):  # noqa: F811
    from lib import stories_ai
    turn_on(world)
    monkeypatch.setattr(stories_ai, "TIMEOUT", 1)
    monkeypatch.setenv("ASK_SLEEP", "5")
    code, b = post(server, "/api/stories/suggest", {**story(), "what": "tasks"}, token=PORTAL)
    assert code == 503 and "1 s" in b["error"]


def test_bad_bodies_are_400s(world, suggester, server, monkeypatch):  # noqa: F811
    turn_on(world)
    reply(monkeypatch, tasks=[])
    for body in ({**story()}, {**story(), "what": "verdict"}, {**story(), "what": 3}, {"what": "tasks"},
                 {**story(), "what": "tasks", "exclude": "no"}, {**story(), "what": "tasks", "exclude": [1]},
                 {**story(), "what": "tasks", "lang": 4}, {"story": {"want": ""}, "what": "tasks"}):
        assert post(server, "/api/stories/suggest", body, token=PORTAL)[0] == 400, body
    assert not suggester.exists()
    assert post(server, "/api/stories/nope", {}, token=PORTAL)[0] == 404
