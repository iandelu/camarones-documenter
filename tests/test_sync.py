"""Sync with the team, as data (env.sync_status) and from the portal (GET /api/sync, POST /api/sync/share): where
cam-docs stands against the team's repo, what is not checkpointed yet, and sharing as the team action it is. And the
--json the desktop app's Team panel reads (`trust`, `hooks`)."""
from __future__ import annotations

import json, os, subprocess, sys, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

from test_team_repo import bare, git, publish


def test_without_a_remote(kit):
    kit.env.init_templates("demo", log=lambda _: None)
    s = kit.env.sync_status()
    assert s["remote"] == "" and s["ahead"] is None and s["behind"] is None and s["last_share"] is None
    (kit.root / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    assert "docs/new.md" in kit.env.sync_status()["pending"]


def test_ahead_behind_and_the_last_share(kit, tmp_path):
    remote = bare(tmp_path)
    publish(kit, remote)
    s = kit.env.sync_status()
    assert s["remote"] and s["branch"] == "main" and (s["ahead"], s["behind"]) == (0, 0)
    assert s["last_share"] and s["pending"] == [] and s["auto"] is False and s["head"]["subject"]
    (kit.root / "docs" / "mine.md").write_text("# Mine\n", encoding="utf-8")
    kit.env.checkpoint_commit("mine")
    assert kit.env.sync_status()["ahead"] == 1
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    (mate / "docs" / "theirs.md").write_text("# Theirs\n", encoding="utf-8")
    git(mate, "add", "-A"); git(mate, "commit", "-q", "-m", "theirs"); git(mate, "push", "-q", "origin", "main")
    assert kit.env.sync_status()["behind"] == 0                           # not fetched yet: the last known state
    assert kit.env.sync_status(fetch=True)["behind"] == 1


def test_auto_share_survives_the_last_share(kit, tmp_path):
    remote = bare(tmp_path)
    kit.env.set_auto_share(True)
    publish(kit, remote)
    s = kit.env.sync_status()
    assert s["auto"] is True and s["last_share"]


@pytest.fixture
def portal(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, header=True):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", **({"X-Camarones": "1"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_portal_shows_and_shares(kit, tmp_path, portal):
    remote = bare(tmp_path)
    publish(kit, remote)
    (kit.root / "docs" / "edit.md").write_text("# Edit\n", encoding="utf-8")
    code, s = call(portal + "/api/sync")
    assert code == 200 and "docs/edit.md" in s["pending"]
    assert call(portal + "/api/sync/share", {}, header=False)[0] == 403
    code, r = call(portal + "/api/sync/share", {})
    assert code == 200 and r["result"]["status"] == "pushed" and r["sync"]["pending"] == []
    assert "docs/edit.md" in git(remote, "ls-tree", "-r", "--name-only", "main").splitlines()


def test_sharing_without_a_remote_says_so(kit, portal):
    kit.env.init_templates("demo", log=lambda _: None)
    code, r = call(portal + "/api/sync/share", {})
    assert code == 200 and r["result"]["status"] == "no-remote"


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL)


def test_trust_and_hooks_as_json(kit):
    r = cli(kit, "trust", "--json")
    assert r.returncode == 0, r.stderr
    assert isinstance(json.loads(r.stdout)["pending"], list)
    r = cli(kit, "hooks", "--json")
    assert r.returncode == 0 and json.loads(r.stdout) == {"enabled": False}
    cli(kit, "hooks", "on")
    assert json.loads(cli(kit, "hooks", "--json").stdout) == {"enabled": True}
