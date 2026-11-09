"""A headless agent for the handoff tests: writes its pids to the file it is given (and those of a child it started,
with `child`), prints one line of stream-json and sleeps. Usage: fake_agent.py <pids> <seconds> [child]"""
import json, os, subprocess, sys, time
from pathlib import Path

pids = [os.getpid()]
if "child" in sys.argv[3:]:
    pids.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]).pid)
tmp = Path(sys.argv[1] + ".tmp")
tmp.write_text(" ".join(map(str, pids)), encoding="utf-8")
tmp.replace(sys.argv[1])
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "working"}]}}), flush=True)
time.sleep(float(sys.argv[2]))
