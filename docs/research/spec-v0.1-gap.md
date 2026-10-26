# External spec v0.1 ("engineering harness") vs the kit — gap analysis

Source: `camarones_implementation_v0.1.zip` (IMPLEMENTATION_SPEC.md, backlog CAM-001…021, examples), received
2026-10-24. The spec was written **without reading this repo** and says so; its module names are proposals. This page
maps each of its pieces to what the kit already has, what clashes with the kit's rules (AGENTS.md), and what is new.
No code was changed.

## 1. The one difference that matters

The kit's agents **write documentation about code** (cam-docs; the service checkout is never touched — see
`lib/propose.py`). The spec's agents **change the code** (ChangeSets on service repos, Maven/Gradle verification,
merge), with the docs as the authority that guards them. Most of the spec's knowledge core already exists here; most
of what is new is the *code-change harness* around it. Adopting it is a scope decision (project brain → brain +
development harness), not a refactor.

## 2. Already in the kit (spec name → kit piece)

| Spec | Kit | Fit |
|---|---|---|
| Knowledge repo as authority (D-01, D-04, §4.1) | `cam-docs/` layout, repos next to it, `workspace.yaml` repos list, `docs.py` incremental state per repo SHA | Same idea. Spec wants a separate knowledge repo referenced, not copied — that is `cam-docs` |
| Document states draft/proposed/approved/superseded/conflicted (§4.2) | `draft` / `confirmed` (hash-locked `x-confirmed.body_sha`) / `needs-reconfirm`; only `camaron confirm` writes it (`docs.py:292`, CONVENTIONS) | Approved = confirmed, conflicted ≈ needs-reconfirm. Missing: `proposed`, `superseded` |
| Approval bound to hash; external edit detected (§4.1, scenario C) | Confirm locks the body hash; any edit drops it to `needs-reconfirm` | Partial: no STALE_SNAPSHOT refusal of a proposal made on an older commit |
| Provenance on every claim (§4.3) | `x-sources` (L1 lines, L2 symbols, L3 pages/C4), fingerprints in `docs/.work/fresh.json` | Per page, not per typed edge |
| `inferred` never satisfies a policy needing `verified` | Freshness AI gate: agents never get suspect/stale/unsourced-unreviewed pages (`harness/freshness.py`) | Same principle, already enforced in MCP/Ask |
| C4 approved vs inferred overlay (§10.5) | `quickarch` draft C4, `#ai-draft` / `#confirmed` elements, confirm in the portal (`c4edit.py`) | Done |
| Drift detection (CAM-016) | Freshness `fresh/suspect/stale`; `pr.py` lists pages a PR leaves out of date; `refresh-docs` unit | Detects *cited code changed*, not *value contradicts decision* (scenario F) |
| ADRs (§15) | `docs/decisions/NNNN-<slug>.md`, `type: decision`, `x-owner: human` | IDs are `NNNN`, not `DEC-` |
| Worktrees, locks, recovery (CAM-010) | `harness/worktrees`, `locks` (cross-process, all OS), `integrate` (main merged first, gates, no-conflict merge), `scheduler` | For cam-docs units only |
| Swappable coding agent (CAM-011, `CodingAgentPort`) | `Runner` port (`harness/ports.py`): claude, codex, opencode, command templates (Gemini); routing by tier; `allow_tools` | Done for doc work. No Aider; OpenCode is already the local-model gateway (CAM-020 ≈ done) |
| Event log (§4.5) | `harness/events.py` JSONL per run, `runs`, `kpis` | Files, not SQLite |
| A/B value metrics (§12.3) | `harness/ab.py` (with vs without cam-docs), `evals` golden questions, `drafts` (AI vs confirmed edits) | Done, for Q&A rather than PR lead time |
| Secrets (§9) | gitleaks in the quality gate, `creds.py` keeps tokens out of AI sessions, `trust.py` for agent config | Partial: no path deny-list for agents |
| Static facts (UC-01, offline first) | `genblocks` (Maven/Gradle commands, endpoints, topics, OpenAPI files), `schemas` (Flyway/Liquibase), `inventory`, `osv`, `radar`, `history`, `codemap` | Done, matches AGENTS.md priority 1 |
| Desktop shell + typed IPC (CAM-006, §7.2) | Electron app, portal server with app token, `appapi.py`, `catalog.py` | Done with Electron (see §3) |
| Discovery (CAM-021) | Interviews, team questionnaire, Excalidraw boards, anchored review comments | Different shape: discovery of *existing* knowledge, not product ideas |
| Multi-repo Spring fixture (CAM-014) | `scripts/sandbox.py`: spring-petclinic-rest + angular, pinned | No messaging/RabbitMQ, two repos not three services |

## 3. Clashes with the kit's rules

| Spec | Rule it hits | Note |
|---|---|---|
| Tauri 2 (D-05, ADR-002) | Already decided: `tooling-candidates.md` K8 adopted Electron 44.7.0; Tauri rejected (Rust toolchain, signed binaries) | Keep Electron; ADR-002 is moot |
| SQLite as operational store (D-03, CAM-005) | Kit state is versioned files (`plan.yaml`, `fresh.json`, JSONL) that travel with git and stay reviewable | Only worth it if a board with thousands of items appears; a YAML/JSONL board fits the current model |
| Its `workspace.yaml` (`project.knowledge`, `repositories[].local_path`, `verification_profile`) | AGENTS.md 2.3: no renamed keys without automatic, idempotent conversion | Add optional keys to the existing `repos` entries instead |
| "Windows first" (§1.3) | AGENTS.md 2.1: macOS, Windows, Linux always | Drop "first" |
| `deny_network_by_default`, OS sandbox (§9, ADR-007) | AGENTS.md 2.4: no admin, no manual steps, all OSes | The spec itself admits it cannot promise this; leave as "not supported", say so |
| Five doc states + `REQ-/DEC-/WI-/CHG-` IDs | 2.3: frontmatter fields and file locations are contracts | New states/IDs only as additive fields (`x-id`?), never rewriting confirmed docs |
| Java/Spring-first vertical (D-10) | Kit is stack-agnostic; JVM is one detector among several | Fine as a first *test case*, not as product scope |
| Agent edits service repos, prepares merge | Kit never touches the service checkout today | The core of the scope decision in §1 |

## 4. Really new

1. **Work items + Kanban** (CAM-007): stories/bugs/spikes with acceptance criteria linked to doc IDs. Nothing like it:
   `plan.yaml` units are documentation jobs, Boards are whiteboards.
2. **ChangeSet state machine + policy/risk engine** (CAM-009, §6.1–6.2): deterministic guards, explainable risk score
   from signals (public contract, SQL migration, auth path, messaging, multi-repo, unknown consumers).
3. **Verification runner with evidence** (CAM-012): run build/tests, store exit code, hashes, JUnit XML per SHA;
   `skipped`/`error` never pass. The kit only *reads* the build commands (`genblocks`).
4. **Document proposals with diff and stale-snapshot refusal** (CAM-008): a proposed state between draft and confirmed,
   tied to the commit it was made on.
5. **Typed traceability graph** (CAM-015): requirement → work item → change → test → evidence, each edge with origin
   and trust. The kit has page-level `x-sources` and the code graph, not cross-artifact edges.
6. **Semantic drift** (scenario F): a decision's value (3 retries) vs the code's value (5). Freshness only knows the
   cited lines moved.
7. **Contract compatibility checks** (CAM-017): OpenAPI/AsyncAPI breaking-change reports, ArchUnit gates.
8. **Issue tracker export** (CAM-019).

## 5. Pieces that fit the kit without the scope change

Ordered by AGENTS.md priority (value without AI first):

1. **Deterministic risk score for a PR**, reusing `pr.py`: the same signals (contract files, migrations from
   `schemas`, auth paths, messaging topics from `genblocks`, repos touched, pages left out of date) as a line in the PR
   comment. No AI, no new tool.
2. **Stale-snapshot check on confirm**: record the cam-docs commit a draft was written on; `confirm` warns when the
   page changed under it since. Small, additive to `x-confirmed`.
3. **Value drift for decisions**: let a decision cite a config key or constant in `x-sources` (L2 already finds
   symbols); flag it `suspect` when that value changes. Extends freshness instead of a new scanner.
4. **Stable IDs as an optional frontmatter field**, so stories elsewhere can link `DEC-0004@sha`.

The rest (work items, ChangeSets, verification runner, code-editing agents) only makes sense after deciding the scope
question in §1.
