# Libraries: current and latest version, one shared screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Libraries shows, in the portal and the app alike, one line per library with the version the repos use and the
latest stable one, and in the app updates it with that version already proposed.

**Architecture:** A new `lib/latest.py` asks public registries for each library's latest stable version when
`camaron inventory --latest` runs, and `lib/inventory.py` keeps the answer in `inventory.json` under `latest`. A new
shared `LibrariesBoard` in `@camaron/ui` draws the screen from that file; the app passes its commands and its `bump`
control, the portal passes nothing and gets the command to copy.

**Tech Stack:** Python 3 standard library (`urllib`, `concurrent.futures`, `xml.etree`), pytest; React 19, Vitest,
Vite (portal and desktop renderer builds).

**Spec:** `docs/superpowers/specs/2026-11-11-libraries-versions-design.md`

## Global Constraints

- macOS, Windows and Linux: `pathlib`, `encoding="utf-8"`, processes only through `lib/common.py` helpers, no `shell=True`.
- No new dependency: registries are read with the standard library only.
- Tests are offline and deterministic (`kit` fixture, `isolated_env`); the only network test lives in `tests/e2e/` with the `e2e` marker.
- Never send a library the workspace itself produces; never send anything unless `--latest` was passed.
- The lookup never raises and never changes the exit code; a failed registry keeps the previous answers.
- `User-Agent: camaron/<VERSIONS["kit"]>`; no user name, email or project in any request.
- Every user-facing string exists in `es` and `en`; no joke in errors, warnings or prompts; at most one per screen.
- Backward compatible: only a new flag and a new optional `inventory.json` key; an `inventory.json` without `latest` keeps working.
- `VERSIONS["kit"]` → `4.80.0`; README badge, guides (en+es) and tutorial move in the same change.
- Conventional commits; no `Co-Authored-By` or "Generated with" lines; stage only this work's files.
- The committed `portal/app-build/` and `desktop/renderer-build/` must match their source after `npm run build`.

## Review Focus

1. A pom with no `<groupId>` of its own inheriting it from an outside parent (`spring-boot-starter-parent`) → that group must not count as the workspace's, or every Spring Boot library would be skipped. Pinned in Task 3 (`test_owned_names_come_from_the_workspace_manifests`).
2. A Maven name (`group:artifact`) or an npm scoped name (`@scope/name`) reaching a URL unescaped → wrong registry path. Pinned in Task 1 (`test_urls`).
3. A library no repo pins exactly (managed by a parent/BOM, or a `^range` with no lock) → it must show what the manifest says, never "up to date", and still propose the latest. Pinned in Task 4 (`versionSpan`/`outdated` with no exact cell).
4. One registry down while others answer → that registry's libraries keep last time's version and are not shown as up to date. Pinned in Task 3 (`test_a_failed_registry_keeps_last_answers`).
5. The workspace's own library declared as a dependency by another of its repos → never fetched. Pinned in Task 2 (`test_owned_libraries_are_never_fetched`).

A long name in a narrow window must not bring the sideways scroll back: checked in the real apps in Task 9.

---

### Task 1: Registry URLs, parsers and the stable version pick

**Files:**
- Create: `.camarones/lib/latest.py`
- Test: `tests/test_latest.py`

**Interfaces:**
- Produces (used by Tasks 2–3):
  - `class NotFound(Exception)`
  - `stable(version: str) -> bool`
  - `newer(current: str | None, candidate: str | None) -> bool` — True when `candidate` is a higher version than `current` (False if either is missing).
  - `pick(versions: Iterable[str], current: str | None = None) -> str | None`
  - `url(ecosystem: str, name: str) -> str | None` — None for an ecosystem not in the table or a malformed name.
  - `parse(ecosystem: str, body: bytes, name: str, current: str | None = None) -> str | None` — None when the payload has no stable version or cannot be read.

- [ ] **Step 1: Write the failing tests** in `tests/test_latest.py` (import with `from lib import latest` inside each test, after the `kit` fixture, as `tests/test_osv.py` does):

```python
@pytest.mark.parametrize("v, ok", [("3.4.1", True), ("33.0.0-jre", True), ("5.3.39.RELEASE", True), ("1.0.0.Final", True),
    ("4.0.0-SNAPSHOT", False), ("6.2.0-M1", False), ("2.0.0-rc.1", False), ("3.0.0-RC2", False), ("1.2.3-beta.2", False),
    ("2.0.0a1", False), ("2.0b3", False), ("1.0.0-alpha", False), ("18.0.0-next.3", False), ("1.0.0-dev.1", False),
    ("21-ea", False), ("1.0.0-build.5", True)])
def test_stable(kit, v, ok): assert latest.stable(v) is ok

def test_newer(kit):
    assert latest.newer("8.3.9", "8.3.10") and latest.newer("2.0.0-rc.1", "2.0.0") and latest.newer(None, "1.0") is False
    assert not latest.newer("v1.2", "1.2.0") and not latest.newer("1.2.0", "1.1.9") and not latest.newer("1.0", None)

def test_pick_prefers_the_current_qualifier(kit):
    assert latest.pick(["32.1.0-jre", "33.0.0-android", "33.0.0-jre", "34.0.0-rc1"], "32.1.0-jre") == "33.0.0-jre"
    assert latest.pick(["1.0", "2.0-M1", "1.5"]) == "1.5" and latest.pick(["2.0-M1"]) is None and latest.pick([]) is None

def test_urls(kit):
    assert latest.url("Maven", "org.postgresql:postgresql") == "https://repo1.maven.org/maven2/org/postgresql/postgresql/maven-metadata.xml"
    assert latest.url("npm", "@angular/core") == "https://registry.npmjs.org/@angular%2Fcore"
    assert latest.url("PyPI", "SQLAlchemy") == "https://pypi.org/pypi/SQLAlchemy/json"
    assert latest.url("Go", "github.com/BurntSushi/toml") == "https://proxy.golang.org/github.com/!burnt!sushi/toml/@latest"
    assert latest.url("NuGet", "Newtonsoft.Json") == "https://api.nuget.org/v3-flatcontainer/newtonsoft.json/index.json"
    assert latest.url("Packagist", "symfony/console") == "https://repo.packagist.org/p2/symfony/console.json"
    assert latest.url("crates.io", "serde") == "https://crates.io/api/v1/crates/serde"
    assert latest.url("Pub", "http") == "https://pub.dev/api/packages/http"
    assert latest.url("Maven", "no-colon") is None and latest.url("Packagist", "novendor") is None and latest.url("Hex", "x") is None
```

  Plus one `test_parse_<ecosystem>` per registry with a small saved payload inline: Maven metadata XML with versions
  `42.6.0, 42.7.4, 42.8.0-SNAPSHOT` → `"42.7.4"`; npm `{"dist-tags": {"latest": "19.0.5"}}` → `"19.0.5"`; PyPI
  `{"info": {"version": "2.0.36"}, "releases": {"2.0.36": [], "2.1.0b1": []}}` → `"2.0.36"`; Go `{"Version": "v1.4.0"}`
  → `"v1.4.0"`; NuGet `{"versions": ["13.0.3", "13.0.4-beta1"]}` → `"13.0.3"`; Packagist
  `{"packages": {"symfony/console": [{"version": "v7.1.0"}, {"version": "v7.2.0-BETA1"}]}}` → `"v7.1.0"`; crates.io
  `{"crate": {"max_stable_version": "1.0.215"}}` → `"1.0.215"`; Pub `{"latest": {"version": "1.2.2"}}` → `"1.2.2"`;
  and `latest.parse("npm", b"not json", "x") is None`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_latest.py -v`
Expected: FAIL, `ImportError: cannot import name 'latest'`.

- [ ] **Step 3: Implement the five functions in `.camarones/lib/latest.py`**

Module docstring states what leaves the machine and when (as `lib/osv.py` does). Version order: the same rules as
`compareVersions` in `ui/src/libs.js` (numbers compared as numbers, a leading `v` ignored, missing parts are 0, a
pre-release before its release). Pre-release markers, as one compiled regex: `alpha, beta, rc, cr, m, milestone,
preview, pre, dev, snapshot, ea, canary, nightly, next, a, b`, each after a separator or directly after a digit, followed
by optional digits and then a separator or the end. The qualifier of a version is its trailing non-numeric suffix
(`-jre`); `pick` keeps only stable versions, narrows to those sharing `current`'s qualifier when any do, and returns the
highest. Go names escape capitals as `!` + lowercase; npm names keep `@` and encode `/`; NuGet ids are lowercased.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/test_latest.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/latest.py tests/test_latest.py
git commit -m "feat(latest): registry URLs, parsers and the stable version pick"
```

---

### Task 2: The lookup: in parallel, owned libraries skipped, failures kept per registry

**Files:**
- Modify: `.camarones/lib/latest.py`
- Test: `tests/test_latest.py`

**Interfaces:**
- Consumes: Task 1's functions.
- Produces (used by Task 3):
  - `is_owned(ecosystem: str, name: str, owned: dict[str, set[str]]) -> bool`
  - `lookup(rows: list[dict], owned: dict[str, set[str]], log=print, fetch=None) -> dict` returning
    `{"at": str, "checked": int, "found": int, "failed": list[str], "versions": dict[str, str]}`; keys of `versions` are
    `f"{ecosystem}|{name}"`; `failed` holds ecosystem names, sorted.
  - `_fetch(url: str) -> bytes` — raises `NotFound` on HTTP 404/410; any other error propagates.

- [ ] **Step 1: Write the failing tests**

```python
ROWS = [{"repo": "api", "ecosystem": "Maven", "name": "org.postgresql:postgresql", "version": "42.6.0"},
        {"repo": "web", "ecosystem": "Maven", "name": "org.postgresql:postgresql", "version": "42.5.0"},
        {"repo": "web", "ecosystem": "npm", "name": "react", "version": "18.2.0"},
        {"repo": "web", "ecosystem": "npm", "name": "@acme/ui", "version": "1.0.0"},
        {"repo": "web", "ecosystem": "Maven", "name": "com.acme:core", "version": "2.0"},
        {"repo": "web", "ecosystem": "npm", "name": "left-pad", "version": None},
        {"repo": "web", "ecosystem": "Hex", "name": "phoenix", "version": "1.7.0"}]
OWNED = {"Maven": {"com.acme"}, "npm": {"@acme/"}}

def test_is_owned(kit):
    assert latest.is_owned("Maven", "com.acme:core", OWNED) and not latest.is_owned("Maven", "com.acmex:core", OWNED)
    assert latest.is_owned("npm", "@acme/ui", OWNED) and latest.is_owned("npm", "web", {"npm": {"web"}})
    assert latest.is_owned("Go", "github.com/acme/api/pkg", {"Go": {"github.com/acme/api"}})
    assert latest.is_owned("PyPI", "My_Worker", {"PyPI": {"my-worker"}})

def test_owned_libraries_are_never_fetched(kit):
    asked = []
    def fetch(u):
        asked.append(u)
        return b'{"dist-tags": {"latest": "19.0.0"}}' if "npmjs" in u else b"<metadata><versioning><versions><version>42.7.4</version></versions></versioning></metadata>"
    out = latest.lookup(ROWS, OWNED, log=lambda _: None, fetch=fetch)
    assert not any("acme" in u for u in asked) and not any("phoenix" in u for u in asked)
    assert out["versions"] == {"Maven|org.postgresql:postgresql": "42.7.4", "npm|react": "19.0.0", "npm|left-pad": "19.0.0"}
    assert out["checked"] == 3 and out["found"] == 3 and out["failed"] == []

def test_a_404_is_not_a_failure_and_a_dead_registry_is(kit):
    def fetch(u):
        if "npmjs" in u: raise OSError("no route")
        raise latest.NotFound(u)
    out = latest.lookup(ROWS, OWNED, log=lambda _: None, fetch=fetch)
    assert out["versions"] == {} and out["failed"] == ["npm"] and out["checked"] == 3

def test_it_never_raises_and_says_what_it_did(kit):
    lines = []
    out = latest.lookup(ROWS, OWNED, log=lines.append, fetch=lambda u: (_ for _ in ()).throw(RuntimeError("boom")))
    assert out["failed"] == ["Maven", "npm"]
    assert lines[-1].startswith("✔ 0 with a newer version") and "could not reach: Maven, npm" in lines[-1]
    assert any(l.startswith("[3/3] newer versions · ") for l in lines)

def test_progress_is_at_most_about_fifty_lines(kit):
    rows = [{"repo": "web", "ecosystem": "npm", "name": f"p{i}", "version": "1.0.0"} for i in range(400)]
    lines = []
    latest.lookup(rows, {}, log=lines.append, fetch=lambda u: b'{"dist-tags": {"latest": "1.0.0"}}')
    progress = [l for l in lines if l.startswith("[")]
    assert 40 <= len(progress) <= 51 and progress[-1].startswith("[400/400] newer versions · ")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_latest.py -v -k "owned or 404 or raises or progress"`
Expected: FAIL, `AttributeError: module 'lib.latest' has no attribute 'is_owned'`.

- [ ] **Step 3: Implement `is_owned`, `_fetch` and `lookup` in `.camarones/lib/latest.py`**

`is_owned`: Maven prefix `group + ":"`; npm exact name or a stored `@scope/` prefix; Go exact or `module + "/"` prefix;
PyPI names compared after `re.sub(r"[-_.]+", "-", n).lower()`; other ecosystems exact. `_fetch`: `urllib.request` with
`timeout=10`, headers `User-Agent: camaron/<VERSIONS["kit"]>` and, for npm, `Accept: application/vnd.npm.install-v1+json`.
`lookup`: one item per unique `(ecosystem, name)` with a `url` and not owned; `current` = the highest exact `version` of
its rows; `ThreadPoolExecutor(max_workers=8)`; a progress line on completion every `max(1, total // 50)` items and on the
last; a `NotFound` or an unreadable payload leaves the item out of `versions`; any other exception adds the ecosystem to
`failed`; the whole body wrapped so nothing escapes. Last line:
`✔ {n} with a newer version ({checked} libraries looked up[; could not reach: A, B])`, where `n` counts items whose
`newer(current, found)`.

- [ ] **Step 4: Run the file to verify it passes**

Run: `uv run pytest tests/test_latest.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/latest.py tests/test_latest.py
git commit -m "feat(latest): look up every library's latest stable version, never the workspace's own"
```

---

### Task 3: `inventory --latest`: owned names, storage, the page and the CLI

**Files:**
- Modify: `.camarones/lib/inventory.py` (`pom`, `owned`, `run`, `render`)
- Modify: `.camarones/camarones.py:74-77` (help line), `:435-437` (flag), `:903-912` (pass it through)
- Test: `tests/test_inventory.py`
- Create: `tests/e2e/test_latest_registries.py`

**Interfaces:**
- Consumes: `latest.lookup`, `latest.newer` (Tasks 1–2).
- Produces (used by Tasks 4–7 through `GET /api/inventory`): `inventory.json` key `latest`, absent/`None` or
  `{"at", "checked", "found", "failed", "versions"}`; `inventory.owned() -> dict[str, set[str]]`;
  `inventory.run(log=print, cves: bool = False, latest: bool = False) -> Path`.

- [ ] **Step 1: Write the failing tests** (in `tests/test_inventory.py`, using the existing `repos` fixture; patch the network with `monkeypatch.setattr(lib.latest, "_fetch", fake)`):

```python
def test_owned_names_come_from_the_workspace_manifests(kit, repos):
    (kit.ws / "worker" / "pom.xml").write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><groupId>com.acme</groupId>'
                                               '<artifactId>worker</artifactId><version>1</version></project>', encoding="utf-8")
    own = repos.owned()
    assert "web" in own["npm"] and "worker" in own["PyPI"] and "com.acme" in own["Maven"]
    assert "org.springframework.boot" not in own["Maven"]      # api inherits its groupId from an outside parent

def test_latest_is_stored_and_carried_over(kit, repos, monkeypatch):
    from lib import latest
    monkeypatch.setattr(latest, "_fetch", lambda u: b'{"dist-tags": {"latest": "19.0.0"}}' if "react" in u else (_ for _ in ()).throw(latest.NotFound(u)))
    repos.run(log=lambda _: None, latest=True)
    data = repos.load()
    assert data["latest"]["versions"]["npm|react"] == "19.0.0" and data["latest"]["failed"] == []
    repos.run(log=lambda _: None)                                   # a reread keeps the last lookup
    assert repos.load()["latest"] == data["latest"]

def test_a_failed_registry_keeps_last_answers(kit, repos, monkeypatch):
    from lib import latest
    monkeypatch.setattr(latest, "_fetch", lambda u: b'{"dist-tags": {"latest": "19.0.0"}}' if "npmjs" in u else (_ for _ in ()).throw(latest.NotFound(u)))
    repos.run(log=lambda _: None, latest=True)
    monkeypatch.setattr(latest, "_fetch", lambda u: (_ for _ in ()).throw(OSError("offline")))
    repos.run(log=lambda _: None, latest=True)
    data = repos.load()
    assert data["latest"]["versions"]["npm|react"] == "19.0.0" and "npm" in data["latest"]["failed"]

def test_an_inventory_from_an_older_kit_has_no_latest(kit, repos):
    repos.run(log=lambda _: None)
    data = repos.load(); data.pop("latest", None)
    (kit.root / "docs" / ".work" / "inventory.json").write_text(json.dumps(data), encoding="utf-8")
    repos.run(log=lambda _: None)
    assert repos.load()["latest"] is None

def test_the_page_gains_a_latest_column_and_counts_newer(kit, repos):
    result = repos.scan()
    assert "| Latest |" not in repos.render(result)
    result["latest"] = {"at": "2026-11-11T10:00:00+00:00", "checked": 1, "found": 1, "failed": [], "versions": {"npm|react": "19.0.0"}}
    text = repos.render(result)
    assert "| Category | Library | Version | Latest | Scope |" in text and "| 19.0.0 |" in text
    assert "; 1 library with a newer version" in text

def test_the_cli_without_network_still_succeeds(kit, repos):
    import os, subprocess, sys
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "HTTPS_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "NO_PROXY": "", "no_proxy": ""}
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "inventory", "--latest", "--json"], env=env,
                       capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["latest"]["versions"] == {} and set(data["latest"]["failed"]) >= {"npm", "PyPI"}
    assert "could not reach" in r.stderr
```

  And `tests/e2e/test_latest_registries.py`, marked `pytestmark = pytest.mark.e2e`, calling `latest._fetch` +
  `latest.parse` for one well-known library per registry (`org.postgresql:postgresql`, `react`, `requests`,
  `golang.org/x/text`, `Newtonsoft.Json`, `symfony/console`, `serde`, `http`) and asserting a non-empty stable version.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_inventory.py -v -k "owned or latest or older or newer or without_network"`
Expected: FAIL (`owned` missing, `run()` got an unexpected keyword `latest`, `--latest` unrecognized).

- [ ] **Step 3: Implement**

  - `inventory.pom()` gains `"ownGroup"`: the pom's own `<groupId>` text, `""` when it inherits it (an addition; nothing
    else reads the dict's keys by position).
  - `inventory.owned()`: for each workspace repo, through `radar.entries` and `_read`: the `ownGroup` of every pom, and
    the inherited group of a pom whose parent is itself one of the workspace's poms (never a group inherited from an
    outside parent), Gradle `^\s*group\s*=\s*['"]([^'"]+)` in `build.gradle(.kts)`, `package.json` `name`
    (and its `@scope/` when scoped), `go.mod` `module`, `[project].name` of `pyproject.toml`, `[package].name` of
    `Cargo.toml`, `name` of `composer.json` and `pubspec.yaml`. Unreadable manifests are skipped. Keys are the
    ecosystem names `lib/inventory.py` already uses.
  - `inventory.run(..., latest=False)`: import the module as `from . import latest as registries` (the parameter has the
    module's name); read `last = load()` once; keep the `vulns` logic as is; then, with `latest`,
    `found = registries.lookup(rows, owned(), log=log)` and store `{**found, "versions": merged}` where `merged` is the
    previous `versions` overlaid with the new ones and limited to keys still in the inventory; without it,
    `result["latest"] = last.get("latest")`.
  - `render`: when `result.get("latest")`, a **Latest** column after Version (`—` when unknown) and the TL;DR clause
    `; N {library|libraries} with a newer version` (unique libraries whose highest exact version is `latest.newer` than
    stored), placed before the vulnerabilities clause; the "How this page is made" note names `--latest`.
  - `camarones.py`: `inv.add_argument("--latest", action="store_true")`; `inventory.run(..., cves=a.cves, latest=a.latest)`;
    help line `inventory [--cves] [--latest] [--json] [--fail-on high|critical]` with "--latest asks public registries
    for each library's latest stable version (your own are never sent)".

- [ ] **Step 4: Run the inventory, latest and catalog tests**

Run: `uv run pytest tests/test_inventory.py tests/test_latest.py tests/test_catalog.py tests/test_osv.py -v`
Expected: all PASS (`catalog --check` sees the new flag through the parser; no catalog change needed).

- [ ] **Step 5: Run the e2e file once**

Run: `uv run pytest -m e2e tests/e2e/test_latest_registries.py -v`
Expected: PASS (needs network; if it is not available, say so instead of skipping silently).

- [ ] **Step 6: Commit**

```bash
git add .camarones/lib/inventory.py .camarones/camarones.py tests/test_inventory.py tests/e2e/test_latest_registries.py
git commit -m "feat(inventory): --latest stores each library's latest stable version; the page shows it"
```

---

### Task 4: Shared helpers for versions and the outdated filter

**Files:**
- Modify: `.camarones/ui/src/libs.js`
- Test: `.camarones/ui/src/libs.test.js`

**Interfaces:**
- Consumes: the `latest` payload of Task 3.
- Produces (used by Tasks 5–7):
  - `matrix(rows)` — each cell gains `exact: string | null` (the row's `version`).
  - `versionSpan(item) -> string` — one exact version; `low – high` (en dash, spaces) when they differ; else the first cell's shown value (`declared`/`managed`); `'—'` when empty.
  - `latestOf(latest, item) -> string | null`
  - `isMajor(from, to) -> boolean` — first number of `to` greater than `from`'s (leading `v` ignored).
  - `outdated(item, version) -> boolean | null` — null when `version` is null or no cell has an exact version.
  - `proposal(row, version) -> { version: string, fix: string | null, latest: string | null }`
  - `applyFilter(rows, f, latest = null)` — `f.outdated` keeps rows with an exact version lower than `latest.versions[key]`.

- [ ] **Step 1: Write the failing tests** (append to `ui/src/libs.test.js`):

```js
const L = { at: '2026-11-11T10:00:00+00:00', checked: 2, found: 2, failed: [], versions: { 'Maven|org.x:boot': '3.4.1', 'npm|left-pad': '2.0.0' } }
const boot = (repo, version, extra = {}) => ({ repo, ecosystem: 'Maven', name: 'org.x:boot', version, declared: version || '', scope: 'runtime', category: 'framework', vulns: [], ...extra })

test('the version column: one version, a range when repos differ, the manifest when none is exact', () => {
  expect(versionSpan(matrix([boot('a', '3.2.0')]).items[0])).toBe('3.2.0')
  expect(versionSpan(matrix([boot('a', '3.2.0'), boot('b', '3.1.5')]).items[0])).toBe('3.1.5 – 3.2.0')
  expect(versionSpan(matrix([boot('a', null, { managedBy: 'org.x:parent:1' })]).items[0])).toBe('managed')
})

test('outdated only when an exact version is behind; unknown otherwise', () => {
  const two = matrix([boot('a', '3.4.1'), boot('b', '3.1.5')]).items[0]
  expect(outdated(two, latestOf(L, two))).toBe(true)
  expect(outdated(matrix([boot('a', '3.4.1')]).items[0], '3.4.1')).toBe(false)
  expect(outdated(matrix([boot('a', null, { managedBy: 'p' })]).items[0], '3.4.1')).toBe(null)
  expect(outdated(two, null)).toBe(null)
})

test('a major jump is marked', () => {
  expect(isMajor('16.2.1', '19.0.5')).toBe(true)
  expect(isMajor('v1.2.0', '1.9.0')).toBe(false)
})

test('the proposed version: the latest when higher, else the CVE fix, else nothing', () => {
  const vuln = boot('a', '3.2.0', { vulns: [{ id: 'G', severity: 'high', fixed: '3.2.5' }] })
  expect(proposal(vuln, '3.4.1')).toEqual({ version: '3.4.1', fix: '3.2.5', latest: '3.4.1' })
  expect(proposal(vuln, null)).toEqual({ version: '3.2.5', fix: '3.2.5', latest: null })
  expect(proposal(boot('a', '3.4.1'), '3.4.1')).toEqual({ version: '', fix: null, latest: null })
  expect(proposal(boot('a', null), '3.4.1').version).toBe('3.4.1')
})

test('only outdated keeps the rows behind their latest', () => {
  const rows = [boot('a', '3.4.1'), boot('b', '3.1.5')]
  expect(applyFilter(rows, { outdated: true }, L).map((r) => r.repo)).toEqual(['b'])
  expect(applyFilter(rows, { outdated: true }, null)).toEqual([])
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd .camarones/portal/app && npm ci && npx vitest run ../../ui/src/libs.test.js`
Expected: FAIL, `versionSpan is not exported`.

- [ ] **Step 3: Implement the helpers in `ui/src/libs.js`**, reusing `compareVersions` and `fixTarget`; update the file's header comment to mention the latest version.

- [ ] **Step 4: Run them to verify they pass**

Run: `cd .camarones/portal/app && npx vitest run ../../ui/src/libs.test.js`
Expected: all PASS, the existing tests in the file included.

- [ ] **Step 5: Commit**

```bash
git add .camarones/ui/src/libs.js .camarones/ui/src/libs.test.js
git commit -m "feat(ui): version span, latest, major jump, proposal and the outdated filter"
```

---

### Task 5: `LibrariesBoard`, the shared screen

**Files:**
- Create: `.camarones/ui/src/libs.jsx`
- Create: `.camarones/ui/src/libsboard.test.jsx`
- Modify: `.camarones/ui/src/index.js` (export `LibrariesBoard`), `.camarones/ui/i18n/index.js` (strings), `.camarones/ui/src/ui.css` (styles)

**Interfaces:**
- Consumes: Task 4's helpers; `Aviso`, `Button`, `Chip` from `./components.jsx`; `t` from `../i18n/index.js`.
- Produces (used by Tasks 6–7):
  - `LibrariesBoard({ inv, actions = null, status = null, renderUpdate = null, repo = '' })` — `inv` is the `/api/inventory` payload (never null here; loading and failure stay in each app). `actions`: nodes drawn at the right of the summary inside `data-tour="libs-actions"`, plus the line that says what each sends out; absent → the read-only note. `status`: a node under them. `renderUpdate(row, proposal)`: the app's per-repo control; absent → `BumpCommand`. `repo`: initial repo filter.
  - `Suggestions({ proposal, value, onPick })` — up to two chip buttons ("fixes the CVEs: X", "latest: Y"), the one equal to `value` pressed (`aria-pressed`).
  - `BumpCommand({ row, proposal })` — keeps a picked version (starts at `proposal.version`), shows `Suggestions` and `camaron bump <repo> <name> <version>` with a Copy button (`navigator.clipboard.writeText` in try/catch, label turns "Copied") and `lb.bumpNote`.
  - `Where`, `Advisory`, `SEV`, `sevWord` move here from `desktop/renderer/src/sections/Libs.jsx` (classes renamed `cu-libs-where`, `cu-libs-where-bad`).
  - Root `<section className="cu-libs">`; filters in `.cu-libs-bar` (`data-tour="libs-filters"`); table `.cu-libs-table` (`data-tour="libs-table"`), `<colgroup>` 46/18/20/16 %, no wrapper with `overflow`.

- [ ] **Step 1: Write the failing tests** in `ui/src/libsboard.test.jsx` (`renderToStaticMarkup`, strings through `t(key, 'en')` so the language does not matter):

```jsx
const rows = [
  { repo: 'api', ecosystem: 'Maven', name: 'org.postgresql:postgresql', version: '42.6.0', declared: '42.6.0', scope: 'runtime',
    category: 'data', language: 'Java', source: 'api:pom.xml', managedBy: null,
    vulns: [{ id: 'GHSA-1', cve: 'CVE-2024-1597', severity: 'critical', score: 9.8, summary: 'SQL injection', fixed: '42.6.1' }] },
  { repo: 'web', ecosystem: 'npm', name: 'rxjs', version: '7.8.1', declared: '^7.8.1', scope: 'runtime', category: 'other',
    language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns: [] },
  { repo: 'web', ecosystem: 'npm', name: '@angular/core', version: '16.2.1', declared: '^16.2.1', scope: 'runtime',
    category: 'framework', language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns: [] }]
const latest = { at: '2026-11-11T10:00:00+00:00', checked: 3, found: 3, failed: [],
  versions: { 'Maven|org.postgresql:postgresql': '42.7.4', 'npm|rxjs': '7.8.1', 'npm|@angular/core': '19.0.5' } }
const inv = { libraries: rows, vulns: { scanned: 2, failed: [], online: false, vulnerable: 1, at: '2026-11-10T10:00:00+00:00' }, latest }
const en = (k) => t(k, 'en')

test('one line per library with its version and the latest, no column per repo', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={inv} />)
  expect(out).toContain('<col style="width:46%"')
  expect(out).not.toContain('<th>api</th>')
  expect(out).toContain('42.6.0'); expect(out).toContain('42.7.4')
  expect(out).toContain(en('lb.major'))                          // 16 → 19
  expect(out).toContain(en('lb.upToDate'))                       // rxjs
  expect(out).not.toContain('overflow')
})

test('up to date and clean lines have no Update button; the others do', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={inv} />)
  expect(out.match(new RegExp(`>${en('lb.updateOpen')}`, 'g'))).toHaveLength(2)
})

test('read-only: no actions, the note says where it is done', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={inv} />)
  expect(out).toContain('camaron inventory --cves --latest')
  expect(out).not.toContain('data-tour="libs-actions"')
})

test('with actions: they are drawn with what each one sends out', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={inv} actions={<button>scan</button>} status={<p>running</p>} />)
  expect(out).toContain('data-tour="libs-actions"'); expect(out).toContain(en('lb.sends')); expect(out).toContain('running')
})

test('an open library puts the update first: the bump command in the portal, the app control when given', () => {
  const item = { key: 'Maven|org.postgresql:postgresql' }
  const portal = renderToStaticMarkup(<LibraryDetail item={matrixItem(rows, item.key)} rows={[rows[0]]} latest={latest} scanned renderUpdate={null} />)
  expect(portal).toContain('camaron bump api org.postgresql:postgresql 42.7.4')
  expect(portal.indexOf('camaron bump')).toBeLessThan(portal.indexOf('CVE-2024-1597'))
  expect(portal).toContain(fill(en('lb.fixes'), { v: '42.6.1' }))
  const app = renderToStaticMarkup(<LibraryDetail item={matrixItem(rows, item.key)} rows={[rows[0]]} latest={latest} scanned
    renderUpdate={(row, p) => <i>update {row.repo} to {p.version}</i>} />)
  expect(app).toContain('update api to 42.7.4'); expect(app).not.toContain('camaron bump')
})

test('an inventory from an older kit: latest shows a dash and the outdated filter is hidden', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={{ libraries: rows, vulns: null }} />)
  expect(out).toContain('—'); expect(out).not.toContain(en('lb.onlyOutdated'))
  expect(out).toContain(en('lb.neverLooked'))
})

test('a lookup that could not reach a registry says so with the date of the versions shown', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={{ ...inv, latest: { ...latest, failed: ['npm'] } }} />)
  expect(out).toContain(fill(en('lb.lookFailed'), { registries: 'npm', day: '2026-11-11' }))
})
```

  (`matrixItem(rows, key)` is a two-line local helper: `matrix(rows).items.find((x) => x.key === key)`; `fill` is the
  placeholder filler exported from `libs.jsx`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `cd .camarones/portal/app && npx vitest run ../../ui/src/libsboard.test.jsx`
Expected: FAIL, `Failed to resolve import "./libs.jsx"`.

- [ ] **Step 3: Add the shared strings** to both languages of `ui/i18n/index.js`, under a `// LibrariesBoard (libs.jsx)` comment.

  Moved from `desktop/renderer/src/i18n.js` with the same keys and text: `lb.lead`, `lb.scope`, `lb.scope.{runtime,dev,test,build}`,
  `lb.in`, `lb.more`, `lb.why`, `lb.whyLead`, `lb.manifest`, `lb.declared`, `lb.version`, `lb.managed`, `lb.flagged`,
  `lb.flaggedLead`, `lb.notScanned`, `lb.clean`, `lb.ids`, `lb.affects`, `lb.range`, `lb.rangeLast`, `lb.rangeOpen`,
  `lb.published`, `lb.modified`, `lb.cwe`, `lb.rescan`, `lb.noText`. Moved and renamed: `q.libsCount`→`lb.count`,
  `q.libsSearch`→`lb.search`, `q.libsCategory`→`lb.category`, `q.libsRepo`→`lb.repo`, `q.libsOnlyVuln`→`lb.onlyVuln`,
  `q.libsVersions`→`lb.versions`, `q.libsFixed`→`lb.fixed`, `q.libsAll`→`lb.all`, `q.libsLibrary`→`lb.library`,
  `q.cvClean`→`lb.cvClean`, `q.cvAt`→`lb.cvAt`, `q.cvNever`→`lb.cvNever`, `q.libsNone`→`lb.none`, `nothing`→`lb.nothing`,
  `sev.*`→`lb.sev.*`. New (es / en):

| Key | es | en |
|---|---|---|
| `lb.latest` | Última | Latest |
| `lb.upToDate` | al día | up to date |
| `lb.major` | mayor | major |
| `lb.newer` | {n} con versión nueva | {n} with a newer version |
| `lb.onlyOutdated` | Solo desactualizadas | Outdated only |
| `lb.lookedAt` | versiones buscadas el {day} | versions looked up on {day} |
| `lb.neverLooked` | Versiones nuevas: sin buscar todavía. | Newer versions: not looked up yet. |
| `lb.lookFailed` | No he podido consultar {registries}. Las versiones son del {day}. | I could not reach {registries}. The versions shown are from {day}. |
| `lb.updateOpen` | Actualizar | Update |
| `lb.fixes` | arregla los CVE: {v} | fixes the CVEs: {v} |
| `lb.latestIs` | última: {v} | latest: {v} |
| `lb.copy` / `lb.copied` | Copiar / Copiado | Copy / Copied |
| `lb.bumpNote` | Primero enseña el cambio; añade --yes para hacerlo. Sin commit ni push. | It shows the change first; add --yes to make it. No commit, no push. |
| `lb.readOnly` | Escanear, buscar versiones nuevas y actualizar se hace en la app de escritorio, o en una terminal: camaron inventory --cves --latest. | Scanning, looking up newer versions and updating happen in the desktop app, or in a terminal: camaron inventory --cves --latest. |
| `lb.sends` | El escaneo no envía nada (base de datos local). Buscar versiones envía los nombres de las librerías a los registros públicos; las vuestras, nunca. | The scan sends nothing (local database). Looking up versions sends library names to public registries; never your own. |

- [ ] **Step 4: Implement `ui/src/libs.jsx`**

  Order inside the root: summary line (count, severity chips or `lb.cvClean`/`lb.cvNever`, `lb.newer` chip, the dates,
  `lb.lookFailed` or `lb.neverLooked`), `actions` + `lb.sends` (or `lb.readOnly`), `status`, the sticky bar (search,
  category, repo, scope, `lb.onlyVuln`, `lb.onlyOutdated` only when `inv.latest`), the table. Row cells: name button
  (toggles, `aria-expanded`) + ecosystem + severity chip + `lb.versions` chip + `<Where>`; `versionSpan`; latest with
  `lb.major` / `lb.upToDate` chip or `—`; **Update ▾** button (same toggle) unless `outdated === false` and no vulns.
  Opening a line scrolls it into view (`scrollIntoView({ block: 'nearest' })` in an effect). `LibraryDetail`: one block
  per row with repo, manifest, scope, `version →`, then `renderUpdate(row, proposal(row, latestOf(...)))` or
  `<BumpCommand>`; then why it is flagged (`Advisory` list, unchanged behaviour); then why it is there. A
  `ResizeObserver` on the bar writes its height to `--cu-libs-bar-h` on the root (skipped when unavailable).

- [ ] **Step 5: Add the `cu-libs*` styles to `ui/src/ui.css`**, with the same tokens as the `.cu-hb-*` rules:
  `.cu-libs { --cu-libs-top: 0px }`; `.cu-libs-bar` sticky at `top: var(--cu-libs-top)` with the canvas background and
  a z-index above the header; `.cu-libs-table` `width: 100%; table-layout: fixed`; its `thead th` sticky at
  `calc(var(--cu-libs-top) + var(--cu-libs-bar-h, 0px))`; names `overflow-wrap: anywhere`; the vulnerable-line left
  mark and the open-line background carried over from `.dk-libs`; the detail rows `white-space: normal`.

- [ ] **Step 6: Run the shared tests**

Run: `cd .camarones/portal/app && npx vitest run ../../ui`
Expected: all PASS (`ui/i18n/i18n.test.js` included: same keys in es and en).

- [ ] **Step 7: Commit**

```bash
git add .camarones/ui/src/libs.jsx .camarones/ui/src/libsboard.test.jsx .camarones/ui/src/index.js .camarones/ui/i18n/index.js .camarones/ui/src/ui.css
git commit -m "feat(ui): LibrariesBoard, one line per library with its version and the latest"
```

---

### Task 6: The app's Libraries on the shared board

**Files:**
- Modify: `.camarones/desktop/renderer/src/sections/Libs.jsx`, `.camarones/desktop/renderer/src/quality.js`, `.camarones/desktop/renderer/src/i18n.js`, `.camarones/desktop/renderer/src/app.css`
- Test: `.camarones/desktop/renderer/src/Libs.test.jsx`, `.camarones/desktop/renderer/src/quality.test.js`

**Interfaces:**
- Consumes: `LibrariesBoard`, `Suggestions` (Task 5); `proposal` shape (Task 4).
- Produces: `ScanStatus({ c, mode, onClose })` with `mode: 'cves' | 'read' | 'latest'`; `inventoryArgs(running) -> { json, cves, latest } | null`; `lookupProgress(lines) -> { n, total, name }`.

- [ ] **Step 1: Write the failing tests**

  In `quality.test.js`:

```js
test('a running lookup is attached to, and its progress read despite the colon in Maven names', () => {
  expect(inventoryArgs([{ kind: 'cmd:inventory --latest --json' }])).toEqual({ json: true, cves: false, latest: true })
  expect(lookupProgress(['[12/400] newer versions · org.postgresql:postgresql', 'noise']))
    .toEqual({ n: 12, total: 400, name: 'org.postgresql:postgresql' })
  expect(lookupProgress([])).toEqual({ n: 0, total: 0, name: '' })
})
```

  In `Libs.test.jsx`: keep the section test (now also expecting `t('lb.lookGo')`); move the `Where`, `Library` and
  advisory tests out (Task 5 covers them); change every `ScanStatus` call to `mode="cves"`/`mode="read"`; add:

```jsx
test('a lookup as it goes names the library and counts, then ends on what it found and what it could not reach', () => {
  const running = scan({ status: 'running', lines: ['[3/40] newer versions · react'] }, 'latest')
  expect(running).toContain(t('lb.looking', { name: 'react' })); expect(running).toContain(t('lb.lookCount', { n: 3, total: 40 }))
  expect(running).not.toContain('dk-scan-repos')
  const done = scan({ status: 'done', lines: [], result: { libraries: [], latest: { checked: 40, found: 38, failed: ['npm'], versions: {} } } }, 'latest')
  expect(done).toContain(t('lb.looked')); expect(done).toContain(t('lb.lookFailedShort', { registries: 'npm' }))
})

test('update proposes the latest version with both suggestions', () => {
  const out = renderToStaticMarkup(<Update row={rows[0]} proposal={{ version: '9.0.0', fix: '8.3.3', latest: '9.0.0' }} srv={srv} jobs={null} onChanged={() => {}} />)
  expect(out).toMatch(/value="9\.0\.0"/); expect(out).toContain('aria-pressed="true"')
})
```

  (`scan(job, mode)` is the file's existing helper with its second argument now the mode; export `Update`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `cd .camarones/desktop/renderer && npm ci && npx vitest run src/Libs.test.jsx src/quality.test.js`
Expected: FAIL (`lookupProgress` not exported, `lb.lookGo` missing).

- [ ] **Step 3: Implement**

  - `quality.js`: `inventoryArgs` also accepts `--latest`; `lookupProgress` reads `/^\[(\d+)\/(\d+)\] newer versions · (.+)$/`.
  - `sections/Libs.jsx`: `Libs` keeps loading/failed (`Skeleton`, `Failed`) and renders
    `<LibrariesBoard inv={inv} actions={…} status={…} renderUpdate={(row, p) => <Update row={row} proposal={p} … />} />`
    inside `<Page title={t('nav.libs')} wide>`. Actions: **Scan for vulnerabilities** (primary, `{cves: true, json: true}`),
    **Look for newer versions** (`{latest: true, json: true}`), **Reread from the code** (`{json: true}`), **Open in the
    portal** (ghost). `mode` state replaces `cves`. `ScanStatus` for `latest` draws the bar from `lookupProgress`, the
    line `lb.looking` + `lb.lookCount`, no repo chips; done: tick, `lb.looked`, `lb.lookedWhat`, `lb.lookFailedShort`
    when `failed` is not empty. `Update` takes `proposal`, starts at `proposal.version`, shows `<Suggestions>` that set
    it; ask/confirm/done unchanged.
  - `i18n.js` new keys (es / en): `lb.lookGo` Buscar versiones nuevas / Look for newer versions; `lb.lookPrep`
    Preparando la búsqueda… / Getting the lookup ready…; `lb.looking` Pescando la última versión de {name}… / Fishing
    for the latest {name}…; `lb.lookCount` {n} de {total} / {n} of {total}; `lb.looked` Búsqueda terminada / Lookup
    finished; `lb.lookedWhat` {checked} librerías consultadas · {n} con versión nueva / {checked} libraries looked up ·
    {n} with a newer version; `lb.lookFailedShort` No he podido consultar: {registries}. / I could not reach:
    {registries}. Delete the keys moved in Task 5 that no file under `desktop/renderer/src` uses any more (`grep`).
  - `app.css`: delete the `.dk-libs*`, `.dk-where*`, `.dk-lib*`, `.dk-adv*` rules no component uses any more.

- [ ] **Step 4: Run the renderer suite**

Run: `cd .camarones/desktop/renderer && npm test`
Expected: all PASS (`i18n.test.js`: every key a component names exists, es = en).

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src
git commit -m "feat(app): Libraries on the shared board; look for newer versions; update proposes the latest"
```

---

### Task 7: The portal's Libraries on the shared board

**Files:**
- Modify: `.camarones/portal/app/src/Libs.jsx`, `.camarones/portal/app/src/i18n.js`, `.camarones/portal/app/src/styles.css`
- Test: `.camarones/portal/app/src/Libs.test.jsx`, `.camarones/portal/app/src/libs.test.js`

**Interfaces:**
- Consumes: `LibrariesBoard` (Task 5); `repoFilter(arg, rows)` (stays in `portal/app/src/libs.js`).

- [ ] **Step 1: Write the failing test** — replace the `Where` test in `Libs.test.jsx`:

```jsx
test('the portal draws the shared board, read-only, filtered by #/libs/<repo>', () => {
  const out = renderToStaticMarkup(<LibsView inv={{ libraries: [row('web'), row('api')], vulns: null, latest: null }} arg="api" />)
  expect(out).toContain('class="cu-libs"'); expect(out).toContain('camaron inventory --cves --latest')
  expect(out).toContain('<option value="api" selected="">')
})
```

  (`LibsView({ inv, arg })` is the pure part of the view, exported from `Libs.jsx`; `row(repo)` a local fixture.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd .camarones/portal/app && npx vitest run src/Libs.test.jsx`
Expected: FAIL, `LibsView` is not exported.

- [ ] **Step 3: Implement**

  `Libs({ arg })` fetches `inventory`, keeps `Skeleton`/`Failed` and the `<h1>`/lede, then renders
  `<LibsView inv={data} arg={arg} />` = `<LibrariesBoard inv={inv} repo={repoFilter(arg, inv.libraries)} />`.
  `portal/app/src/libs.js` re-exports only what the portal still imports. Delete from `i18n.js` the `libs*` keys no file
  under `portal/app/src` uses any more (check `modes.test.js`, which lists some) and from `styles.css` the
  `.libs-*` rules; add `#native .cu-libs { --cu-libs-top: var(--top); }`.

- [ ] **Step 4: Run the portal suite**

Run: `cd .camarones/portal/app && npm test`
Expected: all PASS (portal and `ui/` tests).

- [ ] **Step 5: Commit**

```bash
git add .camarones/portal/app/src
git commit -m "feat(portal): Libraries is the shared board, read-only, with the latest version"
```

---

### Task 8: Docs, tutorial and version

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"]` → `"4.80.0"`), `README.md` (badge; the `camaron inventory` paragraph at ~line 448; the commands table at ~387 if flags are listed)
- Modify: `.camarones/templates/docs/guides/app.md` (`## Libraries`), `portal.md` (~171–174: no more "matrix … scrolls sideways"), `using.md` (~131), `tutorial.md` (~51), and their twins under `.camarones/templates/docs/i18n/es/guides/`
- Modify: `.camarones/lib/tutorial.py` only if a page lists `inventory`'s flags; then regenerate `.camarones/TUTORIAL.md`
- Test: `tests/test_guide.py`, `tests/test_wizard.py`

- [ ] **Step 1: Write the docs.** Each place says: one line per library with Version and Latest; **Look for newer versions** runs `camaron inventory --latest`, sends library names to public registries, never the workspace's own, and a registry it cannot reach keeps the last answer; **Update ▾** proposes the latest (or the CVE fix) and runs `camaron bump` on a new branch, nothing committed; the portal shows the same screen and the `camaron bump` command to copy. Same content in en and es; the README in Spanish.

- [ ] **Step 2: Regenerate the tutorial if `tutorial.py` changed**

Run (from `.camarones/`): `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 3: Run the docs tests**

Run: `uv run pytest tests/test_guide.py tests/test_wizard.py tests/test_catalog.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit** (body notes that templates are copied once, so existing projects keep their guide copy)

```bash
git add README.md .camarones/lib/common.py .camarones/templates/docs .camarones/lib/tutorial.py .camarones/TUTORIAL.md
git commit -m "docs(libs): current and latest version, look up newer versions, update from the line (kit 4.80.0)"
```

---

### Task 9: Bundles, full suite and the app end to end

**Files:**
- Modify: `.camarones/portal/app-build/**`, `.camarones/desktop/renderer-build/**` (generated)

- [ ] **Step 1: Build both apps**

Run: `cd .camarones/portal/app && npm run build` and `cd .camarones/desktop/renderer && npm run build`
Expected: both succeed; `git status` shows only the two build folders changed.

- [ ] **Step 2: Run the whole suite**

Run: `uv run pytest -n auto`
Expected: all pass. Report the summary line; if anything fails, report it with its output.

- [ ] **Step 3: End to end in the sandbox** (a scratch `--dir`, per the memory note on driving the Electron app):
  `uv run scripts/sandbox.py --dir <scratch> reset`, `cli inventory --latest`, then open the app from this checkout on
  it. Check: the Libraries line shows Version and Latest; **Look for newer versions** shows its bar and ends on the tick;
  "Outdated only" filters; **Update ▾** on one library proposes the latest, the ask names the branch, **Yes** makes it;
  the filters and header stay in view while scrolling; at a 900 px wide window
  `main.scrollWidth <= main.clientWidth` in the app and `document.documentElement.scrollWidth <= innerWidth` in the
  portal (`#/libs`). Take one screenshot of each app. Finish with `traces` after `uninstall` (exit 0).

- [ ] **Step 4: Commit the builds**

```bash
git add .camarones/portal/app-build .camarones/desktop/renderer-build
git commit -m "build: portal and app bundles with the shared Libraries board"
```
