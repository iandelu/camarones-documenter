"""The project's chosen components: the kit tools and extras a project can switch on, and the profile that picks them."""
from __future__ import annotations

from lib import docs

KIT_TOOLS = {
    "graphify": "graphify — code knowledge graph (Claude/Codex query it instead of grepping)",
    "likec4": "LikeC4 — C4 architecture diagrams + interactive explorer",
    "openwiki": "OpenWiki — one wiki per repo with grounded claims",
    "quality": "Quality gate — mermaid-cli (diagram validation) + gitleaks (secret scan) for CLI check",
}
EXTRAS = {
    "agents": "Claude Code / Codex wiring in cam-docs (skills, MCP, rules), linked from the workspace root",
}
ALL_COMPONENTS = [*KIT_TOOLS, *EXTRAS]


def components() -> list[str]:
    """Components chosen in the wizard (stored in .camarones/workspace.yaml → project.components). Default: all."""
    chosen = docs.workspace()["project"].get("components")
    return list(ALL_COMPONENTS) if chosen is None else [c for c in chosen if c in ALL_COMPONENTS]


def set_profile(name: str) -> None:
    from lib.install import PROFILES
    if name not in PROFILES:
        raise ValueError(f'Unknown profile: {name}')
    ws = docs.workspace()
    ws['project']['profile'] = name
    ws['project']['components'] = list(PROFILES[name])
    docs.save_workspace(ws)


def set_components(chosen: list[str]) -> None:
    ws = docs.workspace()
    ws["project"]["components"] = [c for c in ALL_COMPONENTS if c in chosen]
    docs.save_workspace(ws)
