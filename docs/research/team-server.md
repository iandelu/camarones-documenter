# Central MCP / team server — spike RFC

Status: **proposal** (R36). Not built. This page decides what a shared server would be for, what it must never do,
and the smallest version worth trying. Related: [harness-refactor.md](harness-refactor.md) §8 (MCP), H16, H23, H27.

## 1. The problem

Today every developer runs the `camarones` MCP server locally (stdio, or `camaron mcp --http` on 127.0.0.1). It
reads that machine's clone of `cam-docs`. That works for people who have the workspace. It does not cover:

- people and agents **without the workspace** (product, support, an agent in a cloud IDE, a chat bot);
- a **single, fresh answer** for everyone: a laptop may be days behind `main` of `cam-docs`;
- **team-level signals**: which questions find nothing, which pages are read most (usage today is per machine and
  rolled up through git).

## 2. What it would be

One process the team hosts on its own infrastructure (H23: never a third-party service), serving the same tools as
the local server over Streamable HTTP, against a read-only checkout of `cam-docs` `main` it pulls every few minutes.

| Area | Local server (today) | Team server (proposal) |
|---|---|---|
| Docs read | the laptop's clone | `main`, pulled on a timer |
| Tools | read, ask, draft writes, pipeline control | read and ask only; writes become feedback entries |
| Freshness gate | yes | yes, the same `freshness.gate` (H27) |
| Auth | per-machine token, 127.0.0.1 only | the company SSO in front (reverse proxy), per-user tokens |
| Code access | the repos next to cam-docs | none by default; `repo_graph` only if graphs are published with the docs |

## 3. What it must never do

- **Run agents or units.** `run_node` stays local: cost and code execution belong to a person's machine or a
  self-hosted runner (R31).
- **Write to `cam-docs` directly.** `propose_edit` and `add_feedback` turn into review-feedback entries opened as a
  docs PR by a bot account, so every change still goes through review (H27, draft → confirmed).
- **Serve withheld pages.** Out-of-date and unreviewed pages stay withheld, exactly as locally.
- **Leave the company network.** No telemetry; the usage counts stay in `cam-docs` like today's roll-ups.

## 4. Smallest version worth trying

1. A container image built from the kit (`camaron mcp --http --bind 0.0.0.0`) with a read-only `cam-docs` checkout
   and a `git pull` loop; tools limited to `search_docs`, `read_doc`, `list_docs`, `doc_status`, `ask`.
2. Behind the company's reverse proxy for SSO; the proxy injects the user in a header the server records in usage.
3. Measure for a month: questions per day, share of `ask` with no result, pages withheld when asked. Decide then.

## 5. Open questions

- Is pulling `main` enough, or do people expect open docs PRs to be visible too (a "preview" flag per request)?
- Should the code graph be published with the docs for `repo_graph`, or stay local?
- Per-user tokens through the proxy, or the proxy's identity only?

## 6. Decision needed

Whether to build the smallest version (§4) as a plugin (`plugins/team-server`) once a team asks for it. Until then
the local server plus `llms.txt` / `llms-full.txt` in the static portal export cover read-only access for people
without the workspace.
