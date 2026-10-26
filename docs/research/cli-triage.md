# CLI triage: where each command lives

Generated from `.camarones/lib/catalog.py` by `camaron catalog --markdown` — do not edit by hand.
The portal is the team's viewer (reading, editing, review, pipeline status, interviews, sync); the
desktop app runs everything that starts a process, calls a model or changes this machine; the CLI keeps
every command either way.

## Portal (2)

| Command | Zone | AI | Destructive | --json |
|---|---|---|---|---|
| `confirm` | — |  |  |  |
| `feedback` | — |  |  |  |

## Desktop app (45)

| Command | Zone | AI | Destructive | --json |
|---|---|---|---|---|
| `ab` | check | yes |  | yes |
| `arch-draft` | analyze |  |  |  |
| `arch-validate` | check |  |  |  |
| `autopilot` | generate | yes |  |  |
| `blocks` | analyze |  |  | yes |
| `bump` | analyze |  |  | yes |
| `check` | check |  |  |  |
| `ci` | team |  |  |  |
| `config` | machine |  |  | yes |
| `detect` | machine |  |  |  |
| `doctor` | check |  |  | yes |
| `down` | machine |  |  |  |
| `eval` | check | yes |  | yes |
| `export` | team |  |  |  |
| `graph` | analyze |  |  |  |
| `health` | check |  |  | yes |
| `history` | analyze |  |  |  |
| `hooks` | team |  |  | yes |
| `init` | projects |  |  |  |
| `join` | projects |  |  |  |
| `llms` | analyze |  |  |  |
| `mark-documented` | analyze |  |  |  |
| `migrate` | machine |  | yes |  |
| `new` | projects |  |  |  |
| `pages` | analyze |  |  | yes |
| `plugins` | team |  |  | yes |
| `portal` | team |  |  |  |
| `pr` | generate | yes |  | yes |
| `profile` | machine |  |  |  |
| `projects` | projects |  |  | yes |
| `radar` | analyze |  |  | yes |
| `repair` | machine |  |  |  |
| `run` | generate | yes |  |  |
| `schemas` | analyze |  |  | yes |
| `self-update` | machine |  |  |  |
| `setup` | machine |  |  |  |
| `stack` | machine |  |  |  |
| `switch` | projects |  |  |  |
| `sync` | machine |  |  |  |
| `trust` | team |  |  | yes |
| `uninstall` | machine |  | yes |  |
| `unlink` | machine |  | yes |  |
| `upgrade` | machine |  |  |  |
| `version` | machine |  |  |  |
| `wiki` | generate | yes |  |  |

## Portal shows it, the app runs it (16)

| Command | Zone | AI | Destructive | --json |
|---|---|---|---|---|
| `board` | team |  |  | yes |
| `changes` | analyze |  |  |  |
| `checkpoint` | team |  |  |  |
| `fresh` | analyze |  |  | yes |
| `interview` | interviews |  |  | yes |
| `inventory` | analyze |  |  | yes |
| `kpis` | check |  |  | yes |
| `pipeline` | check |  |  | yes |
| `plan` | generate |  |  | yes |
| `remote` | team |  |  |  |
| `removed` | team |  |  |  |
| `runs` | generate |  |  | yes |
| `share` | team |  |  |  |
| `stats` | check |  |  | yes |
| `status` | check |  |  | yes |
| `translated` | team |  |  |  |

## Cli only (12)

| Command | Zone | AI | Destructive | --json |
|---|---|---|---|---|
| `app` | — |  |  |  |
| `arch` | — |  |  |  |
| `catalog` | — |  |  | yes |
| `diagrams` | — |  |  | yes |
| `help` | — |  |  |  |
| `hook` | — |  |  |  |
| `install` | — |  |  |  |
| `mcp` | — |  |  |  |
| `prompt` | — |  |  |  |
| `review` | — |  |  |  |
| `up` | — |  |  |  |
| `wizard` | — |  |  |  |
