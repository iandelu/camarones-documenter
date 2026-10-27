"""The guides (lib/guide.py): the kit's own explanation of itself, served to the desktop app's Machine › Guide from the
installed kit (never a project's stale copy), in the machine's language with English as the fallback per file."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

TOKEN = "app-tok"


@pytest.fixture
def app(kit, monkeypatch):
    monkeypatch.setattr(kit.serve, "APP_TOKEN", TOKEN)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, token=TOKEN):
    req = urllib.request.Request(url, headers={"X-Camarones": "1", **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def page(title: str, description: str, body: str) -> str:
    return f"---\ntype: guide\ntitle: {title}\ndescription: {description}\nx-owner: human\n---\n{body}"


def test_guides_follow_the_order_and_fall_back_to_english(kit, tmp_path):
    from lib import guide
    (tmp_path / "guides").mkdir(parents=True)
    (tmp_path / "i18n" / "es" / "guides").mkdir(parents=True)
    (tmp_path / "guides" / "app.md").write_text(page("The app", "Every section", "# The app\n\n## Plan\n"), encoding="utf-8")
    (tmp_path / "guides" / "using.md").write_text(page("Using", "How to", "# Using\n"), encoding="utf-8")
    (tmp_path / "i18n" / "es" / "guides" / "using.md").write_text(page("Usar", "Cómo", "# Usar\n"), encoding="utf-8")
    es = guide.guides("es", tmp_path)
    assert [g["name"] for g in es] == ["using", "app"]
    assert (es[0]["title"], es[0]["description"], es[0]["markdown"]) == ("Usar", "Cómo", "# Usar\n")
    assert (es[1]["title"], es[1]["markdown"]) == ("The app", "# The app\n\n## Plan\n")
    assert guide.guides("en", tmp_path)[0]["title"] == "Using"


def test_a_spanish_twin_without_its_english_original_is_not_listed(kit, tmp_path):
    from lib import guide
    (tmp_path / "i18n" / "es" / "guides").mkdir(parents=True)
    (tmp_path / "i18n" / "es" / "guides" / "app.md").write_text(page("La app", "x", "# La app\n"), encoding="utf-8")
    assert guide.guides("es", tmp_path) == []


def test_guide_endpoint_needs_the_app_token(kit, app):
    status, _ = call(f"{app}/api/app/guide?lang=en", token=None)
    assert status == 403
    status, body = call(f"{app}/api/app/guide?lang=en")
    assert status == 200
    assert body["lang"] == "en" and isinstance(body["guides"], list)
    assert body["guides"] and body["guides"][-1]["name"] == "tutorial"
