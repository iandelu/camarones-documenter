"""lib/core: the leaf modules every layer builds on; the old paths keep handing out the very same objects."""
from __future__ import annotations

import importlib
import os
import re

from conftest import KIT_DIR, purge_kit_modules

COMMON_NAMES = [
    "IS_WIN", "IS_MAC", "HOME", "PREFS", "CTX", "ROOT", "CAM_LAYOUT", "WORKSPACE", "DOCS", "WORK", "WS_FILE", "CACHE",
    "GRAPHS", "KIT", "CAM_DIR", "Ctx", "docs_root", "find_project_marker", "find_root", "repo_dir", "ws_rel",
    "rel_file", "cli_cmd", "sdkman_dir", "extra_bin_dirs", "ensure_path", "which", "run", "out", "PARENT_SESSION",
    "leave_parent_session", "kill_tree", "uv", "retry_busy", "load_json", "save_json", "py", "rmtree", "VERSIONS",
]


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


def test_common_re_exports_every_name_it_had(kit):
    from lib.core import paths, process
    assert [n for n in COMMON_NAMES if not hasattr(kit.common, n)] == []
    assert kit.common.run is process.run and kit.common.ROOT == paths.ROOT
    assert kit.common.__facade__ == "lib.core"


def test_the_kit_version_is_still_written_in_common_py(kit):
    from lib import upgrade
    text = (KIT_DIR / "lib" / "common.py").read_text(encoding="utf-8")
    assert upgrade._version_in(text) == kit.common.VERSIONS["kit"]
    assert re.search(r'"kit":\s*"([\d.]+)"', text).group(1) == kit.common.VERSIONS["kit"]


def test_importing_common_alone_extends_path(isolated_env, monkeypatch):
    extra = isolated_env / ".local" / "bin"
    extra.mkdir(parents=True)
    monkeypatch.delenv("CAMARONES_KEEP_PATH", raising=False)
    monkeypatch.setenv("PATH", "base")
    purge_kit_modules()
    try:
        importlib.import_module("lib.common")
        assert str(extra) in os.environ["PATH"].split(os.pathsep)
    finally:
        purge_kit_modules()
