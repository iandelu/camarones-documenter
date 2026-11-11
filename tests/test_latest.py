"""Newer versions (lib/latest.py): each library's latest stable version, asked of its public registry only when the
person asks (`camaron inventory --latest`), never for a library the workspace itself produces. Offline here: the
registry answers are saved payloads and the fetch is a fake."""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def latest(kit):
    from lib import latest
    return latest


@pytest.mark.parametrize("v, ok", [
    ("3.4.1", True), ("33.0.0-jre", True), ("5.3.39.RELEASE", True), ("1.0.0.Final", True), ("1.0.0-build.5", True),
    ("4.0.0-SNAPSHOT", False), ("6.2.0-M1", False), ("2.0.0-rc.1", False), ("3.0.0-RC2", False), ("1.2.3-beta.2", False),
    ("2.0.0a1", False), ("2.0b3", False), ("1.0.0-alpha", False), ("18.0.0-next.3", False), ("1.0.0-dev.1", False),
    ("21-ea", False)])
def test_stable(latest, v, ok):
    assert latest.stable(v) is ok


def test_newer(latest):
    assert latest.newer("8.3.9", "8.3.10") and latest.newer("2.0.0-rc.1", "2.0.0")
    assert latest.newer(None, "1.0") is False and latest.newer("1.0", None) is False
    assert not latest.newer("v1.2", "1.2.0") and not latest.newer("1.2.0", "1.1.9")


def test_pick_prefers_the_current_qualifier(latest):
    assert latest.pick(["32.1.0-jre", "33.0.0-android", "33.0.0-jre", "34.0.0-rc1"], "32.1.0-jre") == "33.0.0-jre"
    assert latest.pick(["1.0", "2.0-M1", "1.5"]) == "1.5"
    assert latest.pick(["2.0-M1"]) is None and latest.pick([]) is None


def test_urls(latest):
    assert latest.url("Maven", "org.postgresql:postgresql") == \
        "https://repo1.maven.org/maven2/org/postgresql/postgresql/maven-metadata.xml"
    assert latest.url("npm", "@angular/core") == "https://registry.npmjs.org/@angular%2Fcore"
    assert latest.url("PyPI", "SQLAlchemy") == "https://pypi.org/pypi/SQLAlchemy/json"
    assert latest.url("Go", "github.com/BurntSushi/toml") == "https://proxy.golang.org/github.com/!burnt!sushi/toml/@latest"
    assert latest.url("NuGet", "Newtonsoft.Json") == "https://api.nuget.org/v3-flatcontainer/newtonsoft.json/index.json"
    assert latest.url("Packagist", "symfony/console") == "https://repo.packagist.org/p2/symfony/console.json"
    assert latest.url("crates.io", "serde") == "https://crates.io/api/v1/crates/serde"
    assert latest.url("Pub", "http") == "https://pub.dev/api/packages/http"
    assert latest.url("Maven", "no-colon") is None and latest.url("Packagist", "novendor") is None
    assert latest.url("Hex", "phoenix") is None


def j(data) -> bytes:
    return json.dumps(data).encode("utf-8")


def test_parse_maven(latest):
    xml = (b"<metadata><groupId>org.postgresql</groupId><versioning><latest>42.8.0-SNAPSHOT</latest><versions>"
           b"<version>42.6.0</version><version>42.7.4</version><version>42.8.0-SNAPSHOT</version></versions></versioning></metadata>")
    assert latest.parse("Maven", xml, "org.postgresql:postgresql", "42.6.0") == "42.7.4"


def test_parse_npm(latest):
    assert latest.parse("npm", j({"dist-tags": {"latest": "19.0.5", "next": "20.0.0-rc.1"}}), "@angular/core") == "19.0.5"


def test_parse_pypi(latest):
    assert latest.parse("PyPI", j({"info": {"version": "2.0.36"}, "releases": {"2.0.36": [], "2.1.0b1": []}}), "sqlalchemy") == "2.0.36"
    assert latest.parse("PyPI", j({"info": {"version": "1.0"}, "releases": {}}), "x") == "1.0"


def test_parse_go(latest):
    assert latest.parse("Go", j({"Version": "v1.4.0", "Time": "2024-01-01T00:00:00Z"}), "github.com/x/y") == "v1.4.0"


def test_parse_nuget(latest):
    assert latest.parse("NuGet", j({"versions": ["12.0.1", "13.0.3", "13.0.4-beta1"]}), "Newtonsoft.Json") == "13.0.3"


def test_parse_packagist(latest):
    body = j({"packages": {"symfony/console": [{"version": "v7.2.0-BETA1"}, {"version": "v7.1.0"}, {"version": "v6.4.9"}]}})
    assert latest.parse("Packagist", body, "symfony/console") == "v7.1.0"


def test_parse_crates(latest):
    assert latest.parse("crates.io", j({"crate": {"max_stable_version": "1.0.215", "max_version": "1.0.216-rc"}}), "serde") == "1.0.215"


def test_parse_pub(latest):
    assert latest.parse("Pub", j({"latest": {"version": "1.2.2"}}), "http") == "1.2.2"


def test_an_unreadable_payload_is_no_version(latest):
    assert latest.parse("npm", b"not json", "x") is None
    assert latest.parse("Maven", b"<not xml", "a:b") is None
    assert latest.parse("crates.io", j({"crate": {}}), "x") is None
