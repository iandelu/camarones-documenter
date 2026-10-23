"""Portal smoke test (S17): every tab's data comes back from a documented-project fixture, without an error and not
empty, and every tab in the bar has a route and a view. It catches what users met as "the tab does not work": a
silent 500, an endpoint a view calls that the server lacks, a tab with no route. Offline, no browser."""
from __future__ import annotations

import json, re, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

from conftest import wire_project
from test_mcp_resources import FLOW, write

C4 = """model {
  customer = actor 'Customer'
  shop = system 'Shop' {
    orders = service 'Orders' {
      #ai-draft
      technology 'Java'
    }
    db = database 'PostgreSQL: shop'
  }
  customer -> shop.orders 'places orders'
  shop.orders -> shop.db 'reads/writes'
}
views {
  view index {
    include *
  }
  view shop_containers of shop {
    include *
  }
}
"""


@pytest.fixture
def portal(kit, monkeypatch):
    wired = wire_project(kit)
    write(wired, "flows/checkout.md", FLOW)
    arch = wired.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text(C4, encoding="utf-8")
    (arch / "likec4.config.json").write_text('{"name": "shop"}', encoding="utf-8")
    wired.plan.sync()
    from lib import boards, ci
    boards.save("ideas", {"type": "excalidraw", "elements": []})
    monkeypatch.setattr(ci, "_probe", lambda cmd: None)                                  # no forge CLI, no network
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wired.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# (endpoint, what must not be empty in its answer) — one per thing a tab loads
CALLS = [
    ("tree", lambda d: d["docs"] and d["views"] and d["repos"]),
    ("doc?path=flows/checkout.md", lambda d: d["raw"] and d["title"] == "Checkout"),
    ("search?q=payment", lambda d: d),
    ("ask?q=how%20are%20payments%20retried", lambda d: d["sections"]),
    ("status?check=0", lambda d: "plan" in d),
    ("check", lambda d: "errors" in d),
    ("wikis", lambda d: len(d) == 3),
    ("viewers", lambda d: "c4" in d),
    ("pipeline", lambda d: d["units"]),
    ("boards", lambda d: d[0]["name"] == "ideas"),
    ("board?name=ideas", lambda d: d["type"] == "excalidraw"),
    ("sketch?view=shop_containers", lambda d: [e for e in d["elements"] if e["type"] == "rectangle"]),
    ("c4/view?id=shop_containers", lambda d: {e["fqn"] for e in d["elements"]} >= {"shop.orders", "shop.db"}),
    ("reviews", lambda d: isinstance(d, list)),
    ("runs", lambda d: isinstance(d, list)),
    ("jobs", lambda d: isinstance(d, list)),
    ("kpis", lambda d: d["coverage"]["byRepo"] and d["c4"]["elements"] == 4),
    ("ci", lambda d: d["installed"] and d["snippets"]["fresh"]),
]


@pytest.mark.parametrize("path, ok", CALLS, ids=[c[0].split("?")[0] for c in CALLS])
def test_every_tab_gets_its_data(portal, path, ok):
    code, d = get(f"{portal}/api/{path}")
    assert code == 200, d
    assert ok(d)


def test_the_page_and_its_scripts_are_served(portal):
    with urllib.request.urlopen(f"{portal}/", timeout=30) as r:
        html = r.read().decode("utf-8")
    for src in re.findall(r'(?:src|href)="((?:\./)?(?:assets|legacy)/[^"]+)"', html):
        with urllib.request.urlopen(f"{portal}/{src.removeprefix('./')}", timeout=30) as r:
            assert r.status == 200 and r.read(), src


def test_every_tab_has_a_route_and_every_react_view_a_component(kit):
    app = (kit.kit_dir / "portal" / "app" / "public" / "legacy" / "app.js").read_text(encoding="utf-8")
    native = (kit.kit_dir / "portal" / "app" / "src" / "Native.jsx").read_text(encoding="utf-8")
    core = (kit.kit_dir / "portal" / "app" / "public" / "legacy" / "core.js").read_text(encoding="utf-8")
    tabs = re.findall(r"\['([\w-]+)', '#/[\w-]*'\]", app)
    react = re.search(r"if \(\[([^\]]+)\]\.includes\(view\)", app).group(1)
    react = re.findall(r"'([\w-]+)'", react)
    components = re.search(r"const View = \{([^}]+)\}\[view\]", native).group(1)
    for tab in tabs:
        routed = tab in react or re.search(rf"view === '{tab}'", app) or tab in ("docs", "c4")
        assert routed, f"tab {tab} has no route"
        assert re.search(rf"\b{'codeTab' if tab == 'code' else tab}: '", core), f"tab {tab} has no label"
    for view in react:
        assert re.search(rf"\b{view}: \w+", components), f"React view {view} has no component"
