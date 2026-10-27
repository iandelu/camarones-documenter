"""The price table behind the plan bill: USD per million tokens per model, pinned in the kit and overridable per team in
workspace.yaml. A missing price is None (never 0); a local model costs nothing."""
from __future__ import annotations

P = {"revised": "2026-10-27", "models": {"m-1": {"in": 3, "out": 15, "cache_read": 0.3, "cache_write_5m": 3.75,
                                                 "cache_write_1h": 6}},
     "aliases": {"one": "m-1"}, "runners": {"claude": "m-1"}}
M = 1_000_000


def test_cost_per_token_kind(kit):
    from lib.harness import pricing
    t = dict.fromkeys(pricing.KINDS, M)
    assert pricing.cost(t, "m-1", "claude", P) == 28.05


def test_alias_dated_name_and_runner_default(kit):
    from lib.harness import pricing
    assert pricing.resolve("one", None, P) == pricing.resolve("m-1-20260901", None, P) == "m-1"
    assert pricing.resolve(None, "claude:", P) == "m-1"


def test_unknown_model_is_none_never_zero(kit):
    from lib.harness import pricing
    assert pricing.cost({"in": M}, "gpt-x", "codex", P) is None


def test_local_models_cost_nothing(kit):
    from lib.harness import pricing
    assert pricing.cost({"in": M}, None, "opencode:ollama/qwen3-coder:30b", P) == 0.0


def test_legacy_cache_write_counts_as_five_minutes(kit):
    from lib.harness import pricing
    assert pricing.cost({"cache_write": M}, "m-1", None, P) == 3.75


def test_workspace_override_merges_and_names_bad_keys(kit):
    from lib.harness import pricing
    tbl, problems = pricing.table({"pricing": {"models": {"m-2": {"in": 1, "out": 2}, "bad": {"in": "x"}},
                                               "aliases": {"two": "m-2"}}})
    assert tbl["models"]["m-2"]["in"] == 1 and tbl["aliases"]["two"] == "m-2"
    assert "claude-sonnet-5-5" in tbl["models"]                     # the kit's stay
    assert "bad" not in tbl["models"] and any("pricing.models.bad.in" in p for p in problems)


def test_the_kit_table_is_complete(kit):
    from lib.harness import pricing
    tbl, problems = pricing.table()
    assert not problems and str(tbl["revised"]) and tbl["source"]
    assert all(set(pricing.KINDS) <= set(v) for v in tbl["models"].values())
    assert all(t in tbl["models"] for t in [*tbl["aliases"].values(), *tbl["runners"].values()])
