# Plan cost: what documenting a project from zero really took — design

Asked by the user on 2026-10-27: "a token counter to see how much time and money the documentation plan costs from
zero".

## 1. Intent

The kit already records tokens and cost per run (`usage` events in `.camarones/.cache/runs/<run>/events.jsonl`, read
by `runs` and `kpis`), but nothing answers the question a team actually asks: **how many tokens, hours and dollars
did documenting this project take, from the first unit to now?** Today:

- interactive unit sessions (the interviews, any unit opened in its own terminal) are not measured at all;
- Codex reports tokens but no cost, so its work counts as $0;
- wikis generated through an agent runner record nothing;
- nothing adds a whole plan up, by phase or by unit; the KPIs roll-up keeps one total per run.

This piece adds a **plan bill**: every run, session and wiki of the current plan, priced, timed and broken down, for
the whole team, in the CLI, the desktop app and the portal.

**Done when:** `camaron plan cost` (and the cards in the app and the portal) shows, for the current plan, its agent
time, its calendar span, its tokens and its API-equivalent cost, by phase and by unit, summed over every machine that
worked on it — and names what it could not measure or price instead of counting it as 0.

**Anti-goals — a failure even if it works:** a missing price or an unmeasured session shown as $0; the portal writing
files when someone opens it; a window left open overnight counted as hours of work; a git-dirty cam-docs every time
someone looks at the bill; a 3.x/4.x project that needs a manual step; a stats failure that breaks a run or a
`plan done`.

### 1.1 Decisions taken with the user (2026-10-27)

| Question | Decision |
|---|---|
| What the counter is for | Measure the real cost of the plan (not a forecast, not a live ticker) |
| Whose work it adds up | The whole team: each machine's share is committed, like the KPIs roll-up |
| What "money" means | API-equivalent dollars: the agent's reported cost, else tokens × a pinned price table |
| Approach | A: a bill built from what is already recorded, filling the three gaps (sessions, Codex price, wikis) |

## 2. Approach: a bill over what is already recorded

`lib/harness/ledger.py` builds the bill from three sources that all land in the machine's KPIs roll-up
(`docs/.work/kpis/<person-machine>.json`, already committed and shared): runs (with a new per-unit breakdown),
interactive sessions (harvested from Claude Code's transcripts) and agent-runner wikis (which now write a run log of
their own, so they are just runs).

Rejected: **a separate live ledger** (an append-only JSONL of every usage event per machine) — it duplicates what run
logs already hold and writes far more lines into a committed file. **Reading only the agents' own logs**
(`~/.claude/projects`, `~/.codex/sessions`) — machine-local, so it breaks the team scope, and it depends on formats the
kit does not own for every source instead of one.

## 3. Modules

| Module | Does | Depends on |
|---|---|---|
| `lib/harness/transcripts.py` | A Claude Code transcript → tokens per model and active seconds; incremental | stdlib |
| `lib/harness/pricing.py` | Loads the price table (+ workspace override); prices a token bundle | `lib/pricing.yaml`, `docs.workspace()` |
| `lib/harness/ledger.py` | `harvest()` writes this machine's sessions; `bill()` adds the team's plan up | the two above, `runs`, `kpis`, `sessions`, `plan` |

Each is pure where it can be: `transcripts.read(path, offset)` and `pricing.cost(model, tokens, table)` take values and
return values; only `ledger.harvest()` and `kpis.record_run()` write.

## 4. Capture

### 4.1 Runs (autopilot, parallel)

Unchanged events, two additions:

- The `usage` event the scheduler and `plan._run_agent` write gains `model` when the route names one
  (`claude:sonnet` → `sonnet`); without one it is omitted and pricing falls back to the runner's default (§5).
  `cache_read` and `cache_write` are already separate in the events; the run summary keeps adding them into
  `tokens_cache` as today.
- `kpis.run_metrics()` gains `units`: `{<unit id>: {"in", "out", "cache_read", "cache_write", "cost_usd", "seconds",
  "model"}}`, built from `runs.detail()` (a unit retried after a usage limit adds its attempts up). `cost_usd` is the
  reported one or absent.

### 4.2 Interactive unit sessions

- `sessions.start()` keeps the id it replaces: the record gains `previous: [<session id>…]` when a unit is restarted
  or relaunched with a new session (today the old id is overwritten and lost).
- `transcripts.read(path)` streams a Claude Code transcript line by line and returns, per model, `in`, `out`,
  `cache_read`, `cache_write_5m`, `cache_write_1h`, plus `first`/`last` timestamps, `active_seconds` and `bytes` (the
  sizes read, subagent files included):
  - only `type: "assistant"` lines; several lines share one `message.id` (one per content block) with identical
    `usage` — each id counts once;
  - the split of cache writes comes from `usage.cache_creation.ephemeral_5m_input_tokens` /
    `ephemeral_1h_input_tokens`; without it, all of `cache_creation_input_tokens` counts as 5-minute writes;
  - subagents: every `<session dir>/<session id>/subagents/*.jsonl` is read the same way and added in;
  - `active_seconds` = the sum of the gaps between consecutive timestamped lines, each gap capped at `IDLE = 300`
    seconds — a window left open overnight adds 5 minutes, not 10 hours;
  - a damaged line is skipped; a missing file returns None.
- Incremental: the stored session entry keeps `bytes`; a session whose files have not grown is not read again. A
  grown one is re-read whole (message ids may repeat across a boundary, so totals are recomputed, never added).
- Codex interactive sessions: the kit does not know their id, so they are listed as unmeasured with their unit. No
  guessing from timestamps in `~/.codex/sessions`.

### 4.3 Wikis through an agent runner

`env.openwiki_generate()` with an engine other than native `openwiki` builds the request with `stream=True`, parses the
output through the runner's `parse_event` (as autopilot does) and writes a run log of its own:
`r-<YYYYMMDD-HHMMSS>-<pid>-wiki-<repo>` (the scheduler's id form, so it sorts with the others) with `run.started`, `unit.started` (unit `repo-wiki:<repo>`), every `usage`,
`unit.finished` (outcome and seconds) and `run.finished`. It is then an ordinary run for `runs`, `kpis` and the bill.
The log lines the user sees stay the same. Native OpenWiki (its own provider key) reports no tokens: the unit is listed
as unmeasured when its wiki stamp says `engine: openwiki`.

## 5. Price

`lib/pricing.yaml`, pinned in the kit:

```yaml
revised: 2026-10-27
source: <where each family's prices were read>
models:                      # USD per million tokens
  claude-opus-5-5:   {in: …, out: …, cache_read: …, cache_write_5m: …, cache_write_1h: …}
  …
aliases: {opus: claude-opus-5-5, sonnet: claude-sonnet-5-5, haiku: claude-haiku-5-5, fable: claude-fable-5-1}
runners: {claude: claude-sonnet-5-5, codex: gpt-5.6-terra}   # when the run did not say which model
```

- Claude prices come from the `claude-api` reference; Codex's default (`agents.CODEX_MODEL_DEFAULT`) from OpenAI's
  published pricing. Both are read at implementation time and dated in `revised`; the `…` above are filled then.
- Override: `pricing:` in `workspace.yaml` with the same shape (`models`, `aliases`, `runners`), merged over the kit's
  per key. A malformed override is reported by `plan cost` (naming the key) and the kit table is used.
- A model name matches exactly, then through `aliases`, then by its dated form (`claude-sonnet-5-5-20260901` →
  `claude-sonnet-5-5`).
- **Which cost counts:** the agent's reported `cost_usd` when there is one (Claude's is exact and covers models it
  used internally); otherwise tokens × the table; with no price for the model, the cost is `null` and the item is
  listed under "unpriced". Never 0.
- Tokens are stored, dollars computed when the bill is built: a new table re-prices everything already recorded.

## 6. Time

- **Unattended:** the seconds of every run unit (`unit.finished.seconds`), wikis included.
- **With a person:** the `active_seconds` of interactive sessions.
- **Calendar:** from the first activity of the plan (§8) to the last one.

## 7. Storage, for the whole team

The machine's roll-up `docs/.work/kpis/<person-machine>.json` keeps `"v": 1` and gains keys only:

- `runs.<id>.units` (§4.1); older entries without it still count in the totals, under "unit unknown";
- `sessions.<session id>`: `{"unit", "agent", "started", "ended", "active_seconds", "bytes", "models": {<model>:
  {tokens}}}`, capped at `KEEP = 500` like runs.

Writes follow `record_run`'s rules: only when usage stats are on, atomic (temp file + `os.replace`), every exception
swallowed. Two more:

- **Under a lock** (`harness.locks.FileLock` on `<cache>/locks/kpis.lock`): `record_run` and `harvest` may meet.
- **Only when something changed:** the new content is compared with the file's; equal → no write, so looking at the
  bill never dirties cam-docs.

When `harvest()` runs (it writes): at the end of every run (next to `record_run`); when a unit goes to `done`
(`plan.set_status`, for that unit's sessions, so they reach the same docs commit); on `camaron plan cost` and on the
desktop app's request. **The portal's GET never writes:** it builds the bill with this machine's sessions read on the
fly.

The team bill is the union of every `kpis/*.json` plus this machine's runs and sessions not stored yet (stats off, or
not harvested), de-duplicated by run id and session id. People = distinct person hashes among the files with activity
in the plan.

## 8. "From zero": the plan epoch

- `plan.yaml` gains an optional top-level `epoch: <ISO UTC>`.
- Set when the plan is created (`sync` with no `plan.yaml` yet) and renewed by `docs reset --wipe`. `--redo` keeps it:
  it reviews the same plan.
- A plan without `epoch` (any 3.x/4.x project) counts everything recorded; nothing writes one into it.
- A run or session belongs to the plan when it **started** at or after the epoch. What started before is one line,
  "before the last reset: $X · N h", so the interviews a wipe keeps do not vanish from the record.
- In the bill: every run (autopilot, parallel, wiki) and every session of a plan unit. Out: Ask answers, the C4
  refinement session, evals and A/B, and the "update docs" session — they are using and maintaining the docs, not
  building them.
- Units marked done with no run or session behind them (done by hand, or before this kit) are counted: "N units done
  with no record".

## 9. Where it shows

- **CLI:** `camaron plan cost` (a new `plan` action) and `--json`. Text:

  ```
  Plan from zero (since 2026-10-20, 2 people)
    Time      unattended 6 h 40 min · with a person 1 h 55 min · calendar 3 days
    Tokens    in 4.1 M · cache 38 M · out 610 k
    Cost      $48.20 API-equivalent (prices revised 2026-10-27)
    By phase  1 $9.10 · 2 $6.30 · 3 $21.40 · 4 $11.40
    Top units repo-wiki:api $7.90 · arch-system $5.20 · domain $4.10
    Unpriced  3 sessions (model unknown)
    Not measured  repo-wiki:web (native OpenWiki) · interview-context (Codex session)
    Before the last reset  $12.30 · 2 h 10 min
  ```

  `--json`: `{"epoch", "people", "seconds": {"unattended", "with_person", "calendar"}, "tokens": {"in", "out",
  "cache_read", "cache_write"}, "cost_usd", "complete", "phases": [{"phase", "cost_usd", "seconds", "tokens"}],
  "units": [{"unit", "phase", "cost_usd", "seconds", "tokens", "runs", "sessions"}], "unpriced": [...],
  "unmeasured": [{"unit", "why"}], "unrecorded": n, "before": {"cost_usd", "seconds"} | null, "pricing":
  {"revised", "overridden": [...]}}`. `complete` is false when anything is unpriced or unmeasured.
- **API:** `GET /api/plan/cost` (the bill, never writes; the portal uses it). `POST /api/plan/cost` needs the app
  token (added to `APP_ONLY`): it harvests this machine's sessions, then returns the bill; the desktop app uses it.
- **Desktop app:** a card in the Plan section (`sections/Plan.jsx`): cost, the three times, tokens, top three units and
  a "by phase" table that unfolds; unpriced/unmeasured as one muted line. Refreshes with the section.
- **Portal:** a "Plan from zero" card in the KPIs tab (`Kpis.jsx`), read-only, same figures.
- **Catalog:** the `plan` entry's description mentions the cost; `catalog --check` stays green.
- Strings in `es` and `en`. No joke on these screens: it is a report.

## 10. Errors

- A missing or unreadable transcript: the session is "not measured (transcript not found)".
- A damaged line in a transcript or a run log: skipped.
- A damaged KPIs file of another machine: skipped with a note in the bill; this machine's own damaged file is
  rewritten from what is known (as `record_run` does today).
- Unknown model: `null` cost, listed as unpriced. Malformed override: named, kit table used.
- Nothing here may fail a run, a `plan done` or a wiki: stats errors are swallowed and the bill shows what it has.

## 11. Compatibility (3.x and 4.x)

Only new optional keys: `epoch` (plan.yaml), `units` and `sessions` (KPIs roll-up), `model` (usage events),
`previous` (session record). Old plans, roll-ups and run logs are read as they are; old kits ignore the new keys
(`kpis.report()` adds named fields only; `plan.save()` dumps every key it loaded). Each has a test that starts from
the old form. `VERSIONS["kit"]` → 4.68.0.

## 12. macOS, Windows, Linux

`pathlib` only; `encoding="utf-8"` everywhere; transcripts found through `sessions.claude_dir()`, which already handles
Windows' long paths. No new processes; the wiki change reuses the runner's argv and the existing `stream` helper.

## 13. Testing (TDD, offline)

`make_workspace` and `isolated_env`; transcripts and run logs written as fixtures.

- `transcripts`: one id across several lines counts once; subagents added; 5m/1h split and the fallback; damaged
  line skipped; idle cap; `bytes` returned.
- `pricing`: reported cost wins; table cost per token kind; alias and dated names; workspace override merged; unknown
  model → None; malformed override → error text and kit table.
- `kpis`: `record_run` stores `units`; an old entry without `units` still adds up.
- `ledger.harvest`: writes a session entry; second call with an unchanged transcript neither reads it nor writes
  (file mtime unchanged); a grown one is re-read whole; stats off → no write; `previous` sessions harvested; under
  the lock.
- API: `GET /api/plan/cost` writes nothing; `POST` without the app token is refused.
- `ledger.bill`: two machines' files united and de-duplicated; epoch filter and the "before" line; plan without epoch
  counts all; unmeasured (Codex session, native OpenWiki) and unrecorded units listed; phases and top units.
- `plan`: `sync` on a new plan writes `epoch`, on an existing one does not; `reset --wipe` renews it, `--redo` keeps
  it.
- `env.openwiki_generate` with a fake runner: a `-wiki-<repo>` run with `usage` and `unit.finished`.
- CLI: `plan cost` text and `--json`; `catalog --check`.
- Portal (Vitest): the card's pure helper (formatting, phase rows, incomplete note). Desktop renderer (Vitest): the
  Plan card. `app-build/` and `renderer-build/` rebuilt.
- Sandbox: `plan cost` on PetClinic with recorded data only — no real agent is launched (it would spend money).

## 14. Docs that move with it

`README.md` (the command, what it counts, API-equivalent pricing, the version badge); `lib/tutorial.py` es+en and the
regenerated `.camarones/TUTORIAL.md`; `templates/docs/guides/tutorial.md` and `templates/docs/i18n/es/guides/tutorial.md`
(existing projects keep their copy — said in the commit).

## 15. Out of scope

A forecast before starting; a live ticker while a run goes; subscription proration; Codex interactive session
discovery; cost of Ask, C4 refinement, evals and A/B in the plan bill (they keep their own figures where they have
them).
