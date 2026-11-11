# Libraries: the version in view, the latest one, an update a click away — design

The user's request (2026-11-11): the Libraries screen should show the version and let you update it; the portal's and
the app's should be the same; the scroll is uncomfortable.

## 1. Intent

Today the two screens differ and neither answers "which version do we use, is there a newer one, update it":

- **The app** draws a library × repo matrix. Each repo is a column, so with many services the version of a library sits
  off screen to the right. Updating means opening the row, and the version field sits at the far right of a detail row
  as wide as the matrix: a sideways scroll inside a sideways scroll.
- **The portal** draws an older copy of the matrix, with no detail (why it is there, the full advisories) and no
  update.
- The kit knows the version each repo declares and, after a scan, the version that fixes each advisory. It does not
  know the latest published version of anything.

This piece makes Libraries **one shared screen** where every library is one line with its version and the latest
stable one, and **Update** proposes that version.

**Done when:** in the app or the portal, without scrolling sideways, you can tell for every library which version the
repos use, whether a newer stable version exists, and (in the app) update it in a repo in three clicks: Update ▾,
Update, Yes.

**Anti-goals — a failure even if it works:** any sideways scroll at a normal window width; the portal and the app
drawing different tables; a library name sent anywhere without the person asking for it in that moment; a library the
workspace itself produces ever sent to a registry; the lookup failing the command or wiping the last one when there is
no network; a 3.x/4.x project that needs a manual step.

### 1.1 Decisions taken with the user (2026-11-11)

| Question | Decision |
|---|---|
| Which version to show | Current and latest: the latest stable from public registries, looked up on demand |
| App ↔ portal | One shared view in `@camaron/ui`, like Salud's `HealthBoard`; the portal is read-only and shows the `camaron bump` command to copy where the app has the button |
| Where the lookup lives | `camaron inventory --latest`, stored in the same `inventory.json` |
| Privacy | Runs only when the person presses it (or passes `--latest`); the workspace's own libraries are never looked up; one not on a public registry stays "—" |
| Screen | One line per library (no repo columns), filters and table header stick while scrolling, Update ▾ opens the line with the version already filled in |

## 2. The screen (shared)

`LibrariesBoard` in `.camarones/ui/src/libs.jsx`, exported from `@camaron/ui`, with its strings in the shared
dictionary (`.camarones/ui/i18n/index.js`, `lb.*`, es and en). Both apps render it; the portal passes no actions.

**Summary line:** how many libraries, chips per severity (or "no known vulnerabilities", or "not scanned yet"), a chip
"N with a newer version" once a lookup ran, and the dates of the last CVE scan and the last lookup. In the app, on the
right: **Scan for vulnerabilities** (primary), **Look for newer versions**, **Reread from the code**, and a muted line
saying what each one sends out: the scan nothing (offline database), the lookup the library names to public registries.

**Filters** (sticky under the app's header / the portal's top bar while the page scrolls): search, category, repo,
scope, "Only vulnerable", "Only outdated" (shown once a lookup ran).

**Table** (fixed layout, four columns, header sticky under the filters):

| Column | Shows |
|---|---|
| Library | name, ecosystem, severity chip, "different versions" chip, and "in repo · repo · +N more" (flagged repos first, as today's `placesOf`) |
| Version | the version the repos use; when they differ, the range lowest – highest; when no repo has an exact one, what the manifest says (`managed`, a range) |
| Latest | the latest stable version; "major" chip when its first number is higher; "up to date" chip when no repo is behind; "—" when unknown or not looked up |
| (action) | **Update ▾** on every line except an up-to-date one with no known vulnerability (unknown latest included: the field is then empty) |

The vulnerable lines keep their red / amber mark on the left. Sorting stays as today: worst severity first, then
category, then name. With the repo filter set (`#/libs/<repo>` in the portal), Version shows that repo's own version.

**Update ▾ opens the line** (one open at a time, scrolled into view) with the current detail, reordered to put the
action first:

1. **Update, per repo:** repo, manifest, scope, current version →, a version field filled with the proposed version
   (§4), suggestion chips "fixes the CVEs: X" and "latest: Y" that fill the field, and **Update**. In the portal, in
   place of the field and button: the command `camaron bump <repo> <library> <version>` with a copy button and the note
   that it shows the change first and `--yes` makes it.
2. **Why it is flagged:** the advisories, as today (`Advisory`, folded).
3. **Why it is there:** the declared value and who manages it, as today.

Nothing in the detail is wider than the table, so no sideways scroll there either.

## 3. The lookup: `camaron inventory --latest`

New module `.camarones/lib/latest.py`, standard library only (no new dependency; §2.4 of AGENTS.md is not triggered).

- `lookup(rows, owned, log, fetch=_fetch) -> dict`: the unique `(ecosystem, name)` of the inventory rows, minus the
  workspace's own (`owned`), each asked of its registry, 8 at a time, 10 s timeout, `User-Agent: camaron/<kit>` (no
  personal data), proxies from the environment (`urllib` default). Logs `[n/total] newer versions · <name>` as they
  finish, at most about 50 such lines however many libraries there are; the app reads them with its own small parser
  (`lookupProgress`: Maven names hold a colon, which `scanProgress` splits on).
- One pure parser per registry, picking the highest **stable** version (no alpha, beta, rc, cr, milestone `M1`, preview,
  dev, snapshot, ea); when the current version has a qualifier such as Guava's `-jre`, a version with the same qualifier
  is preferred:

| Ecosystem | URL | Read |
|---|---|---|
| Maven | `https://repo1.maven.org/maven2/<group as path>/<artifact>/maven-metadata.xml` | `versioning/versions/version` |
| npm | `https://registry.npmjs.org/<name, / encoded>` (abbreviated metadata) | `dist-tags.latest` |
| PyPI | `https://pypi.org/pypi/<name>/json` | `releases` keys, else `info.version` |
| Go | `https://proxy.golang.org/<module, capitals as !lower>/@latest` | `Version` |
| NuGet | `https://api.nuget.org/v3-flatcontainer/<id lowercased>/index.json` | `versions` |
| Packagist | `https://repo.packagist.org/p2/<vendor>/<package>.json` | `packages[name][].version` |
| crates.io | `https://crates.io/api/v1/crates/<name>` | `crate.max_stable_version` |
| Pub | `https://pub.dev/api/packages/<name>` | `latest.version` |

- **Owned libraries** (`inventory.owned()`, from the workspace's manifests): the groupIds of its poms and Gradle
  `group =`, the names and `@scopes` of its `package.json`, its Go module paths (and anything under them), the project
  names of its `pyproject.toml`, `Cargo.toml`, `composer.json` and `pubspec.yaml`. They are never sent.
- **Never raises.** A 404 leaves that library without a latest; a registry that does not answer (timeout, DNS, 5xx)
  is listed in `failed` once, by registry name, and its libraries keep the version the last lookup found.
- Returns `{"at": iso, "checked": n, "found": n, "failed": [registry, …], "versions": {"<ecosystem>|<name>": "x.y.z"}}`.

**Stored** in `docs/.work/inventory.json` under a new top-level key `latest` (absent or `null` = never looked up).
`inventory.run(cves=…, latest=…)`: with `latest`, the lookup runs after the scan and merges over the previous
`versions` (so a failed registry keeps its old answers); without it, the previous `latest` is carried over unchanged,
as `vulns` already is.

**CLI:** `camaron inventory [--cves] [--latest] [--json] [--fail-on …]`. Text output adds
"✔ N with a newer version (lookup: K libraries, F registries failed)". The exit code ignores the lookup. The catalog
entry does not change (`inventory` is already `both`); the app's `/api/app/*` sees the new flag through the parser.

**Page:** `docs/overview/libraries.md` gains a **Latest** column when `latest` exists, and the TL;DR counts the
libraries with a newer version.

**App progress:** the job shows the bar and "Checking `<name>` · n of total" without the per-item chip list the CVE
scan draws per repo; it ends on the tick with "N with a newer version" and, if any, "Could not reach: npm, …".
`inventoryArgs` accepts `--latest` so leaving and coming back re-attaches to a running lookup.

**Exit:** a lookup never changes the exit code; `--fail-on` still reads only the vulnerabilities.

## 4. Update

The command does not change: `camaron bump <repo> <library> <version>` plans first, the app asks, `--yes` makes branch
`camaron/bump-<name>-<version>` with the repo's package manager, nothing committed (`lib/bump.py`).

Proposed version, per repo: the latest stable when known and higher than that repo's version; else the version that
fixes its advisories (`fixTarget`); else empty for the person to type. Both known and different → both chips shown.
After a bump the inventory is reloaded, as today.

## 5. The code

| Piece | Change |
|---|---|
| `lib/latest.py` | new: parsers, stable filter, `lookup` |
| `lib/inventory.py` | `owned()`, `run(latest=)`, carry `latest` over, Latest column in `render` |
| `camarones.py` | `--latest` on `inventory`; help line |
| `ui/src/libs.js` | pure helpers: `versionSpan`, `latestOf`, `isMajor`, `outdated`, `proposed`, the "outdated" filter; `matrix()` gains `latest` per item |
| `ui/src/libs.jsx` | new: `LibrariesBoard`, `LibraryDetail`, `Advisory`, `Where` (moved from the app), the portal's `BumpCommand` |
| `ui/i18n/index.js` | the `lb.*` strings, es and en (moved from both apps, plus the new ones) |
| `ui/src/ui.css` | `cu-libs*` styles (sticky filters and header, fixed columns, open line) |
| `desktop/renderer/src/sections/Libs.jsx` | wiring only: commands, `ScanStatus`, the stateful `Update` passed in as the action |
| `portal/app/src/Libs.jsx` | fetch + `LibrariesBoard` read-only; old `libs*` strings and matrix styles go |

The tour targets `libs-actions`, `libs-filters`, `libs-table` stay on the same controls.

## 6. Errors

- No network / registry down: the job ends normally; the summary line says, without a joke, "Could not reach npm,
  PyPI. The versions shown are from <date>." (or "never looked up").
- A library not on a public registry: "—" in Latest; Update ▾ still opens, with an empty field.
- `inventory.json` missing or from an older kit: rendered as today, Latest "—", "Only outdated" hidden.

## 7. Tests (written first)

- **pytest** (offline, `isolated_env`, `make_workspace`): each parser on a saved payload; the stable filter and the
  qualifier preference; `lookup` with a fake `fetch` (found, 404, timeout → `failed`, owned skipped and never fetched);
  `owned()` per manifest type; `run(latest=True)` stores and merges, `run()` carries `latest` over, an old
  `inventory.json` without the key loads; `inventory --latest --json` through the CLI with `fetch` patched; the Latest
  column in the page.
- **e2e** (`tests/e2e`, `-m e2e`): one known library per registry returns a version.
- **Vitest:** the new helpers in `ui/src/libs.test.js`; `LibrariesBoard` read-only (no buttons, the bump command) and
  with actions; the app's `Libs.test.jsx` and the portal's `Libs.test.jsx` updated; `scanProgress`/`inventoryArgs`
  with `--latest`.
- `uv run pytest -n auto` green on the three OSes; both bundles rebuilt and matching their source.
- End to end in the sandbox with this checkout's app: lookup, filter outdated, update one library, `traces` clean.

## 8. Compatibility and docs

Only additions: one flag, one optional key, new strings. Nothing renamed or removed from the CLI, `workspace.yaml`,
frontmatter or file locations. `VERSIONS["kit"]` → **4.80.0**. Same commit: `README.md`, the guides `app`, `portal`
and `using` (en and es), the tutorial pages if they list `inventory`'s flags, `.camarones/TUTORIAL.md` regenerated.
