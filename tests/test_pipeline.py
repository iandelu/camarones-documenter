"""Pipelines in YAML (R7): the kit's plan comes from lib/pipelines/*.yaml instead of code. The legacy blueprint and
TYPES below are frozen copies of the code they replace: every profile × interview mode × repo set must give the same
units, in the same order, with the same dependencies, so stored plan.yaml statuses carry over untouched."""
from __future__ import annotations

import pytest

LEGACY_TYPES = {
    "quick-overview":   (2, "agent", "First overview: purpose, run instructions, one flow and sources", "quick-overview"),
    "setup":            (0, "wizard", "Environment ready (tools, repos, agent wiring)", "setup"),
    "discovery":        (1, "agent",  "Discovery of {repo}", "discovery"),
    "discovery-cross":  (1, "agent",  "Cross-repo correlation (integrations, shared DBs, candidate flows)", "discovery-cross"),
    "questionnaire":    (2, "agent",  "Team questionnaire: inferred answers and options to share with the team", "questionnaire"),
    "answers":          (2, "wizard", "Team answers: share the questionnaire and import the answers", "answers"),
    "interview-context":  (2, "agent", "Interview 1: bounded contexts, external actors, environments", "interview"),
    "interview-language": (2, "agent", "Interview 2: DDD glossary, SLAs / NFRs", "interview"),
    "interview-history":  (2, "agent", "Interview 3: historical decisions, known debt, validate integrations/flows/data", "interview"),
    "repo-brief":       (3, "agent",  "{repo}: README + AGENTS.md/CLAUDE.md (stack) + C4 components + OpenWiki brief", "repo-brief"),
    "repo-wiki":        (3, "agent",  "{repo}: OpenWiki repository wiki", "repo-wiki"),
    "arch-system":      (4, "agent",  "C4 system: context + containers views", "arch-system"),
    "domain":           (4, "agent",  "Domain: bounded contexts, context map, glossary, actors", "domain"),
    "data":             (4, "agent",  "Data models: ERDs, ownership, shared DBs", "data"),
    "deployment":       (4, "agent",  "Deployment: environments + C4 deployment views", "deployment"),
    "decisions-quality": (4, "agent", "ADRs, SLAs, tech debt", "decisions-quality"),
    "security-review":  (5, "agent",  "[beta] Security review: threats and vulnerabilities", "security-review"),
    "architecture-review": (5, "agent", "[beta] Architecture review: coupling, duplication, tech debt", "architecture-review"),
    "flows-catalog":    (5, "agent",  "Business flows catalog (propose, validate, create flow units)", "flows-catalog"),
    "flow":             (5, "agent",  "Flow: {slug}", "flow"),
    "diagrams":         (5, "agent",  "Diagrams: sequences, lifecycles (state), data and context maps where pages lack them", "diagrams"),
    "i18n":             (6, "agent",  "Spanish translations + index", "i18n"),
    "portal":           (7, "wizard", "Build and run the portal", "portal"),
    "ci":               (7, "wizard", "CI pipelines (umbrella + per-repo snippets)", "ci"),
    "confirm":          (7, "wizard", "Human review: confirm pages", "confirm"),
    "handover":         (7, "agent",  "Handover: summary, commits on branches, next steps", "handover"),
    "review-fixes":     (7, "agent",  "Apply human review feedback", "review-fixes"),
    "doc-fixes":        (7, "agent",  "Fix documentation problems (check errors, orphans, re-confirmations, translations)", "doc-fixes"),
}


def legacy_unit(uid, type_, deps, repo=None):
    phase, runner, tpl, _ = LEGACY_TYPES[type_]
    return {"id": uid, "type": type_, "phase": phase, "runner": runner, "title": tpl.format(repo=repo or "", slug=""),
            "status": "todo", "deps": deps, "repo": repo, "notes": "", "updated": None}


def legacy_blueprint(repos, profile, team):
    u_ = legacy_unit
    disc = [f"discovery:{r}" for r in repos]
    briefs = [f"repo-brief:{r}" for r in repos]
    wikis = [f"repo-wiki:{r}" for r in repos]
    if profile == "quick":
        return [u_("setup", "setup", []), *[u_(f"discovery:{r}", "discovery", ["setup"], repo=r) for r in repos],
                u_("quick-overview", "quick-overview", disc), u_("portal", "portal", ["quick-overview"]),
                u_("confirm", "confirm", ["quick-overview"]), u_("handover", "handover", ["portal", "confirm"])]
    u = [u_("setup", "setup", [])]
    u += [u_(f"discovery:{r}", "discovery", ["setup"], repo=r) for r in repos]
    u += [u_("discovery-cross", "discovery-cross", disc)]
    first_interview = ["discovery-cross"]
    if team:
        u += [u_("questionnaire", "questionnaire", ["discovery-cross"]), u_("answers", "answers", ["questionnaire"])]
        first_interview = ["answers"]
    u += [u_("interview-context", "interview-context", first_interview),
          u_("interview-language", "interview-language", ["interview-context"]),
          u_("interview-history", "interview-history", ["interview-context"])]
    for r in repos:
        u += [u_(f"repo-brief:{r}", "repo-brief", ["interview-context"], repo=r),
              u_(f"repo-wiki:{r}", "repo-wiki", [f"repo-brief:{r}"], repo=r)]
    u += [u_("arch-system", "arch-system", briefs), u_("domain", "domain", ["interview-language"]),
          u_("data", "data", ["discovery-cross", "interview-history"]), u_("deployment", "deployment", ["arch-system"]),
          u_("decisions-quality", "decisions-quality", ["interview-history"]),
          u_("flows-catalog", "flows-catalog", ["arch-system", "interview-history"]),
          u_("diagrams", "diagrams", ["domain", "data", "flows-catalog"]), u_("i18n", "i18n", ["domain", "flows-catalog"]),
          u_("portal", "portal", ["arch-system"]), u_("ci", "ci", ["setup"]),
          u_("confirm", "confirm", ["domain", "decisions-quality", "flows-catalog"]),
          u_("handover", "handover", ["i18n", "portal", "confirm", *wikis])]
    return u


def test_unit_types_are_unchanged(kit):
    assert {t: kit.plan.TYPES[t] for t in LEGACY_TYPES} == LEGACY_TYPES        # new types may be added, none changed


@pytest.mark.parametrize("profile", ["quick", "full"])
@pytest.mark.parametrize("mode", ["live", "team"])
@pytest.mark.parametrize("repos", [[], ["api"], ["api", "web", "worker"]])
def test_blueprint_is_unchanged_for_every_combination(kit, profile, mode, repos):
    ws = kit.docs.workspace()
    ws["project"]["profile"] = profile
    kit.docs.save_workspace(ws)
    kit.docs.set_interview_mode(mode)
    assert kit.plan.blueprint(repos) == legacy_blueprint(repos, profile, mode == "team")


@pytest.fixture
def pipeline(kit):
    from lib.harness import pipeline
    return pipeline


def test_kit_pipelines_load_and_validate(pipeline):
    for name in ("full", "quick"):
        p = pipeline.load(name)
        assert p["name"] == name and pipeline.validate(p) == []


def test_expand_fans_out_per_repo_and_resolves_wildcards(pipeline):
    spec = {"name": "t", "nodes": [
        {"id": "setup", "type": "setup"},
        {"for_each": "repos", "nodes": [{"id": "discovery:{repo}", "type": "discovery", "needs": ["setup"]},
                                        {"id": "repo-brief:{repo}", "type": "repo-brief", "needs": ["discovery:{repo}"]}]},
        {"id": "arch-system", "type": "arch-system", "needs": ["repo-brief:*"]},
        {"id": "ci", "type": "ci", "needs": ["setup"], "when": "team-interviews"},
        {"id": "portal", "type": "portal", "needs": ["setup"], "unless": "team-interviews"}]}
    got = pipeline.expand(spec, repos=["a", "b"], predicates={"team-interviews": False})
    assert [(n["id"], n["needs"], n.get("repo")) for n in got] == [
        ("setup", [], None), ("discovery:a", ["setup"], "a"), ("repo-brief:a", ["discovery:a"], "a"),
        ("discovery:b", ["setup"], "b"), ("repo-brief:b", ["discovery:b"], "b"),
        ("arch-system", ["repo-brief:a", "repo-brief:b"], None), ("portal", ["setup"], None)]


def test_validation_names_the_yaml_path_of_each_problem(pipeline):
    spec = {"name": "t", "nodes": [
        {"id": "setup", "type": "setup"},
        {"id": "x", "type": "nope", "needs": ["setup"]},
        {"id": "y", "type": "domain", "needs": ["ghost"]},
        {"id": "z", "type": "domain", "when": "full-moon"},
        {"for_each": "planets", "nodes": []}]}
    errors = pipeline.validate(spec)
    assert "nodes[1].type: unknown unit type 'nope'" in errors
    assert "nodes[2].needs: unknown node 'ghost'" in errors
    assert "nodes[3].when: unknown condition 'full-moon'" in errors
    assert "nodes[4].for_each: can only fan out over 'repos'" in errors


def test_a_dependency_cycle_is_reported(pipeline):
    spec = {"name": "t", "nodes": [{"id": "a", "type": "domain", "needs": ["b"]}, {"id": "b", "type": "data", "needs": ["a"]}]}
    assert any("cycle" in e for e in pipeline.validate(spec))
