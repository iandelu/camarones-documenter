"""Newer versions of the inventory's libraries: each one's latest stable version, from its public registry (Maven
Central, npm, PyPI, the Go proxy, NuGet, Packagist, crates.io, pub.dev).

This sends library names (never code) to those registries, so it runs only when the person asks for it in that moment
(`camaron inventory --latest`, or Look for newer versions in the desktop app), and never for a library the workspace
itself produces. Standard library only; proxies come from the environment. Never raises: a registry that does not
answer is listed in `failed` and the inventory keeps the versions the last lookup found."""
from __future__ import annotations

import json, re, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import cmp_to_key
from typing import Iterable
from urllib.parse import quote

from .common import VERSIONS

TIMEOUT = 10
WORKERS = 8
MAX_BYTES = 32_000_000          # PyPI's JSON for a package with thousands of releases is large; past this it is skipped
PROGRESS_LINES = 50
STRIKES = 2                     # failures after which a registry is given up for the run (a network that drops packets)


class NotFound(Exception):
    """The registry has no such library (HTTP 404/410): not a failure of the registry."""


PRE = re.compile(r"(?i)(?:[.\-_+]|(?<=\d))(?:alpha|beta|rc|cr|milestone|m|preview|pre|dev|snapshot|ea|canary|nightly|next|a|b)"
                 r"[.\-_]?\d*(?=[.\-_+]|$)")
QUALIFIER = re.compile(r"[A-Za-z][\w.-]*$")
RELEASE_MARKERS = {"release", "final", "ga"}       # 5.3.39.RELEASE is just 5.3.39: Spring dropped the suffix at 6.0


def stable(version: str) -> bool:
    return bool(version) and not PRE.search(version)


def _split(v: str) -> tuple[list, str]:
    main, _, pre = str(v or "").removeprefix("v").partition("-")
    return [int(x) if x.isdigit() else x for x in re.split(r"[.+]", main)], pre


def _cmp(a: str, b: str) -> int:
    """The order of ui/src/libs.js compareVersions: numbers as numbers, missing parts are 0, a pre-release first."""
    (x, xp), (y, yp) = _split(a), _split(b)
    for i in range(max(len(x), len(y))):
        p, q = x[i] if i < len(x) else 0, y[i] if i < len(y) else 0
        if p == q:
            continue
        if isinstance(p, int) and isinstance(q, int):
            return p - q
        return (str(p) > str(q)) - (str(p) < str(q))
    if xp == yp:
        return 0
    return 1 if not xp else -1 if not yp else (xp > yp) - (xp < yp)


def newer(current: str | None, candidate: str | None) -> bool:
    return bool(current) and bool(candidate) and _cmp(candidate, current) > 0


def _qualifier(v: str | None) -> str:
    """A version's flavour, its letters only: `jre`, `android`, `groovy`. A date stamp (Jetty's 9.4.53.v20231009) or a
    release marker is not one, so it never keeps a library on its old line."""
    m = QUALIFIER.search(str(v or "").removeprefix("v"))
    q = re.sub(r"[\d.\-_+]+", "", m.group()).lower() if m else ""
    return "" if q in RELEASE_MARKERS or len(q) < 2 else q


def pick(versions: Iterable[str], current: str | None = None) -> str | None:
    """The highest stable version; with a qualified current one (Guava's 33.0.0-jre), the highest with that qualifier."""
    ok = [v for v in versions if isinstance(v, str) and stable(v)]
    q = _qualifier(current)
    same = [v for v in ok if _qualifier(v) == q] if q else []
    pool = same or ok
    return max(pool, key=cmp_to_key(_cmp)) if pool else None


def _maven(name: str) -> str | None:
    parts = name.split(":")
    if len(parts) != 2 or not all(parts):
        return None
    group, artifact = parts
    return f"https://repo1.maven.org/maven2/{'/'.join(quote(g, safe='') for g in group.split('.'))}/{quote(artifact, safe='')}/maven-metadata.xml"


def _packagist(name: str) -> str | None:
    parts = name.split("/")
    return f"https://repo.packagist.org/p2/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}.json" if len(parts) == 2 and all(parts) else None


def _go(name: str) -> str:
    escaped = re.sub(r"[A-Z]", lambda m: "!" + m.group().lower(), name)
    return f"https://proxy.golang.org/{quote(escaped, safe='/!~')}/@latest"


URLS = {
    "Maven": _maven,
    "npm": lambda n: f"https://registry.npmjs.org/{quote(n, safe='@')}",
    "PyPI": lambda n: f"https://pypi.org/pypi/{quote(n, safe='')}/json",
    "Go": _go,
    "NuGet": lambda n: f"https://api.nuget.org/v3-flatcontainer/{quote(n.lower(), safe='')}/index.json",
    "Packagist": _packagist,
    "crates.io": lambda n: f"https://crates.io/api/v1/crates/{quote(n, safe='')}",
    "Pub": lambda n: f"https://pub.dev/api/packages/{quote(n, safe='')}",
}


def url(ecosystem: str, name: str) -> str | None:
    build = URLS.get(ecosystem)
    return build(name) if build and name else None


def _versions_of(ecosystem: str, body: bytes, name: str, current: str | None) -> str | None:
    if ecosystem == "Maven":
        root = ET.fromstring(body)
        return pick([(e.text or "").strip() for e in root.findall("./versioning/versions/version")], current)
    data = json.loads(body)
    if ecosystem == "npm":
        return data["dist-tags"]["latest"]
    if ecosystem == "PyPI":
        return pick(data.get("releases") or {}, current) or data["info"]["version"]
    if ecosystem == "Go":
        return data["Version"]
    if ecosystem == "NuGet":
        return pick(data["versions"], current)
    if ecosystem == "Packagist":
        return pick([p["version"] for p in data["packages"][name]], current)
    if ecosystem == "crates.io":
        return data["crate"]["max_stable_version"]
    if ecosystem == "Pub":
        return data["latest"]["version"]
    return None


def parse(ecosystem: str, body: bytes, name: str, current: str | None = None) -> str | None:
    try:
        found = _versions_of(ecosystem, body, name, current)
    except (ValueError, KeyError, TypeError, AttributeError, IndexError, ET.ParseError):
        return None
    return found if isinstance(found, str) and found else None


def _canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def is_owned(ecosystem: str, name: str, owned: dict[str, set[str]]) -> bool:
    """Whether the workspace produces this library (inventory.owned()): then its name never leaves the machine."""
    mine = owned.get(ecosystem) or set()
    if ecosystem == "Maven":
        return any(name.startswith(group + ":") for group in mine)
    if ecosystem == "npm":
        return name in mine or any(p.endswith("/") and name.startswith(p) for p in mine)
    if ecosystem == "Go":
        return any(name == m or name.startswith(m + "/") for m in mine)
    if ecosystem == "PyPI":
        return _canon(name) in {_canon(x) for x in mine}
    if ecosystem == "NuGet":
        return name.lower() in {x.lower() for x in mine}
    return name in mine


def _fetch(address: str) -> bytes:
    headers = {"User-Agent": f"camaron/{VERSIONS['kit']}"}
    if address.startswith("https://registry.npmjs.org/"):
        headers["Accept"] = "application/vnd.npm.install-v1+json"        # the abbreviated metadata: dist-tags, no readmes
    try:
        with urllib.request.urlopen(urllib.request.Request(address, headers=headers), timeout=TIMEOUT) as r:
            return r.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise NotFound(address) from None
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _items(rows: list[dict], owned: dict[str, set[str]]) -> dict[tuple[str, str], dict]:
    """One per library the registries may be asked about, with the highest exact version the repos use."""
    items: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r.get("registry") is False:                       # git, a path, a URL, an SDK: no public version applies
            continue
        key = (r.get("ecosystem") or "", r.get("name") or "")
        if key not in items:
            address = url(*key)
            if not address or is_owned(*key, owned):
                continue
            items[key] = {"url": address, "current": None}
        version = r.get("version")
        if version and (not items[key]["current"] or newer(items[key]["current"], version)):
            items[key]["current"] = version
    return items


def _one(key: tuple[str, str], item: dict, fetch, strikes: dict) -> tuple[tuple[str, str], str | None, str | None]:
    if strikes.get(key[0], 0) >= STRIKES:                # a registry that keeps failing is not asked again this run
        return key, None, key[0]
    try:
        return key, parse(key[0], fetch(item["url"]), key[1], item["current"]), None
    except NotFound:
        return key, None, None
    except Exception:                                    # noqa: BLE001 — timeouts, DNS, 5xx, a proxy: the registry failed
        strikes[key[0]] = strikes.get(key[0], 0) + 1
        return key, None, key[0]


def _lookup(rows: list[dict], owned: dict[str, set[str]], log, fetch) -> dict:
    items = _items(rows, owned)
    total, done = len(items), 0
    step = max(1, -(-total // PROGRESS_LINES))
    versions: dict[str, str] = {}
    failed: set[str] = set()
    strikes: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for future in as_completed([pool.submit(_one, k, it, fetch, strikes) for k, it in items.items()]):
            key, found, bad = future.result()
            done += 1
            if found:
                versions[f"{key[0]}|{key[1]}"] = found
            if bad:
                failed.add(bad)
            if done % step == 0 or done == total:        # `[n/total]`: the desktop app's bar counts these lines
                log(f"[{done}/{total}] newer versions · {key[1]}")
    behind = sum(1 for k, it in items.items() if newer(it["current"], versions.get(f"{k[0]}|{k[1]}")))
    log(f"✔ {behind} with a newer version ({total} {'library' if total == 1 else 'libraries'} looked up"
        + (f"; could not reach: {', '.join(sorted(failed))}" if failed else "") + ")")
    return {"at": _now(), "checked": total, "found": len(versions), "failed": sorted(failed), "versions": versions}


def lookup(rows: list[dict], owned: dict[str, set[str]], log=print, fetch=None) -> dict:
    """Ask each library's registry for its latest stable version. `fetch` (default `_fetch`, looked up now so tests can
    replace it) returns the body or raises NotFound. Returns {at, checked, found, failed, versions}."""
    try:
        return _lookup(rows, owned, log, fetch or _fetch)
    except Exception as e:                               # noqa: BLE001 — never raises: the inventory is written anyway
        log(f"⚠ newer versions could not be looked up: {e}")
        return {"at": _now(), "checked": 0, "found": 0, "failed": [], "versions": {}}
