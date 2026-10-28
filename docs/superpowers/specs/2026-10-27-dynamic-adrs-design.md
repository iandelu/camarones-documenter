# Dynamic ADRs: frame a decision, research it with a jury of agents, decide it together — design

Asked by the user on 2026-10-27: "a feature to create ADRs dynamically: the problem is defined, research is done, three
independent agents investigate the code, then one looks at the results and merges them. It proposes an ADR with
diagrams when useful, it is reviewed part by part and decisions are made (a developer shares their screen). Find out
whether it is overkill. I want an ADR interface; this will be the source of truth, it will update the docs and stay
reviewed. A beautiful interface."

Builds on: the decision page of `CONVENTIONS.md` §6 and its skeleton `templates/skeletons/decision.md`; the runners
behind the `Runner` port (`lib/adapters/runners/`) and their routing tiers (`harness/routing.py`); the code map and
its search box of *Historias* (`lib/kanban/index.py`, [user stories](2026-10-26-user-stories-design.md) §2); the
bounded AI calls of Ask and Stories (`lib/answers.py`, `lib/stories_ai.py`); the live read-only stream of the
[agent board](2026-10-26-agent-board-design.md) §5.3; `docs.confirm`, `harness/worktrees` and `harness/integrate`;
the library inventory (`lib/inventory.py`) and git mining (`lib/history.py`).

## 1. Intent

Today an ADR is written by the `decisions-quality` unit from the interviews, or by hand. Nothing helps a team *make*
a decision: frame the problem, gather what the code already says, weigh options with evidence, and record who decided
what. The kit has every piece — code graph, docs citing code, history, runners, worktrees — but not the flow.

This piece adds a **Decisiones / Decisions** section to the desktop app where a person frames a decision (new, or one
the code already took), the kit builds an evidence pack without AI, a **jury** of agents researches it read-only
through three different lenses, a judge merges their findings into a proposed ADR whose **disagreements become decision
points**, and the team decides those points in a live review led by one developer sharing their screen. The accepted
ADR is the source of truth: hash-locked by `confirm`, read by agents, and carried into the docs.

**Done when:** in the desktop app, a developer opens *Decisiones*, starts a new ADR (or one from *Candidatas*), sees
the evidence pack, launches the jury, watches its three lanes live, opens the proposed ADR, presents it with `P`,
walks its parts and decision points with the team, chooses an option per point, and presses *Aceptar*; the ADR in
`docs/decisions/` is `Accepted`, confirmed, lists who decided, and the affected pages either got reviewed diffs
(retroactive) or show a computed "accepted, pending implementation" banner with a story on the board (new).

**Anti-goals — a failure even if it works:** a research agent editing any file; an agent writing `Accepted`; a
citation in the ADR that points at nothing; the proposed future written into the docs as if it were today's code; a
`.c4` file describing a future that is not built (LikeC4 reads every `.c4` under `docs/architecture/`); an ADR written
by a 3.x/4.x kit that no longer opens; the section unusable with no runner installed; the portal gaining a machine
action; three agents run for a one-file decision without the person choosing it.

### 1.1 Decisions taken with the user (2026-10-27)

| Question | Decision |
|---|---|
| Which ADRs | **New and retroactive**, one flow; the lenses differ by kind (§4.2) |
| How the three agents differ | **One lens each, and mixed runners** when several are installed (Claude, Codex, opencode); one runner → all three on it; the person can reassign before starting |
| The review session | **One developer drives** the app and shares their screen; a **presentation mode**; who attended and what was decided per point is recorded; AI during the meeting only for short actions |
| Docs after accepting | **By kind**: retroactive → reviewed page diffs; new → computed banner + a story on the board, text rewritten when the code changes |
| Approach | **A — its own ADR pipeline** in the desktop app, the flow as data, agents through the existing `Runner` port (§1.3) |
| Modes | **Ligero / Light** (one combined lens) and **Jurado / Jury** (three lenses + a judge); the kit suggests one from the scope, the person picks |
| Interface | The three screens agreed in chat: list, live research, review in presentation mode (§2) |

### 1.2 Is it overkill?

Not for real decisions, on three conditions the design keeps.

- **Evidence.** Anthropic measured a multi-agent research setup beating a single agent by 90.2% on breadth-first
  research, at about 15× the tokens of a chat; it fits questions with independent directions and fits poorly when
  every agent needs the same context ([Anthropic, 2025](https://www.anthropic.com/engineering/multi-agent-research-system)).
  An ADR — today's code and its impact, the options, the risks — is breadth-first.
- **The real risk is redundancy.** Three copies of one model with one prompt converge (correlated errors), so three
  runs buy the same answer three times; and agents without clear boundaries duplicate work and leave gaps (same
  source). Hence: a distinct lens per agent with an explicit scope and output schema, mixed runners when available,
  and a judge that **surfaces disagreement instead of averaging it** — the disagreements are what the meeting decides.
- **Cost is opt-in and visible.** Evidence comes first and without AI (AGENTS.md §1: value almost without AI); the
  *Light* mode runs one agent; the kit suggests *Jury* only when the scope is wide (§4.5); the estimate is shown before
  anything runs and a per-ADR budget stops the run (§5).

### 1.3 Approaches considered

- **A (chosen). Its own pipeline.** `lib/adr.py` plus a *Decisiones* section; the lenses and prompts as data in
  `lib/pipelines/adr.yaml`; agents through the `Runner` port, read-only, in parallel, with the board's live stream.
  An ADR's lifecycle (ad hoc, interactive, decided in a meeting) stays apart from the documentation plan.
- **B. Units of the documentation plan.** Reuses `plan.yaml` and the scheduler, but mixes an interactive, one-off
  conversation into the unattended plan, bloats `plan.yaml` and couples two lifecycles. Rejected.
- **C. One Claude session with its own subagents.** The least code, but Claude only (no runner mix), no live lane per
  lens, cost hidden in one session, less deterministic. Rejected.

## 2. User flow (desktop app › *Decisiones*, `#/decisions`)

A new project section in `nav.js` (`PROJECT` gains `decisions`, after `board`). Strings in `es` and `en`; at most one
joke, only on the research screen while the person waits (AGENTS.md §3) — none on the review screen, which asks for
decisions.

### 2.1 List

```
petclinic › Decisiones                                        [Candidatas · 6]  [+ Nuevo ADR]
[Todas 14] [En curso 2] [En revisión 1] [Aceptadas 10] [Sustituidas 1]        [buscar…        ]
0013  Mover notificaciones a Kafka            Nueva · api, notifications · hace 6 min   Investigando 2/3
0012  Sesiones en Redis en vez de en memoria  Nueva · api · 3 puntos, 1 resuelto        En revisión
0011  Por qué Spring Data JPA y no JDBC plano Retro · api, vets · aceptada 21 oct LA,MP Aceptada
0009  Cache con EhCache 2                     Retro · sustituida por 0010               Sustituida
┆ 6 decisiones en el código sin ADR — Postgres, Liquibase, Kafka (pagos)…  [Revisar candidatas] ┆
```

Every ADR under `docs/decisions/` is listed, including the ones written before this piece (§4.13). Search covers title,
repo and glossary terms. A row opens the ADR at its current phase.

### 2.2 New ADR: *Problema*

Title; kind (*Nueva* / *Retroactiva*); the problem; drivers and constraints (one per line); candidate options
(optional); **Toca** — the same search box as *Historias*, over the code graph's files and groups and the doc pages.
*Afinar el problema* (optional, bounded AI as in `stories_ai`) suggests wording only. A retroactive ADR opened from
*Candidatas* (§4.4) arrives prefilled. Creating it reserves the next number (§4.1).

### 2.3 *Evidencia*

The pack (§4.3) as a one-line summary — "14 files · 3 doc pages · ADR 0007 related · 31 commits · 2 C4 containers" —
and *Ver paquete* to read it. Two ways on:

- **Escribir sin IA**: the proposed ADR from the skeleton, with the problem, drivers and the pack's evidence already in
  place; the person writes it in the app and adds decision points by hand. Works with no runner installed.
- **Investigar**: mode (*Ligero* / *Jurado*, the suggested one preselected), the lens → runner assignment, and the
  estimate ("~8 min · ~$1.40") with the budget. The button names what it starts: *Investigar con 3 agentes*.

### 2.4 *Investigación* (live)

A stepper (Problema ✓ · Evidencia ✓ · **Investigación** · Síntesis · Revisión · Aceptado), elapsed time and cost, then
one lane per lens: its title, its runner, the live tool calls and text (the board's read-only stream, §4.5), and a
footer with time, cost and findings count. *Parar* stops every lane; a failed lane offers *Reintentar esta lente*.
Synthesis starts by itself when the lanes end (§4.6).

### 2.5 *Revisión* and presentation mode

```
┌ 0012 · Partes ────────┬───────────────────────────────────────────────────────────────────────┐
│ ✓ Contexto            │ Punto de decisión 2 de 3                     [Las lentes no coinciden] │
│ ✓ Drivers             │ ¿Dónde viven las sesiones?                                           │
│ ✓ Punto 1 · TTL       │ Hoy en memoria del pod: un redeploy cierra la sesión de todos.        │
│ ● Punto 2 · Dónde     │ ┌ A · Redis gestionado [1]┐ ┌ B · Tabla en Postgres [2]┐ ┌ C · JWT [3]┐ │
│ ○ Punto 3 · Migración │ │ 2 de 3 lentes           │ │ 1 de 3 · Riesgos         │ │ ninguna    │ │
│ ○ Diagrama            │ │ + ya en notifications   │ │ + cero infra nueva       │ │ + escala   │ │
│ ○ Consecuencias       │ │ − un servicio más       │ │ − escritura por request  │ │ − revocar  │ │
│ ○ Docu afectada       │ └─────────────────────────┘ └──────────────────────────┘ └────────────┘ │
│                       │ Por qué discrepan: … deployment/environments.md#redis                │
│                       │ [Elegir y seguir] [Investigar más · ~2 min] [Aplazar punto]           │
│                       │ Asistentes LA MP JR +      ← → partes · 1–3 elegir · E editar · P     │
└───────────────────────┴───────────────────────────────────────────────────────────────────────┘
```

- **Parts**: Contexto, Drivers, each decision point, Opciones consideradas, Diagrama, Consecuencias, Confirmación,
  Docu afectada. A text part is *aprobada*, *editada* (inline Markdown), *regenerada* (bounded AI with an instruction
  the person types, ~90 s) or *aplazada*.
- **Decision points**: the options with their backing lenses, pros and cons, evidence links and *why they disagree*.
  *Elegir* records the option and a one-line rationale; *Otra* records an option typed in the meeting; *Investigar
  más* runs one focused, read-only lens on that point (§4.7) and adds what it finds.
- **Attendees**: initials or names typed once per session, kept for the ADR's *Decided by*.
- **Presentation mode** (`P`, `Esc` leaves): hides the rail and the app chrome, one part per screen, a larger type
  scale, everything by keyboard (`←/→` parts, `1–9` choose, `E` edit, `R` regenerate, `D` defer, `A` accept). The
  larger type is a new approved exception to the console density of `CAMARON.md`, recorded there.
- **Diagrama**: a new ADR shows *before* — the LikeC4 view of the containers it touches, embedded as the portal does —
  next to *after*, a Mermaid diagram in the ADR itself (flowchart, or sequence when the decision is about a flow). A
  retroactive ADR shows the current view only. The future is never written as `.c4` (anti-goals).

*Aceptar* is offered when every point is chosen; a deferred point keeps the ADR *En revisión*. *Rechazar* records why
and keeps the file (`Rejected`), as MADR does.

### 2.6 After *Aceptar*

The *Docu afectada* part lists the pages that overlap the ADR (§4.9) and what happens to each:

- **Retroactive** → *Actualizar docu*: an agent proposes edits in its own cam-docs worktree; the app shows one diff per
  page with *Aprobar* / *Descartar*; *Integrar* merges the approved ones.
- **New** → nothing is rewritten. The overlapping pages show a computed banner; *Crear historia* adds a story to the
  board with the ADR's *Toca* and a reference to the ADR. When that story is Done the ADR reads *implementada*.

## 3. Files and state

### 3.1 The ADR — `docs/decisions/NNNN-<slug>.md` (git)

The current skeleton, plus **optional** sections the parser tolerates missing. Frontmatter keeps only existing fields
(`type: decision`, `title`, `description`, `tags`, `x-sources`, `x-owner`, `x-confirmed`): no new key.

| Section | Proposed | Accepted |
|---|---|---|
| `# NNNN — title`, `> **TL;DR:**` | yes | yes |
| `## Status` | `Proposed` | `Accepted (YYYY-MM-DD)` · `Rejected` · `Superseded by [NNNN](…)` · `Deprecated` |
| `## Context` | yes | yes |
| `## Decision drivers` *(new, optional)* | bullets | bullets |
| `## Considered options` *(new, optional)* | `### A · name` with pros/cons/evidence | kept, all of them |
| `## Decision` | "To be decided in review: see the decision points." + `### Decision points` | one paragraph per point: the chosen option and its rationale; the points subsection is removed |
| `## Consequences` | good / bad | good / bad |
| `## Confirmation` *(new, optional)* | observable checks (tests, lint rules, dashboards) | same |
| `## Diagram` *(new, optional)* | `mermaid` blocks (*after*; *before* is a link to the C4 view) | same |
| `## Evidence` | claim · evidence table | same |
| `## Decided by` *(new)* | — | date, attendees, mode, who drove |

The kit renders the file from the synthesis JSON or the person's edits through one deterministic template; models never
write the Markdown directly. `x-owner: ai` while proposed; `x-owner: human` once accepted or rejected.

### 3.2 The ADR's working state — `docs/.work/adr/NNNN.yaml` (git, small)

`{id, slug, kind: new|retro, mode: light|jury, title, problem, drivers, constraints, options_hint, touches, phase,
runners: {lens: runner}, parts: {part: pending|approved|edited|regenerated|deferred}, points: [{id, question,
options, chosen, other, rationale, deferred}], attendees, decided: {date, by, driver}, supersedes, story,
implementation: pending|done|n/a}`. Written atomically (temp + `os.replace`) under a lock in `harness/locks`. It is what
lets a teammate pull and continue a review; it holds no model output beyond the points.

### 3.3 The machine's cache — `.camarones/.cache/adr/NNNN/` (not in git)

`pack.md` and `pack.json` (§4.3), `<lens>.prompt.md`, `<lens>.jsonl` (every event of the lane), `<lens>.json` (the
validated answer), `synthesis.json`, `run.json` (`{phase, pids, started, ended, cost_usd, budget_usd}`). Deleting it
loses the research trail, never a decision: the ADR and its working state are in git.

### 3.4 Phases

`problem → evidence → research → synthesis → review → accepted | rejected`; `research` and `synthesis` are skipped by
*Escribir sin IA*. A lane is `pending · running · done · failed · limited · interrupted`. Phases are derived from the
working state and the cache; the list's chip (*En curso*, *En revisión*, *Aceptada*, *Sustituida*) is derived from them
and from the ADR's `Status`.

## 4. Backend

### 4.1 `lib/adr.py` (new)

`list()`, `get(id)`, `new(fields)`, `pack(id)`, `estimate(id, mode, runners)`, `start(id, mode, runners)`,
`stop(id)`, `retry(id, lens)`, `synthesize(id)`, `write_without_ai(id)`, `part(id, part, action, text|instruction)`,
`point(id, point, chosen|other, rationale|deferred)`, `research_point(id, point)`, `accept(id, by)`, `reject(id, why,
by)`, `docs_plan(id)`, `docs_apply(id, approved)`, `story(id)`, `candidates()`. Pure helpers (numbering, status
parsing, rendering, validation) are separate functions so pytest pins them without a runner.

**Numbering**: the next number above every `NNNN` in `docs/decisions/` and `docs/.work/adr/`, reserved at `new`.
When the file is written and the number has been taken meanwhile (a pull), the next free one is used and the person is
told.

### 4.2 The flow as data — `lib/pipelines/adr.yaml` (new)

```yaml
modes:
  light: {new: [all], retro: [all]}
  jury:  {new: [code, options, risks], retro: [code, why, cost]}
lenses:
  code:    {tier: agentic-heavy, title: "Code and impact today",   title_es: "Código e impacto"}
  options: {tier: agentic-heavy, title: "Options and trade-offs",  title_es: "Opciones"}
  risks:   {tier: agentic-heavy, title: "Risks, devil's advocate", title_es: "Riesgos"}
  why:     {tier: agentic-heavy, title: "Why: history and PRs",    title_es: "Por qué: historia y PRs"}
  cost:    {tier: agentic-heavy, title: "What it costs today",     title_es: "Qué cuesta hoy"}
  all:     {tier: agentic-heavy, title: "All lenses at once",      title_es: "Todas las lentes"}
judge:     {tier: judge}
```

Each lens has its prompt beside it (`lib/pipelines/adr/<lens>.md`): its objective, **what is out of its scope** (the
other lenses' ground), which sources to prefer, and the output schema. A project's plugin may add lenses or override
prompts as it does for units (`harness/plugins.py`); a missing or invalid file falls back to the kit's.

### 4.3 The evidence pack (deterministic, no AI)

From the ADR's *Toca*, bounded to a character `LIMIT` (as `answers.LIMIT`), in this order:

1. The touched files and groups, and their one-hop neighbours in the code graph (`kanban/index.edges`), capped.
2. The doc pages citing them (`index.pages_citing`): title, description, the citing section's excerpt, trust state.
3. Related ADRs: overlapping `x-sources` or tags, or a glossary term in the title.
4. Commits touching those files in the last 12 months (`history`'s git mining, filtered by path): subject, date,
   PR/task references (`sourcelinks.pr_and_tasks`).
5. The C4 elements of those repos (`metadata { repo }`) and their relationships.
6. The inventory rows of the touched manifests (`docs/.work/inventory.json`).
7. Open questions in `docs/interview/open-questions.md` that mention any of the above.

`pack.json` is the data; `pack.md` its rendering, shown by *Ver paquete*, given to every lens, and used to seed the
*Evidence* table of *Escribir sin IA*.

### 4.4 *Candidatas* (deterministic, no AI)

Decisions the code already took and no ADR covers: inventory rows in the categories that carry an architectural
choice (data, cache, messaging, security, web framework, build/deploy — `dep_categories.yaml`), the technologies on
C4 containers and relationships, and the deployment sources (compose, Helm). One candidate per choice per repo group
("Postgres · api, vets"), dropped when an ADR's `x-sources`, tags or title already cover it. A candidate opens §2.2 as
a retroactive ADR with *Toca* = its manifests and the files that import it.

### 4.5 The lenses

- **Read-only, enforced twice.** `RunRequest` gains `read_only: bool = False` (absent = today's behaviour). Claude:
  `--permission-mode default`, `--allowedTools` = `Read Grep Glob Bash(git log:*) Bash(git show:*) Bash(git blame:*)`
  and `--disallowedTools Edit Write NotebookEdit`; Codex: `exec -s read-only`; opencode: its permission config with
  edits denied. After every lane the kit compares `git status --porcelain` of cam-docs and each repo with the snapshot
  taken before it: any change fails the lane and names the files (the kit reverts nothing by itself).
- **Where it runs**: the workspace folder (repos and cam-docs side by side), so the lens reads code and docs.
- **The call**: the prompt is written to `<lens>.prompt.md`; the agent gets a one-line pointer (`RunRequest.prompt` is
  one line, as in `agents.py`), with `stream=True` so the lane shows tool calls and text and the cost adds up.
- **Runners**: the `agentic-heavy` candidates of `routing`, filtered to the installed ones, assigned to the lenses in
  order without repeats while different ones remain; one runner → every lens on it. The person can change any
  assignment before starting.
- **Suggested mode**: *Ligero* when *Toca* stays in one repo, one C4 container and under a file threshold; otherwise
  *Jurado*. Deterministic; the threshold is the builder's (§9).
- **Output** (the agent's final message, parsed from the stream's result): `{lens, findings: [{claim, evidence:
  ["<repo>:<path>#L<a>-L<b>" | "docs/<page>.md" | "c4:<id>"], confidence: high|medium|low, contradicts?:
  "docs/<page>.md"}], options: [{name, summary, pros, cons, evidence}], recommendation: {option, why}, questions}`.
- **Validation**: invalid JSON → one retry with the error, then the lane fails. Every evidence reference is resolved
  against the files on disk (and the line span against the file's length); unresolvable ones are dropped and counted
  ("2 citas descartadas"); a finding left with no evidence is kept, marked *sin evidencia*, and the judge is told.

### 4.6 The judge (synthesis)

The `judge` tier, preferring a runner that ran no lens when one is installed. It gets the pack and the validated lens
answers, nothing else: no tools, in an empty folder (as `answers`), so it judges the evidence it was given. It
returns `{title, tldr, context, drivers, options: [{id, name, summary, pros, cons, evidence, backers: [lens]}], points:
[{id, question, why, options: [id], disagreement, evidence}], consequences: {good, bad}, confirmation, diagram:
{after: "<mermaid>", before_view: "<c4 view id>"}, questions}`. The first point is the main decision. The kit checks
it: ≥ 2 options per point (a single-option point is dropped with a note), every option and backer known, evidence
re-validated, the Mermaid checked with the `quality` component's mermaid-cli (an invalid diagram is dropped and the
part says so). Then it renders the proposed ADR (§3.1) and the points into the working state. In *Ligero* the judge
runs too, on the single lens's answer, so every proposed ADR comes out of the same checks and the same template; its
points then come from the options that lens weighed rather than from disagreement between lenses.

### 4.7 Review actions

`part(…, regenerate)` is a bounded call (as `stories_ai`: the route for bounded work, a cheap model, no tools, an
empty folder, 90 s) with the part, the pack's relevant excerpt and the instruction typed by the person; it returns
text for that part only. `research_point` is one read-only lens (§4.5) scoped to one question, with a 5-minute cap; its
findings are appended to the point and to *Evidence*. Every edit is a human edit: it rewrites the proposed file through
the template and keeps `x-owner: ai` until acceptance. A save whose base hash differs from the file on disk is refused
(`409`) and the app reloads, as stories do.

### 4.8 Accept, reject, supersede

`accept` (only when every point is chosen): renders `Accepted (date)`, one *Decision* paragraph per point, *Decided
by* (date, attendees, mode, the git user who drove), sets `x-owner: human`, then `docs.confirm([file], by)`. When the
ADR supersedes another, that one's `Status` becomes `Superseded by [NNNN](…)` and it is re-confirmed in the same
action, since the person accepting is the one superseding it. `reject` writes `Rejected` and the reason, `x-owner:
human`, confirmed. From then on the existing freshness gate covers the ADR like any confirmed page: when its evidence
files change it reads *changed*, which is how an accepted decision that the code drifted from shows up.

### 4.9 Docs after accepting

- **Affected pages**: pages citing any of the ADR's `x-sources` (`index.pages_citing`) plus pages a lens marked
  `contradicts`.
- **Retroactive** (`docs_plan` / `docs_apply`): one agent run in a cam-docs worktree (`harness/worktrees`, edits
  allowed under `docs/` only) that adds the ADR to each page's `x-sources` and corrects statements the ADR
  contradicts. The kit reverts any change to a page with `x-owner: human` and writes a question to
  `docs/interview/open-questions.md` instead. The app shows one diff per page; `docs_apply` keeps the approved ones and
  `harness/integrate` merges them. Confirmed pages drop to `needs-reconfirm` as any edit does today.
- **New**: nothing is written to the pages. The banner is computed wherever a page is shown (portal, app *Docs*):
  pages overlapping an accepted ADR whose `implementation` is `pending`. `story` adds a board story (`ops.add`) with
  `x-touches` = the ADR's *Toca* and the ADR in its `references`; `implementation` reads `done` once that story is
  Done (derived on read, nothing to sync).

### 4.10 API (`lib/serve.py`, app token only — `is_app()`; the portal token and no token get 403)

| Route | Does |
|---|---|
| `GET /api/app/adr`, `GET /api/app/adr/<id>`, `GET /api/app/adr/candidates` | §4.1 reads |
| `GET /api/app/adr/events?id=&lens=&offset=N` | SSE of a lane's events from `offset`, live while it runs (same loop as `stream_job`) |
| `POST /api/app/adr/{new,pack,estimate,start,stop,retry,synthesize,write,part,point,research-point,accept,reject,docs-plan,docs-apply,story}` | §4.1–4.9 |

`400` on bad input, `409` on a stale save or a second run of the same ADR, `503` with the setup message when no runner
is installed for an AI action.

### 4.11 CLI

`camaron adr list | new | show <id> | pack <id> | research <id> [--mode light|jury] [--runner lens=runner…] | accept
<id> | reject <id> --why … | candidates` (`--json` everywhere) — the same functions, for scripting and tests;
registered in `catalog.py` (verdict `app`) so `catalog --check` stays green. Review itself (parts, points, attendees)
is the app's: it is a meeting, not a script.

### 4.12 Portal and agents

- **Portal (reader)**: an ADR page shows a status pill, *Decided by*, the points with their outcome; the docs tree's
  *decisions* section shows each ADR's status; pages show the computed banner (§4.9). No machine action.
- **MCP**: a `decisions` tool — the accepted (and, flagged, proposed) ADRs whose `x-sources` cover given files or
  pages — so an agent can check before changing code a decision covers.
- **Agent rules**: `templates/AGENTS.md` gains one line: before changing code covered by an accepted ADR, read it; if
  the change contradicts it, say so instead of rewriting it. Templates are copied once: existing projects keep their
  copy (said in the commit).

### 4.13 Compatibility (AGENTS.md §2.3)

- ADRs written by any 3.x/4.x kit or by hand open as they are: the new sections are optional, `Status` is read in
  English and Spanish (`Proposed/Propuesto`, `Accepted/Aceptado`, `Rejected/Rechazado`, `Superseded by/Sustituido
  por`, `Deprecated/Obsoleto`) with or without the skeleton's comment, and an ADR without working state lists as
  *legacy* with *Revisar en sesión* (which creates the state, never rewrites a human-owned file until the person
  accepts).
- `RunRequest.read_only` defaults to `False`; runners and tests that never set it see no change.
- `workspace.yaml` gains an optional `adr: {ai: true, budget_usd: 3}`; an old workspace without it works with the
  defaults. `adr: {ai: false}` hides every AI action.
- No migration; nothing a human wrote or confirmed is rewritten without that person pressing *Aceptar*.
- `VERSIONS["kit"]` minor bump per visible slice.

## 5. Errors and limits

| Case | Behaviour |
|---|---|
| No runner installed | AI actions hidden; *Escribir sin IA*, review and accept work |
| A lane fails, hits a usage limit or times out | The other lanes continue; the judge runs with what finished and the ADR names the missing lens; *Reintentar esta lente* |
| A lane changed a file | The lane fails and lists the files; the person decides what to keep |
| Invalid lens or judge JSON | One retry with the parse error, then the phase fails with *Reintentar* |
| Budget reached | Running lanes stop; what finished is kept; the person may raise the budget and retry |
| App or server closed mid-run | Lanes read `interrupted`; reopening offers to rerun only those |
| Two edits to one ADR | The stale save gets `409` and the app reloads |
| Number taken after a pull | The next free number is used and the person is told |
| A proposed ADR edited in git meanwhile | Treated like a stale save: reload, nothing lost |

Messages say what happened and what to do (es/en), no jokes (AGENTS.md §3).

## 6. Tests

All offline and deterministic (`make_workspace`, `isolated_env`, a fake runner that replays canned streams).

- **Pure** (`tests/test_adr.py`): numbering with gaps and collisions; status parsing in both languages and from the
  old skeleton; rendering proposed → accepted → superseded; lens and judge validation (bad JSON, unknown options,
  single-option points, fake and out-of-range citations dropped and counted); mode suggestion; runner assignment with
  one, two and three installed runners.
- **Pack and candidates**: a fixture workspace with a code graph, citing pages, commits and an inventory gives the
  same pack and the same candidates on every run; covered choices are not candidates.
- **Runs**: `read_only` argv per runner pinned (`build` is pure); a fake lane that writes a file fails with that file
  named; a failed lane still lets the judge run; budget stop; interrupted lanes resume one by one.
- **Accept and docs**: accept confirms and sets `x-owner: human`; supersede re-confirms the old ADR; retro docs: a
  change to an `x-owner: human` page is reverted and becomes an open question; new: banners computed, nothing written;
  story created with the ADR's touches; `implementation` follows the story.
- **Compatibility**: an ADR from the 4.x skeleton and one written by hand list, open and accept.
- **API**: app token only (portal token and none → 403), `409` paths, SSE offsets.
- **App** (Vitest): pure helpers in `renderer/src/adr.js` (phases, chips, keyboard map), the list, the lanes and the
  review screen including presentation mode keys. **Portal** (Vitest): status pill, banner, tree chips.
- **CLI**: `catalog --check` green; `adr list --json` shape.
- **Sandbox** (AGENTS.md §2.2): on Spring PetClinic, a retroactive ADR from the *Spring Data JPA* candidate, end to end
  in *Ligero* mode, then `traces`.

## 7. Delivery in vertical slices

| Slice | End to end | Done when |
|---|---|---|
| **S1 — no AI** | Section and list, *Problema*, numbering, pack + *Ver paquete*, *Candidatas*, *Escribir sin IA*, review with hand-made points and presentation mode, accept/reject/supersede, portal pill and computed banner, CLI `list/new/show/pack/candidates/accept/reject` | On the sandbox with no runner installed, a retroactive ADR is created from a candidate, presented, decided and accepted |
| **S2 — the jury** | `read_only` in the port, lenses from `adr.yaml`, runner assignment, live lanes over SSE, estimate and budget, validation, the write guard | *Investigar con 3 agentes* shows three lanes live and leaves three validated answers |
| **S3 — the judge** | Synthesis into a proposed ADR with points, backers and disagreement; *Regenerar*; *Investigar más*; before/after diagrams | A jury run ends in a proposed ADR whose points are decided in presentation mode |
| **S4 — the docs after** | Retro page diffs through a worktree and `integrate`; new → story and `implementation`; MCP `decisions`; the `AGENTS.md` template line | Accepting a retro ADR yields reviewed page diffs; accepting a new one creates its story and banners |

Each slice ships with its tests, the README and both tutorials (AGENTS.md §5.1), and a `VERSIONS["kit"]` minor bump.

## 8. Later (not in this design)

Every attendee deciding from their own machine (shared live state); a translated view in presentation mode; a
timeline and supersede graph of all ADRs; lenses that run a team's own tools (benchmarks, load tests); proposing a new
ADR automatically when a PR contradicts an accepted one.

## 9. Left to the builder

Exact prompt wording within §4.2's rules, the pack's caps, the *Ligero* threshold, JSON field names inside `get()`,
layout details within the agreed mock-ups, the presentation type scale (within the theme's tokens), toast and error
wording (es/en, AGENTS.md §3).
