---
type: guide
title: Self-hosted runner for docs proposals
description: How to register a machine of your own as a GitHub or GitLab runner so the AI docs proposal runs there, on your account or local model, never on a fork's code.
x-owner: human
---
# Self-hosted runner for docs proposals

> **TL;DR:** The `docs-propose` job runs an agent, so it only runs on a machine you control. Register one as a
> runner, log the agent in on it, set `ci.target: self-hosted` in `workspace.yaml`, run `camaron ci` and copy the
> generated job into each service repo. A member labels a PR `docs:update`; the runner opens the docs PR.

## When you need it

Without a runner, the same proposal runs on your machine: `camaron pr propose <PR url>`. The runner only makes it
automatic. The no-AI check (`docs-fresh`) needs no runner of yours.

## What the machine needs

| What | Why |
|---|---|
| git, and uv (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) | the job clones cam-docs and the kit and runs it with uv |
| The agent CLI, logged in as the account that pays: Claude Code, Codex, or OpenCode with a local model | the agent does the writing |
| A dedicated user without other secrets | the job runs the PR's code; keep it away from anything else |

## GitHub

1. Repo or organisation → Settings → Actions → Runners → New self-hosted runner. Follow the commands it shows on the
   machine, and give it the labels you will put in `workspace.yaml` (for example `self-hosted, docs`).
2. Run it as a service (`./svc.sh install && ./svc.sh start`) under the dedicated user.
3. In each service repo: variable `DOCS_REPO_URL` (the cam-docs https URL) and secret `DOCS_WRITE_TOKEN` (can push
   branches and open PRs on cam-docs).
4. Create the `docs:update` label. Only people who can label (triage permission or more) start the job, and it never
   runs for pull requests from forks.

## GitLab

1. Group or project → Settings → CI/CD → Runners → New runner, with a tag (for example `docs-ai`); install
   `gitlab-runner` on the machine with the shell executor and register it with the token it gives.
2. In each service repo: variables `DOCS_REPO_URL`, `DOCS_WRITE_TOKEN` (masked: `write_repository` and `api` on
   cam-docs) and `DOCS_BOT_TOKEN` (masked: `api` on that repo, to comment on the merge request).
3. Create the `docs:update` label. The job skips merge requests whose source is a fork.

## Turn it on

```yaml
# cam-docs/.camarones/workspace.yaml
ci:
  target: self-hosted
  runner_labels: [self-hosted, docs]     # GitHub runs-on
  runner_tags: [docs-ai]                 # GitLab tags
```

Then `camaron ci` writes `.camarones/ci/docs-propose.github.yml` (or `.gitlab-ci.yml`) next to `docs-fresh`. Copy it
into each service repo. Check a proposal first with `camaron pr propose <PR url> --dry-run` on the runner.

## Security

- The job only runs for labelled PRs from the same repository: a fork's code never reaches your machine.
- The cam-docs token lives in the job's environment, never in the runner's git configuration.
- The agent writes on a `docs/pr-<repo>-<n>` branch; nothing reaches cam-docs without a person merging the docs PR.
