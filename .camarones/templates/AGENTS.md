# {{PROJECT_NAME}} — umbrella repository

<!-- camarones:start -->
This folder is the documentation hub of **{{PROJECT_NAME}}**, managed with the Camarones Documenter kit 🦐. Service repos listed in
`.camarones/workspace.yaml` live next to this file (git-ignored).

## Start of every session
1. Read `docs/.work/handoff.md` (what the last session did and left pending) and run `./camarones.command plan next`.
2. A unit marked `[in progress]` was interrupted (session closed): resume it from its checkpoints in `docs/.work/units/`
   instead of starting over. Otherwise, if the user did not give a task, propose the next ready unit. Follow
   `.camarones/PLAYBOOK.md` ("Session protocol"); save progress often with `./camarones.command plan note <unit> "…"`.
   Human review comments waiting to be applied live in `docs/.work/review-feedback.md` (unit `review-fixes`).
3. Doc rules: `.camarones/CONVENTIONS.md` (binding). Doc index for retrieval: `docs/llms.txt`.
4. JVM repos with SDKMAN: run `source ~/.sdkman/bin/sdkman-init.sh && sdk env` in the repo before `mvn`/`gradle` (prefer `./mvnw`, `./gradlew`).
5. Code questions: `graphify query "<question>" --graph .camarones/.cache/graph/graph.json` (all repos) or `graphify query "…"` inside a repo.

## Trust rule
`confirmed` pages (`./camarones.command status`) were validated by a human: treat them as the source of truth and flag contradictions
instead of rewriting them. `draft` pages are AI-generated: verify against code. Never write `x-confirmed`; never edit
`<!-- human -->` blocks or files with `x-owner: human`.

## CLI (Windows: `camarones.cmd` instead of `./camarones.command`)
`./camarones.command help` · `plan next` · `plan start|note|done <unit>` · `checkpoint` · `status` · `check` · `changes` ·
`arch-validate` · `translated` · `llms` · `portal`
<!-- camarones:end -->
