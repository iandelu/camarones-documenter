# {{PROJECT_NAME}} — documentation hub

<!-- camarones:start -->
This is the living documentation of **{{PROJECT_NAME}}**, managed with the Camarón kit 🦐. Docs, architecture and
agent config live in `{{CAM}}` (its own git repo); the service repos listed in `{{CAM}}.camarones/workspace.yaml` sit next to it
and never receive kit files.

## Implementing a feature (any repo)
1. Before coding, look it up: `camarones` MCP tools (`search_docs`, `read_doc`, `repo_graph`) or `{{CAM}}docs/llms.txt`.
   `confirmed` pages are the source of truth; `draft` pages must be verified against the code.
2. Code questions: `graphify query "<question>" --graph {{CAM}}graph/<repo>/graph.json` (one repo) or
   `--graph {{CAM}}.camarones/.cache/graph/graph.json` (all repos).
3. After changing behaviour, update the affected pages in `{{CAM}}docs/` in the same session (skill `cam-docs-update`),
   then `{{CLI}} check`. The docs are alive: code and docs change together.

## Documentation sessions
1. Read `{{CAM}}docs/.work/handoff.md` (what the last session did and left pending) and run `{{CLI}} plan next`.
2. A unit marked `[in progress]` was interrupted: resume it from its checkpoints in `{{CAM}}docs/.work/units/` instead of starting
   over. Otherwise propose the next ready unit. Follow `{{CAM}}.camarones/PLAYBOOK.md` ("Session protocol"); save progress often
   with `{{CLI}} plan note <unit> "…"`. Human review comments waiting to be applied: `{{CAM}}docs/.work/review-feedback.md`.
3. Doc rules: `{{CAM}}.camarones/CONVENTIONS.md` (binding). Paths in the playbook and conventions are relative to `{{CAM}}`.
4. JVM repos with SDKMAN: run `source ~/.sdkman/bin/sdkman-init.sh && sdk env` in the repo before `mvn`/`gradle` (prefer `./mvnw`, `./gradlew`).

## Trust rule
`confirmed` pages (`{{CLI}} status`) were validated by a human: treat them as the source of truth and flag contradictions
instead of rewriting them. `draft` pages are AI-generated: verify against code. Never write `x-confirmed`; never edit
`<!-- human -->` blocks or files with `x-owner: human`.

## CLI
`{{CLI}} help` · `plan next` · `plan start|note|done <unit>` · `checkpoint` · `status` · `check` · `changes` ·
`arch-validate` · `translated` · `llms` · `up` (portal: read, edit, confirm)
<!-- camarones:end -->
