"""R32: the MCP server can write, but only drafts. `propose_edit` changes an AI draft directly and leaves anything a
person confirmed or owns untouched (the proposal waits for review); nothing it does confirms a page. Pipeline control
needs an explicit opt-in. The same server answers over HTTP on 127.0.0.1, only with this machine's token."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request

import pytest

FLOW = "---\ntitle: Checkout\n---\n# Checkout\n\n> **TL;DR:** Pay.\n\n## Steps\nPay once.\n\n## Data touched\nThe `orders` table.\n"


@pytest.fixture
def mcp(kit):
    import importlib
    kit.plan.sync()
    for rel in ("flows/draft.md", "flows/confirmed.md", "flows/mine.md"):
        f = kit.root / "docs" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(FLOW.replace("title: Checkout", "title: Checkout\nx-owner: human") if "mine" in rel else FLOW,
                     encoding="utf-8")
    kit.docs.confirm([str(kit.root / "docs" / "flows" / "confirmed.md")], by="ana")
    return importlib.import_module("lib.mcp")


def read(kit, rel):
    return (kit.root / "docs" / rel).read_text(encoding="utf-8")


def test_a_draft_section_is_edited_in_place_and_stays_a_draft(kit, mcp):
    out = mcp.propose_edit("flows/draft.md", "Pay once; retry twice on timeout.", section="steps", reason="retries added")
    assert "applied" in out
    text = read(kit, "flows/draft.md")
    assert "retry twice on timeout" in text and "The `orders` table." in text and "## Steps" in text
    assert next(r for r in kit.docs.collect() if r["path"] == "flows/draft.md")["trust"] == "draft"


@pytest.mark.parametrize("rel", ["flows/confirmed.md", "flows/mine.md"])
def test_confirmed_or_human_pages_are_never_touched(kit, mcp, rel):
    before = read(kit, rel)
    out = mcp.propose_edit(rel, "Something else.", section="steps", reason="looks wrong")
    assert read(kit, rel) == before and "waits for review" in out
    feedback = (kit.root / "docs" / ".work" / "review-feedback.md").read_text(encoding="utf-8")
    assert rel in feedback and "looks wrong" in feedback
    proposals = list((kit.root / "docs" / ".work" / "proposals").glob("*.md"))
    assert proposals and "Something else." in proposals[0].read_text(encoding="utf-8")


def test_nothing_written_through_the_mcp_confirms(kit, mcp):
    mcp.propose_edit("flows/draft.md", "---\nx-confirmed: {by: me}\n---\nPay.", section="steps")
    assert "x-confirmed" not in read(kit, "flows/draft.md")
    assert "confirm" not in mcp.HANDLERS                                                  # there is no such tool


def test_add_feedback(kit, mcp):
    assert "recorded" in mcp.add_feedback("flows/confirmed.md", "Retries are missing", by="agent")
    assert "Retries are missing" in (kit.root / "docs" / ".work" / "review-feedback.md").read_text(encoding="utf-8")


def test_mark_suspect_withholds_the_page_until_refreshed_or_acked(kit, mcp):
    from lib.harness import freshness
    f = kit.root / "docs" / "flows" / "src.md"
    f.write_text("---\ntitle: Src\nx-sources:\n  - api:README.md\n---\n# Src\n\nREST backend.\n", encoding="utf-8")
    freshness.stamp_all()
    assert "marked" in mcp.mark_suspect("flows/src.md", "the code now uses gRPC")
    s = freshness.status("flows/src.md")
    assert s["state"] == "suspect" and "the code now uses gRPC" in s["changed"][0]
    assert "withheld" in mcp.read_doc("flows/src.md")
    freshness.ack(["flows/src.md"], by="ana")
    assert freshness.status("flows/src.md")["state"] == "fresh"


def test_pipeline_status_and_kpis(kit, mcp):
    text = mcp.pipeline_status()
    assert "setup" in text and "todo" in text
    assert isinstance(mcp.kpis(), str)


def test_running_units_needs_an_opt_in(kit, mcp, monkeypatch):
    started = []
    monkeypatch.setattr(mcp, "_spawn_run", lambda uid: started.append(uid) or "r-1")
    assert "disabled" in mcp.run_node("discovery:api") and started == []
    ws = kit.docs.workspace()
    ws["mcp"] = {"pipeline_control": True}
    kit.docs.save_workspace(ws)
    assert "r-1" in mcp.run_node("discovery:api") and started == ["discovery:api"]
    assert "unknown unit" in mcp.run_node("nope")


def test_write_tools_are_listed(mcp):
    names = {t["name"] for t in mcp.TOOLS}
    assert {"propose_edit", "add_feedback", "mark_suspect", "pipeline_status", "run_node", "run_events", "kpis"} <= names


# ---------- HTTP on 127.0.0.1 ----------
@pytest.fixture
def http(kit, mcp):
    srv = mcp.http_server(port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/mcp", mcp.token()
    srv.shutdown()


def call(url, body, token=None, origin=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}


def test_http_needs_the_token(http):
    url, token = http
    assert call(url, INIT)[0] == 401
    assert call(url, INIT, token="wrong")[0] == 401
    status, body = call(url, INIT, token=token)
    assert status == 200 and body["result"]["serverInfo"]["name"] == "camarones"


def test_http_rejects_other_origins(http):
    url, token = http
    assert call(url, INIT, token=token, origin="https://evil.example")[0] == 403
    assert call(url, INIT, token=token, origin="http://localhost:3000")[0] == 200


def test_a_refused_request_is_read_before_the_answer(mcp):
    """Answering before the body is read resets the connection on Windows: the client never sees the 403."""
    import io
    h = mcp.HttpHandler.__new__(mcp.HttpHandler)
    body = json.dumps(INIT).encode()
    h.rfile, h.wfile = io.BytesIO(body), io.BytesIO()
    h.path, h.command, h.request_version, h.requestline = "/mcp", "POST", "HTTP/1.1", "POST /mcp HTTP/1.1"
    h.headers = {"Origin": "https://evil.example", "Content-Length": str(len(body))}
    h.do_POST()
    assert h.rfile.tell() == len(body) and b" 403 " in h.wfile.getvalue().split(b"\r\n")[0] + b" "


def test_http_tool_call(http):
    url, token = http
    status, body = call(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                              "params": {"name": "read_doc", "arguments": {"path": "flows/confirmed.md"}}}, token=token)
    assert status == 200 and "Pay once" in body["result"]["content"][0]["text"]


def test_the_token_is_per_machine_and_stable(kit, mcp):
    t = mcp.token()
    assert len(t) >= 32 and mcp.token() == t and mcp.TOKEN_FILE.parent.name == ".camarones"


def test_run_only_limits_the_scheduler_to_those_units(wired, tmp_path, monkeypatch):
    import sys
    from test_scheduler import FAKE
    script = tmp_path / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    monkeypatch.setenv("KIT_DIR", str(wired.kit_dir))
    monkeypatch.setenv("FAKE_SLEEP", "0.1")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"]}})
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    from lib.harness import scheduler
    scheduler.run_parallel(echo=lambda _: None, poll=0.05, only={"discovery:web"})
    done = {u["id"] for u in wired.plan.load()["units"] if u["status"] == "done"}
    assert "discovery:web" in done and "discovery:api" not in done
