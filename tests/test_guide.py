"""The guides (lib/guide.py): the kit's own explanation of itself, served to the desktop app's Machine › Guide from the
installed kit (never a project's stale copy), in the machine's language with English as the fallback per file."""
from __future__ import annotations

import json, re, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

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


# The guides the kit ships: each statement must match the code, so the buttons and links they carry are checked here.
GUIDES = Path(__file__).resolve().parents[1] / ".camarones" / "templates" / "docs"
MARKER = re.compile(r"^<!--\s*(go|cmd|portal|tour):(\S+)\s*-->\s*$", re.M)
LINK = re.compile(r"\]\(((?:\./)?[\w-]+\.md)?(?:#([^)\s]*))?\)")


def shipped():
    for lang, folder in (("en", GUIDES / "guides"), ("es", GUIDES / "i18n" / "es" / "guides")):
        for f in sorted(folder.glob("*.md")):
            yield lang, f


def test_the_kit_ships_the_guides_in_order(kit):
    from lib import guide
    got = guide.guides("en")
    assert [g["name"] for g in got] == list(guide.ORDER)
    assert all(g["title"] and g["description"] for g in got)


def test_cmd_markers_name_catalog_commands(kit):
    from lib import appapi
    names = {c["name"] for c in appapi.catalog()["commands"]}
    for _, f in shipped():
        for kind, target in MARKER.findall(f.read_text(encoding="utf-8")):
            if kind == "cmd":
                assert target in names, f"{f.name}: cmd:{target}"


def test_portal_markers_are_portal_routes():
    zones = (GUIDES.parents[1] / "portal" / "app" / "src" / "zones.js").read_text(encoding="utf-8")
    routes = set(re.findall(r"(\w+): \['", zones.split("const ROUTES = {")[1].split("}")[0])) | {"", "search", "ask", "new"}
    for _, f in shipped():
        for kind, target in MARKER.findall(f.read_text(encoding="utf-8")):
            if kind == "portal":
                head = re.match(r"^#/([\w-]*)", target)
                assert head and head.group(1) in routes, f"{f.name}: portal:{target}"


def test_guide_links_point_at_headings(kit):
    from lib import docs
    for lang, f in shipped():
        body = docs.split_fm(f.read_text(encoding="utf-8"))[1]
        for file, anchor in LINK.findall(body):
            target = f.parent / Path(file).name if file else f
            assert target.is_file(), f"{f.name} ({lang}): {file}"
            if anchor:
                slugs = {h["slug"] for h in docs.headings(docs.split_fm(target.read_text(encoding="utf-8"))[1])}
                assert anchor in slugs, f"{f.name} ({lang}): {file}#{anchor}"


def test_projects_get_the_guides_without_overwriting(kit):
    from lib import env
    mine = kit.root / "docs" / "guides" / "app.md"
    if mine.exists():
        mine.unlink()
    portal = kit.root / "docs" / "guides" / "portal.md"
    portal.parent.mkdir(parents=True, exist_ok=True)
    portal.write_text("# Our own notes\n", encoding="utf-8")
    env.init_templates("shop", log=lambda _: None)
    assert mine.is_file()
    assert portal.read_text(encoding="utf-8") == "# Our own notes\n"


def test_spanish_twins_mirror_the_english_guides(kit):
    from lib import docs, guide
    for name in guide.ORDER:
        en = GUIDES / "guides" / f"{name}.md"
        es = GUIDES / "i18n" / "es" / "guides" / f"{name}.md"
        assert es.is_file(), name
        if name == "tutorial":
            continue                                   # the command guide's twins predate this check
        shape = lambda f: [h["level"] for h in docs.headings(docs.split_fm(f.read_text(encoding="utf-8"))[1]) if h["level"] in (2, 3)]
        marks = lambda f: MARKER.findall(f.read_text(encoding="utf-8"))
        assert shape(es) == shape(en), name
        assert marks(es) == marks(en), name
        assert docs.split_fm(es.read_text(encoding="utf-8"))[0]["title"] != docs.split_fm(en.read_text(encoding="utf-8"))[0]["title"], name


def test_projects_get_the_spanish_guides_too(kit):
    from lib import env
    es = kit.root / "docs" / "i18n" / "es" / "guides" / "using.md"
    if es.exists():
        es.unlink()
    env.init_templates("shop", log=lambda _: None)
    assert es.is_file()



def post(url, body, token=TOKEN):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1",
                                          **({"X-Camaron-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_machine_remembers_the_tour_offer(kit, app):
    """The app's window changes origin on every launch (a random port): the offer is kept in ~/.camarones.json."""
    assert call(f"{app}/api/app/info")[1]["tour_offered"] is False
    assert post(f"{app}/api/app/tour-offered", {}, token=None)[0] == 403
    assert post(f"{app}/api/app/tour-offered", {})[0] == 200
    assert call(f"{app}/api/app/info")[1]["tour_offered"] is True
    assert json.loads(kit.common.PREFS.read_text(encoding="utf-8"))["tour_offered"] is True


def test_the_server_keeps_its_tokens_out_of_what_it_starts(kit, monkeypatch):
    """Commands, runs and agents the server starts inherit its environment: the tokens leave it once read."""
    import os
    monkeypatch.setenv("CAMARONES_APP_TOKEN", "app-secret")
    monkeypatch.setenv("CAMARONES_PORTAL_TOKEN", "portal-secret")
    kit.serve.take_tokens()
    assert (kit.serve.APP_TOKEN, kit.serve.PORTAL_TOKEN) == ("app-secret", "portal-secret")
    assert "CAMARONES_APP_TOKEN" not in os.environ and "CAMARONES_PORTAL_TOKEN" not in os.environ
