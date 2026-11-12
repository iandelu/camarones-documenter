---
name: cam-task
description: Start here for any code change (feature, fix, refactor) in {{PROJECT_NAME}} — read cam-docs first, judge difficulty, test first, verify, pass the guardrails, state the impact, then open linked code and docs PRs.
---

# Make a code change

Every code change goes through these steps, in this order. Run commands from the workspace root (the folder that holds
the service repos and `{{CAM}}`) unless a step says otherwise.

1. **Set up the change.**
   - `<id>`: the board item in lower case (`WI-12` → `wi-12`), else a short slug. `<slug>`: 2–4 words of the title.
   - In each service repo you will change: `git fetch`, note the branch you start from as `<base>` (e.g.
     `origin/main`), then `git switch -c cam/<id>-<slug> <base>`. A dirty tree, or a non-default branch already
     checked out: ask the person first.
   - The docs, in their own worktree: `git -C {{CAM}}. worktree add ../.cw/<id> -b cam/<id>-<slug>`. The docs' `<base>`
     is the branch `{{CAM}}` had checked out. Edit docs only in `.cw/<id>/docs/`, never in `{{CAM}}docs/`.
   - **On the worktree** means `{{CLI}}` with three variables set; without them it misreads the layout and reports
     false errors: `CAMARONES_ROOT="$PWD/.cw/<id>" CAMARONES_WORKSPACE="$PWD" CAMARONES_STATE_ROOT="$PWD/{{CAM}}." {{CLI}} <command>`
     (PowerShell: set the three with `$env:`, run, then remove them).
2. **Read the docs first** with `cam-docs-lookup`: the feature's terms, the files you expect to touch,
   `overview/removed.md`. Before changing any code, summarise what they say with citations `[path#section]`, and flag
   draft or suspect pages and anything that contradicts the code.
3. **Score the difficulty** with `cam-difficulty`. Its level decides step 4.
4. **Design and plan as the level says**: low → a short plan in chat; medium → a written plan the person approves
   before any code; high → a spec and a plan, both approved, then a split into board items.
5. **Implement test-first**: for each behaviour a failing test, watch it fail, make it pass. Commit with the repo's
   own conventions.
6. **Update the docs in the worktree** with `cam-docs-update`, adapted: edit `.cw/<id>/docs/` instead of
   `{{CAM}}docs/`, run its `{{CLI}}` commands on the worktree, skip its `llms`, `checkpoint` and `mark-documented`, and
   do not use the MCP's `propose_edit` (it writes to the main checkout). A board item: link it to the pages you
   updated, on the worktree, as `cam-ship` guardrail 8 says. Then commit the docs locally, leaving out the four derived
   files the kit's commands rewrite (`docs/.status.json`, `docs/.work/fresh.json`, `docs/llms.txt`,
   `docs/llms-full.txt`):
   `git -C .cw/<id> add -A -- . ":(exclude)docs/.status.json" ":(exclude)docs/llms.txt" ":(exclude)docs/llms-full.txt" ":(exclude)docs/.work/fresh.json"`,
   then `git -C .cw/<id> commit -m "docs: <title>"`. Commit every later docs edit the same way: verification and the
   guardrails read commits, not the working tree. A tree is **clean** when `git status --porcelain` lists nothing, or,
   in `.cw/<id>`, nothing but the four derived files.
7. **Verify** with `cam-verify`.
8. **Ship** with `cam-ship`: guardrails, impact, one question, linked draft PRs.
9. **Retro** with `cam-retro`.

## With superpowers

When superpowers' skills are available, use them for the generic steps: step 4 → `brainstorming` and `writing-plans`
(medium and high), step 5 → `test-driven-development`, any failure → `systematic-debugging`. Without them, follow the
steps above as written: write the failing test, watch it fail, make it pass. Camarón's own steps 1–3 and 6–9 are
never skipped either way. While a change is open, `cam-ship` replaces `finishing-a-development-branch`.

Step 1's branches and docs worktree are the change's workspace: create no other worktree (they already satisfy
`using-git-worktrees`), and keep the code on its branch in the person's own checkout. Specs and plans stay in chat or
go into `.cw/<id>/docs/.work/plans/`, never at the workspace root or in a service repo.

## When to ask the person

- To approve the plan (medium and high) before any code.
- When the difficulty level goes up.
- When a step skill says to stop and ask (a flaky check, a failed guardrail).
- Once, before opening the PRs (`cam-ship`).

Otherwise keep going. Never merge. Never write `x-confirmed`; never edit `<!-- human -->` blocks or pages with
`x-owner: human`.
