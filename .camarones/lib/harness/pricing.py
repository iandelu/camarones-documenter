"""API prices for the plan bill: lib/pricing.yaml (USD per million tokens per model), merged per key with a team's
`pricing:` in workspace.yaml. A model with no price costs None, never 0; a local model (Ollama, LM Studio…) costs 0."""
from __future__ import annotations

import copy
import functools
import re
from pathlib import Path

import yaml

from . import routing

KINDS = ("in", "out", "cache_read", "cache_write_5m", "cache_write_1h")
FILE = Path(__file__).resolve().parent.parent / "pricing.yaml"
DATED = re.compile(r"-\d{8}$")


@functools.lru_cache(maxsize=1)
def _kit() -> dict:
    return yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def table(workspace: dict | None = None) -> tuple[dict, list[str]]:
    tbl = copy.deepcopy(_kit())
    for key in ("models", "aliases", "runners"):
        tbl.setdefault(key, {})
    over = (workspace or {}).get("pricing")
    if over is None:
        return tbl, []
    if not isinstance(over, dict):
        return tbl, ["pricing: not a mapping"]
    problems = []
    for model, prices in (over.get("models") or {}).items():
        if not isinstance(prices, dict):
            problems.append(f"pricing.models.{model}: not a mapping")
            continue
        bad = [k for k, v in prices.items() if k not in KINDS or not _number(v)]
        if bad:
            problems += [f"pricing.models.{model}.{k}: " + ("unknown price kind" if k not in KINDS else "not a number")
                         for k in bad]
            continue
        tbl["models"][str(model)] = {**tbl["models"].get(str(model), {}), **prices}
    for key in ("aliases", "runners"):
        for name, target in (over.get(key) or {}).items():
            if isinstance(target, str):
                tbl[key][str(name)] = target
            else:
                problems.append(f"pricing.{key}.{name}: not a model name")
    return tbl, problems


def _local(model: str | None, runner: str | None) -> bool:
    if model and model.split("/", 1)[0].lower() in routing.LOCAL_PROVIDERS:
        return True
    return bool(runner) and routing.parse(runner).local


def resolve(model: str | None, runner: str | None, tbl: dict) -> str | None:
    if _local(model, runner):
        return "local"
    models, aliases = tbl.get("models") or {}, tbl.get("aliases") or {}
    if model:
        for name in (model, aliases.get(model), DATED.sub("", model)):
            if name in models:
                return name
            if name in aliases:
                return aliases[name]
        return None
    route = routing.parse(runner) if runner else None
    if route and route.model:
        return resolve(route.model, None, tbl)
    default = (tbl.get("runners") or {}).get(route.runner) if route else None
    return default if default in models else None


def cost(tokens: dict, model: str | None, runner: str | None, tbl: dict) -> float | None:
    key = resolve(model, runner, tbl)
    if key == "local":
        return 0.0
    if key is None:
        return None
    t = dict(tokens)
    if "cache_write" in t:
        t["cache_write_5m"] = t.get("cache_write_5m", 0) + t.pop("cache_write")
    prices = tbl["models"][key]
    return round(sum((t.get(k) or 0) * (prices.get(k) or 0) for k in KINDS) / 1_000_000, 6)
