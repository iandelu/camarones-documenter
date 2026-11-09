"""A kit started from inside a Claude Code session (its Bash tool, a shell it opened) opens sessions of their own. Claude
Code sets its markers on what it launches, and a `claude` that inherits them is that session's child: it saves no
transcript, so the board has nothing to read and Continue nothing to reopen. Settings that are the person's own share
the prefix and stay: a Bedrock user's session would not even start without them."""
from __future__ import annotations

import json, os, subprocess, sys

from test_run_cli import cli, fake_agent  # noqa: F401  (fixture)
from test_scheduler import FAKE

MARKERS = {"CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "1", "CLAUDE_CODE_SESSION_ID": "parent",
           "CLAUDE_CODE_SESSION_ATTENDED": "1", "CLAUDE_CODE_HOST_SESSION_ID": "host", "CLAUDE_CODE_ENTRYPOINT": "claude-desktop",
           "CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/s", "CLAUDE_CODE_MESSAGING_TOKEN": "t", "CLAUDE_CODE_EXECPATH": "/x/claude",
           "CLAUDE_PID": "1", "CLAUDE_EFFORT": "high"}
SETTINGS = {"CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_OAUTH_TOKEN": "oauth", "CLAUDE_CODE_GIT_BASH_PATH": "C:/git/bash.exe",
            "CLAUDE_CONFIG_DIR": "/cfg", "ANTHROPIC_API_KEY": "key", "ANTHROPIC_BASE_URL": "https://gateway"}


def test_an_agent_the_kit_starts_inherits_the_persons_settings_and_no_parent_session(wired, fake_agent, tmp_path):  # noqa: F811
    from lib.common import PREFS, load_json, save_json
    seen = tmp_path / "env.json"
    script = tmp_path / "dump_agent.py"
    script.write_text(f"import json, os\njson.dump(dict(os.environ), open({str(seen)!r}, 'w', encoding='utf-8'))\n{FAKE}",
                      encoding="utf-8")
    prefs = load_json(PREFS, {})
    prefs["runners"]["fake"]["argv"] = [sys.executable, str(script), "ok"]
    save_json(PREFS, prefs)
    r = cli(wired, "run", "--parallel", "1", "--per-runner", "fake=1", "--max-units", "1",
            env={**fake_agent, **MARKERS, **SETTINGS})
    assert r.returncode == 0, r.stderr
    env = json.loads(seen.read_text(encoding="utf-8"))
    assert not set(MARKERS) & set(env)
    assert {k: env.get(k) for k in SETTINGS} == SETTINGS


def test_the_cli_cleans_its_own_environment_for_all_it_goes_on_to_start(wired):
    """`camaron app` from such a shell: its Electron, and the servers and terminals under it, inherit this one."""
    code = ("import json, os, runpy, sys\n"
            "from pathlib import Path\n"
            f"sys.argv = [{str(wired.kit_dir / 'camarones.py')!r}, 'help']\n"
            "try:\n"
            f"    runpy.run_path({str(wired.kit_dir / 'camarones.py')!r}, run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "print('ENV=' + json.dumps(sorted(os.environ)))\n")
    r = subprocess.run([sys.executable, "-c", code], env={**os.environ, "CAMARONES_ROOT": str(wired.root), **MARKERS, **SETTINGS},
                       capture_output=True, text=True, encoding="utf-8")
    names = json.loads(next(line for line in r.stdout.splitlines() if line.startswith("ENV="))[4:])
    assert not set(MARKERS) & set(names)
    assert set(SETTINGS) <= set(names)
