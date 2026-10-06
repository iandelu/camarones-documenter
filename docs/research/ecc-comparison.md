# ECC (Everything Claude Code) vs Camarón: what to borrow

Research pass, 2026-10-06. Source: [ecc.tools](https://ecc.tools), the [affaan-m/ECC](https://github.com/affaan-m/ECC)
repo at v2.2.3 (4,212 files read, nothing executed) and the AI Dive review
["ECC: what to steal"](https://aidive.dev/videos/ecc-what-to-steal/). Ideas have IDs (`X1`…) so we can discard them by
ID, the same way as [tooling-candidates.md](tooling-candidates.md).

## 1. What ECC is

An "operating layer" for coding agents: 68 agents, 293 skills, 94 commands, a hook runtime, a cross-harness memory
vault, a browser plan review (`plan-canvas`) and a config scanner (AgentShield). It targets Claude Code first and has
adapters for Codex, Cursor, OpenCode and about 15 other harnesses. It is MIT. The paid product is a GitHub App that
analyses repo history on ECC's servers and proposes `SKILL.md` files.

**It does not compete with Camarón.** ECC is about *how the agent works*; Camarón is about *what the agent knows* about a
multi-repo system. They overlap on four surfaces: installing skills/MCP for Claude and Codex, memory and handoff between
sessions, human review loops, and docs that drift from code.

## 2. Where Camarón is already stronger (keep it)

| Topic | ECC | Camarón |
|---|---|---|
| Scope and size | ~4,200 files, 15 MB of docs in 22 languages; a full install costs ~27k tokens of standing context (AI Dive's count) | ~8k lines of Python, auditable end to end |
| Documenting a system | `doc-updater` writes ASCII "codemaps" for one repo | Multi-repo, C4, domain, flows, portal, i18n, interviews |
| Trust | Memory is all `unreviewed`; verified knowledge is meant to be "promoted into governed docs" | Camarón *is* that governed layer: draft → confirmed, `x-sources`, `needs-reconfirm` |
| Value without AI | Nearly everything is prompts | Static analysis, `arch-draft`, `radar` |
| Privacy | The paid analysis runs on ECC's servers | Everything local |

ECC's adoption figures (stars, "used at Tesla…", the GateGuard A/B) are self-reported and were not verified.

## 3. Ideas to borrow

| ID | Idea | ECC source | What it gives Camarón | Signal |
|---|---|---|---|---|
| X1 | **Approve the team's agent config before linking it** | AgentShield, `unified-memory` trust model | `join`/`share` bring `.claude/`, `.mcp.json`, `.codex/` and skills from a shared repo; anyone with push access could make a hook or MCP server run on every teammate's machine | ✅ **adopted in kit 3.13.0** (`lib/trust.py`, `CLI trust`) |
| X2 | **Hooks that enforce the method** (opt-in, in `cam-docs/.claude/settings.json`, never in service repos): SessionStart injects the plan status/handoff/pending feedback (capped); PostToolUse on `cam-docs/docs/**` runs `check` on that page and feeds errors back; Stop reminds to update docs when repos changed since `mark-documented` | `hooks/hooks.json`, `memory-persistence/`, `hooks.metadata.json` (stable IDs, fingerprints) | Rules that hold even when the agent skims the skill text; today `cam-docs-update` only *asks*. Kit hooks must be recognised by `trust.owned()` | 🟢 next |
| X3 | **Generated blocks from sources of truth, no AI**: `<!-- generated:env -->` tables for env vars (`application.yml`, `.env.example`), commands (`pom`, `gradle`, `package.json`), endpoints (OpenAPI); refreshed by `sync`, `check` flags hand edits | `commands/update-docs.md` (`AUTO-GENERATED` markers) | More value at install time (AGENTS.md priority 1) | 🟢 next |
| X4 | **Install state**: record every file/link/registry entry the kit owns, with hashes, so `doctor` reports drift, `repair` restores and `uninstall` removes only what is the kit's | `schemas/install-state.schema.json`, `scripts/doctor.js`, `repair.js` | Today `doctor` only checks prerequisites. Must be rebuilt from the current layout when absent (3.x compatibility) | 🟡 |
| X5 | **Context budget**: `doctor --context` counts the standing tokens of `AGENTS.md`, skills and MCP schemas; a test keeps it under a budget; token estimate per page in `llms.txt` | `skills/context-budget`, codemap freshness header | ECC is the cautionary tale; measure before it grows | 🟡 |
| X6 | **Anchored, live review**: annotate a heading or passage in the portal (slug + snippet), and `CLI feedback wait` blocks until approve/request-changes, returning JSON to the agent | `skills/plan-canvas` (`open`/`await`/`--reply`, Stop hook for undelivered feedback) | Today feedback is per file and asynchronous. Depends on P6 (stable anchors) in [ai-first-docs.md](ai-first-docs.md) | 🟡 |
| X7 | **Compliance evals for the PLAYBOOK**: run one unit with `claude -p` / `codex exec` on the sandbox and score the output deterministically (`check --strict`, P5 structure, sources that exist); `eval` marker, out of CI | `skills/skill-comply`, `eval-harness` | Tells whether a prompt change actually helps | 🟡 |
| X8 | **Business rules as `Requirement` / `Invariant` blocks** with a stable `id`, `enforced: Class.method()` and `test:` anchors; `check` verifies the symbol still exists through graphify | `agents/spec-miner.md` | Checkable rules; same goal as I4 in tooling-candidates | 🟡 |
| X9 | **Status page with a delete-zone**: what was removed on purpose and why, so agents do not recreate it; AGENTS.md routing reads map → status → relevant ADRs | `skills/living-docs-governance` | Fits P9 (agent entry points) | 🟡 |
| X10 | **CodeTour export**: `.tours/` in cam-docs (linked like `.claude`), steps anchored from a flow page's `x-sources` | `skills/code-tour` | Guided onboarding in VS Code; plain JSON, no dependency | 🟡 |
| X11 | **Local git-history mining, no AI**: hotspots, owners, co-change across repos, commit conventions → `docs/overview/history.md` and "who to interview" | the ECC GitHub App (done server-side there) | Same as I3 in tooling-candidates, without code leaving the machine | 🟡 |
| X12 | **Handoff that separates verified results from intents** (objective, state, evidence, commands run, remaining, next action) | `skills/unified-memory` | Small tweak to `handoff.md` | 🟡 |

## 4. Not to copy

- **Volume**: dozens of generic agents and commands (TDD, per-language reviewers). Out of Camarón's scope and costly in
  standing context.
- **19 harness adapters**: at most Cursor or Gemini, pointing at `AGENTS.md`.
- **Automatic "instincts"**: they log every prompt and tool call to `observations.jsonl`; noisy and a privacy cost.
- **A 40 KB minified hooks file**: if Camarón ships hooks (X2), few, with IDs and readable.

## 5. X1 as built

- `lib/trust.py` lists what can run code, widen access or steer an agent: MCP servers, Claude hooks and risky settings
  (`settings.json` and `settings.local.json`), Codex config outside the kit's block and `.codex/hooks.json`, and every
  file under `.claude/`, `.codex/` and `.agents/` (symlinks are shown, never followed).
- What the kit writes is recognised by re-rendering it for this machine (`env.refresh_agent_config`): a kit skill edited
  in the team's repo goes back to the kit's text; a file planted next to it is asked about.
- Approvals are per machine in `~/.camarones/trust/<hash of the project path>.json`, outside the repo. A project this
  machine already linked before 3.13.0 is trusted as it is once; anything after that is asked.
- The wizard asks on open (default No); No drops the workspace links to `.claude`, `.codex`, `.agents`, `.mcp.json`.
  `setup` never links unapproved config. `uninstall` forgets the approvals; `scripts/sandbox.py traces` reports leftovers.
- Limit: opening an agent directly inside `cam-docs/` bypasses the workspace links; only the agent's own folder-trust
  prompt applies there.
