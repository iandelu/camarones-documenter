"""The kit's benchmark: ask the sandbox's golden questions (scripts/evals/petclinic.yaml) to a real agent once the
sandbox is documented. Spends tokens, so it only runs with `uv run pytest -m eval`; compare scores across kit versions,
prompts and models with `camaron kpis`."""
from __future__ import annotations

import json, os, shutil, subprocess, sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SANDBOX = Path(os.environ.get("CAMARONES_SANDBOX", Path.home() / "projects" / "camarones-sandbox"))


@pytest.mark.eval
def test_the_documented_sandbox_answers_its_golden_questions():
    cam = SANDBOX / "cam-docs"
    briefs = list((cam / "docs" / "repos").glob("*/brief.md")) if cam.is_dir() else []
    if not briefs:
        pytest.skip("document the sandbox first (uv run scripts/sandbox.py cli run …)")
    if not (shutil.which("claude") or shutil.which("codex")):
        pytest.skip("no agent installed")
    (cam / "evals").mkdir(exist_ok=True)
    shutil.copy(REPO / "scripts" / "evals" / "petclinic.yaml", cam / "evals" / "questions.yaml")
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sandbox.py"), "cli", "eval", "run", "--json"],
                       capture_output=True, text=True, encoding="utf-8", timeout=3600)
    result = json.loads(r.stdout[r.stdout.index("{"):])
    print(f"\nPetClinic golden questions: score {result['score']} with {result['runner']}")
    assert result["score"] is not None and len(result["questions"]) >= 8
