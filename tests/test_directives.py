"""R29: `:::` directives render in the portal (src/content/directives.js) and are flattened to plain Markdown for agents
(MCP, llms-full.txt, exports), so what an agent reads never carries portal syntax."""
from __future__ import annotations

import importlib
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden" / "directives"


def test_flattening_matches_the_golden_file(kit):
    src = (GOLDEN / "page.md").read_text(encoding="utf-8")
    assert kit.docs.flatten_directives(src) == (GOLDEN / "page.flat.md").read_text(encoding="utf-8")


def test_flattening_is_idempotent_and_leaves_plain_pages_alone(kit):
    flat = (GOLDEN / "page.flat.md").read_text(encoding="utf-8")
    assert kit.docs.flatten_directives(flat) == flat


def test_agents_read_flattened_pages(kit):
    f = kit.root / "docs" / "guides" / "build.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: Build\n---\n# Build\n\n## Commands\n:::tabs\n::tab Maven\n`./mvnw test`\n:::\n", encoding="utf-8")
    kit.docs.confirm([str(f)], by="ana")
    mcp = importlib.import_module("lib.mcp")
    for text in (mcp.read_doc("guides/build.md"), mcp.read_doc("guides/build.md", section="commands")):
        assert "**Maven**" in text and ":::" not in text and "::tab" not in text
    kit.docs.llms()
    full = (kit.root / "docs" / "llms-full.txt").read_text(encoding="utf-8")
    assert "**Maven**" in full and "::tab" not in full
