---
name: cam-ship
description: Step of cam-task — guardrails, impact, then the linked code and docs PRs.
---

# Ship a change

From the workspace root. `<id>`, `<base>`, `.cw/<id>` and "on the worktree" are set in `cam-task` step 1.

## 1. Guardrails

Each failure stops here: fix it, or ask the person. A fix is a new commit: run `cam-verify` again for what it changed,
then the guardrails again.

1. Everything is committed: the code in every repo (the repo's own conventions), the docs in `.cw/<id>`
   (`cam-task` step 6). Every tree, the worktree included, is clean: `git status --porcelain` prints nothing.
2. Score again with the real diff (`cam-difficulty`). The level went up → stop and ask.
3. Forbidden paths: `git diff --name-only <base>...HEAD` in each repo shows none of `.env*`, `*.pem`, `*.key`,
   `id_rsa*`, `secrets/`. A match → stop and ask.
4. Secrets: `<gitleaks>` is the kit's copy `~/.camarones/bin/gitleaks-*/gitleaks` (`gitleaks.exe` on Windows), or
   else `gitleaks` on PATH. In each repo: `<gitleaks> git --redact --log-opts="<base>..HEAD" .`. A finding → stop.
   Neither exists → write "gitleaks not run" under Warnings.
5. Stale docs: `{{CLI}} pr fresh <repo> --base <base>` for each repo lists the pages its code diff leaves stale (read
   from the main checkout, so pages you already updated still show). Each one is updated and committed in the worktree,
   or explained under Warnings.
6. `{{CLI}} check` on the worktree: no errors. Its warnings go under Warnings.
7. Trust: the docs commits (`git -C .cw/<id> diff <base>...HEAD`, the docs' `<base>`) add no `x-confirmed`, and edit
   no `<!-- human -->` block and no page with `x-owner: human`.
8. Board item, if any: linked to the pages the change updated, on the worktree, then committed (`cam-task` step 6):
   `{{CLI}} board link <ITEM> <page>[#section]`. It takes doc pages, not PR URLs. "Unknown item" means the card was
   made after the worktree's commit (cards are committed only at a checkpoint): skip the link, do not retry, and write
   "board item <ITEM> not linked to the docs" under Warnings. The PR bodies name the item either way.
9. Verification (`cam-verify`) is green for the current commit of every repo and of `.cw/<id>`. A commit came after →
   run it again.

## 2. Impact

- Repos and files: `git diff --stat <base>...HEAD` in each repo.
- Risk: the `Difficulty:` line from guardrail 2.
- Docs: the pages updated in the worktree; the confirmed ones among them need re-confirming by a person after merging.
- C4: the elements whose sources or repo the diff touches, and the elements related to them, their consumers (likec4
  MCP, or `{{CAM}}docs/architecture/*.c4`).
- Decisions: the ADRs in `{{CAM}}docs/decisions/` that cite the changed files.
- Your summary in two or three sentences, marked as yours.

## 3. Ask once

Show the impact, the verification table and the warnings, then ask: **"Open the PRs?"** Wait for a yes. A no, or a
change asked for → go back to the step it concerns.

## 4. On yes

1. Commit whatever is still pending in the worktree (after guardrail 1 there is nothing; if there was, run
   `cam-verify` and the guardrails again first). Push every branch: `git push -u origin cam/<id>-<slug>` in each repo
   and in `.cw/<id>`.
2. The code PR(s) first, as drafts, in each repo: `gh pr create --draft --base <branch> --title "<title>" --body-file <file>`
   (GitLab: `glab mr create --draft --target-branch <branch> --title "<title>" --description "<body>"`). `<branch>` is
   `<base>` without `origin/`; `<file>` a temporary file outside the repos.
3. Then the docs PR, from `.cw/<id>`, also a draft, its body linking the code PRs.
4. Then add the docs PR's link to each code PR body (`gh pr edit <url> --body-file <file>`,
   `glab mr update <n> --description "<body>"`).
5. Every body has these sections:

   ```
   ## Linked PRs
   Code: <url>… · Docs: <url> · Board: <ITEM> — merge the code first, the docs right after.
   ## Impact
   ## Difficulty
   ## Verification
   ## Warnings
   ```
6. No `gh`/`glab`, or not logged in: push, then give the person the URL that opens each PR and the bodies to paste.
7. A step failed halfway: run again from it, looking first for a PR already open for the branch
   (`gh pr list --head cam/<id>-<slug>`, `glab mr list --source-branch cam/<id>-<slug>`); never open a second one.
   The same step fails again → stop and give the person the error; never loop.

## 5. Hand over

- Give the PR URLs. You never move board columns: tell the person to move the item to review.
- Never merge, neither the code nor the docs. The person merges the code first and the docs right after, then
  re-confirms the confirmed pages the change edited.
- Then `cam-retro`.
