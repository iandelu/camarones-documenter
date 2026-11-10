"""The managed `.gitignore` block (docs.write_gitignore): kit checkouts and zips at the project root are ignored,
but a doc folder named after a repo that starts like the kit (`docs/repos/camarones-documenter/`) is not."""
from __future__ import annotations

import subprocess

# What kits up to 4.79.2 wrote: unanchored kit patterns that also matched nested doc folders.
OLD_BLOCK = """# >>> camarones repos >>>
/.camarones/.cache/
/graph/
/.claude/settings.local.json
camarones-documenter*/
camarones-kit*/
camarones-documenter*.zip
.DS_Store
# <<< camarones repos <<<
"""


def ignored(root, rel: str) -> bool:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x\n", encoding="utf-8")
    return subprocess.run(["git", "check-ignore", "-q", rel], cwd=root).returncode == 0


def test_an_old_block_is_replaced_by_anchored_kit_patterns(kit):
    root = kit.root
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("my-own/\n\n" + OLD_BLOCK + "\n!keep-me/\n", encoding="utf-8")
    assert ignored(root, "docs/repos/camarones-documenter/brief.md")         # the bug, before the fix

    kit.docs.write_gitignore()

    text = (root / ".gitignore").read_text(encoding="utf-8")
    assert text.count("# >>> camarones repos >>>") == 1 and text.count("# <<< camarones repos <<<") == 1
    assert text.startswith("my-own/\n") and "!keep-me/" in text              # the person's own lines stay
    assert "/camarones-documenter*/" in text and "/camarones-kit*/" in text
    # doc folders of a repo named like the kit are documentation: tracked
    for rel in ("docs/repos/camarones-documenter/brief.md", "wikis/camarones-documenter/index.md",
                "docs/i18n/es/repos/camarones-documenter/brief.md", "docs/repos/camarones-kit-x/brief.md"):
        assert not ignored(root, rel), rel
    # everything the block meant to ignore still is
    for rel in ("camarones-documenter/.camarones/lib/common.py", "camarones-documenter-4.79.2/README.md",
                "camarones-kit/README.md", "camarones-documenter-upgrade/x.py", "camarones-documenter-4.79.2.zip",
                ".camarones/.cache/graph/graph.json", "graph/api/graph.json", ".claude/settings.local.json",
                "docs/.DS_Store", "my-own/a.txt"):
        assert ignored(root, rel), rel


def test_rewriting_the_block_is_idempotent(kit):
    kit.docs.write_gitignore()
    first = (kit.root / ".gitignore").read_text(encoding="utf-8")
    kit.docs.write_gitignore()
    assert (kit.root / ".gitignore").read_text(encoding="utf-8") == first
