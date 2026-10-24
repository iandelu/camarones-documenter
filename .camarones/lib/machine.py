"""This machine, as data: the wizard's settings (language, the Claude Code and Codex models) behind `camaron config`,
and what the desktop app's Machine panel shows — the repos with their stack, the plan profile, the kit and how many
steps `setup` takes. Settings live in ~/.camarones.json, per machine, exactly where the wizard keeps them."""
from __future__ import annotations

import os

from .common import PREFS, VERSIONS, load_json, repo_dir, save_json
from .agents import CODEX_MODEL_DEFAULT

MODELS = ["sonnet", "opus", "haiku"]           # Claude Code's --model aliases
LANGS = ("es", "en")
DEFAULTS = {"lang": "es", "model": "sonnet", "codex_model": CODEX_MODEL_DEFAULT}


def settings() -> dict:
    prefs = load_json(PREFS, {})
    return {k: prefs.get(k, v) for k, v in DEFAULTS.items()}


def set_setting(key: str, value: str) -> dict:
    value = str(value or "").strip()
    if key == "lang" and value not in LANGS:
        raise ValueError(f"lang: one of {', '.join(LANGS)}")
    if key == "model" and value not in MODELS:
        raise ValueError(f"model: one of {', '.join(MODELS)}")
    if key == "codex_model" and (not value or value.startswith("-")):
        raise ValueError("codex_model: a model name")
    if key not in DEFAULTS:
        raise ValueError(f"unknown setting {key}: one of {', '.join(DEFAULTS)}")
    prefs = load_json(PREFS, {})
    prefs[key] = value
    save_json(PREFS, prefs)
    return settings()


def panel() -> dict:
    from . import agents, docs, env
    ws = docs.workspace()
    repos = [{"name": r["name"], "url": r.get("url", ""), "stack": r.get("stack", ""),
              "cloned": repo_dir(r["name"]).is_dir()} for r in ws["repos"]]
    return {"settings": settings(), "models": MODELS, "agents": agents.installed(), "setup_steps": env.setup_steps(),
            "repos": repos, "profile": ws["project"].get("profile"),
            "kit": {"version": VERSIONS["kit"], "global": bool(os.environ.get("CAMARONES_GLOBAL"))}}
