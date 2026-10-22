"""`doctor --local` (H26): propose a free, open-weight model for bounded and judge work from this machine's memory.
It only detects and suggests; it never installs Ollama, OpenCode or models, nor writes their config."""
from __future__ import annotations

import pytest


@pytest.fixture
def local(kit):
    from lib.adapters.runners import local
    return local


def test_the_proposal_follows_memory(local):
    assert local.propose(64)["tag"] == "qwen3-coder:30b"
    assert local.propose(32)["tag"] == "qwen3-coder:30b"
    assert local.propose(16)["tag"].startswith("qwen3")
    assert local.propose(8) is None


def test_every_proposed_model_is_free_and_open_weight(local):
    for m in local.models():
        assert {"min_gb", "provider", "tag", "name", "licence", "why"} <= set(m)
        assert m["provider"] == "ollama" and m["licence"] in ("Apache-2.0", "MIT")


def test_this_machine_reports_its_memory(local):
    gb = local.memory_gb()
    assert gb is None or gb > 0


def test_report_lists_what_is_missing_and_how_to_route_it(local, monkeypatch):
    monkeypatch.setattr(local, "which", lambda name: "/bin/ollama" if name == "ollama" else None)
    monkeypatch.setattr(local, "out", lambda cmd: "NAME  ID  SIZE\nqwen3:14b  x  9 GB\n")
    text = "\n".join(local.report(gb=32))
    assert "32 GB" in text and "qwen3-coder:30b" in text and "Apache-2.0" in text
    assert "opencode" in text and "not installed" in text
    assert "ollama pull qwen3-coder:30b" in text
    assert '"opencode:ollama/qwen3-coder:30b"' in text and "bounded" in text and "judge" in text


def test_a_pulled_model_needs_no_pull(local, monkeypatch):
    monkeypatch.setattr(local, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(local, "out", lambda cmd: "NAME  ID  SIZE\nqwen3-coder:30b  x  19 GB\n")
    assert "ollama pull" not in "\n".join(local.report(gb=48))


def test_small_machines_keep_the_cloud_runners(local):
    text = "\n".join(local.report(gb=8))
    assert "8 GB" in text and "pull" not in text and "claude" in text
