"""Newer versions of the inventory's libraries: each one's latest stable version, from its public registry (Maven
Central, npm, PyPI, the Go proxy, NuGet, Packagist, crates.io, pub.dev).

This sends library names (never code) to those registries, so it runs only when the person asks for it in that moment
(`camaron inventory --latest`, or Look for newer versions in the desktop app), and never for a library the workspace
itself produces. Standard library only; proxies come from the environment. Never raises: a registry that does not
answer is listed in `failed` and the inventory keeps the versions the last lookup found."""
from __future__ import annotations

import json, re
import xml.etree.ElementTree as ET
from functools import cmp_to_key
from typing import Iterable
from urllib.parse import quote


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
    m = QUALIFIER.search(str(v or "").removeprefix("v"))
    q = m.group().lower() if m else ""
    return "" if q in RELEASE_MARKERS else q


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
