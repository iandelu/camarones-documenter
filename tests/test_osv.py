"""Known vulnerabilities (S8): OSV-Scanner, a pinned binary checked against its SHA-256, scans each repo with its
offline database (downloaded once; no package names leave the machine); the online API is used only when this machine
says so (`osv: {online: true}` in ~/.camarones.json). Findings join the inventory rows. Without the binary the
inventory is written anyway, with no vulnerability column."""
from __future__ import annotations

import hashlib, io, json

import pytest

from test_inventory import LOCK, PACKAGE, POM, repos  # noqa: F401 — the three-repo fixture

OSV_OUT = {"results": [
    {"source": {"path": "/x/web/package-lock.json", "type": "lockfile"}, "packages": [{
        "package": {"name": "axios", "version": "1.6.2", "ecosystem": "npm"},
        "vulnerabilities": [{"id": "GHSA-wf5p-g6vw-rhxx", "aliases": ["CVE-2023-45857"], "summary": "CSRF token leak",
                             "details": "Axios sends the XSRF-TOKEN to any host.", "published": "2023-11-08T21:30:37Z",
                             "modified": "2024-01-02T10:00:00Z",
                             "references": [{"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-45857"},
                                            {"type": "WEB", "url": "javascript:alert(1)"}],
                             "affected": [{"package": {"name": "axios", "ecosystem": "npm"},
                                           "ranges": [{"type": "SEMVER", "events": [{"introduced": "0.8.1"}, {"fixed": "1.6.3"}]}]}],
                             "database_specific": {"severity": "MODERATE", "cwe_ids": ["CWE-352"]}}],
        "groups": [{"ids": ["GHSA-wf5p-g6vw-rhxx"], "aliases": ["CVE-2023-45857"], "max_severity": "6.5"}]},
        {"package": {"name": "lodash", "version": "4.17.20", "ecosystem": "npm"},
         "vulnerabilities": [{"id": "GHSA-35jh-r3h4-6jhm", "aliases": ["CVE-2021-23337"], "summary": "Command injection",
                              "affected": [{"package": {"name": "lodash", "ecosystem": "npm"},
                                            "ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}]}]}],
         "groups": [{"ids": ["GHSA-35jh-r3h4-6jhm"], "max_severity": "7.2"}]}]},
    {"source": {"path": "/x/api/pom.xml", "type": "lockfile"}, "packages": [{
        "package": {"name": "org.postgresql:postgresql", "version": "42.7.1", "ecosystem": "Maven"},
        "vulnerabilities": [{"id": "GHSA-24rp-q3w6-vc56", "aliases": ["CVE-2024-1597"], "summary": "SQL injection",
                             "affected": [{"package": {"name": "org.postgresql:postgresql", "ecosystem": "Maven"},
                                           "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "42.7.0"}, {"fixed": "42.7.2"}]}]}]}],
        "groups": [{"ids": ["GHSA-24rp-q3w6-vc56"], "max_severity": "9.8"}]}]},
]}


@pytest.fixture
def scanner(kit, monkeypatch):
    from lib import osv
    seen = []
    monkeypatch.setattr(osv.binaries, "ensure", lambda name, log=print: "/bin/osv-scanner")

    def run(argv, env):
        seen.append((argv, env))
        from pathlib import Path
        results = [r for r in OSV_OUT["results"] if f"/{Path(argv[-1]).name}/" in r["source"]["path"]]
        return 1 if results else 0, json.dumps({"results": results})
    monkeypatch.setattr(osv, "_run", run)
    return seen


def test_findings_join_the_inventory_rows(kit, repos, scanner):  # noqa: F811
    repos.run(log=lambda _: None, cves=True)
    data = repos.load()
    rows = {(r["repo"], r["name"]): r for r in data["libraries"]}
    axios = rows[("web", "axios")]["vulns"][0]
    assert axios == {"id": "GHSA-wf5p-g6vw-rhxx", "cve": "CVE-2023-45857", "summary": "CSRF token leak",
                     "severity": "medium", "score": 6.5, "fixed": "1.6.3", "aliases": ["CVE-2023-45857"],
                     "details": "Axios sends the XSRF-TOKEN to any host.", "published": "2023-11-08T21:30:37Z",
                     "modified": "2024-01-02T10:00:00Z", "ranges": [{"introduced": "0.8.1", "fixed": "1.6.3"}],
                     "references": [{"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-45857"}],
                     "cwes": ["CWE-352"]}                                # the whole advisory, readable offline
    assert rows[("web", "lodash")]["vulns"][0]["severity"] == "high"
    pg = rows[("api", "org.postgresql:postgresql")]                    # version managed by the parent: matched by name
    assert pg["vulns"][0]["severity"] == "critical" and pg["vulns"][0]["fixed"] == "42.7.2"
    assert rows[("web", "react")]["vulns"] == []
    assert data["vulns"]["scanned"] == 3 and data["vulns"]["online"] is False and data["vulns"]["vulnerable"] == 3
    page = (kit.root / "docs" / "overview" / "libraries.md").read_text(encoding="utf-8")
    assert "CVE-2024-1597 (critical, fixed in 42.7.2)" in page


def test_the_offline_database_is_the_default(kit, repos, scanner):  # noqa: F811
    repos.run(log=lambda _: None, cves=True)
    argv, env = scanner[0]
    assert "--offline-vulnerabilities" in argv and "--download-offline-databases" in argv
    assert "--no-resolve" in argv                 # resolving a parent pom would send its coordinates to Maven Central
    assert env["OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY"].endswith("osv-db")


def test_online_only_when_this_machine_says_so(kit, repos, scanner):  # noqa: F811
    from lib.common import PREFS, save_json
    save_json(PREFS, {"osv": {"online": True}})
    repos.run(log=lambda _: None, cves=True)
    assert all("--offline-vulnerabilities" not in argv and "--no-resolve" not in argv for argv, _ in scanner)
    assert repos.load()["vulns"]["online"] is True


def test_without_the_binary_the_inventory_is_still_written(kit, repos, monkeypatch):  # noqa: F811
    from lib import osv
    monkeypatch.setattr(osv.binaries, "ensure", lambda name, log=print: None)
    logs = []
    repos.run(log=logs.append, cves=True)
    data = repos.load()
    assert data["vulns"] is None and data["libraries"] and any("OSV-Scanner" in l for l in logs)


def test_a_scan_that_breaks_is_reported_not_raised(kit, repos, monkeypatch):  # noqa: F811
    from lib import osv
    monkeypatch.setattr(osv.binaries, "ensure", lambda name, log=print: "/bin/osv-scanner")
    monkeypatch.setattr(osv, "_run", lambda argv, env: (127, "not json"))
    repos.run(log=lambda _: None, cves=True)
    assert repos.load()["vulns"]["failed"] == ["api", "web", "worker"]


def test_the_pinned_binary_is_a_single_file_checked_by_sha256(kit, monkeypatch, isolated_env):
    from lib import binaries
    body = b"\x7fELF fake scanner"
    monkeypatch.setattr(binaries, "_target", lambda: ("linux", "x64", "tar.gz"))
    monkeypatch.setitem(binaries.RELEASES["osv-scanner"]["sha256"], "linux_x64", hashlib.sha256(body).hexdigest())
    asked = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(binaries.urllib.request, "urlopen", lambda url, timeout: asked.append(url) or Resp(body))
    monkeypatch.setattr(binaries, "BIN_DIR", isolated_env / ".camarones" / "bin")
    exe = binaries.ensure("osv-scanner", log=lambda _: None)
    assert exe.read_bytes() == body and asked[0].endswith("/v2.6.0/osv-scanner_linux_amd64")
    monkeypatch.setitem(binaries.RELEASES["osv-scanner"]["sha256"], "linux_x64", "0" * 64)
    exe.unlink()
    binaries.ensure("osv-scanner", log=lambda _: None)
    assert not binaries.pinned_path("osv-scanner").exists()                             # checksum mismatch: not installed


def test_a_finding_stays_with_the_repo_it_was_found_in(kit, repos, scanner):  # noqa: F811
    (kit.ws / "web" / "pom.xml").write_text(POM, encoding="utf-8")     # postgresql managed by the parent here too
    repos.run(log=lambda _: None, cves=True)
    rows = {(r["repo"], r["name"]): r for r in repos.load()["libraries"]}
    assert rows[("api", "org.postgresql:postgresql")]["vulns"]
    assert rows[("web", "org.postgresql:postgresql")]["vulns"] == []    # OSV found nothing in web's pom


def test_each_repo_is_counted_as_it_starts(kit, repos, scanner):  # noqa: F811
    """`[n/total] repo:` before each repo's scan, the convention of the setup job: the desktop app draws its bar
    from these lines."""
    logs = []
    repos.run(log=logs.append, cves=True)
    counted = [l for l in logs if l.startswith("[")]
    assert counted == ["[1/3] api: scanning for known vulnerabilities (offline database)…",
                       "[2/3] web: scanning for known vulnerabilities (offline database)…",
                       "[3/3] worker: scanning for known vulnerabilities (offline database)…"]
