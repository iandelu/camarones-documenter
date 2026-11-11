"""A laptop has some of the kit's tools and agent CLIs installed and CI has none, so a test that finds one on PATH runs
what CI never does: slower, and green or red depending on the machine. Every test that uses `isolated_env` runs without
them: each PATH folder holding one is swapped for a folder of links to everything else in it, and CAMARONES_KEEP_PATH
stops the kit from putting its usual tool folders back. A test of a real tool asks for it with `needs("likec4")`; e2e
and eval tests, and a run with CAMARONES_TEST_HOST_TOOLS=1, keep the machine's PATH as it is."""
from __future__ import annotations

import atexit, os, shutil, tempfile
from pathlib import Path

import pytest

# what the kit pins or installs, the agent CLIs it drives and its own launchers: CI has none of them
HIDDEN = frozenset({"backlog", "camaron", "camarones", "claude", "codex", "gemini", "gitleaks", "graphify", "likec4",
                    "mmdc", "ollama", "opencode", "openwiki", "osv-scanner"})
# the kit looks these up too, but CI has them or the tests that care stub them
KEPT = frozenset({"brew", "caffeinate", "docker", "git", "java", "systemd-inhibit", "uv", "winget", "wl-copy"})

_masked: dict[tuple[str, frozenset[str]], str] = {}


def hidden_tools(node=None) -> frozenset[str]:
    """The tools a test (`node`, a pytest item) runs without; without a node, what a test asks for nothing gets."""
    if os.environ.get("CAMARONES_TEST_HOST_TOOLS"):
        return frozenset()
    if node is None:
        return HIDDEN
    if node.get_closest_marker("e2e") or node.get_closest_marker("eval"):
        return frozenset()
    asked = node.get_closest_marker("host_tools")
    return HIDDEN - set(asked.args if asked else ())


def masked_path(path: str, hidden: frozenset[str]) -> str:
    """`path` without the `hidden` tools, built once per process for each PATH and set of tools."""
    key = (path, hidden)
    if key not in _masked:
        base = Path(tempfile.mkdtemp(prefix="camaron-path-"))
        atexit.register(shutil.rmtree, base, True)
        dirs = (_without(Path(d), base / str(i), hidden) for i, d in enumerate(path.split(os.pathsep)) if d)
        _masked[key] = os.pathsep.join(d for d in dirs if d)
    return _masked[key]


def _without(folder: Path, shadow: Path, hidden: frozenset[str]) -> str | None:
    """`folder` when none of `hidden` is in it, None when nothing else is, else a folder of links to the rest; `folder`
    as it is where this machine cannot make links (Windows without the right to)."""
    try:
        with os.scandir(folder) as entries:
            names = [e.name for e in entries if not e.is_dir()]
    except OSError:
        return str(folder)
    rest = [n for n in names if n.split(".")[0].lower() not in hidden]
    if len(rest) == len(names):
        return str(folder)
    if not rest:
        return None
    shadow.mkdir()
    try:
        for n in rest:
            (shadow / n).symlink_to(folder / n)
    except OSError:
        return str(folder)
    return str(shadow)


def needs(tool: str):
    """A test of the real `tool`: it runs with the machine's own, and is skipped where there is none (CI)."""
    def mark(fn):
        fn = pytest.mark.skipif(not shutil.which(tool), reason=f"{tool} not installed")(fn)
        return pytest.mark.host_tools(tool)(fn)
    return mark
