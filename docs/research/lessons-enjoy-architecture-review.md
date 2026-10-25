# Lessons from enjoy: an architecture and security review run outside the plan

Field notes, 2026-10-25, companion to [lessons-enjoy-payments-review.md](lessons-enjoy-payments-review.md) (L1–L11,
written by the other session of the same day; not repeated here). The user asked an agent for a deep analysis of
enjoy — does it need a backend, should it move to AWS or PostgreSQL, costs, quick wins — then for Firestore rules with
emulator tests, then to document everything in `cam-docs/`. The work is now in `docs/security/`, ADR 0004–0006,
`docs/quality/architecture-review.md` and `docs/guides/payment-backend-patterns.md` of enjoy's cam-docs. Each lesson
names the kit area and a candidate change; none is implemented yet.

## What happened

1. The analysis was answered in chat first. The kit has the opt-in `security-review` and `architecture-review` units,
   but nothing linked the user's question to them; they were added to the plan only when the user asked to document.
2. The pages that frame the system (`overview/system.md`, `deployment/environments.md`, `data/firestore-*.md`,
   `index.md`) still described the Flutter `UserWebApp` as the guest app a day after `repo-brief:User` ran. That unit's
   handoff even listed "refresh of cross-repo pages that predate `User`" under *Remaining*, and no unit was created.
3. Both sessions called the kit launcher by absolute path (`…\kit\camaron.cmd`). It does `cd /d "%~dp0"`, so `plan add`
   created a fresh blueprint `plan.yaml` **inside the kit checkout** and `check` validated the kit's own `docs/`. Nothing
   said which root it used. The fix was the global launcher (`~\.local\bin\camaron.cmd`, keeps the cwd) or
   `CAMARONES_ROOT`.
4. The Firestore rules fix was proven with an emulator harness (a rules matrix across apps plus 38 assertion tests, and a
   control run showing every new deny passes on the live rules). It lives in a service repo; the kit has no notion of it.
5. The cost and capacity answers came from `User/docs/operations/` (load test, cost model, runbook). Discovery had
   listed that folder but no unit used it as a source.
6. `camaron check` printed ~300 lines (wiki translations, glossary false positives on "bid"); the one real ERROR in a
   touched page had to be found with `Select-String`.

## Lessons and candidate changes

| # | Lesson | Kit area | Candidate change |
|---|---|---|---|
| M1 | A launcher that changes directory silently documents the wrong project | `camaron.cmd` / `camaron.command`, `harness/ctx.py#find_root` | Print the resolved root on every write command; refuse `plan`/`checkpoint`/`translated` when the root is the kit itself and no `workspace.yaml` is there; make the per-kit launcher keep the caller's cwd (or set `CAMARONES_ROOT=%CD%` before `cd`) |
| M2 | *Remaining* items in a handoff die there | `plan done`, handoff template | `plan done` reads the handoff's *Remaining* list and offers one `plan add` per item; `plan next` shows open *Remaining* items from earlier handoffs |
| M3 | A new repo that replaces an old one does not ripple into the pages that list repos | `workspace.yaml`, `CLI check` | `replaces: <repo>` / `status: legacy` per repo; `check` marks as suspect every page whose `x-sources` or prose names the replaced repo as current (overview, deployment, data, index) until a unit refreshes them |
| M4 | A chat question that matches an opt-in unit is answered once and lost | `cam-docs-lookup` skill, PLAYBOOK | When a question maps to `security-review`, `architecture-review` or a flow ("should we migrate", "is X secure", "how much does it cost"), suggest adding/running that unit so the answer lands in `docs/` with evidence |
| M5 | BaaS rules need executable tests, not prose | `quality` component, `security-review` | Ship a Firebase rules harness template (matrix of every app's real queries incl. collection groups + assertion tests + control run against the live file); `:::rule` blocks accept `test:` anchors to a test file and test name, not only symbols |
| M6 | Operational docs inside repos (runbooks, load tests, cost models) answer cost and scaling questions | discovery, `deployment`, `architecture-review` | Discovery tags `docs/operations/`-style files as sources for `deployment` and `architecture-review`; `architecture-review` gets a "cost and capacity" section fed by them |
| M7 | For a `#shared-db`, "who writes" is not enough; what matters is what enforces it | data-model skeleton, CONVENTIONS §6 | Add an "Enforced by" column (rules / server function / convention only) to the ownership table of shared stores; `check` warns when every row says "convention" |
| M8 | Freshness messages can mislead and fire on same-session edits | `CLI fresh` | Say "line range beyond end of file (448 lines)" instead of "its code is gone"; do not flag a page whose cited doc changed in the same unit/session |
| M9 | `check` output is too noisy to read as a gate | `CLI check` | `check --changed` (pages touched since the last checkpoint) and a final summary (`N errors, M warnings, K in touched pages`); group repeated warnings (same rule, many files) into one line |
| M10 | `plan done` commits a checkpoint of every `CHECKPOINT_PATHS` file, so it swept another session's untracked CI work (`.gitlab-ci.yml`, `.camarones/ci/`) into this unit's commit; `plan add` without `--type` types any unit as `flow` (and `discovery-refresh:User` got `deps=['flows-catalog']`) | `plan done`, `env.checkpoint_commit`, `plan add` | Commit only the files the unit declared or touched, and list anything else as "left uncommitted"; say "will commit" in `plan done --help`; infer the type from the id prefix or require `--type` |

## Suggested order

M1 first (it writes into the kit and validates the wrong tree, silently), then M2 and M3 (stale framing pages caused
both sessions' confusion about what is live), then M9 and M8 (cheap, make `check` usable as a gate), then M4, M6, M7
and M5.
