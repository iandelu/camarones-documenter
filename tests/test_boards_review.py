"""R34: whiteboards (Excalidraw files in cam-docs, free-form or sketched from a C4 view), "ask the docs" in the portal,
and anchored, live review: comments point at a section (found again after a heading rename), and an agent can wait
for a person's decision on a page."""
from __future__ import annotations

import json, threading, time, urllib.request
from http.server import ThreadingHTTPServer

import pytest

C4 = """specification {
  element system
  element service
}
model {
  customer = actor 'Customer'
  shop = system 'Shop' {
    orders = service 'Orders' {
      -> billing 'charges'
    }
    billing = service 'Billing'
  }
  customer -> shop.orders 'places orders'
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
def portal(kit):
    arch = kit.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text(C4, encoding="utf-8")
    page = kit.root / "docs" / "flows" / "checkout.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: Checkout\n---\n# Checkout\n\n> **TL;DR:** Pay.\n\n## Failure handling\n"
                    "Payments are retried once by the PaymentRetryJob.\n", encoding="utf-8")
    kit.docs.confirm([str(page)], by="ana")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Camarones": "1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ---------- boards ----------
def test_a_board_round_trips_through_the_api(kit, portal):
    scene = {"type": "excalidraw", "version": 2, "elements": [{"id": "a", "type": "rectangle", "x": 1, "y": 2}],
             "appState": {"viewBackgroundColor": "#fff", "collaborators": []}, "files": {}}
    assert post(f"{portal}/api/board", {"name": "ideas", "scene": scene})["elements"] == 1
    back = get(f"{portal}/api/board?name=ideas")
    assert back["elements"] == scene["elements"] and "collaborators" not in back["appState"]
    assert get(f"{portal}/api/boards")[0]["name"] == "ideas"
    assert (kit.root / "docs" / "boards" / "ideas.excalidraw").is_file()


def test_bad_boards_are_refused(kit, portal):
    import urllib.error
    with pytest.raises(urllib.error.HTTPError):
        post(f"{portal}/api/board", {"name": "../x", "scene": {"type": "excalidraw", "elements": []}})
    with pytest.raises(urllib.error.HTTPError):
        post(f"{portal}/api/board", {"name": "ok", "scene": {"elements": "nope"}})


def test_a_c4_view_becomes_a_sketch(kit, portal):
    s = get(f"{portal}/api/sketch?view=shop_containers")
    boxes = {e["id"] for e in s["elements"] if e["type"] == "rectangle"}
    assert boxes == {"el-shop.orders", "el-shop.billing"}
    arrows = [e for e in s["elements"] if e["type"] == "arrow"]
    labels = {e["containerId"]: e["text"] for e in s["elements"] if e["type"] == "text"}
    assert len(arrows) == 1 and labels[arrows[0]["id"]] == "charges"
    assert arrows[0]["startBinding"]["elementId"] == "el-shop.orders"
    top = get(f"{portal}/api/sketch?view=index")
    assert {e["id"] for e in top["elements"] if e["type"] == "rectangle"} == {"el-customer", "el-shop"}
    assert "places orders" in {e["text"] for e in top["elements"] if e["type"] == "text"}


# ---------- ask the docs ----------
def test_ask_answers_with_cited_sections(kit, portal):
    r = get(f"{portal}/api/ask?q=how+are+payments+retried")
    assert r["sections"][0]["cite"] == "flows/checkout.md#failure-handling"
    assert "PaymentRetryJob" in r["sections"][0]["text"] and r["sections"][0]["trust"] == "confirmed"


# ---------- anchored review ----------
def test_an_anchor_is_found_again_after_a_heading_rename(kit, portal):
    from lib import review
    page = kit.root / "docs" / "flows" / "checkout.md"
    page.write_text(page.read_text(encoding="utf-8").replace("## Failure handling", "## When a payment fails"),
                    encoding="utf-8")
    assert review.resolve_anchor("flows/checkout.md", "failure-handling", "retried once by the PaymentRetryJob") == \
        "when-a-payment-fails"
    assert review.resolve_anchor("flows/checkout.md", "gone", "nowhere") is None


def test_an_anchored_comment_lands_in_review_feedback(kit, portal):
    post(f"{portal}/api/feedback", {"path": "flows/checkout.md", "text": "Retries are twice now", "by": "ana",
                                    "slug": "failure-handling", "snippet": "retried once"})
    fb = (kit.root / "docs" / ".work" / "review-feedback.md").read_text(encoding="utf-8")
    assert "§ failure-handling" in fb and '"retried once"' in fb


def test_an_agent_waits_for_a_persons_decision(kit, portal):
    from lib import review
    rid = review.request("flows/checkout.md", by="claude", note="new retry section")
    assert [r["id"] for r in get(f"{portal}/api/reviews")] == [rid]
    got = {}
    t = threading.Thread(target=lambda: got.update(review.wait(rid, timeout=10, poll=0.05)))
    t.start()
    time.sleep(0.2)
    post(f"{portal}/api/review/decide", {"id": rid, "decision": "changes", "comments": "Name the job", "by": "ana"})
    t.join(10)
    assert got["decision"] == "changes" and got["comments"] == "Name the job" and got["decided_by"] == "ana"
    assert get(f"{portal}/api/reviews") == []


def test_wait_times_out_with_no_decision(kit):
    from lib import review
    rid = review.request("flows/checkout.md")
    assert review.wait(rid, timeout=0.1, poll=0.02)["decision"] is None


def test_the_review_commands(kit):
    import os, subprocess, sys
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "review", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    rid = json.loads(cli("request", "flows/checkout.md", "--note", "please").stdout)["id"]
    from lib import review
    review.decide(rid, "approve", "ana")
    assert json.loads(cli("wait", rid, "--timeout", "1").stdout)["decision"] == "approve"
