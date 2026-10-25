# Lessons from enjoy: a newcomer's payment questions

Field notes, 2026-10-25. A team member new to apps, Firebase and Stripe asked an agent to explain enjoy's architecture,
then asked: "what if everyone writes at once?", "who calls Stripe?", "how should the request be made?", "security?
JWT?". Answering meant re-reading code the kit had already documented, and the answers surfaced gaps in the kit
itself. Each lesson names the kit area and a candidate change; none is implemented yet.

## What happened

1. The agent read `docs/llms.txt`, `overview/system.md` and one flow page, and explained the system.
2. The follow-up questions needed code: the agent found the live Stripe key in source, seven public `onRequest`
   payment functions, a client-set amount and a lost-update race in the expiry scheduler.
3. Several of those facts were **already in the docs**, scattered: the public cancel endpoints and the scheduler
   overlap sat in `flows/bid-expiry-refund.md` §5, the secrets and open rules in `quality/tech-debt.md`, and twenty
   related items in `interview/open-questions.md`. Nothing ranked them or answered "is the payment path safe?".
4. The answer was **partly wrong**: the repo `User` (a SvelteKit rewrite of the guest app with authenticated `v2_*`
   callables, a Stripe webhook, idempotency keys and transactions) had been documented the day before, but
   `docs/llms.txt` had not been regenerated, so the agent never saw it and proposed, as new, a design that `User`
   already implements.
5. While writing `docs/security/*`, a **second session** in the same `cam-docs/` was running a full security review
   and overwrote `threat-model.md` mid-write. Neither session knew about the other. They then split the files by
   hand over cross-session messages (one owned `docs/security/`, ADRs and briefs; the other tech debt, flows, guides
   and open questions) and agreed that only one of them runs `check` / `llms` / `checkpoint`, which commits both.
6. The two sessions disagreed on a fact: was `User` live? The repo brief and the discovery note said "preview only",
   copied from `User:README.md`; a runbook in the same repo (`User:docs/operations/event-runbook.md`) and the git log
   showed a production cut-over on 2026-10-23, before discovery ran. Discovery trusted the README over newer evidence.

## Lessons and candidate changes

| # | Lesson | Kit area | Candidate change |
|---|---|---|---|
| L1 | A stale `llms.txt` silently hides whole repos from agents, and the agent answers confidently from what it sees | `CLI llms`, `cam-docs-lookup` skill | Regenerate `llms.txt` at the end of every unit (`plan done`) and in `checkpoint`; `cam-docs-lookup` compares `llms.txt` against `workspace.yaml` repos and `docs/` files and warns when they differ |
| L2 | Two sessions can write the same page at once; the last writer wins with no warning | units, `cam-docs-update`, portal | A per-page (or per-unit) lease in `docs/.work/` that `plan start` takes and editing skills check; `cam-docs-update` first lists running units and their files |
| L3 | Risks found by flow units stay buried in each flow's §5 and in open questions; nobody gets a ranked view | flow skeleton, `security-review` | Flow §5 bullets carry a severity tag (`[risk:high]`); `CLI check` or the portal aggregates them into one "risks" view; `security-review` starts from that list |
| L4 | `security-review` is opt-in and reasons only over earlier docs ("no code re-reading"), so it cannot see code-level issues: client-set amounts, read-modify-write without a transaction | PLAYBOOK `security-review` | Add a short code pass for money and state: who computes amounts, who writes status fields, every read-then-write on shared docs; propose the unit automatically when discovery finds a payment provider |
| L5 | Concurrency is a question every flow should answer, and the flow template only asks about failure, idempotency and retries | flow skeleton §5, CONVENTIONS §6 | Rename §5 to "Failure handling, concurrency, idempotency, retries" with a prompt: "who else writes these docs at the same time, and with what (transaction, atomic op, plain write)?" |
| L6 | BaaS stacks (Firebase, Supabase) move the trust boundary into rules and function auth; generic checklists ("endpoints without protection") miss it | `security-review` checklist | Stack-specific checks: `onRequest` vs `onCall`, `cors({ origin: true })`, `request.auth` checks, rules in the repo vs only in the console, anonymous auth treated as authenticated, App Check |
| L7 | gitleaks runs on `docs/` and wikis only, so a live secret in a service repo is found by reading, not by the kit | `quality` component, discovery | Run gitleaks (report-only, values redacted) over each repo during discovery and list hits by file and line in the discovery note |
| L8 | Newcomers need concepts before architecture: "what is Firestore", "what is a hold/capture", "what is an ID token" | guides, `domain` unit | A generated "Concepts for newcomers" guide per external system found in discovery (Firebase, Stripe…), linked from `overview/system.md`, written in plain language and cross-linked to the flows that use each concept |
| L9 | An answer that recommends a design should check whether a newer repo or ADR already does it | `cam-docs-lookup` skill | Before proposing a design, search `decisions/` and every repo brief for the same mechanism (e.g. "webhook", "onCall") and cite what exists |
| L10 | READMEs go stale; deployment state ("live", "preview") is better read from runbooks, deploy workflows and recent commits | discovery unit | Discovery reads `docs/operations/`, runbooks and the last 30 commits for deploy/cut-over/rollback words, and flags a README claim the newer evidence contradicts |
| L11 | Hand-made coordination works but costs messages: file ownership, who runs `checkpoint`, how to cite each other's pages (paths and stable IDs like `SEC-2`, no anchors that may move) | units, CONVENTIONS | Make it explicit: each unit declares the files it writes (`plan.yaml`), `checkpoint` refuses while another unit holding a lease is `doing`, and CONVENTIONS recommends citing findings by stable ID |

## Suggested order

L1, L2 and L11 first (they made answers wrong and lost work), then L10, L5 and L3 (cheap discovery, template and
check changes), then L4, L6 and L7 (the `security-review` unit), and L8 and L9 last.
