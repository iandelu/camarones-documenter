---
name: cam-difficulty
description: Step of cam-task — score a change's difficulty, then escalate or split it.
---

# Score a change's difficulty

1. List the files in scope: the ones you expect to touch (before coding), or `git diff --name-only <base>...HEAD` in
   each repo (at ship time).
2. Add up the signals that apply, each with a few words on why:

   | Signal | Applies when | Weight |
   |---|---|---|
   | `repos` | 2 or more repos change | 2 |
   | `contract` | a public contract changes: OpenAPI, proto, Avro, GraphQL, or the code behind a documented endpoint | 2 |
   | `migration` | a SQL migration or schema: Liquibase/Flyway paths, `*.sql` under migration folders | 2 |
   | `auth` | an auth or secrets path (`auth`, `security`, `secret`, `crypto`…) | 2 |
   | `messaging` | the code behind a message topic | 1 |
   | `weak-docs` | a page in scope is draft, suspect or missing (from `cam-task` step 2) | 1 each, max 2 |
   | `open-questions` | `TODO(question)` in those pages | 1 |
   | `hotspot` | a hotspot or single-owner file (`{{CAM}}docs/overview/history.md`, or `git log` on the file) | 1 |
   | `big-item` | the board item has more than 5 acceptance criteria (`{{CLI}} board show <ITEM>`) | 1 |

   `change.signals` and `change.thresholds` in `{{CAM}}.camarones/workspace.yaml`, when present, replace these weights
   and the levels below.
3. A risk no signal covers (a hot loop, a data backfill…): list it apart as `inferred`, with its why. Inferred signals
   do not count toward the score; the person reads them and decides.
4. Follow the level:
   - **0–2 low**: a short plan in chat, then implement.
   - **3–5 medium**: a written plan (steps, files, tests) the person approves before any code. You may suggest more
     effort or a stronger model; you cannot change the session's model yourself.
   - **6+ high**: a spec and a plan, both approved by the person, then a split.
5. Split (high, or when the person asks): one draft board item per part, and give the person each part's acceptance
   criteria:
   `{{CLI}} board add story "<part title>" --label draft --repo <repo> --doc <page>` (`--repo`, `--doc` as needed).
   The person accepts the parts; you never move board columns. Each part becomes its own change with its own PRs:
   continue with the first part, or stop.
6. At ship time (`cam-ship`), score again with the real diff. The level never goes down. If it went up, stop and ask
   the person to accept the new level or to split.
7. Report one line, and repeat it in the PR bodies:
   `Difficulty: <score> (<level>) — signals: …; inferred: …`
   e.g. `Difficulty: 4 (medium) — signals: repos (api, web), migration (V12__retry.sql); inferred: perf (hot loop)`.
