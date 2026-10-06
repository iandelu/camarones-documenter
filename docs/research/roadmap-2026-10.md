# Roadmap after the 2026-09-30 AI tooling report

Plan, 2026-10-06. **Status: approved for planning, not implemented.** Source: the report "Herramientas de IA para
desarrollo: revisión crítica y ampliación" (Apipana + Camarones, 2026-09-30), crossed with kit 3.5.0. Every scope
decision below was taken by the project owner in an interview; nothing here is a default.

## 0. Why

The report says Camarón's edge is **verifiable knowledge**, not more generated pages: provenance per claim and per
relation (repo + commit), freshness after each merge, a service catalog with evidence states, an evaluation bank of
real questions, and agent access through MCP. It also suggests Camarón could grow into a self-hosted portal.

Kit 3.5.0 against that:

| Report asks for | Kit today |
|---|---|
| Provenance with repo + **commit** + date + owner | `x-sources` = `repo:path#L..`, **no commit**; line ranges go stale silently |
| Know which docs went stale after a merge | Per **repo** only (`docs/.state.json`); change → page mapping is done by agents, not code |
| Four evidence states (team / code / environment / AI) | Binary trust (draft/confirmed) + `#ai-draft` C4 tags |
| Keep human contributions apart from generated output | `<!-- human -->` and `x-owner: human` are agent rules; **no code enforces them** (the portal can overwrite) |
| Service catalog (owner, APIs, events, schemas, dependencies) with provenance per relation | None; `radar`/`quickarch` find loose pieces (Rabbit/Kafka repo→broker, HTTP by name) |
| Evaluation with real questions and expected sources | None |
| Agent context over MCP | Read-only MCP, 5 tools; no catalog, impact or section reads |
| After a merge, detect affected docs and propose changes | CI `docs:update` (full AI run); no deterministic "these pages are affected" step |
| Self-hosted portal | Live/static portal + Docker image; no auth, single user |
| Telemetry off | Done (`common.ensure_path`), except `DO_NOT_TRACK` in per-repo CI snippets |

Target: Apipana first (Java/Kotlin, GitLab, RabbitMQ, Helm), designed generic. Local stays the default mode.

## 1. Phases

| Phase | Line | Notes |
|---|---|---|
| 0 | `fix(ci)` binary name | CI templates install `camarones` but call `camaron` (since 973d0a5) — generated pipelines fail today |
| 1 | **A** provenance & freshness · **B** service catalog · **C** evaluation bank | One branch + PR per line, in that order (C uses A's freshness and unit `base`; B reuses A's `changed_since`) |
| 2 | Change impact: `camaron impact` + MR/PR comment | Changed files → pages, services, flows; no AI. Uses A + B |
| 3 | Extended MCP | Service card, impact, `read_doc(section)` (= P7 of [ai-first-docs.md](ai-first-docs.md), built once), verify sources, abstain without evidence |
| 4 | "Grill" interviews | Answers become checkable decisions (idempotency key, retention, timeout, late reply) → Given/When/Then examples and contract-test proposals (inspired by mattpocock/skills) |
| 5 | Self-hosted portal | Deployable, OIDC in front, read-only, multi-project; local remains the default |
| ∥ | AI-first docs P1–P10 | [ai-first-docs.md](ai-first-docs.md), parallel line |

Rules for every PR (AGENTS.md): three OSes, TDD with `make_workspace` + `isolated_env`, 3.x compatibility (new fields
optional, nothing human or confirmed rewritten), bump `VERSIONS["kit"]` (3.6.0 / 3.7.0 / 3.8.0), no new external tools
(stdlib + PyYAML), wizard/portal strings in es + en, new modules added to `MODULES` in `tests/conftest.py`.

## 2. Phase 0 — `fix(ci)`

`.camarones/ci/umbrella.gitlab-ci.yml` and `umbrella.github.yml` install `/usr/local/bin/camarones` and the jobs call
`camaron …`. Install both names (alias, compatibility) and add a text test: every template calls a binary it installs.

## 3. Line A — provenance & freshness (`feat/provenance-freshness`, 3.6.0)

**Formats**

- New kit-written frontmatter (CONVENTIONS §2):
  ```yaml
  x-sources-at: {body_sha: <16hex>, at: <iso>, via: edit|verified, by: <name if verified>,
                 repos: {orders-service: <sha40>}}
  ```
  Tolerant reader (a flat `{repo: sha}` is accepted). No field → fall back to the repo sha in `.state.json`.
  Translations are not stamped.
- `docs/.human.json` (committed ledger): per page `{owner, page_sha, blocks: [hash], by, at, via}`. Blocks are a
  multiset: moving one is fine, editing or deleting it is a violation.
- `.state.json` gets an optional `update: {last: {result, source, unit, at, detail}, last_ok}`.
- `plan.yaml`: optional `base` per unit (cam-docs HEAD when it enters `doing`); `plan.sync` must keep it.
- Git cache: `.camarones/.cache/freshness.json`.

**Stamp policy (decided)**: renewed when the body changes (plan done, CLI `check`, checkpoint, mark-documented) and
explicitly with `camaron verified`. A **portal save renews only if the page was not stale**; if it was, the editor shows
an unchecked "I re-checked the sources" box. `x-owner: human` pages are never stamped automatically. Restamping lives
in the CLI branch of `check`, never inside `docs.check()` (the portal and wizard call it on GET).

**Code**

- New `lib/freshness.py`: `parse_source` (refactor of `docs.repo_file_exists`), `read_stamp`, `stamp_fm`, `repo_head`
  (memoized), `changed_since` (`git diff --name-status -M -z`; `None` = unknown: sha missing, repo missing, git missing,
  shallow clone), `page_freshness` → `fresh|stale|unknown|n/a` + changed sources + `#L` beyond end of file,
  `restamp_changed` (idempotent), `verify`, `record_update` / `last_update`.
- New `lib/protect.py`: block and human-page hashes, baseline from `git show HEAD:` when no ledger exists, `record`
  (human actions only; refuses under `CAMARONES_UNATTENDED=1`), `violations`, `assert_clean`, `check` in
  `quality.CHECKS`. Tamper-evident, not a security boundary (autopilot agents run without permission prompts); the
  ledger shows up in MR diffs.
- `docs.py`: `doc_status` adds `freshness`; `summary` adds `stale`; `check` WARNs stale (ERROR with `--strict`), ranges,
  unknown repos, last update failed; `confirm` records protection; `mark_documented` restamps and records `ok`.
- `plan.py`: `set_status` records `base`; `done` runs `protect.assert_clean()` (refuses, status unchanged) then
  `restamp_changed()`; `_run_agent` exports `CAMARONES_UNATTENDED=1`; autopilot records `failed` / `ok`.
- `env.checkpoint_commit`: restamp + ledger baseline before `git add`.
- `serve.py`: `tree` with `stale` and `lastUpdate`; `read` uses a single-page `doc_status` (not `collect()`); `write`
  records protection and applies the stamp policy above.
- `mcp.py`: `read_doc` header `freshness: stale (N sources changed since repo@sha: …)`; `[draft, stale]` in
  `search_docs` / `list_docs`; `doc_status` with stale count and "last update FAILED".
- Portal: ⏳ in the tree, per-page banner with changed sources, global banner when the last update failed, Review list;
  the static export inherits it from `tree.json` / `doc/*.json`.
- Wizard `do_status`: ⏳ counter and the `doc-fixes` offer (es/en).
- CI umbrella: `CAMARONES_UNATTENDED=1` for the agent step; `camaron update-status failed …` when the agent fails.
- Small fix: `quickarch.save()` must not rewrite a `first-look.md` with `x-owner: human` (as `radar.run` already does).
- Docs: CONVENTIONS §2/§3/§9/§10, PLAYBOOK (`update` uses `status --stale`, `doc-fixes`, session protocol), skill
  `cam-docs-update`, `tutorial.py` check table (es/en).

**CLI (additions only)**: `verified FILE.. [--by]` · `protect FILE.. --by` (human; refuses unattended) ·
`update-status [ok|failed] [--unit --source --detail --json]` · `status --stale` · `status --json` rows with `freshness`.

**Tests (TDD order)**: characterize `repo_file_exists`, `mcp.handle`, `serve.tree/read/write/status` → flat/nested
stamp → `.state.json` fallback (cited file changed = stale, unrelated file = fresh) → page stamp, rename, directory
prefix → `#L` beyond end (CRLF) → unknown without crash (missing sha, repo not cloned, git exit 127) →
`restamp_changed` idempotent and skipping human pages → `verified` → checkpoint / plan done restamp → check WARN,
`--strict` ERROR, `serve.status()` writes nothing → update status (the `pilot` fixture in `test_autopilot.py`) →
protection (normalization, HEAD baseline, move vs edit, owner flipped, `plan done` refused, `protect` clears it,
unattended refused) → **an old 3.x project is byte-identical after `status` / `check` / `llms`**.

## 4. Line B — service catalog (`feat/service-catalog`, 3.7.0)

**Format**: `docs/catalog/<repo>.yaml`, `schema: camaron.catalog/v1`. LikeC4 stays the *intended* architecture; the
catalog holds *observed* facts with evidence; `check` warns about divergences between them.

- `declared` (team; never rewritten by the kit; humans use `note:` fields because PyYAML drops comments), `observed`
  (owner, stack, apis, events, datastores + migrations; rewritten on every scan), `generated` (kit version, commits,
  truncation, unmatched env files), `relations` (outbound; inbound computed).
- Relation id `<proto>:<from>-><to>[:<qualifier>]`: http has no qualifier (endpoints in `via`), amqp
  `<exchange>/<routing-key>`, kafka `<topic>`, db `db:<id>`. `to` = repo | `ext:<host>` | `db:` | `idp:` | `?`.
- **Evidence per relation** (decided level): `state` ∈ {declared-by-team, observed-in-code, observed-in-environment,
  inferred-by-ai}, `source` ∈ {extract, ai, interview, human}, `kind`, `ref repo:path#L`, `commit`, `env`, `by`, `at`.
- Merge by id: `extract` evidence is replaced, the rest kept; a relation that lost its code evidence gets
  `no-longer-observed`; no rewrite when nothing changed. Conflicts (`target-differs`, `owner-differs`, `not-observed`,
  `c4-divergence`) are computed on read, never merged. Events are joined by exchange/topic, never by class name.

**Static draft (no AI), decided scope**: stack; RabbitMQ/Kafka chain publisher → exchange/topic → routing key → queue →
consumer across repos; HTTP clients (`@FeignClient`, WebClient/RestClient/RestTemplate, `@Value`, URLs in
`application*.yml` / env, Spring relaxed binding, `${a:b}`, host + port + context-path aliases); contracts parsed when
present (OpenAPI yaml/json, AsyncAPI 2/3, proto; parse errors become evidence); datastores + Flyway / Liquibase /
`schema.sql`; owner from `catalog-info.yaml` and CODEOWNERS. **Observed in environment** = Helm/K8s files in the repos
(`values*.yaml` per env, overlays, manifests, ConfigMaps; templates with `{{` skipped; no helm binary).

**Code**: new `lib/extract.py` (reuses `quickarch.files`, `SKIP_DIRS`, `MAX_FILES`, `MAX_BYTES`, `DB_PATTERNS`,
`RABBIT_DEPS`, `KAFKA_DEPS`, `PUBLISH`, `CONSUME`, `radar.read_backstage`); new `lib/catalog.py` (`load/save`,
`extract_all`, `resolve_chains` with `*`/`#` wildcards, direct and fanout, `merge`, `run`, `relate`, `card`, `c4_edges`
via `metadata { repo }`, `divergences`, `check_catalog` in `quality.CHECKS`, stale AI/declared evidence via
`freshness.changed_since`). `serve.py` `GET /api/catalog[?service=]`; export `api/catalog.json` +
`api/catalog/<svc>.json`. Portal **Services** tab (read-only card: owner, stack, APIs, events with chains, datastores,
in/out dependencies with state chips, conflicts, C4 divergences, expandable evidence). Wizard runs `catalog.run` after
`radar.run`. AI completion inside **`discovery-cross`** (`catalog relate --state inferred-by-ai`); interviews promote to
`declared-by-team`. CONVENTIONS §11. `make_workspace(..., files=None)` + synthetic Rabbit/Kafka/Helm fixtures.

**CLI**: `catalog [scan] [--dry-run --json --service]` · `catalog show SERVICE [--json]` ·
`catalog relate FROM TO --kind --state --ref --by [--via k=v] [--note]`.

**Tests**: stable ids → owner conflict → stack → HTTP (Feign + placeholder, localhost:port/context, `ext:`) → Rabbit
chain across two repos (wildcard, default exchange, dangling) → Kafka + Cloud Stream → OpenAPI / AsyncAPI v2/v3 / proto
/ malformed → datastores, shared DB, Flyway create→drop, Liquibase → Helm (`env`, env vs code conflict, `{{` skipped,
ConfigMap) → merge (declared survives, extract refreshed, `no-longer-observed`, second run byte-identical) → `relate` →
`check_catalog` → C4 divergences (direct, via queue, nested, both ways) → portal API + export → project without catalog
prints nothing new → CRLF line numbers and posix refs. Known limit: one entry per repo (multi-service monorepos later).

## 5. Line C — evaluation bank (`feat/eval-bank`, 3.8.0)

**Formats**: `docs/eval/questions.yaml` (`schema: camaron.eval/v1`): `id`, `q`, `lang`, `expect_pages`,
`expect_facts` (list = any-of, `re:` prefix), `abstain`, `state` draft|confirmed|discarded, `proposed {by, unit, at}`,
`reviewed {by, at, sha}` (edited after confirmation → scored as draft + WARN). `docs/eval/history.jsonl`, append-only,
`merge=union` in a managed `.gitattributes` block: date, commit, dirty, kit, mode, agent, k, counts,
`scores {hit@1, hit@k, mrr, facts, fresh}`, `agent_scores`, drafts apart. Per-question detail in
`.camarones/.cache/eval/last.json`.

**Decisions**: questions are **proposed by AI** — every unit that writes pages proposes 1–3 about its own pages; **only
confirmed questions score**; a unit with no proposals gets a WARN at `plan done` (malformed proposals are refused);
modes = deterministic + optional agent, **no LLM judge**; history versioned + portal trend.

**Code**: new `lib/evals.py`: `propose` (agents; validates pages via `iter_docs`), `review` (human; refuses
unattended), `fact_hit`, `score_deterministic` (rank in `docs.search`, facts in expected pages, `fresh` from A),
`run_agent_eval` — Claude with a temporary `--mcp-config` + `--strict-mcp-config` + `--allowedTools` limited to the
kit MCP and the rest disallowed, run from an empty temp folder, single-line prompt (Windows `.cmd` shims), timeout;
**Codex experimental**, recording every non-MCP call; scored without a judge (cites an expected page, facts, correct
abstention) — `record`, `history`, `unit_pages(uid)` (diff since A's `base`), `after_done`, `check_bank`.
`plan.prompt()` asks for proposals in page-writing units (interviews, discovery, questionnaire and wizard units exempt).
`serve.py` `GET /api/eval`, `POST /api/eval/review`; export `api/eval.json`. Portal **Evaluation** tab (inline SVG
trend per mode, last run table, draft queue with Confirm/Discard in live mode). Wizard: "n questions to confirm" in
Review. PLAYBOOK session protocol, CONVENTIONS §12.

**CLI**: `eval [run] [--k --agent claude|codex --ids --include-drafts --no-record --json]` ·
`eval propose UNIT --q --page.. --fact.. [--abstain --lang]` · `eval confirm|discard ID.. --by` ·
`eval list [--state --json]` · `eval history [--json]`.

**Tests**: round-trip / empty bank → `propose` and stable id → human `review` + sha → exact hit@k / MRR, fact
normalization, `fresh` drops on a stale page → drafts apart → history line, `--no-record`, dirty → `base` in the plan,
WARN without proposals, malformed refused, interviews exempt → agent mode with a mocked runner (strict flags,
single-line prompt, parsing, abstention, broken output = fail not crash) → portal GET/POST + export → CLI `eval --json`.

## 6. Risks

- Shallow clones or rewritten history → freshness `unknown` with a clear WARN.
- Performance: memoized HEADs, cached diffs, single-page reads in portal and MCP.
- Regex false positives in extraction → explicit evidence states and conflicts; `truncated` suppresses "not observed".
- Rebase conflicts on `.human.json` / `.state.json` → minimal writes, sorted keys.
- Agent-mode eval spends tokens → opt-in, never mixed with the deterministic trend.

## 7. Verification

1. `uv run pytest` green on each PR (CI on the three OSes).
2. Sandbox (`uv run scripts/sandbox.py reset`, then `cli init/detect/radar/arch-draft --save`):
   - **A**: a page citing `OwnerRestControllerV1.java` → `checkpoint`, `mark-documented`; commit in the repo →
     `status --stale` lists it, `check` WARNs, `check --strict` exits 1, `verified` clears it; human block + `protect`
     + edit → `check` ERROR and `plan done` refused; `mcp` over stdin shows stale; `portal` → `tree.json` has `stale`;
     `update-status failed` → banner.
   - **B**: `cli catalog --json` → stack, OpenAPI endpoints, datastores and `schema.sql` tables,
     `http:spring-petclinic-angular->spring-petclinic-rest` observed in code; a `declared-by-team` relation survives a
     rescan; `portal` exports `api/catalog/*.json`. Rabbit and Helm come from synthetic fixtures.
   - **C**: `eval propose` + `eval confirm` + `eval --json` appends a history line; `portal` exports `api/eval.json`;
     `eval --agent claude` only with the owner's go-ahead.
   - Finish with `reset` and `traces` (exit 0).
3. An old 3.x project opens and passes `status` / `check` with no byte changes.

## 8. Left out of the kit (from the report)

| Topic | Why |
|---|---|
| AI MR reviewers (OpenCodeReview, PR-Agent, GitLab Duo, CodeRabbit) | A team CI choice, not documentation; phase 2 only posts deterministic impact |
| Gateways (LiteLLM, OmniRoute, Portkey…) | No problem measured in a local kit |
| Output compression (RTK, context-mode, Headroom, Caveman) | Not shown to save cost globally; a per-user experiment |
| External memory (claude-mem, LangMem) | `cam-docs/` *is* the versioned memory; inferred memory must not replace it |
| LangGraph / LangSmith / Deep Agents | The plan + autopilot already resume work; revisit only with a resumable multi-step need |
| Parallel-agent managers | Out of scope for the kit |

Deferred: Backstage `catalog-info.yaml` and EventCatalog exports, docker-compose as `env: local`, symbol anchors
(I1/I4 in [tooling-candidates.md](tooling-candidates.md)), RabbitMQ `definitions.json` and OpenTelemetry service graphs
as more environment sources.
