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


ROWS = [{"repo": "api", "ecosystem": "Maven", "name": "org.postgresql:postgresql", "version": "42.6.0"},
        {"repo": "web", "ecosystem": "Maven", "name": "org.postgresql:postgresql", "version": "42.5.0"},
        {"repo": "web", "ecosystem": "npm", "name": "react", "version": "18.2.0"},
        {"repo": "web", "ecosystem": "npm", "name": "@acme/ui", "version": "1.0.0"},
        {"repo": "web", "ecosystem": "Maven", "name": "com.acme:core", "version": "2.0"},
        {"repo": "web", "ecosystem": "npm", "name": "left-pad", "version": None},
        {"repo": "web", "ecosystem": "Hex", "name": "phoenix", "version": "1.7.0"}]
OWNED = {"Maven": {"com.acme"}, "npm": {"@acme/"}}
METADATA = b"<metadata><versioning><versions><version>42.7.4</version></versions></versioning></metadata>"


def test_is_owned(latest):
    assert latest.is_owned("Maven", "com.acme:core", OWNED) and not latest.is_owned("Maven", "com.acmex:core", OWNED)
    assert latest.is_owned("npm", "@acme/ui", OWNED) and latest.is_owned("npm", "web", {"npm": {"web"}})
    assert not latest.is_owned("npm", "@acmex/ui", OWNED)
    assert latest.is_owned("Go", "github.com/acme/api/pkg", {"Go": {"github.com/acme/api"}})
    assert not latest.is_owned("Go", "github.com/acme/apix", {"Go": {"github.com/acme/api"}})
    assert latest.is_owned("PyPI", "My_Worker", {"PyPI": {"my-worker"}})
    assert not latest.is_owned("crates.io", "serde", {})


def test_owned_libraries_are_never_fetched(latest):
    asked = []

    def fetch(u):
        asked.append(u)
        return b'{"dist-tags": {"latest": "19.0.0"}}' if "npmjs" in u else METADATA
    out = latest.lookup(ROWS, OWNED, log=lambda _: None, fetch=fetch)
    assert not any("acme" in u for u in asked) and not any("phoenix" in u for u in asked)
    assert out["versions"] == {"Maven|org.postgresql:postgresql": "42.7.4", "npm|react": "19.0.0", "npm|left-pad": "19.0.0"}
    assert out["checked"] == 3 and out["found"] == 3 and out["failed"] == [] and out["at"]


def test_a_404_is_not_a_failure_and_a_dead_registry_is(latest):
    def fetch(u):
        if "npmjs" in u:
            raise OSError("no route")
        raise latest.NotFound(u)
    out = latest.lookup(ROWS, OWNED, log=lambda _: None, fetch=fetch)
    assert out["versions"] == {} and out["failed"] == ["npm"] and out["checked"] == 3


def test_it_never_raises_and_says_what_it_did(latest):
    lines = []

    def boom(u):
        raise RuntimeError("boom")
    out = latest.lookup(ROWS, OWNED, log=lines.append, fetch=boom)
    assert out["failed"] == ["Maven", "npm"]
    assert lines[-1].startswith("✔ 0 with a newer version") and "could not reach: Maven, npm" in lines[-1]
    assert any(line.startswith("[3/3] newer versions · ") for line in lines)


def test_progress_is_at_most_about_fifty_lines(latest):
    rows = [{"repo": "web", "ecosystem": "npm", "name": f"p{i}", "version": "1.0.0"} for i in range(400)]
    lines = []
    latest.lookup(rows, {}, log=lines.append, fetch=lambda u: b'{"dist-tags": {"latest": "1.0.0"}}')
    progress = [line for line in lines if line.startswith("[")]
    assert 40 <= len(progress) <= 51 and progress[-1].startswith("[400/400] newer versions · ")


def test_the_count_of_newer_ones_and_the_default_fetch(latest, monkeypatch):
    lines = []
    monkeypatch.setattr(latest, "_fetch", lambda u: b'{"dist-tags": {"latest": "19.0.0"}}' if "npmjs" in u else METADATA)
    out = latest.lookup(ROWS, OWNED, log=lines.append)
    assert out["found"] == 3 and lines[-1].startswith("✔ 2 with a newer version (3 libraries looked up)")


def test_a_date_in_the_qualifier_is_not_a_flavour(latest):
    assert latest.pick(["9.4.53.v20231009", "9.4.57.v20241219", "12.0.15"], "9.4.53.v20231009") == "12.0.15"
    assert latest.pick(["3.18.0.v20230101-1200", "3.19.0.v20240101-0900"], "3.18.0.v20230101-1200") == "3.19.0.v20240101-0900"
    assert latest.pick(["4.0.0-groovy-4.0", "4.1.0-groovy-4.0", "4.1.0-groovy-3.0"], "4.0.0-groovy-4.0") in ("4.1.0-groovy-4.0", "4.1.0-groovy-3.0")


def test_a_registry_that_keeps_failing_is_not_asked_again(latest, monkeypatch):
    monkeypatch.setattr(latest, "WORKERS", 1)
    rows = [{"repo": "web", "ecosystem": "npm", "name": f"p{i}", "version": "1.0.0"} for i in range(20)]
    calls = []

    def dead(address):
        calls.append(address)
        raise OSError("dropped")
    out = latest.lookup(rows, {}, log=lambda _: None, fetch=dead)
    assert len(calls) == 2 and out["failed"] == ["npm"] and out["checked"] == 20


def test_rows_marked_as_not_from_a_registry_are_skipped(latest):
    rows = [{"repo": "web", "ecosystem": "npm", "name": "private-lib", "version": None, "registry": False},
            {"repo": "web", "ecosystem": "npm", "name": "react", "version": "18.2.0", "registry": True}]
    asked = []
    out = latest.lookup(rows, {}, log=lambda _: None, fetch=lambda u: asked.append(u) or b'{"dist-tags": {"latest": "19.0.0"}}')
    assert asked == ["https://registry.npmjs.org/react"] and out["checked"] == 1


def test_nuget_ids_are_owned_whatever_their_case(latest):
    assert latest.is_owned("NuGet", "acme.common", {"NuGet": {"Acme.Common"}})


def test_a_library_is_newer_when_any_repo_is_behind_as_on_the_screen(latest):
    rows = [{"repo": "a", "ecosystem": "npm", "name": "react", "version": "18.2.0"},
            {"repo": "b", "ecosystem": "npm", "name": "react", "version": "19.0.0"}]
    lines = []
    latest.lookup(rows, {}, log=lines.append, fetch=lambda u: b'{"dist-tags": {"latest": "19.0.0"}}')
    assert lines[-1].startswith("✔ 1 with a newer version")


def test_a_page_that_is_not_the_registry_answer_is_a_failure(latest):
    """A captive portal or a proxy's login page answers 200 with HTML: the registry was not reached."""
    def portal(address):
        return b"<!DOCTYPE html><html><body>Sign in to the network" if "npmjs" in address else METADATA
    out = latest.lookup(ROWS, OWNED, log=lambda _: None, fetch=portal)
    assert out["failed"] == ["npm"] and "npm|react" not in out["versions"]
    assert out["versions"]["Maven|org.postgresql:postgresql"] == "42.7.4"


def test_a_real_answer_with_no_stable_version_is_not_a_failure(latest):
    out = latest.lookup([{"repo": "a", "ecosystem": "npm", "name": "x", "version": "1.0.0"}], {}, log=lambda _: None,
                        fetch=lambda u: b'{"name": "x", "versions": {}}')
    assert out["failed"] == [] and out["versions"] == {}
