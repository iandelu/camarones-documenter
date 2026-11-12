"""lib/core: the leaf modules every layer builds on; the old paths keep handing out the very same objects."""
from __future__ import annotations

from conftest import KIT_DIR


def test_kit_is_still_the_kit_folder(kit):
    from lib.core import ctx
    assert ctx.KIT.resolve() == KIT_DIR.resolve()


def test_old_lock_paths_give_the_same_objects(kit):
    from lib.core import locks as new
    from lib.harness import locks as old
    assert (old.FileLock, old.LockBusy, old.pid_alive) == (new.FileLock, new.LockBusy, new.pid_alive)
    assert old.LockBusy is new.LockBusy


def test_old_ctx_path_gives_the_same_objects(kit):
    from lib.core import ctx as new
    from lib.harness import ctx as old
    for name in ("KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root"):
        assert getattr(old, name) is getattr(new, name)


def test_common_still_offers_the_file_helpers(kit):
    from lib.core import fsutil
    for name in ("retry_busy", "load_json", "save_json", "rmtree"):
        assert getattr(kit.common, name) is getattr(fsutil, name)
