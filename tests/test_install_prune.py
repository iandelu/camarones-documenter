"""`upgrade` drops the kit files a release no longer ships: listed in the old receipt, absent from the new payload and
untouched since the kit wrote them. Edited or team-made files stay."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from conftest import REPO

QUIET = {"log": lambda _: None}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def old_layout(kit, tmp_path, extra: dict[str, bytes], receipt: Path | None = None):
    """A project installed by an older kit: today's files plus `extra`, which that kit shipped and listed."""
    dest = tmp_path / "proj"
    kit.install.install(REPO, dest, **QUIET)
    for rel, data in extra.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_bytes(data)
    path = receipt or dest / ".camarones" / "install.json"
    doc = json.loads((dest / ".camarones" / "install.json").read_text(encoding="utf-8"))
    doc["version"] = "4.48.0"
    doc["files"].update({rel: sha(data) for rel, data in extra.items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return dest


GONE = {".camarones/lib/boards.py": b"# whiteboards\n",
        ".camarones/portal/app-build/excalidraw/fonts/Virgil.woff2": b"font",
        ".camarones/portal/app-build/assets/index-0ld.js": b"old chunk"}


def test_update_removes_files_the_new_kit_no_longer_ships(kit, tmp_path):
    dest = old_layout(kit, tmp_path, GONE)
    res = kit.install.install(REPO, dest, update=True, **QUIET)
    assert sorted(res["removed"]) == sorted(GONE)
    for rel in GONE:
        assert not (dest / rel).exists()
    assert not (dest / ".camarones/portal/app-build/excalidraw").exists()     # emptied folders go too
    assert (dest / ".camarones/portal/app-build").is_dir()
    receipt = json.loads((dest / ".camarones" / "install.json").read_text(encoding="utf-8"))
    assert not set(GONE) & set(receipt["files"])


def test_update_keeps_an_edited_kit_file_and_team_files(kit, tmp_path):
    dest = old_layout(kit, tmp_path, {".camarones/lib/boards.py": b"# whiteboards\n"})
    (dest / ".camarones/lib/boards.py").write_bytes(b"# our tweak\n")
    mine = dest / ".camarones/templates/ours.md"
    mine.write_text("team page\n", encoding="utf-8")
    res = kit.install.install(REPO, dest, update=True, **QUIET)
    assert res["removed"] == []
    assert res["kept"] == [".camarones/lib/boards.py"]
    assert (dest / ".camarones/lib/boards.py").read_bytes() == b"# our tweak\n"
    assert mine.read_text(encoding="utf-8") == "team page\n"
    assert (dest / ".camarones/workspace.yaml").is_file()


def test_update_prune_is_idempotent(kit, tmp_path):
    dest = old_layout(kit, tmp_path, GONE)
    kit.install.install(REPO, dest, update=True, **QUIET)
    again = kit.install.install(REPO, dest, update=True, **QUIET)
    assert again["removed"] == [] and again["changed"] == []


def test_dry_run_reports_removals_without_deleting(kit, tmp_path):
    dest = old_layout(kit, tmp_path, GONE)
    lines = []
    res = kit.install.install(REPO, dest, update=True, dry_run=True, log=lines.append)
    assert sorted(res["removed"]) == sorted(GONE)
    assert all((dest / rel).is_file() for rel in GONE)
    assert any("boards.py" in line and "-" in line for line in lines)


def test_update_removes_a_read_only_stale_file(kit, tmp_path):
    dest = old_layout(kit, tmp_path, {".camarones/lib/boards.py": b"# whiteboards\n"})
    target = dest / ".camarones/lib/boards.py"
    os.chmod(target, stat.S_IREAD)
    try:
        kit.install.install(REPO, dest, update=True, **QUIET)
    finally:
        if target.exists():
            os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
    assert not target.exists()


def test_a_receipt_backed_up_by_an_older_upgrade_still_counts(kit, tmp_path):
    """Upgrades run by a pre-pruning kit rewrote install.json without the dropped files; its backup still lists them."""
    dest = tmp_path / "proj"
    backup = dest / ".camarones/.cache/install-backups/0123abcd/.camarones/install.json"
    dest = old_layout(kit, tmp_path, GONE, receipt=backup)
    res = kit.install.install(REPO, dest, update=True, **QUIET)
    assert sorted(res["removed"]) == sorted(GONE)


def test_prune_never_leaves_the_kit_folders(kit, tmp_path):
    dest = tmp_path / "proj"
    kit.install.install(REPO, dest, **QUIET)
    outside = {".camarones/workspace.yaml": (dest / ".camarones/workspace.yaml").read_bytes(),
               "../outside.txt": b"not ours", "docs/page.md": b"a page"}
    (tmp_path / "outside.txt").write_bytes(b"not ours")
    (dest / "docs").mkdir()
    (dest / "docs/page.md").write_bytes(b"a page")
    doc = json.loads((dest / ".camarones" / "install.json").read_text(encoding="utf-8"))
    doc["files"].update({rel: sha(data) for rel, data in outside.items()})
    (dest / ".camarones" / "install.json").write_text(json.dumps(doc), encoding="utf-8")
    res = kit.install.install(REPO, dest, update=True, **QUIET)
    assert res["removed"] == []
    assert (tmp_path / "outside.txt").is_file() and (dest / "docs/page.md").is_file()
    assert (dest / ".camarones/workspace.yaml").is_file()


def test_a_failed_removal_puts_everything_back(kit, tmp_path, monkeypatch):
    dest = old_layout(kit, tmp_path, GONE)
    real, calls = kit.install.remove, []

    def flaky(target, top):
        calls.append(target)
        if len(calls) == 2:
            raise OSError("locked")
        real(target, top)

    monkeypatch.setattr(kit.install, "remove", flaky)
    try:
        kit.install.install(REPO, dest, update=True, **QUIET)
    except OSError:
        pass
    else:
        raise AssertionError("the failed removal should surface")
    assert all((dest / rel).read_bytes() == data for rel, data in GONE.items())
