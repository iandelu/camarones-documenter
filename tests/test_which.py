"""`which` never picks a program from the current folder on Windows (shutil.which does, before PATH): a launcher left
in the folder a command runs from changed how the kit rendered its skills (CI on Windows), and could impersonate a tool."""
from __future__ import annotations


def setup(kit, tmp_path, monkeypatch, in_path: bool):
    here, bin_dir = tmp_path / "here", tmp_path / "bin"
    here.mkdir()
    bin_dir.mkdir()
    (here / "camaron.cmd").write_text("@echo planted\n", encoding="utf-8")
    if in_path:
        (bin_dir / "camaron.cmd").write_text("@echo real\n", encoding="utf-8")
    monkeypatch.setattr(kit.common, "IS_WIN", True)
    monkeypatch.setenv("PATHEXT", ".com;.exe;.bat;.cmd")        # Windows matches any case; Linux CI does not
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.chdir(here)
    return bin_dir


def test_the_current_folder_is_not_searched(kit, tmp_path, monkeypatch):
    setup(kit, tmp_path, monkeypatch, in_path=False)
    assert kit.common.which("camaron") is None


def test_path_wins_and_extensions_follow_pathext(kit, tmp_path, monkeypatch):
    bin_dir = setup(kit, tmp_path, monkeypatch, in_path=True)
    assert kit.common.which("camaron") == str(bin_dir / "camaron.cmd")
    assert kit.common.which("camaron.cmd") == str(bin_dir / "camaron.cmd")
    assert kit.common.which("nope") is None
