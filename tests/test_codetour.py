"""X10: `camaron export codetour flows/x.md` turns a flow's Steps table into a VS Code CodeTour (.tours/<flow>.tour in
cam-docs, linked at the workspace root like .claude): one step per row, opened at the evidence's line or symbol."""
from __future__ import annotations

import json, os, subprocess, sys

from conftest import KIT_DIR

FLOW = """---
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
---
# Checkout

> **TL;DR:** The cart calls the API; a failed payment leaves the order pending.

## Steps

| # | Step | Repo | Entrypoint | Evidence |
|---|---|---|---|---|
| 1 | Pick the items | `web` | `CartPage` | `web:src/cart.tsx` |
| 2 | Place the order | `api` | `POST /orders` | `api:src/OrderController.java#L3-L5` |
| 3 | Charge the card | `api` | `PaymentService.charge` | `src/PaymentService.java#PaymentService.charge` |
| 4 | Send the invoice | `worker` | `InvoiceJob` | `worker:src/Gone.java` |
"""


def setup_flow(kit):
    for repo, rel, text in (("web", "src/cart.tsx", "export function CartPage() {}\n"),
                            ("api", "src/OrderController.java", "class OrderController {\n\n  @PostMapping\n  void place() {}\n}\n"),
                            ("api", "src/PaymentService.java", "class PaymentService {\n  void refund() {}\n  void charge() {\n  }\n}\n")):
        f = kit.ws / repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    page = kit.root / "docs" / "flows" / "checkout.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(FLOW, encoding="utf-8")


def test_a_flow_becomes_a_codetour(kit):
    setup_flow(kit)
    from lib import exporters
    out = exporters.export_codetour("flows/checkout.md")
    assert out == kit.root / ".tours" / "checkout.tour"
    tour = json.loads(out.read_text(encoding="utf-8"))
    assert tour["title"] == "Checkout" and tour["$schema"] == "https://aka.ms/codetour-schema"
    intro, *steps = tour["steps"]
    assert "file" not in intro and "failed payment" in intro["description"]
    assert [(s.get("file"), s.get("line")) for s in steps] == [
        ("web/src/cart.tsx", 1), ("api/src/OrderController.java", 3), ("api/src/PaymentService.java", 3), (None, None)]
    assert steps[1]["title"] == "2. Place the order" and "`POST /orders`" in steps[1]["description"]
    assert "worker:src/Gone.java" in steps[3]["description"]                     # missing evidence: said, not dropped
    link = kit.ws / ".tours"
    assert link.is_symlink() or link.is_dir()
    assert os.path.realpath(link) == os.path.realpath(kit.root / ".tours")


def test_cli_and_errors(kit):
    setup_flow(kit)
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "export", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    r = cli("codetour", "flows/checkout.md")
    assert r.returncode == 0 and "checkout.tour" in r.stdout, r.stderr
    assert cli("codetour").returncode == 2
    assert cli("codetour", "flows/nope.md").returncode == 2
