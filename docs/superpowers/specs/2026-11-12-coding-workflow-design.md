# Coding workflow: docs first, linked PRs — design

Asked by the user on 2026-11-12: when a person opens Claude Code or Codex in a project that has Camarón and asks for a
code change, the agent follows a disciplined workflow (like superpowers) that **reads the documentation first**, and at
the end **opens a docs PR and a code PR, linked**, after passing the **guardrails**, stating the **impact** and passing
the **verification plan**. When the task turns out to be hard, it decides to escalate. The skill set can be reviewed
and rewritten by the team to tune it.

## 1. Intent

Today an agent coding in a Camarón project has `cam-docs-lookup` and `cam-docs-update`, two MCP prompts and, when the
project opts in, a Stop hook that reminds it to update the docs. Nothing makes it read the docs before coding, judge
how hard the change is, verify it with evidence it did not write itself, check it against guardrails, say what it
affects, or ship code and docs together. And the kit's skills are rewritten on every refresh, so a team cannot tune
them.

**Done when:** in a Camarón project, a person opens Claude Code or Codex — at the workspace root or inside a service
repo — and asks for a code change, and the session:

1. reads cam-docs and cites what it read before it changes code;
2. scores the change's difficulty with fixed signals and, above the thresholds, escalates to a written plan or spec
   and proposes splitting it into board items;
3. passes the kit's verification plan and guardrails, with evidence the kit produced for the exact commits;
4. states the impact (risk signals, docs pages, C4 elements and their consumers, decisions);
5. after one yes from the person, opens draft code PR(s) and a docs PR that link each other;

and a team can fork, diff and reset any of the kit's skills, and collects feedback notes per skill from end-of-session
retros, PR review comments and board items.

**Anti-goals — a failure even if it works:** evidence taken from the agent's own text; a PR opened with red or missing
evidence, or before the person said yes; the kit merging anything; the kit writing into a service repo's tracked
files; a team's copy of a skill overwritten by a kit upgrade; a team skill loading on a machine that has not approved
it; standing context over budget; a 3.x/4.x project needing a manual step; a forge failure leaving half-linked PRs
that a rerun cannot finish; a check that could not run reported as green.

### 1.1 Decisions taken with the user (2026-11-12)

| Question | Decision |
|---|---|
| What "a hard task" triggers | **Decide when to escalate** (fixed signals and thresholds) and **split into board items**. Not a cost estimate, not an ETA |
| Where sessions are opened | **Both**: the full workflow at the workspace root; inside a service repo the same steps through the camarones MCP, nothing written into the repo |
| Relation to superpowers | **Camarón's own pack, which composes**: complete without superpowers; when superpowers is installed, its generic steps (brainstorming, writing-plans, TDD, debugging) are used and Camarón keeps its own (docs first, difficulty, verification, guardrails, impact, linked PRs, retro) |
| Opening the PRs | **Ask once, then open**: the agent shows impact and verification and asks; on yes the kit opens both as drafts |
| Tuning in the first delivery | **Team copies** of skills; **session retro notes**; feedback from **PR review comments** and **board items**. Not AI rewrite proposals, not an editor in the desktop app |
| Approach | **B**: thin skills plus a kit `change` command and MCP tool for every deterministic step |
| Where the code and docs are edited | Code on a branch in the person's own service-repo checkout; docs in a cam-docs worktree under `<workspace>/.cw/` |
| Agent-added difficulty signals | Shown apart, tagged `inferred`; they **do not** change the score |
| Acceptance criterion without a linked test | A warning in v1, not a block |
| PR state when opened | Draft |
| Team copies of skills | Approved once per machine in `camaron trust` |
| Backward compatibility | **Kept** (AGENTS.md 2.3). The user first said it was not needed, then confirmed it is |

### 1.2 Requirements this builds on

From [dev-harness-requirements.md](../../research/dev-harness-requirements.md): E1 (interactive runs verified by the
kit), E3 (one change, N linked PRs; none opens if one fails), E4 (own branch, PR after explicit approval, never merge),
E5 (board follows the PR), E9 (`.cw/` worktrees), E10 (branch template), E12 (evidence valid for its commit), C1,
C1b–C1e (detected and declared checks, criterion ↔ test, JUnit XML, flaky, un-runnable), C2 (base plan without AI, AI
additions), C3b (`repos[].verify`), C4 (evidence summary in the PR and the item), R1/R1b (risk signals and
thresholds), R2/R3 (approvals), R4 layer 3 (diff gate), U4 (agents create board items as drafts), K3 (docs inside the
same change).

Left out on purpose: headless execution (E1 headless, the `Runner` port), CI jobs, reading PR state on sync (E6) other
than review comments, architecture rules from the C4 (C3), value drift (K4), exploratory testing (C5).

## 2. Approach

Thin skills say **when and why**; every deterministic step is a kit command, `camaron change <action>`, with `--json`
and no AI, also exposed as one MCP tool. The skill tells the agent to call the command; the command decides whether
the change passes. The same steps behave the same in Claude Code, Codex and CI, and most of the value works with no
model at all (AGENTS.md priority 1).

Rejected: **skills only** (the agent runs `git`/`gh` and reports results) — evidence would be the agent's word (R4)
and Claude and Codex would drift. **A headless harness** (the kit launches and drives the agent) — another product;
the user asked for their own interactive session. It can reuse these commands later.

```
person ─▶ Claude Code / Codex ─▶ skill cam-task ─▶ camaron change start|assess|verify|gate|impact|pr
                                    │                        │
                                    ├─ cam-docs-lookup        ├─ docs search, pr.impact, c4edit.index, history
                                    ├─ superpowers (if any)   ├─ checks run in the repo, evidence in the cache
                                    ├─ cam-docs-update        ├─ forge: API token → gh/glab → "prepared"
                                    └─ cam-retro              └─ board: link PRs, move to in review
```

## 3. `camaron change`

### 3.1 The change record

One JSON per change in the git-ignored cache, `cam-docs/.camarones/.cache/changes/<id>.json`, written only by the
kit:

```json
{"id": "wi-12", "title": "…", "item": "WI-12", "created": "…", "by": "<git user>",
 "repos": {"api": {"branch": "cam/wi-12-retry-payments", "base": "<sha>", "base_ref": "origin/main"}},
 "docs": {"worktree": "<workspace>/.cw/7", "branch": "cam/wi-12-retry-payments", "base": "<sha>"},
 "assess": {"score": 4, "level": "medium", "signals": […], "inferred": […], "at": "…"},
 "verify": {"plan": […], "evidence": {"api": {"commit": "<sha>", "checks": […]}}},
 "gate": {"commit": {"api": "<sha>", "docs": "<sha>"}, "errors": […], "warnings": […], "acks": […]},
 "prs": {"api": "<url>", "docs": "<url>"}, "state": "open|prepared|in-review|closed"}
```

- `id`: the board item's id in lower case when one is linked, else `<slug>-<4 hex>`.
- Branch from the template `change.branch` in `workspace.yaml` (E10), default `cam/{id}-{slug}`; the same name in
  every repo and in cam-docs.
- Its summary (not the record) travels in the PR bodies and on the board item (C4).

### 3.2 Actions

Every action takes `--json`; exit code 0 = passed, 1 = blocked (the reasons are in the output), 2 = usage error. The
change is found by `--change <id>`, else the one whose branch is checked out in the current folder, else the only open
change; with several open and none of those, it stops and lists them.

| Action | Does |
|---|---|
| `start "<title>" [--item WI-n] [--repo r]… [--files repo:path,…]` | Creates the record, the branch in each named repo (adopts the current branch when it is not the default one and the tree is clean), the cam-docs worktree (`harness/worktrees`, with the change's branch), and returns the **docs to read** (§3.3) |
| `assess [--files …] [--signal "<name>: <why>"]… [--split]` | Difficulty score and level (§3.4); `--split` prints the format for draft board items |
| `verify [--add <id> --why "…" -- <argv>] [--accept-flaky <check> --why "…"]` | Builds the verification plan and runs it (§3.5) |
| `gate [--ack <page> --why "…"] [--accept-level --why "…"]` | Guardrails on the current commits (§3.6) |
| `impact [--summary "…"]` | The impact report (§3.7) |
| `pr` | Opens the linked draft PRs (§3.8); refuses unless the gate passed for the current commits |
| `status [<id>]` | Open changes, the step each reached and what comes next |
| `feedback [<id>]` | PR review comments and board items to triage into skill notes (§5.3) |
| `close <id> [--abandon]` | Removes the docs worktree (branches stay); `--abandon` also marks the board item back |

### 3.3 Docs to read (`start`)

Without AI: `docs.search` with the title (and the item's body), the pages whose `x-sources` cite the files given in
`--files`, the decisions citing them, and entries of `overview/removed.md` that match. Each hit with its path, the
section that matched, and its trust (`confirmed`, `draft`, `needs-reconfirm`, suspect). At most 12; the agent reads
them with `read_doc(path, section)` or the files, and cites them before it changes code (skill `cam-docs-lookup`).

### 3.4 Difficulty (`assess`)

Signals detected from the files in scope (given with `--files`, or the diff once there is one) and from what cam-docs
already knows. Default weights, overridable in `change.signals`:

| Signal | Detected from | Weight |
|---|---|---|
| `repos` — 2 or more repos | the record | 2 |
| `contract` — a public contract | OpenAPI/proto/Avro/GraphQL files; files behind the endpoints of the generated blocks | 2 |
| `migration` — SQL migration or schema | Liquibase/Flyway paths, `*.sql` under migration folders | 2 |
| `auth` — auth or secrets path | path patterns (`auth`, `security`, `secret`, `crypto`…), configurable | 2 |
| `messaging` — a message topic | files behind the topics of the generated blocks | 1 |
| `weak-docs` — pages in scope are draft, suspect or missing | the docs to read (§3.3) | 1 each, max 2 |
| `open-questions` — `TODO(question)` in those pages | the pages | 1 |
| `hotspot` — git hotspot or single-owner file | `history.mine()` | 1 |
| `big-item` — the board item has more than 5 criteria | the item | 1 |

- **Inferred signals:** the agent may add `--signal "<name>: <why>"`. They are listed apart, tagged `inferred`, and do
  not change the score; the person reads them and decides.
- **Levels** (`change.thresholds`, R1): 0–2 **low** → a short plan in chat, then implement; 3–5 **medium** → a
  written plan the person approves before any code; the agent may suggest more effort or a stronger model (the kit
  cannot change the model of a session the person opened); 6+ **high** → a spec and a plan, both approved, and a
  proposed split.
- **Split:** `--split` prints how to create the parts: `camaron board add story "<title>" --label draft …`, one per
  part, each with its criteria and the docs it links. The person accepts them (U4: agents never move columns). Each
  part later becomes its own change with its own PR pair; the session continues with the first part, or stops.
- **Ratchet:** `gate` re-scores with the real diff. A level above the assessed one stops the gate until the person
  accepts it (`gate --accept-level --why "…"`). A level never goes down.
- The output always lists which signals added up.

### 3.5 Verification plan (`verify`)

**Base, without AI** (C2), per repo touched:

- A **profile** detected from the repo: `mvnw`/`pom.xml`, `gradlew`/`build.gradle*`, `package.json` (npm/pnpm/yarn by
  lockfile), `pyproject.toml`/`pytest`, `go.mod`, `Cargo.toml`, `*.sln`/`*.csproj`. It brings compile and unit tests;
  integration tests when a signal calls for them (`migration`, `contract`); the repo's own linters when configured in
  the repo.
- `repos[].verify` from `workspace.yaml` (C3b): `profile` overrides the detected one; `extra: [{id, run: [argv…]}]`
  adds checks. Argv lists only, never a shell string.
- `camaron check` on the docs worktree.
- **Acceptance criteria:** when the linked board item lists the tests that cover each criterion (C1b), those tests are
  read from JUnit XML (surefire, failsafe, Gradle; C1c). A criterion without a listed test is a warning.

**Agent additions:** `verify --add <id> --why "…" -- <argv>`. Recorded with origin `ai` and shown apart in the PR. The
agent cannot remove a base check (only `workspace.yaml` can).

**Running:** the kit runs every check in the repo through `lib/core/process.py` (JVM repos with SDKMAN: the
`sdk env` the kit already knows), and records per check: exit code, duration, the repo's `HEAD` commit, whether the
tree was clean, and a hash of the log. Logs stay in the cache (`changes/<id>/logs/`).

- **Evidence counts only for that commit** (E12): a new commit or a dirty tree makes it stale.
- **Flaky** (C1d): a failed check is retried once; failed-then-passed is `flaky` and blocks until the person runs
  `verify --accept-flaky <check> --why "…"`.
- **Cannot run** (C1e): a missing tool or service (e.g. Docker for Testcontainers) is an error with the command that
  fixes it, never green.

### 3.6 Guardrails (`gate`)

Without AI, on the current commits of every repo and of the docs worktree. Errors block `pr`; warnings go into the
PR bodies.

| Check | Error | Warning |
|---|---|---|
| Forbidden paths (`change.forbidden`; default `.env*`, `*.pem`, `*.key`, `id_rsa*`, `secrets/`) | any match in the diff | |
| Secrets: gitleaks (pinned) on the diff | any finding | gitleaks missing (with `doctor`'s fix) |
| Scope: files outside the repos named at `start` | | yes |
| Size: diff above `change.max_lines` (default 1500) | | yes |
| Docs: every page `pr.impact` finds left stale by the code diff is updated on the docs branch, or acknowledged (`--ack <page> --why`) | a stale page neither updated nor acknowledged | |
| Docs: generated blocks refreshed (`camaron blocks` in the worktree) and `check` in the worktree | `check` errors | `check` warnings |
| Trust: the docs diff writes `x-confirmed`, edits a `<!-- human -->` block or an `x-owner: human` page | yes | |
| Evidence: `verify` green for the current commit of every repo | missing, stale or red | criteria without tests |
| Difficulty ratchet (§3.4) | level went up and was not accepted | |
| Removed on purpose: the diff brings back a name listed in `overview/removed.md` | | yes |

A confirmed page edited on the docs branch becomes `needs-reconfirm`; the gate lists those pages, and the PR body asks
a person to re-confirm them after merging.

### 3.7 Impact (`impact`)

Without AI, from the diff and what cam-docs knows; it heads both PR bodies:

- repos, files and lines changed;
- the risk score of the real diff with the signals that added up (§3.4);
- docs: pages updated, pages acknowledged, confirmed pages that need re-confirming;
- C4: elements whose `x-sources` or repo mapping the diff touches, and the elements related to them in the model
  (`c4edit.index()` relations) — who may be affected;
- decisions (ADRs) citing the changed files;
- the agent's summary paragraph, passed with `impact --summary "…"`, marked as agent text.

### 3.8 Linked PRs (`pr`)

**Preconditions:** every code repo's tree is clean (the agent commits its code with the repo's own conventions); the
gate passed for exactly the current commits; the base did not move — if `origin/<default>` is ahead of the recorded
base, it refuses with "merge `<default>` and run `change verify` again". The kit never merges.

**On the person's yes** (the skill asks; `pr` itself never asks), in order:

1. Commit whatever is pending in the docs worktree (`docs: <title>`), push every branch.
2. Open the code PR(s) as drafts.
3. Open the docs PR as a draft, linking the code PRs.
4. Edit the code PR bodies to add the docs PR's link.
5. Link the PRs to the board item and move it to "in review" (E5 — the kit following its fixed rule, not the agent).

**Forge:** `propose.open_docs_pr` generalises into `lib/forge.py`: open a PR/MR on any remote, find the one already
open for a branch, edit its body, list its review comments. The API with the token the kit keeps (`creds.py`, or
`DOCS_WRITE_TOKEN` in CI), else `gh`/`glab`, else leave the branches pushed, print the URL that opens each PR, and set
the change to `prepared`. GitHub drafts use `draft: true`; GitLab, a `Draft:` title prefix.

**Idempotent:** a rerun finds the PRs already open for each branch and finishes the rest; it never opens a second one.
E3: if any code repo fails its preconditions, no PR opens.

**Body block**, in the project's language (es/en), between `<!-- camaron:change id=<id> -->` and
`<!-- /camaron:change -->`, rewritten in place on a rerun: linked PRs and "merge the code first, the docs right after";
impact; difficulty; an evidence table (check, origin, result, commit, log hash); warnings and acknowledgements; the
board item.

## 4. The skill pack

Kit defaults in `templates/skills/`, rendered into `.claude/skills/` and `.agents/skills/` like today. Agent-facing,
English. Each skill says which kit command it calls and never asks the agent to judge what a command decides.

| Skill | Purpose (its description triggers it) |
|---|---|
| `cam-task` | Entry point for any code change in a Camarón project: the order of the steps, when to ask the person, how to compose with superpowers |
| `cam-difficulty` | Run `change assess`, read the signals, follow the level; the split format |
| `cam-verify` | Run `change verify`; when to propose an addition and how to justify it; reading failures; flaky and un-runnable checks |
| `cam-ship` | `change gate`, `change impact`, the single question to the person, `change pr`, what to report |
| `cam-retro` | 0–3 notes at the end, only when the workflow got in the way; triaging `change feedback` |
| `cam-docs-lookup`, `cam-docs-update` | Kept; `cam-task` calls them for reading and updating docs |
| `cam-docs-unit`, `cam-docs-diagrams` | Unchanged |

**`cam-task`, in order:** 1 `change start` · 2 read the docs it lists (`cam-docs-lookup`) and summarise them with
citations · 3 `cam-difficulty` · 4 design and plan as the level says · 5 implement test-first · 6 update the docs in
the worktree (`cam-docs-update`) · 7 `cam-verify` · 8 `cam-ship` · 9 `cam-retro`.

**Composing with superpowers:** when the session has superpowers' skills, steps 4 and 5 hand off to
`brainstorming`/`writing-plans` (medium and high) and `test-driven-development`, and a failure goes through
`systematic-debugging`; without them, `cam-task` carries a short version of each. Camarón's own steps (1–3, 6–9) are
never skipped either way. Step 9 never replaces superpowers' `finishing-a-development-branch`; `cam-ship` is the
finish when a change is open.

**Context budget:** the new descriptions are short (a test caps each and the kit's total in `doctor --context`); their
bodies load only on use. `budget.py` counts every `cam-` skill as the kit's.

## 5. Tuning: team copies and notes

### 5.1 Team copies

- A team's version of a skill lives in `cam-docs/.camarones/skills/<name>/SKILL.md` (and any files beside it),
  versioned and reviewed in a normal docs PR. A folder there whose name is no kit skill is a **team skill**.
- Rendering (`env.write_kit_skills`): for each kit skill, the team copy when there is one, else the kit's text; plus
  every team skill; `{{PROJECT_NAME}}`, `{{CLI}}`, `{{CAM}}` filled as today; into both agent hosts.
- `camaron skills`:
  - `list` — name, origin (`kit`, `team`, `team-only`), and "the kit changed this skill since your copy" when it did;
  - `fork <name>` — copies the kit's text into the team folder and records the kit text's hash in
    `.camarones/.kit-skills.json` (like `.kit-docs.json`);
  - `diff <name>` — the team copy against the kit's current text; with `--kit`, the kit's text when forked against
    now;
  - `reset <name>` — back to the kit's text; the team's copy stays aside as `SKILL.md.<date>` (as
    `docs reset --templates` does);
  - `notes [<name>]` — §5.2.
- **Upgrades** never touch a team copy; `doctor` warns when the kit's version of a forked skill moved on.
- **Trust:** a team copy is not the kit's text, so `trust` lists it (kind `skill`, labelled "team copy of <name>") and
  each machine approves it once; a changed copy asks again. Nobody can push a skill that approves itself.

### 5.2 Notes

- One file per skill: `cam-docs/docs/.work/skill-notes/<skill>.md`, committed with the next checkpoint or sync. One
  entry per line, parseable and readable:
  `- 2026-11-12 · retro · step verify · change wi-12 · lanerid — <text> (<ref>)`.
- `camaron skills note <skill> "<text>" --source retro|review|board [--step <step>] [--change <id>] [--ref <url|WI-n>]`;
  the same through the MCP `change` tool (`action: note`).
- **Retro** (`cam-retro`): at the end of every change session, 0–3 notes, only for friction in the workflow (a missing
  step, a wrong gate, noise, a doc that misled). None is a valid outcome. Code problems are not skill notes.
- `skills notes [<name>]` groups them by skill and step, newest first. A person — or an agent asked to — rewrites the
  team copy (`skills fork`, edit) in a docs PR. AI rewrite proposals and an editor in the desktop app are next steps,
  not this delivery.

### 5.3 Feedback from PR reviews and board items (`change feedback`)

- **PR reviews:** the review comments on the change's PRs (`forge`), each with its id, author, file and link.
- **Board items:** items linked to the change that were reopened (moved back out of "in review" or "done"), bugs that
  link the change or its PRs, and cards labelled `skill-feedback`.
- The kit only lists them. The agent addressing them (`cam-retro`) decides, per entry, whether it is a code matter (no
  note) or a step that should have caught it (`skills note … --source review|board --ref <link>`). The kit never turns
  an entry into a note by itself, and it remembers which entries were triaged (`changes/<id>.json`, `triaged`) so they
  are not listed again.

## 6. Reaching the agent

**Workspace root** (the links to cam-docs' `.claude`, `.codex`, `.agents`, `AGENTS.md`, `CLAUDE.md`):

- the skills, in both hosts;
- one line in the `AGENTS.md` kit block (`camarones:start/end`): "For any code change, start with skill `cam-task`.";
- the method hooks, still opt-in (`camaron hooks on`), gain: SessionStart lists open changes and their next step;
  Stop reminds once when a repo has commits on a change branch and no `change pr` ran. Codex gets the same hooks in
  `.codex/hooks.json` when the installed Codex supports them (verified in slice 5); otherwise `AGENTS.md` carries the
  rule alone. The workflow never depends on a hook.

**Inside a service repo** (nothing written into the repo):

- one MCP tool `change` with an `action` (`start`, `assess`, `verify`, `gate`, `impact`, `pr`, `status`, `feedback`,
  `note`) — one schema instead of nine, for the context budget;
- an MCP prompt `cam-task` with the same steps; `implement-feature` stays and points to it;
- Claude Code: the `camarones` MCP is already registered per folder (`wire_repo_mcp`);
- Codex: a `camarones` entry in Codex's user config whose server resolves the project from the session's folder
  (`projects.find_marker` and the machine's project registry) and answers "no Camarón project here" elsewhere.
  Validated in slice 5; if Codex cannot do it cleanly, the fallback is the optional repo pointer the kit already offers
  for `CLAUDE.md`, extended to `AGENTS.md`.

## 7. Configuration

All optional in `workspace.yaml`; absent keys take the kit's defaults:

```yaml
change:
  branch: "cam/{id}-{slug}"
  thresholds: {medium: 3, high: 6}
  signals: {repos: 2, contract: 2, migration: 2, auth: 2, messaging: 1, weak-docs: 1, open-questions: 1, hotspot: 1, big-item: 1}
  auth_paths: ["auth", "security", "secret", "crypto"]
  forbidden: [".env*", "*.pem", "*.key", "id_rsa*", "secrets/"]
  max_lines: 1500
repos:
  - name: api
    verify: {profile: spring-maven, extra: [{id: arch, run: ["./mvnw", "-q", "test", "-Dtest=ArchTest"]}]}
```

## 8. Compatibility (AGENTS.md 2.3)

- A 3.x/4.x project gets the new skills and the `AGENTS.md` line on its next refresh (`refresh_agent_config`,
  `refresh_block`), with no manual step; a `workspace.yaml` without `change:` works with defaults.
- No command, flag, key, frontmatter field or file location is renamed or dropped; `implement-feature` and
  `update-docs` stay.
- New file locations (`.camarones/skills/`, `.camarones/.kit-skills.json`, `docs/.work/skill-notes/`, the cache's
  `changes/`) are created on first use; a project without them behaves as today.
- Team copies and notes are human work: no migration or upgrade rewrites them.
- `VERSIONS["kit"]` bumps (minor) with each slice.

## 9. Cross-platform (AGENTS.md 2.1)

Paths through `pathlib`, files with `encoding="utf-8"`, every check and git call through `lib/core/process.py` as argv
(no shell strings, `.cmd` resolution on Windows), worktree paths short (`.cw/<n>`), `IS_WIN`/`IS_MAC` only from
`lib/core/platform.py`. gitleaks and `gh`/`glab` are optional and degrade with a clear message. No new external tool
(2.4): gitleaks is already pinned; `gh`/`glab` are already used by `pr propose`.

## 10. Testing

Test first, offline, deterministic, on the three OSes:

- `change start`: branches in `make_workspace` repos, adoption of a non-default branch, the docs worktree, docs to read
  from fixture pages.
- `assess`: each signal from fixture files, weights and thresholds from `workspace.yaml`, inferred signals not
  counted, the ratchet.
- `verify`: profile detection per stack, `extra` argv, agent additions kept apart, evidence made stale by a commit and
  by a dirty tree, flaky retry, a missing tool as an error, JUnit XML per criterion.
- `gate`: forbidden path, gitleaks (`needs("gitleaks")`; a fake on PATH otherwise), stale page from `pr.impact` and its
  acknowledgement, trust breaks in the docs diff, the removed-on-purpose warning.
- `impact`: C4 relations from a fixture model, ADRs citing files.
- `pr`: local bare remotes as the forge; a fake opener for the GitHub and GitLab APIs; `gh`/`glab` absent → prepared;
  rerun after a failure between the code and the docs PR; E3 (one repo fails → no PR); board link and move.
- `skills`: rendering with a team copy and a team skill in both hosts, fork/diff/reset, upgrade leaves copies alone,
  trust lists a team copy and asks again when it changes, `doctor` warning, context budget.
- notes and `feedback`: entry format round trip, review comments from a fake forge, board reopen and labels, triaged
  entries not listed again.
- MCP: the `change` tool and the `cam-task` prompt; CLI snapshot; `catalog --check`.
- End to end on the PetClinic sandbox (from slice 4): start → edit → verify → gate → pr against a local bare remote,
  then `traces`.

## 11. User docs (AGENTS.md 5.1)

Each slice, in the same commit: `README.md` (es), the guides `using`, `internals` (and `app` where it shows) in en and
es, the tutorial (`lib/tutorial.py` → `.camarones/TUTORIAL.md`, and `templates/docs/guides/tutorial.md` with its es
twin — existing projects keep their copy, said in the commit), `catalog.py` placement (CLI and MCP; no portal or app
screen in this delivery).

## 12. Delivery in slices

One plan and one minor version per slice; each is useful on its own.

| Slice | Delivers | Useful because |
|---|---|---|
| 1 | Skill pack (`cam-task`, `cam-difficulty`, `cam-verify`, `cam-ship`, `cam-retro`), `AGENTS.md` line, team copies (`camaron skills list/fork/diff/reset`), trust and budget, notes (`skills note/notes`) | An agent already follows the workflow with today's commands; teams can tune it from day one |
| 2 | `change start`, `assess`, `impact`, `status`, `close`; the change record | Docs to read, difficulty with escalation and split, impact — all without AI |
| 3 | `change verify`, `gate` | Evidence produced by the kit; guardrails |
| 4 | `change pr`, `lib/forge.py`, board link and move | The linked draft PRs |
| 5 | MCP `change` tool and `cam-task` prompt, Codex inside a service repo, hooks, `change feedback` | The same workflow in a service repo and in Codex; feedback from reviews and the board |

## 13. Open questions for the slice plans

1. Codex hooks: whether the pinned/installed Codex reads `.codex/hooks.json` events equivalent to SessionStart and Stop
   (slice 5).
2. Codex inside a service repo: whether a user-level MCP entry that resolves the project from the session's folder is
   clean on all three OSes (slice 5).
3. Docs edits during a change happen in the worktree; the MCP's `propose_edit` writes to the main checkout. Either the
   MCP server learns the open change's worktree, or `cam-task` says to edit the worktree's files directly (slice 2).
4. `pr.impact` reads pages from the main checkout; the gate needs them from the docs worktree (slice 3).
5. `harness/worktrees` names branches `cam/u/<n>-<unit>`; a change needs its own branch name (slice 2).
6. Detecting public contracts and topics per stack beyond the generated blocks (slice 2).
7. Module placement within the hexagonal layers (`tests/test_architecture.py`): `change*` and `forge` as application
   modules over `lib/core` (each slice's plan).
