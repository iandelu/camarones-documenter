---
name: cam-verify
description: Step of cam-task — build and run the change's verification plan.
---

# Verify a change

Build the plan for each repo you changed, run it, and record the evidence. Commit first, the code and the docs
(`cam-task` steps 5 and 6): evidence counts for one commit only, on a clean tree.

1. Detect the profile at the repo's root and run its checks:

   | Detect | Run |
   |---|---|
   | `mvnw` / `pom.xml` | `./mvnw -q test`; `./mvnw -q verify` with the `migration` or `contract` signal |
   | `gradlew` / `build.gradle*` | `./gradlew test`; `./gradlew check` with `migration` or `contract` |
   | `package.json` | `npm test`, `pnpm test` or `yarn test` by lockfile, plus its `lint` script when it has one |
   | `pyproject.toml` | `uv run pytest` (or `pytest`) |
   | `go.mod` | `go test ./...` |
   | `Cargo.toml` | `cargo test` |
   | `*.sln` / `*.csproj` | `dotnet test` |

   Windows: `mvnw.cmd`, `gradlew.bat`. JVM repos with SDKMAN: `source ~/.sdkman/bin/sdkman-init.sh && sdk env` in the
   repo first.
2. Add the repo's declared checks: `repos[].verify` in `{{CAM}}.camarones/workspace.yaml`, when present. `profile`
   replaces the detected one; each entry of `extra: [{id, run: [argv…]}]` is one more check.
3. The docs: `{{CLI}} check` on the docs worktree, from the workspace root, with no errors:
   `CAMARONES_ROOT="$PWD/.cw/<id>" CAMARONES_WORKSPACE="$PWD" CAMARONES_STATE_ROOT="$PWD/{{CAM}}." {{CLI}} check`
   (plain `check` inside the worktree reports false "sources no longer exist" errors). It rewrites the four derived
   files of `cam-task` step 6: leave them uncommitted.
4. You may add checks for a risk (e.g. an integration test for `migration`), each with a one-line why, listed apart as
   yours. Never drop a check from steps 1–3.
5. Evidence, per check: the command, its exit code and `git rev-parse HEAD` of its repo (for `check`, of `.cw/<id>`),
   with a clean tree as `cam-task` step 6 defines it (in `.cw/<id>`, only the four derived files may be listed). A new
   commit makes it stale: run it again.
6. A failed check: run it once more, unchanged.
   - Failed then passed is `flaky`: report it; it needs the person's word before `cam-ship`.
   - Failed again: read the log, fix the code (not the test, unless the test is wrong, and then say so), run again.
   - A check that cannot run (no Docker, a missing tool or service) is `not green`: say what is missing and how to
     fix it. Never report it as passed.
7. Report a table: check · command · exit · commit · origin (`base`, or `added: <why>`).

Copy commands and exit codes from real runs, never from memory. A later kit version adds `change verify`, which runs
this plan and records the evidence itself; it does not exist yet.
