# Tooling candidates for the Camarones method

Research pass, 2026-09-24. Goal: list every tool that could improve how Camarones documents a multi-repo project, so we
can **discard** in a second pass. Nothing here is a decision.

**How to read it**

- Every candidate has an ID (`A3`, `J1`…) so we can discard by ID.
- **Signal** is a first-pass opinion only: 🟢 strong fit · 🟡 worth a look · 🔴 probably not (kept for completeness).
- **Fit** criteria used: runs locally/offline (code never leaves the machine), no kit files in service repos, works with
  Claude Code *and* Codex, cross-platform (macOS/Windows/Linux), low install weight (the kit prefers stdlib / `uv` /
  pinned npm), license compatible with internal use.
- † = listed from prior knowledge, not re-verified in this pass (check version/status before adopting).

## 0. The method today and the gaps that drive this list

| Stage | Today | Observed gap |
|---|---|---|
| Repo onboarding | wizard `sync`, `detect_repos` | — |
| First look (no AI) | `quickarch.py` regex scan → LikeC4 draft | Regex heuristics; no contract extraction, no runtime evidence |
| Code navigation for agents | graphify 0.9.65 (AST graph) + `repo_graph` MCP tool | Single engine; no LSP-precise references; no impact/blast radius |
| Discovery / interviews | Agent + DDD interview units | Context map and glossary are free-form Markdown, not a model |
| Repo wikis | OpenWiki 0.5.2 | One engine; one full agent run per repo |
| Architecture | LikeC4 1.59.4 (`arch-validate`) | LikeC4's own MCP / agent skills not used |
| Data | Agent writes `erDiagram` by hand | No DB/migration introspection |
| Flows | Agent-written sequence diagrams + LikeC4 dynamic views | Evidence only from code, never from real traffic |
| Diagrams | Mermaid in Markdown | Mermaid syntax never validated |
| Quality gate | `CLI check` (`lib/docs.py:338`) | Checks frontmatter, orphan `x-sources`, trust, i18n. **No link check** (the PLAYBOOK's `doc-fixes` step assumes one), no prose lint, no secret scan, no claim verification |
| Agent retrieval | `camarones` MCP `search_docs` (`lib/docs.py:354`) | Naive term counting over every file per query; no ranking, no semantic match |
| Portal | Own no-build app (marked, DOMPurify, Mermaid) | Static export search is client-side; no catalog export |
| Plan / sessions | `plan.yaml`, `handoff.md`, checkpoints | Custom; fine for one agent, untested for parallel agents |
| i18n | Agent translates, hash stamp via `CLI translated` | Every translation is a full agent pass |
| Opt-in reviews | `security-review`, `architecture-review` (beta) | Pure LLM reasoning; no scanner evidence |

---

## A. Repo wikis — alternatives or complements to OpenWiki

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| A1 | [CodeWiki (FSoft-AI4Code)](https://github.com/FSoft-AI4Code/CodeWiki) | Open-source repo-level doc generator (ACL 2026). Builds a dependency graph, clusters it into a module tree, one agent per leaf module, parents written from children, Mermaid diagrams | Scales to very large repos (1M+ LOC) where a single OpenWiki run struggles; ships **CodeWikiBench**, a benchmark we could reuse to score our own wikis | 11 languages incl. Java/Kotlin/TS. Needs an LLM provider key; check if it can drive Claude Code/Codex headless | 🟡 |
| A2 | [deepwiki-open (AsyncFuncAI)](https://github.com/AsyncFuncAI/deepwiki-open) | Self-hosted DeepWiki clone: RAG over the repo, wiki + diagrams + chat | Supports Ollama → fully local generation for sensitive code | Web app + API server (heavier than the kit); local-path / self-hosted GitLab support was an open issue | 🟡 |
| A3 | [RepoWiki](https://github.com/he-yufeng/RepoWiki) | Open-source DeepWiki alternative, terminal or browser | Lightweight CLI option | Small project; maturity unknown | 🔴 |
| A4 | [repowise](https://github.com/repowise-dev/repowise) | Self-hosted "codebase intelligence": dependency graph + git analytics (churn, ownership, bus factor) + auto docs + decisions, served over MCP; SQLite; AGPL-3.0 | Adds **git behavioural signals** we lack (hotspots, ownership, dead code) — useful for `architecture-review`, `decisions-quality` and the update loop | AGPL: fine to run as a tool, not to embed. Overlaps graphify + OpenWiki; would be a replacement, not an add-on | 🟡 |
| A5 | [DeepWiki (Cognition)](https://deepwiki.com) | Hosted wiki for public GitHub repos + MCP server | Useful for **third-party / OSS dependencies** the project uses, not for private repos | Public repos only | 🔴 for private code, 🟡 as a lookup MCP |
| A6 | [Google Code Wiki](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/) | Gemini-generated, auto-updating wikis with architecture/class/sequence diagrams | Same use as A5 | Public preview; private-repo Gemini CLI extension still on a waitlist | 🔴 |
| A7 | Swimm / Mintlify / GitBook / DeepDocs (SaaS) | Commercial doc platforms with AI generation and code coupling | Reference for features (see section I) | Code leaves the machine; cost | 🔴 |

## B. Code graph and code intelligence — alternatives or complements to graphify

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| B1 | [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Tree-sitter → SQLite knowledge graph, single static C binary, 14 MCP tools, incremental re-index by content hash, HTTP routes and cross-service links | Paper reports ~10× fewer tokens and ~2× fewer tool calls across 31 repos. Zero deps fits the kit; **cross-service links** is exactly `discovery-cross` | Very young project (Feb 2026); verify Windows build and Java/Kotlin quality | 🟢 |
| B2 | [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | Tree-sitter graph + MCP (16 tools): impact/blast radius with confidence, process-grouped search, change detection; one global registry serves many repos | **Impact analysis** would sharpen the `update` unit (changed file → affected flows/pages); multi-repo registry matches our workspace | Stores the graph in KuzuDB† (Kùzu's upstream status should be checked); browser mode also exists | 🟡 |
| B3 | [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | MCP + CLI indexing code into a graph DB | Similar to B1/B2 | Needs a graph DB service | 🔴 |
| B4 | [code-graph-mcp](https://github.com/sdsrss/code-graph-mcp) | AST graph MCP for Claude Code: semantic search, call graph, **HTTP route tracing**, impact | Route tracing helps flow documentation | 10 languages; small project | 🟡 |
| B5 | [Serena](https://github.com/oraios/serena) | MCP server backed by real language servers (LSP): `find_symbol`, `find_referencing_symbols`… 30+ languages, MIT | **Exact** references (graphify is AST-only, so cross-file calls through interfaces/DI can be missed). Good for evidence lines `#Lx-Ly` | Needs each language server installed (jdtls for Java is heavy); per-repo project activation | 🟡 |
| B6 | Sourcegraph SCIP indexers (scip-java, scip-typescript…) † | Precise, compiler-grade code index format | Precise cross-repo navigation | Needs builds to succeed; heavy for a local kit | 🔴 |
| B7 | ast-grep † | Structural search/rewrite with tree-sitter patterns (CLI + MCP) | Replace some `quickarch.py` regexes (listeners, clients, `convertAndSend`) with AST patterns → fewer false positives | Single binary; rules as YAML | 🟢 |
| B8 | Semgrep (CE) † | Pattern-based static analysis, many rulesets | Same as B7 for extraction, plus evidence for `security-review` (see N1) | LGPL engine; some rules are commercial | 🟡 |
| B9 | Aider repo-map † | Tree-sitter + PageRank "most relevant symbols" summary | Idea to borrow: a ranked, token-budgeted repo map in each `discovery` prompt | Technique, not a dependency | 🟡 |
| B10 | Zoekt † | Fast trigram code search (Sourcegraph/Google) | Fast grep across all repos for agents and the portal | Server process; overkill for local | 🔴 |

## C. Static and runtime architecture extraction — complements to `quickarch` and discovery

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| C1 | springdoc-openapi (build-time plugin) † | Generates OpenAPI from Spring controllers at build | Discovery's "truth order" starts at OpenAPI; many repos have none. Generating it gives the agent a contract instead of reading controllers | Requires the repo to build; run in a temp dir, never commit into the service repo | 🟡 |
| C2 | Springwolf † | Generates **AsyncAPI** from Spring Kafka/Rabbit/SQS listeners and producers | Same as C1 for events; direct input for EventCatalog (D1) and for `-[async]->` edges | Library added at build time; same "no files in repo" caveat | 🟡 |
| C3 | Spring Modulith Documenter † | Generates C4/PlantUML component diagrams and module canvases from a Spring Modulith app | Component views for `repos/<repo>.c4` with real module boundaries | Only useful for repos using Spring Modulith | 🔴 |
| C4 | [jQAssistant](https://jqassistant.github.io/jqassistant/current/) | Scans bytecode, Maven, git into Neo4j; Cypher rules; arc42 reports | Queryable structural facts for Java repos; rule reports usable as `architecture-review` evidence | Needs Neo4j (embedded available); Java-only | 🔴 |
| C5 | ArchUnit † | Architecture rules as JUnit tests | Turn documented architecture (hexagonal layers, allowed deps) into executable checks → docs that fail when code drifts | Lives in the service repo's tests (conflicts with "no kit files"); propose to teams, don't install | 🟡 as a recommendation in `decisions-quality` |
| C6 | dependency-cruiser / Madge † | Dependency graphs and rules for JS/TS | Same as C5 for the frontend repos | JS/TS only | 🔴 |
| C7 | [OpenTelemetry service graph](https://oneuptime.com/blog/post/2026-02-06-living-architecture-diagram-otel-service-graph/view) (Collector `servicegraph` connector, Tempo, Jaeger dependencies) | Service-to-service edges derived from real traces | **Runtime evidence** for C4 relationships and flows: confirm INFERRED cross-repo edges, find calls the code scan missed | Only if the project already has tracing; import as a read-only source (e.g. `CLI import-traces`) | 🟢 where tracing exists |
| C8 | KubeDiagrams † | Diagrams from Kubernetes manifests / Helm charts | Draft `deployment.c4` from real Helm/K8s files | Output is images, not LikeC4; would need a converter | 🔴 |
| C9 | Syft (SBOM) † | Software bill of materials for a repo or image | Exact stack/versions for discovery's "Stack" section and `security-review` | Single binary; CycloneDX/SPDX output | 🟡 |

## D. Contracts and event documentation

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| D1 | [EventCatalog](https://www.eventcatalog.dev/) | Docs-as-code catalog of **domains, services, events, commands, channels, flows**; generators from AsyncAPI/OpenAPI/schema registries; visualizer | Overlaps our `domain` + `flows` output and adds a first-class event/message view we don't have. Could be an export target or a portal tab | Node/Astro site; some features are paid tiers | 🟡 |
| D2 | AsyncAPI CLI / Studio † | Validate/render AsyncAPI documents | Validate C2 output; render event contracts in the portal | — | 🔴 unless C2 is adopted |
| D3 | [Spectral](https://github.com/stoplightio/spectral) | OpenAPI/AsyncAPI linter | Lint contracts found in repos during discovery; findings for `architecture-review` | npm | 🔴 |
| D4 | [oasdiff](https://github.com/oasdiff/oasdiff) | OpenAPI diff with breaking-change detection | In the `update` loop: "the API changed" → which flows/pages to revisit, with a precise changelog | Single Go binary | 🟡 |
| D5 | Scalar / Redoc † | OpenAPI reference renderers | Render repo contracts inside the portal (Docs → repos/<repo>/api) | Static JS | 🟡 |

## E. Architecture and domain modelling — around LikeC4

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| E1 | [LikeC4 MCP server + Agent Skills](https://likec4.dev/tooling/ai-tools/) | LikeC4's own MCP (query the model in natural language) and skills that teach agents the DSL | We already pin LikeC4: the skills should cut `arch-validate` failures (the CONVENTIONS "syntax traps" list), the MCP lets implementing agents ask "who calls X?" against the confirmed model | Near-zero cost; check it ships in 1.59.x | 🟢 |
| E2 | [Structurizr DSL + MCP](https://docs.structurizr.com/ai/mcp) | Reference C4 models-as-code tool; hosted MCP with DSL/PlantUML/Mermaid tools | Alternative engine; its C4 semantics are built in (LikeC4 needs our `spec.c4`) | Switching cost is high; hosted MCP sends the model out | 🔴 |
| E3 | IcePanel (SaaS) | Visual C4 modelling with flows, for non-technical audiences | Stakeholder-friendly views | Proprietary, cloud | 🔴 |
| E4 | Context Mapper † | DDD DSL (CML) for bounded contexts and context-map relationships (customer/supplier, ACL, shared kernel); generators to diagrams, service cuts | Turns `domain/bounded-contexts.md` into a validated model — the `interview-context` unit already asks exactly these relationship types | Java/VS Code tooling; a third DSL next to LikeC4 and Mermaid | 🟡 |
| E5 | Egon.io (Domain Storytelling) † | Browser tool to record domain stories as pictographic diagrams | Visual aid during `interview-*` units with business people | Manual, not agent-driven | 🔴 |
| E6 | arc42 template † | Standard 12-section architecture doc structure | Cross-check that our sections (quality, risks, constraints, crosscutting concepts) cover arc42; map pages to it for teams that require arc42 | Template, not a tool | 🟡 |
| E7 | [log4brains](https://github.com/thomvaill/log4brains) / MADR / adr-tools † | ADR management: templates, CLI to create/supersede, static ADR site with timeline | MADR as the template for `docs/decisions/`; supersede links between ADRs | Our portal already renders ADRs; log4brains' site would duplicate it | 🟡 MADR, 🔴 log4brains |

## F. Data documentation

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| F1 | [tbls](https://github.com/k1LoW/tbls) | CI-friendly DB documenter (Go): Markdown + ER diagrams (incl. **Mermaid**), many engines incl. Postgres, MySQL, SQL Server, DynamoDB | `data` unit gets a real schema (tables, columns, FKs, comments) instead of an agent-inferred `erDiagram`; `tbls diff` detects schema drift | Needs a DB connection: run against a local DB built from the repo's Liquibase/Flyway migrations (compose) | 🟢 |
| F2 | [SchemaSpy](https://github.com/schemaspy/schemaspy) | Java DB documenter, HTML + ER | Same as F1 | HTML output fits worse than tbls' Markdown | 🔴 |
| F3 | Liquibase `db-doc` / Flyway info † | Changelog-based docs from the migration tool itself | Migration history per table for the ownership table | Only for repos using them | 🟡 |
| F4 | Atlas `schema inspect` † | Schema as code; inspect → HCL/SQL/ERD | Alternative to F1 | — | 🔴 |

## G. Diagrams

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| G1 | mermaid-cli (`mmdc`) † | Renders Mermaid headless | **Validate every Mermaid block in `CLI check`** — broken diagrams currently reach the portal silently | Pulls Puppeteer/Chromium (heavy); alternative: validate with Mermaid's `parse()` in Node without a browser | 🟢 |
| G2 | [Kroki](https://kroki.io/) | One API for D2, PlantUML, Mermaid, Structurizr, Excalidraw, BPMN… | Lets pages use other notations (BPMN for business processes) | Self-host via Docker, or it sends diagrams out | 🔴 |
| G3 | D2 † | Diagram language with good auto-layout | Nicer large diagrams than Mermaid | Another notation to support | 🔴 |
| G4 | Mermaid ELK layout † | Alternative layout engine for Mermaid flowcharts | Readability of dense flowcharts without changing notation | Portal-side config | 🟡 |

## H. Documentation quality gate (extends `CLI check`)

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| H1 | [lychee](https://github.com/lycheeverse/lychee) | Fast link checker (Rust) for Markdown/HTML | Implements the **broken-link check the PLAYBOOK already promises** (internal links, anchors, i18n pairs) | Single binary; or do internal links in stdlib Python and skip the dependency | 🟢 |
| H2 | markdownlint-cli2 † | Markdown structure linter | Consistent headings/lists across agent-written pages | npm; config lives in `cam-docs/` | 🟡 |
| H3 | [Vale](https://vale.sh/) | Prose linter with custom styles and vocabularies | Enforce the **DDD glossary** (preferred terms, banned synonyms) and a house style in EN/ES | Go binary; vocabulary can be generated from `glossary.md` | 🟢 |
| H4 | [Doc Detective](https://docs.doc-detective.com/) | Executes the procedures in docs (commands, API calls, UI steps) as tests; has agent skills | Verify each repo brief's "how to build/test/run" actually works → confirmed-by-execution | Runs commands: sandbox it; opt-in per repo | 🟡 |
| H5 | [gitleaks](https://github.com/gitleaks/gitleaks) / TruffleHog | Secret scanners (regex+entropy / live verification) | Discovery copies config snippets into docs: scan `cam-docs/` **before commit and before `portal` export** | gitleaks: single binary, offline, pre-commit-friendly | 🟢 |
| H6 | [promptfoo](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/) | Eval framework with LLM-as-judge, factuality and grounding assertions | A "claim audit": sample statements + their `x-sources`, ask a judge if the source supports them → score per page before human review | Costs tokens; best as an opt-in unit or CI job | 🟡 |
| H7 | CodeWikiBench (from A1) | Benchmark/rubric for repo-level documentation quality | Measure whether kit changes make docs better, not just different | Research artefact | 🟡 |
| H8 | pre-commit framework † | Git hook manager | One place to run H1/H2/H3/H5 on `cam-docs/` commits | Python; fits `uv` | 🟡 |

## I. Freshness and drift (extends `changes` / `x-sources`)

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| I1 | [Swimm](https://swimm.io) (reference) | Docs coupled to code via "smart tokens"; auto-sync through refactors; CI flags stale docs | Idea to borrow: anchor `x-sources` to **symbols** (class/method) instead of line ranges, so refactors don't orphan pages | SaaS; borrow the idea, not the tool | 🟡 idea |
| I2 | [DeepDocs](https://medium.com/@deepdocs/deepdocs-keep-your-documentation-in-sync-with-your-code-73699b73c1d2) (reference) | GitHub agent: on each commit, proposes doc updates on a branch with a report | Same pattern as our CI `update` templates; compare their report format | GitHub-only SaaS | 🔴 |
| I3 | code-maat / CodeScene † | Behavioural code analysis from git: hotspots, temporal coupling, knowledge loss | Evidence for `architecture-review` and tech debt; "who knows this repo" for the interviews | code-maat is OSS (JVM); CodeScene is commercial | 🟡 |
| I4 | Symbol anchors via B1/B5 | Resolve `x-sources` like `orders:OrderService#place` through the code graph/LSP | Sources that survive line shifts; orphan detection gets precise | Needs a stable graph API | 🟡 |

## J. Retrieval for agents and the portal (`camarones` MCP, search)

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| J1 | SQLite FTS5 (Python stdlib `sqlite3`) † | Built-in full-text index with BM25 ranking | Replace the per-query file scan in `search_docs` with a ranked index; **zero new dependencies** | FTS5 is compiled into most Python builds; verify on Windows `uv` Python | 🟢 |
| J2 | [qmd](https://github.com/tobi/qmd) | Local hybrid search for Markdown: BM25 + vectors + LLM reranking (GGUF models via node-llama-cpp), MCP stdio/HTTP | Semantic search ("how do refunds work?") over docs + wikis, fully local | Downloads local models (hundreds of MB); Node | 🟡 |
| J3 | sqlite-vec † | Vector search extension for SQLite | Add semantic search on top of J1 without a server | Needs an embedding model | 🔴 |
| J4 | [Pagefind](https://pagefind.app) † | Static-site search index built at export time | Better search for the **static** portal export (`CLI portal`) with tiny payloads | Binary/npm at build time only | 🟡 |
| J5 | Context7 MCP † | Up-to-date docs of third-party libraries for agents | Agents documenting a repo can check framework semantics (Spring, Quarkus versions) | Hosted | 🔴 |
| J6 | llms.txt conventions (`llms-full.txt`) † | Emerging standard for AI-readable site indexes | We already write `llms.txt`; add `llms-full.txt` in the static export | Trivial | 🟡 |

## K. Portal and publishing

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| K1 | [Backstage](https://backstage.io/docs/features/software-catalog/descriptor-format/) catalog + TechDocs | Developer portal; `catalog-info.yaml` entities (Component, API, System, Domain, Resource) with typed relations | **Export target**: generate `catalog-info.yaml` from `model.c4` + discovery so companies with Backstage consume our work | Export only — never run Backstage from the kit; writing into service repos would need the teams' consent | 🟡 |
| K2 | [Zensical](https://squidfunk.github.io/mkdocs-material/blog/2025/11/05/zensical/) | Successor of Material for MkDocs (which ends maintenance 2026-11-05), MIT | Alternative static export for teams wanting a "standard" docs site | Our own portal already covers this; relevant only if we drop it | 🔴 |
| K3 | Astro Starlight / Docusaurus / VitePress † | Static docs frameworks | Same as K2 | Build step + npm, against the kit's no-build choice | 🔴 |
| K4 | Quartz / Obsidian † | Markdown knowledge garden / vault | Open `cam-docs/docs` as an Obsidian vault (graph view, backlinks) with no extra work | Only needs wiki-link compatibility checks | 🔴 |

## L. Plan, sessions and agent orchestration

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| L1 | [Beads (`bd`)](https://github.com/gastownhall/beads) | Git-friendly, dependency-aware issue graph for coding agents (Dolt or SQLite), hash IDs, "ready" detection, memory decay of closed tasks | Replacement for `plan.yaml` if we want **parallel agents** (one per repo) without merge conflicts, plus a standard CLI both Claude and Codex already know | Go binary + DB; our plan is simple and works — high switching cost | 🟡 |
| L2 | Claude Agent SDK / `claude -p` headless † | Programmatic Claude Code sessions | Run independent units (discovery per repo, wikis) unattended in parallel, with structured JSON results | We already run headless for wikis; generalise to other units | 🟡 |
| L3 | Codex `exec` † | Codex non-interactive mode | Same as L2 for Codex users | — | 🟡 |
| L4 | Claude Code subagents / hooks † | Scoped sub-agents and lifecycle hooks | A `discovery` subagent per repo returning only the summary keeps the main context small; a `Stop` hook could enforce `plan note` | Claude-only; keep Codex parity | 🟡 |
| L5 | GitHub Spec Kit / Task Master † | Spec-driven agent workflows | Inspiration only; different goal (building features) | — | 🔴 |

## M. Interviews and knowledge capture

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| M1 | Whisper / whisper.cpp † | Local speech-to-text | Record a 30-min interview with an architect, transcribe locally, let the `interview-*` unit extract answers | Local models; privacy consent needed | 🟡 |
| M2 | NotebookLM (MCP available in this environment) | Grounded Q&A over uploaded sources | Load existing PDFs/Confluence exports as interview material | Sends content to Google | 🔴 for private code |
| M3 | Confluence / Jira / Notion MCP connectors | Read existing wikis and tickets | Discovery of **historical decisions** (ADRs hidden in tickets and old wiki pages) for `interview-history` | Read-only use; auth per company | 🟡 |

## N. Evidence for the beta review units

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| N1 | Semgrep CE † | SAST rules | `security-review` findings with scanner evidence instead of pure LLM reasoning | See B8 | 🟡 |
| N2 | OSV-Scanner † | Known-vulnerability scan of lockfiles/SBOMs | "Outdated dependency" findings with CVE IDs | Offline DB download possible | 🟢 |
| N3 | Trivy † | Vulns, misconfig (Dockerfile, Helm, K8s), secrets | One binary covers deployment misconfig + deps | Large DB download | 🟡 |
| N4 | [Threagile](https://versprite.com/threat-modeling-tools/threat-modeling-tools-compared/) | Threat model as YAML → risk rules, diagrams, reports | Generate `threat-model.md` from a YAML derived from `model.c4` (actors, trust boundaries, data assets) | Another model to keep in sync | 🟡 |
| N5 | [OWASP pytm](https://devguide.owasp.org/en/04-design/01-threat-modeling/02-pytm/) | Threat model in Python, reports/diagrams as outputs | Same as N4, Python-native (fits `uv`) | — | 🟡 |
| N6 | [OWASP Threat Dragon](https://owasp.org/projects/threat-dragon) | Visual threat-modelling app | Manual workshops | Diagram-first, not code-first | 🔴 |

## O. Translations

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| O1 | [Lingo.dev CLI](https://lingo.dev/en/cli) | Localisation CLI for Markdown/JSON/YAML with `i18n.lock` (SHA-256 per string) and bring-your-own LLM (incl. Anthropic, Ollama) | **Segment-level** incremental translation (only changed paragraphs) instead of retranslating whole pages; our `translated` stamp is per file | Needs a provider key or Ollama; would run outside Claude/Codex sessions | 🟡 |
| O2 | DeepL API † | Machine translation with glossaries | Glossary-enforced EN→ES from `glossary.md` | Paid API, sends text out | 🔴 |
| O3 | po4a / mdpo † | Markdown ↔ gettext PO | Human translators could use Weblate/Crowdin on PO files | Heavy workflow for a two-language kit | 🔴 |

## P. Multi-repo workspace management

| ID | Tool | What it is | What it would improve here | Notes | Signal |
|---|---|---|---|---|---|
| P1 | [mani](https://dev.to/alajmo/mani-a-cli-tool-to-manage-multiple-repositories-1eg) | Repo list with tags + run commands across repos (Go) | Replace parts of `sync_repos` / per-repo loops | We already have `workspace.yaml` + sync; little gain | 🔴 |
| P2 | [gita](https://terminaltrove.com/gita/) | Batch git ops over many repos (Python) | Same as P1 | — | 🔴 |

---

## Candidate short-list if we only picked a few (for the discard pass)

Quick wins that fill a documented gap with low install weight:

1. **H1 lychee** (or stdlib link check) — the PLAYBOOK already assumes broken-link detection.
2. **G1 Mermaid validation** in `CLI check`.
3. **J1 SQLite FTS5** for `search_docs` — ranked search, no new dependency.
4. **E1 LikeC4 MCP + skills** — tool already pinned.
5. **H5 gitleaks** on `cam-docs/` before commit/export.
6. **H3 Vale** with a vocabulary generated from the glossary.

Bigger bets worth a spike:

7. **B1 codebase-memory-mcp** (or **B2 GitNexus**) next to graphify — compare on one real multi-repo project.
8. **F1 tbls** for the `data` unit against migration-built local DBs.
9. **C7 OpenTelemetry service graph** as runtime evidence where tracing exists.
10. **A1 CodeWiki** as a second wiki engine for very large repos.

## Sources

- Wikis: [CodeWiki](https://github.com/FSoft-AI4Code/CodeWiki) · [CodeWiki paper](https://arxiv.org/html/2510.24428v5) · [deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open) · [RepoWiki](https://github.com/he-yufeng/RepoWiki) · [repowise](https://github.com/repowise-dev/repowise) · [repowise vs DeepWiki](https://www.repowise.dev/blog/comparisons/repowise-vs-deepwiki) · [Google Code Wiki](https://developers.googleblog.com/introducing-code-wiki-accelerating-your-code-understanding/) · [Code Wiki status](https://pasqualepillitteri.it/en/news/1942/google-code-wiki-automatic-ai-documentation)
- Code graphs: [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) · [Codebase-Memory paper](https://arxiv.org/html/2603.27277v1) · [GitNexus](https://github.com/abhigyanpatwari/GitNexus) · [GitNexus overview](https://www.marktechpost.com/2026/04/24/meet-gitnexus-an-open-source-mcp-native-knowledge-graph-engine-that-gives-claude-code-and-cursor-full-codebase-structural-awareness/) · [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) · [code-graph-mcp](https://github.com/sdsrss/code-graph-mcp) · [Serena](https://github.com/oraios/serena)
- Architecture: [LikeC4 AI tools](https://likec4.dev/tooling/ai-tools/) · [Structurizr MCP](https://docs.structurizr.com/ai/mcp) · [IcePanel vs Structurizr](https://icepanel.io/blog/2025-11-14-icepanel-vs-structurizr) · [jQAssistant manual](https://jqassistant.github.io/jqassistant/current/) · [OTel living architecture](https://oneuptime.com/blog/post/2026-02-06-living-architecture-diagram-otel-service-graph/view)
- Contracts/events: [EventCatalog](https://www.eventcatalog.dev/features/documentation) · [EventCatalog AsyncAPI](https://www.eventcatalog.dev/docs/plugins/asyncapi/intro) · [oasdiff](https://github.com/oasdiff/oasdiff) · [oasdiff vs Spectral](https://dev.to/deepaksatyam/openapi-contract-testing-in-2026-oasdiff-vs-spectral-vs-pactflow-and-what-i-built-21an)
- Data: [tbls](https://github.com/k1Low/tbls) · [SchemaSpy vs tbls](https://dev.to/bmf_san/tools-for-automatically-generating-db-documents-er-diagrams-etc-schemaspy-tbls-213f)
- Quality: [docs linting in CI](https://www.netlify.com/blog/a-key-to-high-quality-documentation-docs-linting-in-ci-cd/) · [GitLab docs testing](https://docs.gitlab.com/development/documentation/testing/) · [Doc Detective](https://docs.doc-detective.com/) · [gitleaks vs TruffleHog](https://secrails.com/blog/trufflehog-vs-gitleaks-github-secret-scanning-guide) · [promptfoo LLM-as-judge](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/)
- Drift: [Swimm](https://swimm.io/blog/feature-updates) · [DeepDocs](https://medium.com/@deepdocs/deepdocs-keep-your-documentation-in-sync-with-your-code-73699b73c1d2)
- Search/portal: [qmd](https://github.com/tobi/qmd) · [Kroki](https://kroki.io/) · [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format/) · [Material for MkDocs EOL](https://github.com/squidfunk/mkdocs-material/issues/8523) · [Zensical](https://squidfunk.github.io/mkdocs-material/blog/2025/11/05/zensical/)
- Orchestration: [Beads](https://github.com/gastownhall/beads) · [Beads guide](https://betterstack.com/community/guides/ai/beads-issue-tracker-ai-agents/)
- ADRs: [log4brains](https://github.com/thomvaill/log4brains)
- Security: [threat modeling tools 2026](https://versprite.com/threat-modeling-tools/threat-modeling-tools-compared/) · [pytm](https://devguide.owasp.org/en/04-design/01-threat-modeling/02-pytm/) · [Threat Dragon](https://owasp.org/projects/threat-dragon)
- i18n: [Lingo.dev lockfile](https://lingo.dev/en/cli/fundamentals/i18n-lock-lockfile)
- Multi-repo: [mani](https://dev.to/alajmo/mani-a-cli-tool-to-manage-multiple-repositories-1eg) · [gita](https://terminaltrove.com/gita/)
