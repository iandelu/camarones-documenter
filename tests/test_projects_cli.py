"""`camaron projects --inspect/--adopt` and `join --no-open`: the CLI the desktop app's start screen calls. Everything
it needs comes through the argument folder, so the CLI runs with CAMARONES_ROOT unset, like the app starts it."""
from __future__ import annotations

import json, os, runpy, subprocess, sys
from pathlib import Path

import pytest

from fixtures.builder import make_workspace


def cli(kit, *args, **env):
    e = {k: v for k, v in os.environ.items() if k != "CAMARONES_ROOT"} | env
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)


def test_inspect_json(kit, tmp_path):
    ws = make_workspace(tmp_path / "other", name="umb")
    (ws / "cam-docs").rename(ws.parent / "gone")                  # repos only, no project: an umbrella
    r = cli(kit, "projects", "--inspect", str(ws), "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["case"] == "umbrella"


def test_inspect_without_json_prints_a_line_per_field(kit):
    r = cli(kit, "projects", "--inspect", str(kit.ws))
    assert r.returncode == 0, r.stderr
    assert any(line.startswith("case") and "project" in line for line in r.stdout.splitlines())


def test_inspect_a_missing_folder_is_one_line_on_stderr(kit, tmp_path):
    r = cli(kit, "projects", "--inspect", str(tmp_path / "nope"), "--json")
    assert r.returncode == 1 and "Traceback" not in r.stderr and r.stdout == ""


def test_adopt_json_then_list(kit, tmp_path):
    ws = make_workspace(tmp_path / "other", name="umb")
    (ws / "cam-docs").rename(ws.parent / "gone")
    r = cli(kit, "projects", "--adopt", str(ws), "--name", "shop", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["path"].endswith("cam-docs")
    rows = json.loads(cli(kit, "projects", "--json").stdout)
    assert [p["name"] for p in rows] == ["shop"]


def test_adopt_refuses_a_non_empty_cam_docs(kit, tmp_path):
    ws = tmp_path / "stray"
    (ws / "cam-docs").mkdir(parents=True)
    (ws / "cam-docs" / "notes.txt").write_text("mine", encoding="utf-8")
    r = cli(kit, "projects", "--adopt", str(ws), "--json")
    assert r.returncode == 1 and "cam-docs" in r.stderr and "Traceback" not in r.stderr


def test_git_init_json(kit, tmp_path):
    folder = tmp_path / "code"
    folder.mkdir()
    (folder / "pom.xml").write_text("<project/>", encoding="utf-8")
    r = cli(kit, "projects", "--git-init", str(folder), "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"initialised": [str(folder.resolve())]}
    assert (folder / ".git").exists()
    r = cli(kit, "projects", "--git-init", str(folder), "--json")          # already a repo
    assert r.returncode == 1 and r.stderr.startswith("✖") and "Traceback" not in r.stderr
    out = json.loads(r.stdout)
    assert out["error"] == "git-init" and "already" in out["detail"]
    r = cli(kit, "projects", "--git-init", str(folder))                    # no --json: stdout stays empty
    assert r.returncode == 1 and r.stdout == ""


def test_adopt_home_and_no_git_say_so_as_json(kit, tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    (code / "pom.xml").write_text("<project/>", encoding="utf-8")
    for folder, want in ((kit.home, "home"), (code, "no-git")):
        r = cli(kit, "projects", "--adopt", str(folder), "--json")
        assert r.returncode == 1 and r.stderr.startswith("✖") and "Traceback" not in r.stderr
        out = json.loads(r.stdout)
        assert out["error"] == want and out["detail"]
        assert not (folder / "cam-docs").exists()


def test_adopt_a_taken_cam_docs_says_so_as_a_json_code(kit, tmp_path):
    """The app words "taken" itself: a stable code on stdout, the CLI's line unchanged on stderr."""
    ws = tmp_path / "stray"
    (ws / "cam-docs").mkdir(parents=True)
    (ws / "cam-docs" / "notes.txt").write_text("mine", encoding="utf-8")
    r = cli(kit, "projects", "--adopt", str(ws), "--json")
    row = json.loads(r.stdout)
    assert r.returncode == 1 and row["error"] == "taken" and "cam-docs" in row["detail"]
    assert row["detail"] in r.stderr and not row["detail"].startswith("✖")


def test_adopt_a_cam_docs_that_is_a_file_is_taken_too(kit, tmp_path):
    ws = tmp_path / "stray"
    ws.mkdir()
    (ws / "cam-docs").write_text("not a folder", encoding="utf-8")
    r = cli(kit, "projects", "--adopt", str(ws), "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["error"] == "taken" and "Traceback" not in r.stderr


def test_adopt_without_json_keeps_stdout_empty_when_taken(kit, tmp_path):
    ws = tmp_path / "stray"
    (ws / "cam-docs").mkdir(parents=True)
    (ws / "cam-docs" / "notes.txt").write_text("mine", encoding="utf-8")
    r = cli(kit, "projects", "--adopt", str(ws))
    assert r.returncode == 1 and r.stdout == "" and "cam-docs" in r.stderr


def test_adopt_a_file_is_one_line_on_stderr(kit, tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    r = cli(kit, "projects", "--adopt", str(f), "--json")
    assert r.returncode == 1 and "Traceback" not in r.stderr and r.stdout == ""


def test_projects_add_unchanged(kit, tmp_path):
    r = cli(kit, "projects", "--add", str(tmp_path), "--json")
    assert r.returncode == 1 and "is not a Camarón project" in r.stderr


def _join_in_process(kit, monkeypatch, capsys, *extra, folder=None):
    """Run camarones.py's own `join` dispatch in this process (so projects.* can be monkeypatched)."""
    monkeypatch.delenv("CAMARONES_ROOT", raising=False)
    monkeypatch.setattr(sys, "argv", ["camarones.py", "join", "https://git.example.com/team/docs.git",
                                      str(folder or kit.ws), *extra])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(kit.kit_dir / "camarones.py"), run_name="__main__")
    return e.value.code, capsys.readouterr()


def test_join_no_open_says_why_as_json(kit, monkeypatch, capsys):
    monkeypatch.setattr(kit.projects, "reach", lambda url: ("auth", "401"))
    monkeypatch.setattr(kit.projects, "connect", lambda url, ask=None, log=print: False)
    code, out = _join_in_process(kit, monkeypatch, capsys, "--no-open")
    assert code == 1
    row = json.loads(out.out.strip().splitlines()[-1])
    assert row["error"] == "auth" and row["host"] == "git.example.com" and row["detail"] == "401"


def test_join_failure_json_never_carries_the_urls_userinfo(kit, monkeypatch, capsys):
    monkeypatch.setattr(kit.projects, "reach", lambda url: ("auth", "401"))
    monkeypatch.setattr(kit.projects, "connect", lambda url, ask=None, log=print: False)
    monkeypatch.setattr(sys, "argv", ["camarones.py", "join", "https://me:s3cr3t@git.example.com/t/d.git", str(kit.ws),
                                      "--no-open"])
    with pytest.raises(SystemExit):
        runpy.run_path(str(kit.kit_dir / "camarones.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert json.loads(out.strip().splitlines()[-1])["host"] == "git.example.com" and "s3cr3t" not in out


def test_join_token_comes_from_the_environment(kit, monkeypatch, capsys):
    seen = {}

    def connect(url, ask=None, log=print):
        seen["first"], seen["again"] = ask("git.example.com", False), ask("git.example.com", True)
        return False
    monkeypatch.setattr(kit.projects, "reach", lambda url: ("auth", "401"))
    monkeypatch.setattr(kit.projects, "connect", connect)
    monkeypatch.setenv("CAMARONES_JOIN_TOKEN", "t0k")
    code, out = _join_in_process(kit, monkeypatch, capsys, "--no-open")
    assert seen == {"first": "t0k", "again": None} and code == 1      # one-shot: later calls give nothing
    assert "t0k" not in out.out + out.err                         # the token is never printed


def test_join_without_a_token_asks_nobody(kit, monkeypatch, capsys):
    got = {}
    monkeypatch.setattr(kit.projects, "reach", lambda url: ("network", "no route"))
    monkeypatch.setattr(kit.projects, "connect", lambda url, ask=None, log=print: got.setdefault("ask", ask) and False)
    monkeypatch.delenv("CAMARONES_JOIN_TOKEN", raising=False)
    code, _ = _join_in_process(kit, monkeypatch, capsys, "--no-open")
    assert code == 1 and got["ask"] is None                       # as before: no terminal, no token, no prompt


def test_the_taller_never_runs_the_hubs_commands(kit):
    from lib import appapi
    assert appapi.HUB == {"new", "join", "switch", "projects"}
    with pytest.raises(ValueError):
        appapi.entry("projects")


def test_the_catalog_keeps_inspect_and_adopt_out_of_the_apps_forms(kit):
    """--inspect/--adopt/--name are the start screen's way in (IPC), not a form: the catalog lists `projects` with
    --add only, so no command form shows them (`arg.adopt` labels `pages --adopt`)."""
    r = cli(kit, "catalog", "--json", CAMARONES_ROOT=str(kit.root))
    assert r.returncode == 0, r.stderr
    row = next(c for c in json.loads(r.stdout)["commands"] if c["name"] == "projects")
    assert {a["dest"] for a in row["args"]} == {"json", "add"}


def test_the_env_token_is_tried_even_when_a_saved_one_was_refused(kit, monkeypatch, capsys):
    """The app's retry: the saved token is refused, the user pastes a new one, the app reruns join with it in the
    environment. `connect` passes again=True from its first ask (a saved token exists): the env token must still go."""
    from test_team_repo import fake_host
    fake_host(kit, monkeypatch, good="new-token")
    kit.creds.save("git.example.com", "gitlab", "old-token", "me")
    monkeypatch.setattr(kit.projects, "join", lambda url, ws, *a: (ws / "cam-docs", True))
    monkeypatch.setenv("CAMARONES_JOIN_TOKEN", "new-token")
    code, out = _join_in_process(kit, monkeypatch, capsys, "--no-open")
    assert code == 0 and json.loads(out.out.strip().splitlines()[-1])["joined"] is True
    assert kit.creds.get("git.example.com") == "new-token" and "new-token" not in out.out + out.err


def test_a_refused_env_token_is_not_offered_twice_and_the_saved_one_stays(kit, monkeypatch, capsys):
    from test_team_repo import fake_host
    fake_host(kit, monkeypatch, good="never")
    kit.creds.save("git.example.com", "gitlab", "old-token", "me")
    monkeypatch.setenv("CAMARONES_JOIN_TOKEN", "bad-token")
    code, out = _join_in_process(kit, monkeypatch, capsys, "--no-open")
    row = json.loads(out.out.strip().splitlines()[-1])
    assert code == 1 and row["error"] == "auth" and row["host"] == "git.example.com"
    assert kit.creds.get("git.example.com") == "old-token" and "bad-token" not in out.out + out.err


def _taken_by_another_remote(tmp_path):
    """A folder whose cam-docs is already a git repo with another origin: join refuses it before any network call."""
    ws = tmp_path / "here"
    (ws / "cam-docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(ws / "cam-docs")], check=True)
    subprocess.run(["git", "-C", str(ws / "cam-docs"), "remote", "add", "origin", "https://other.example.com/x/docs.git"],
                   check=True)
    return ws


def test_join_no_open_into_a_taken_cam_docs_says_taken(kit, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(kit.projects, "connect", lambda url, ask=None, log=print: True)
    code, out = _join_in_process(kit, monkeypatch, capsys, "--no-open", folder=_taken_by_another_remote(tmp_path))
    row = json.loads(out.out.strip().splitlines()[-1])
    assert code == 1 and row["error"] == "taken" and "cam-docs" in row["detail"]
    assert row["detail"] in out.err                               # the stderr line is unchanged


def test_join_into_a_taken_cam_docs_without_no_open_prints_no_json(kit, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(kit.projects, "connect", lambda url, ask=None, log=print: True)
    code, out = _join_in_process(kit, monkeypatch, capsys, folder=_taken_by_another_remote(tmp_path))
    assert code == 1 and out.out.strip() == "" and "cam-docs" in out.err
