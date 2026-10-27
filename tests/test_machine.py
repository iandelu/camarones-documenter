"""This machine (lib/machine.py and the desktop app's Machine panel): the wizard's settings (language, models) as
`camaron config`, tokens saved through the app's server only (never on a command line), what the panel shows about
the repos, the kit and the setup, and uninstall / migrate previewed without asking first."""
from __future__ import annotations

import json, os, subprocess, sys, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "app-tok"


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL)


def test_config_reads_and_writes_the_wizard_settings(kit):
    r = cli(kit, "config", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"lang": "es", "model": "sonnet", "codex_model": kit.wizard.CODEX_MODEL_DEFAULT,
                                    "sessions": "canvas"}
    assert cli(kit, "config", "set", "lang", "en").returncode == 0
    assert cli(kit, "config", "set", "model", "opus").returncode == 0
    assert cli(kit, "config", "set", "codex_model", "gpt-9").returncode == 0
    assert cli(kit, "config", "set", "sessions", "window").returncode == 0
    prefs = json.loads(kit.common.PREFS.read_text(encoding="utf-8"))
    assert (prefs["lang"], prefs["model"], prefs["codex_model"], prefs["sessions"]) == ("en", "opus", "gpt-9", "window")
    assert cli(kit, "config", "get", "lang").stdout.strip() == "en"
    assert cli(kit, "config", "get", "sessions").stdout.strip() == "window"


@pytest.mark.parametrize("key,value", [("lang", "fr"), ("model", "gpt"), ("nope", "x"), ("codex_model", " "),
                                       ("sessions", "tab")])
def test_config_refuses_what_the_wizard_would_not_offer(kit, key, value):
    r = cli(kit, "config", "set", key, value)
    assert r.returncode == 2 and r.stderr


@pytest.fixture
def app(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, token=TOKEN):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1",
                                          **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_tokens_go_through_the_server_and_never_come_back(kit, app, monkeypatch):
    from lib import creds
    monkeypatch.setattr(creds, "_keyring", lambda: None)                # the fallback file in the test's HOME
    monkeypatch.setattr(creds, "verify", lambda host, kind, token: (token == "good", "ana" if token == "good" else "401"))
    code, r = call(app + "/api/app/creds", {"host": "https://gitlab.example.com/group", "kind": "gitlab", "token": "bad"})
    assert code == 400 and "401" in r["error"]
    assert creds.get("gitlab.example.com") is None
    code, r = call(app + "/api/app/creds", {"host": "gitlab.example.com", "kind": "gitlab", "token": "good"})
    assert code == 200 and r["user"] == "ana"
    assert creds.get("gitlab.example.com") == "good"
    code, listed = call(app + "/api/app/creds")
    assert listed["hosts"] == [{"host": "gitlab.example.com", "kind": "gitlab", "user": "ana", "saved": True}]
    assert "good" not in json.dumps(listed)
    code, r = call(app + "/api/app/creds/test", {"host": "gitlab.example.com"})
    assert code == 200 and r == {"ok": True, "info": "ana"}
    code, _ = call(app + "/api/app/creds/delete", {"host": "gitlab.example.com"})
    assert code == 200 and creds.get("gitlab.example.com") is None
    assert call(app + "/api/app/creds")[1]["hosts"] == []
    assert call(app + "/api/app/creds", token=None)[0] == 403


def test_a_sonarqube_token_is_saved_under_its_host_as_given(kit, app, monkeypatch):
    from lib import creds
    monkeypatch.setattr(creds, "_keyring", lambda: None)
    asked = []
    monkeypatch.setattr(creds, "verify", lambda host, kind, token: (asked.append((host, kind)) or token == "good", ""))
    code, r = call(app + "/api/app/creds", {"host": "https://sonar.example.com/sonar/", "kind": "sonarqube", "token": "bad"})
    assert code == 400 and creds.get("https://sonar.example.com/sonar") is None
    code, r = call(app + "/api/app/creds", {"host": "https://sonar.example.com/sonar/", "kind": "sonarqube", "token": "good"})
    assert code == 200 and r["host"] == "https://sonar.example.com/sonar"
    assert creds.get("https://sonar.example.com/sonar") == "good"
    assert asked[-1] == ("https://sonar.example.com/sonar", "sonarqube")
    code, listed = call(app + "/api/app/creds")
    assert listed["hosts"] == [{"host": "https://sonar.example.com/sonar", "kind": "sonarqube", "user": "", "saved": True}]
    assert "good" not in json.dumps(listed) and "good" not in creds.META.read_text(encoding="utf-8")
    code, r = call(app + "/api/app/creds/test", {"host": "https://sonar.example.com/sonar"})
    assert code == 200 and r == {"ok": True, "info": ""} and asked[-1][1] == "sonarqube"
    code, _ = call(app + "/api/app/creds/delete", {"host": "https://sonar.example.com/sonar/"})
    assert code == 200 and creds.get("https://sonar.example.com/sonar") is None and not creds.hosts()


def test_a_sonarqube_http_host_is_refused_by_the_server(kit, app, monkeypatch):
    from lib import creds
    monkeypatch.setattr(creds, "_keyring", lambda: None)
    code, r = call(app + "/api/app/creds", {"host": "http://sonar.example.com", "kind": "sonarqube", "token": "t", "anyway": True})
    assert code == 400 and "solo https" in r["error"]
    assert not creds.hosts()


def test_a_bad_token_can_be_kept_on_purpose(kit, app, monkeypatch):
    from lib import creds
    monkeypatch.setattr(creds, "_keyring", lambda: None)
    monkeypatch.setattr(creds, "verify", lambda host, kind, token: (False, "no network"))
    code, r = call(app + "/api/app/creds", {"host": "github.com", "kind": "github", "token": "t", "anyway": True})
    assert code == 200 and creds.get("github.com") == "t"


def test_the_machine_panel_data(kit, app):
    code, m = call(app + "/api/app/machine")
    assert code == 200
    assert m["settings"]["lang"] == "es" and m["setup_steps"] > 0 and m["kit"]["version"]
    assert {r["name"] for r in m["repos"]} == set(kit.docs.repo_names())
    assert all({"name", "url", "stack", "cloned"} <= set(r) for r in m["repos"])
    assert m["profile"] in ("quick", "full", None)
    assert m["sessions"] == ["canvas", "window"] and isinstance(m["terminals"], bool)


@pytest.fixture
def entries(kit):
    from lib import appapi
    return {c["name"]: c for c in appapi.catalog()["commands"]}


def test_uninstall_and_migrate_preview_without_asking(kit, entries):
    from lib import appapi
    assert appapi.argv(entries["uninstall"], {"dry_run": True}) == ["uninstall", "--dry-run"]
    assert appapi.argv(entries["migrate"], {"dry_run": True}) == ["migrate", "--dry-run"]
    with pytest.raises(PermissionError):
        appapi.argv(entries["uninstall"], {"user_level": True})
    assert appapi.argv(entries["uninstall"], {"user_level": True}, confirmed=True) == ["uninstall", "--global", "--yes"]


def test_codex_models_come_from_codex_s_own_cache(kit, monkeypatch):
    """Codex keeps the models it offers in ~/.codex/models_cache.json: the app's dropdown lists the visible ones in
    Codex's order, then the one saved here and the kit's default when Codex does not list them."""
    from lib import common, machine
    home = common.HOME / ".codex"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    (home / "models_cache.json").write_text(json.dumps({"models": [
        {"slug": "gpt-b", "display_name": "GPT-B", "visibility": "list", "priority": 2},
        {"slug": "hidden", "display_name": "Hidden", "visibility": "hide", "priority": 1},
        {"slug": "gpt-a", "display_name": "GPT-A", "visibility": "list", "priority": 1}]}), encoding="utf-8")
    machine.set_setting("codex_model", "my-own")
    slugs = [m["slug"] for m in machine.codex_models()]
    assert slugs == ["gpt-a", "gpt-b", "my-own", kit.wizard.CODEX_MODEL_DEFAULT]
    assert machine.codex_models()[0]["label"] == "GPT-A"
    assert "codex_models" in machine.panel()


def test_codex_models_without_a_cache_keep_the_saved_one(kit, monkeypatch):
    from lib import common, machine
    monkeypatch.setenv("CODEX_HOME", str(common.HOME / "nowhere"))
    assert [m["slug"] for m in machine.codex_models()] == [kit.wizard.CODEX_MODEL_DEFAULT]
    (common.HOME / "nowhere").mkdir(parents=True)
    (common.HOME / "nowhere" / "models_cache.json").write_text("{not json", encoding="utf-8")
    assert [m["slug"] for m in machine.codex_models()] == [kit.wizard.CODEX_MODEL_DEFAULT]
