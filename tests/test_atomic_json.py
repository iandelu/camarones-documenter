"""save_json replaces the file in one step, so a reader polling it (`review wait`, the portal) sees the old content or
the new one, never an empty or half-written file; load_json rides out the moment Windows refuses to open it."""
from __future__ import annotations

import json, os
from pathlib import Path


def test_the_old_file_stays_whole_until_the_new_one_replaces_it(kit, monkeypatch):
    c, f = kit.common, kit.root / "state.json"
    c.save_json(f, {"n": 1})
    seen, real = [], os.replace

    def spy(src, dst):
        seen.append(json.loads(Path(dst).read_text(encoding="utf-8")))
        real(src, dst)
    monkeypatch.setattr(c.os, "replace", spy)
    c.save_json(f, {"n": 2})
    assert seen == [{"n": 1}] and c.load_json(f, None) == {"n": 2}
    assert [p.name for p in f.parent.iterdir() if "state" in p.name] == ["state.json"]


def test_a_failed_write_leaves_the_old_file_and_no_temp(kit, monkeypatch):
    c, f = kit.common, kit.root / "state.json"
    c.save_json(f, {"n": 1})

    def boom(*_a):
        raise OSError("disk full")
    monkeypatch.setattr(c.os, "replace", boom)
    try:
        c.save_json(f, {"n": 2})
    except OSError:
        pass
    assert c.load_json(f, None) == {"n": 1}
    assert [p.name for p in f.parent.iterdir() if "state" in p.name] == ["state.json"]


def test_a_replace_refused_for_a_moment_is_retried(kit, monkeypatch):
    c, f = kit.common, kit.root / "state.json"
    calls, real = [], os.replace

    def busy_once(src, dst):                    # Windows: a reader has the file open
        calls.append(dst)
        if len(calls) == 1:
            raise PermissionError("in use")
        real(src, dst)
    monkeypatch.setattr(c.os, "replace", busy_once)
    monkeypatch.setattr(c.time, "sleep", lambda _s: None)
    c.save_json(f, {"n": 3})
    assert len(calls) == 2 and c.load_json(f, None) == {"n": 3}


def test_a_read_refused_for_a_moment_is_retried(kit, monkeypatch):
    c, f = kit.common, kit.root / "state.json"
    c.save_json(f, {"n": 4})
    real, calls = Path.read_text, []

    def busy_once(self, *a, **kw):              # Windows: the file is being replaced right now
        calls.append(self)
        if len(calls) == 1:
            raise PermissionError("in use")
        return real(self, *a, **kw)
    monkeypatch.setattr(Path, "read_text", busy_once)
    monkeypatch.setattr(c.time, "sleep", lambda _s: None)
    assert c.load_json(f, None) == {"n": 4} and len(calls) == 2


def test_a_symlinked_file_is_written_through(kit, tmp_path):
    c = kit.common
    target, link = tmp_path / "real.json", kit.root / "link.json"
    c.save_json(target, {"n": 1})
    try:
        link.symlink_to(target)
    except OSError:                             # Windows without developer mode: no symlinks to test
        return
    c.save_json(link, {"n": 2})
    assert link.is_symlink() and c.load_json(target, None) == {"n": 2}
