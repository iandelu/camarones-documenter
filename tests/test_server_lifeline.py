"""The project server ends with its app, however the app ends: a crash or a force-quit runs none of its code, so the
app holds the other end of the server's stdin and the system closes it. Real processes, on every OS."""
from __future__ import annotations

import json, os, subprocess, sys, time, urllib.request

import pytest

from test_terminals import until


def start_server(wired, **env):
    """As desktop/main.cjs starts it: its own process group on POSIX, stdin a pipe the parent holds."""
    pr = subprocess.Popen([sys.executable, str(wired.kit_dir / "camarones.py"), "up", "--foreground", "--port", "0"],
                          env={**os.environ, "CAMARONES_ROOT": str(wired.root), "CAMARONES_APP_TOKEN": "tok", **env},
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
                          start_new_session=os.name != "nt")
    return pr, json.loads(pr.stdout.readline())["port"]


def answers(port: int) -> bool:
    return urllib.request.urlopen(f"http://127.0.0.1:{port}/desktop/", timeout=5).status == 200


def test_the_server_stops_when_its_app_is_gone(wired):
    pr, port = start_server(wired, CAMARONES_LIFELINE="1")
    try:
        assert answers(port)
        pr.stdin.close()                                        # what the system does for a crashed app
        pr.wait(timeout=20)
    finally:
        pr.kill()
        pr.stdout.close()


def test_the_server_outlives_a_closed_stdin_when_no_app_asked_for_that(wired):
    pr, port = start_server(wired)
    try:
        pr.stdin.close()
        time.sleep(1)
        assert pr.poll() is None and answers(port)
    finally:
        pr.kill()
        pr.wait()
        pr.stdout.close()


def test_what_the_server_starts_does_not_wait_on_the_apps_pipe(wired, tmp_path):
    """Nothing is ever written to it, so a child reading an inherited stdin (`claude -p` does) would wait for the app."""
    out = tmp_path / "read.txt"
    code = ("import subprocess, sys, pathlib, os\n"
            f"sys.path.insert(0, {str(wired.kit_dir)!r})\n"
            "from lib import serve\n"
            "serve.watch_app()\n"
            "r = subprocess.run([sys.executable, '-c', 'import sys; print(repr(sys.stdin.read()))'], capture_output=True,"
            " text=True, timeout=15)\n"
            f"pathlib.Path({str(out)!r}).write_text(r.stdout, encoding='utf-8')\n"
            "os._exit(0)\n")
    pr = subprocess.Popen([sys.executable, "-c", code], env={**os.environ, "CAMARONES_ROOT": str(wired.root)},
                          stdin=subprocess.PIPE, start_new_session=os.name != "nt")
    try:
        assert pr.wait(timeout=30) == 0
        assert out.read_text(encoding="utf-8").strip() == "''"
    finally:
        pr.kill()
        pr.stdin.close()


@pytest.mark.skipif(os.name == "nt", reason="on Windows taskkill /T takes the terminals with the server")
def test_a_live_terminal_ends_with_a_server_whose_app_is_gone(wired, tmp_path):
    from lib.harness.locks import pid_alive
    from test_terminals_api import call, ready_agent_unit
    from test_terminals import ECHO
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    fake = bin_ / "claude"
    fake.write_text(f"#!{sys.executable}\nimport runpy; runpy.run_path({str(ECHO)!r}, run_name='__main__')\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    pr, port = start_server(wired, CAMARONES_LIFELINE="1", PATH=f"{bin_}{os.pathsep}{os.environ['PATH']}")
    try:
        code, r = call(f"http://127.0.0.1:{port}/api/app/terminals", {"unit": ready_agent_unit(wired)["id"], "agent": "claude"},
                       token="tok")
        assert code == 200, r
        pr.stdin.close()
        pr.wait(timeout=20)
    finally:
        pr.kill()
        pr.stdout.close()
    until(lambda: not pid_alive(r["terminal"]["pid"]))
