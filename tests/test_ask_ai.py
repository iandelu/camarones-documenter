"""Ask with an optional AI answer: the sections Ask found (only those agents may read) go to the runner configured for
bounded work (a local model is fine), which answers from them alone with citations. Off with `ask: {ai: false}`."""
from __future__ import annotations

import json, sys

import pytest

from test_mcp_resources import FLOW, write
from test_portal_actions import post, server  # noqa: F401 — the portal server fixture

ANSWERER = r'''
import json, os, sys
open(os.environ["ASK_LOG"], "w", encoding="utf-8").write(sys.argv[1])
print("thinking…")
if os.environ.get("ASK_PLAIN"):
    print("Retried once by PaymentRetryJob [flows/checkout.md#failure-handling] [made/up.md].")
    sys.exit(0)
print(json.dumps({"answer": "It is retried once by PaymentRetryJob.",
                  "cited": ["flows/checkout.md#failure-handling", "made/up.md"]}))
'''


@pytest.fixture
def answerer(kit, tmp_path, monkeypatch):
    script = tmp_path / "answerer.py"
    script.write_text(ANSWERER, encoding="utf-8")
    log = tmp_path / "prompt.txt"
    monkeypatch.setenv("ASK_LOG", str(log))
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "{prompt}"]}},
                      "routing": {"bounded": ["fake"]}})
    write(kit, "flows/checkout.md", FLOW)
    write(kit, "flows/draft.md", "---\ntitle: Draft\n---\n# Draft\n\nGuessing the retry policy for payments.\n",
          confirm=False)
    return log


def test_an_answer_from_the_sections_with_real_citations(kit, answerer):
    from lib import answers
    r = answers.answer("how are failed payments retried?")
    assert r["answer"] == "It is retried once by PaymentRetryJob." and r["runner"] == "fake"
    assert r["cited"] == ["flows/checkout.md#failure-handling"]                      # made-up citations are dropped
    prompt = answerer.read_text(encoding="utf-8")
    assert "\n" not in prompt and "PaymentRetryJob" in prompt and "[flows/checkout.md" in prompt
    assert "Guessing the retry policy" not in prompt                                # withheld from agents, not sent


def test_nothing_found_means_no_model_call(kit, answerer):
    from lib import answers
    r = answers.answer("zzqx")
    assert r["answer"] is None and not answerer.exists()


def test_it_can_be_turned_off(kit, answerer):
    from lib import answers
    ws = kit.docs.workspace(); ws["ask"] = {"ai": False}; kit.docs.save_workspace(ws)
    assert answers.runner() is None
    with pytest.raises(RuntimeError):
        answers.answer("how are failed payments retried?")


def test_portal_endpoint(kit, answerer, server):  # noqa: F811
    from lib import serve
    assert serve.api_ask("payments retried")["ai"] == "fake"
    assert serve.api_ask("guessing policy")["ai"] is None                          # only a withheld draft matches
    code, r = post(f"{server}/api/ask/answer", {"q": "how are failed payments retried?"})
    assert code == 200 and r["cited"] == ["flows/checkout.md#failure-handling"]
    assert post(f"{server}/api/ask/answer", {"q": "x"}, header=False)[0] == 403


def test_a_plain_text_answer_still_counts(kit, answerer, monkeypatch):
    from lib import answers
    monkeypatch.setenv("ASK_PLAIN", "1")
    r = answers.answer("how are failed payments retried?")
    assert "Retried once" in r["answer"] and r["cited"] == ["flows/checkout.md#failure-handling"]
