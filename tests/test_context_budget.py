"""X5: `doctor --context` counts what every agent session loads before reading a page (AGENTS.md, skill descriptions,
MCP tool schemas); the kit's own wiring stays under the budget, and llms.txt tells an agent what each page costs."""
from __future__ import annotations

import json, os, subprocess, sys

from conftest import KIT_DIR

KIT_SHARE = 2500


def _doctor(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "doctor", "--context", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def test_tokens_are_estimated_without_a_tokenizer():
    sys.path.insert(0, str(KIT_DIR))
    from lib import budget
    assert budget.tokens("abcd" * 100) == 100 and budget.tokens("") == 0


def test_the_kit_wiring_stays_under_its_budget(wired):
    from lib import budget
    r = budget.standing()
    kinds = {i["kind"] for i in r["items"]}
    assert {"rules", "skill", "mcp"} <= kinds
    assert any(i["path"] == "AGENTS.md" for i in r["items"])
    assert any(i["path"] == "camarones/read_doc" for i in r["items"])
    assert r["total"] <= KIT_SHARE, budget.report(r)          # ~2k in 4.18: the kit leaves most of it to the project
    assert r["on_use"] > 0                                                  # skill bodies are counted apart


def test_doctor_context_json_and_over_budget(wired):
    ws = wired.docs.workspace(); ws["context"] = {"budget": 10}; wired.docs.save_workspace(ws)
    r = _doctor(wired, "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["over"] is True and data["budget"] == 10 and data["total"] > 10
    text = _doctor(wired).stdout
    assert "OVER BUDGET" in text and "workspace.yaml" in text


def test_llms_txt_gives_a_token_estimate_per_page(kit):
    page = kit.root / "docs" / "flows" / "checkout.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("---\ntitle: Checkout\n---\n# Checkout\n\n" + "word " * 400, encoding="utf-8")
    kit.docs.confirm([str(page)], by="ana")
    kit.docs.llms()
    lines = [l for l in (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8").splitlines() if l.startswith("- [")]
    assert lines and all("tokens)" in l for l in lines)
    assert any("Checkout" in l and "(~50" in l for l in lines)                     # ~2000 chars of body
