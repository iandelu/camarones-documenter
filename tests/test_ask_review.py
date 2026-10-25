"""R34: "ask the docs" in the portal, and anchored, live review: comments point at a section (found again after a
heading rename), and an agent can wait for a person's decision on a page."""
from __future__ import annotations

import json, threading, time, urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def portal(kit):
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
