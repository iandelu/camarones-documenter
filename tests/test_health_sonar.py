"""The SonarQube read of the health snapshot (lib/sonar.py `read`, called by `health.build`), against fake Sonar servers on
ports the OS picks and a token in the keychain's file fallback. Reads happen in build() only."""
from __future__ import annotations

import json
import re

import pytest

from test_health import NO_PROBES, JACOCO, clean_snapshot, health_cli, put, repo_block, quiet, TODAY
from test_sonar import Fake

TOKEN = "squ_s3cr3t-token"
GOOD = {"coverage": "81.5", "bugs": "3", "vulnerabilities": "2", "security_hotspots": "4", "code_smells": "120",
        "sqale_index": "1500", "sqale_rating": "1.0", "reliability_rating": "2.0", "security_rating": "5.0"}
SERVER = {"gate": "OK", "coverage": 81.5, "bugs": 3, "vulnerabilities": 2, "security_hotspots": 4, "code_smells": 120,
          "debt_minutes": 1500, "ratings": {"maintainability": "A", "reliability": "B", "security": "E"}}


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.srv.shutdown()
    f.srv.server_close()


@pytest.fixture
def other():
    f = Fake()
    yield f
    f.srv.shutdown()
    f.srv.server_close()


def serve(fake, gate="OK", **metrics):
    """What a Sonar answers for a project: its measures (GOOD unless given) and its quality gate."""
    values = metrics or GOOD
    fake.json("/api/measures/component", {"component": {"key": "k", "measures": [
        {"metric": m, "value": v} for m, v in values.items()]}})
    fake.json("/api/qualitygates/project_status", {"projectStatus": {"status": gate}} if gate else {"projectStatus": {}})


@pytest.fixture
def lib(kit, monkeypatch):
    from lib import creds, sonar
    monkeypatch.setattr(creds, "_keyring", lambda: None)             # the fallback file in the test's HOME
    return creds, sonar


@pytest.fixture
def probed(wired, monkeypatch):
    import copy
    from lib import creds, doctor
    monkeypatch.setattr(doctor, "report", lambda: copy.deepcopy(NO_PROBES))
    monkeypatch.setattr(creds, "_keyring", lambda: None)
    return wired


def point(probed, repo, host, key="acme"):
    put(probed.common.repo_dir(repo), "sonar-project.properties", f"sonar.projectKey={key}_{repo}\nsonar.host.url={host}\n")


def block(**over):
    return {"used": True, "project": "acme_api", "organization": "", "host": "", "link": "", **over}


# ---- a good read ----

def test_a_good_read_fills_the_server_figures_and_the_gate(probed, fake):
    from lib import creds, health
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    snap = health.build(log=quiet)
    sonar = snap["repos"]["api"]["sonar"]
    assert sonar["server"].pop("at") and sonar["server"] == SERVER
    assert "connect" not in sonar and "error" not in sonar and sonar["project"] == "acme_api" and sonar["used"] is True
    assert len(fake.lines) == 2
    assert "component=acme_api" in fake.lines[0] and "metricKeys=coverage%2Cbugs%2C" in fake.lines[0]
    assert "projectKey=acme_api" in fake.lines[1]
    assert snap["repos"]["web"]["sonar"]["used"] is False


def test_metrics_are_the_ones_the_brief_names(lib):
    _, sonar = lib
    assert sonar.METRICS == ("coverage,bugs,vulnerabilities,security_hotspots,code_smells,sqale_index,sqale_rating,"
                             "reliability_rating,security_rating")


def test_a_metric_sonar_does_not_give_is_none_never_zero(lib, fake):
    creds, sonar = lib
    serve(fake, gate=None, bugs="0", sqale_rating="oops", coverage="nan")
    creds.save(fake.host, "sonarqube", TOKEN)
    out = sonar.read(block(host=fake.host), None, {})
    assert out["server"]["bugs"] == 0 and isinstance(out["server"]["bugs"], int)
    assert out["server"]["coverage"] is None and out["server"]["vulnerabilities"] is None
    assert out["server"]["debt_minutes"] is None and out["server"]["gate"] is None
    assert out["server"]["ratings"] == {"maintainability": None, "reliability": None, "security": None}


def test_sonars_coverage_wins_and_says_where_it_comes_from(probed, fake):
    from lib import creds, health
    serve(fake)
    api = probed.common.repo_dir("api")
    put(api, "target/site/jacoco/jacoco.xml", JACOCO)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    repo = health.build(log=quiet)["repos"]["api"]
    assert repo["coverage"] == {"percent": 81.5, "at": repo["sonar"]["server"]["at"], "source": "sonar", "path": None}
    assert repo["reports"][0]["percent"] == 80.0                               # the local report is still listed


def test_without_a_sonar_coverage_the_local_report_stays(probed, fake):
    from lib import creds, health
    serve(fake, bugs="1")
    put(probed.common.repo_dir("api"), "target/site/jacoco/jacoco.xml", JACOCO)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    repo = health.build(log=quiet)["repos"]["api"]
    assert repo["sonar"]["server"]["coverage"] is None
    assert repo["coverage"]["source"] == "report" and repo["coverage"]["percent"] == 80.0


# ---- the quality gate ----

def test_a_failed_gate_makes_code_bad(probed, fake):
    from lib import creds, health
    serve(fake, gate="ERROR")
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    snap = health.build(log=quiet)
    code = snap["areas"]["code"]
    assert code["state"] == "bad" and code["next"] == {"key": "code.gateFailed", "row": "repos"}
    assert {"key": "code.gateFailed", "n": 1} in snap["verdict"]
    assert snap["repo_state"]["api"] == "bad" and snap["repo_state"]["web"] != "bad"


def test_gate_failed_counts_repos_and_follows_the_vulnerabilities_in_rule_order():
    from lib import health
    assert health.ROWS["code.gateFailed"] == "repos"
    assert list(health.ROWS).index("code.gateFailed") == list(health.ROWS).index("code.vulnHigh") + 1

    def gated(gate):
        return repo_block(sonar={**repo_block()["sonar"], "used": True, "server": {"gate": gate}})
    s = clean_snapshot()
    s["repos"] = {"a": gated("ERROR"), "b": gated("ERROR"), "c": gated("WARN"), "d": gated("OK"), "e": gated(None)}
    s["repos"]["a"]["vulnerable"] = [{"severity": "high"}]
    got = health.areas(s, today=TODAY)
    assert [(v["key"], v["n"]) for v in got["verdict"]] == [("code.vulnHigh", 1), ("code.gateFailed", 2)]
    assert got["repo_state"] == {"a": "bad", "b": "bad", "c": "ok", "d": "ok", "e": "ok"}


def test_a_warn_gate_and_a_missing_one_do_not_fail_code():
    from lib import health
    s = clean_snapshot()
    s["repos"]["api"] = repo_block(sonar={**repo_block()["sonar"], "used": True, "server": {"gate": "WARN"}})
    s["repos"]["web"] = repo_block(sonar={**repo_block()["sonar"], "used": True, "connect": True})
    assert health.areas(s, today=TODAY)["areas"]["code"]["state"] == "ok"


# ---- which host, which token ----

class Calls:
    def __init__(self, sonar, monkeypatch, status="OK"):
        self.calls = []
        monkeypatch.setattr(sonar, "sonar_get", self.get)
        self.status = status

    def get(self, host, token, path, params):
        self.calls.append((host, token, path, params))
        if path == "/api/qualitygates/project_status":
            return {"projectStatus": {"status": self.status}}
        return {"component": {"measures": [{"metric": "bugs", "value": "1"}]}}

    @property
    def hosts(self):
        return {c[0] for c in self.calls}


def test_host_resolution_order(lib, monkeypatch):
    creds, sonar = lib
    for h in ("https://repo.example.com", "https://sonarcloud.io", "https://team.example.com"):
        creds.save(h, "sonarqube", TOKEN)
    ws = {"sonar": {"host": "https://team.example.com"}}
    own = block(host="https://repo.example.com", organization="acme")
    for repo, workspace, want in [(own, ws, "https://repo.example.com"),            # the repo's own host.url
                                  (block(organization="acme"), ws, "https://sonarcloud.io"),   # SonarCloud for an organization
                                  (block(), ws, "https://team.example.com")]:      # the team's host
        calls = Calls(sonar, monkeypatch)
        assert sonar.read(repo, None, workspace)["server"]["bugs"] == 1
        assert calls.hosts == {want} and len(calls.calls) == 2


def test_no_host_leaves_the_block_as_it_is(lib, monkeypatch):
    creds, sonar = lib
    creds.save("https://sonarcloud.io", "sonarqube", TOKEN)
    calls = Calls(sonar, monkeypatch)
    for ws in ({}, {"sonar": None}, {"sonar": {}}, {"sonar": {"host": ""}}, {"sonar": "x"}):
        repo = block(link="https://x/dashboard")
        assert sonar.read(repo, {"sonar": {"server": SERVER}}, ws) == repo
    assert calls.calls == []


def test_a_repo_without_a_project_key_or_not_using_sonar_is_not_read(lib, monkeypatch):
    creds, sonar = lib
    creds.save("https://sonarcloud.io", "sonarqube", TOKEN)
    calls = Calls(sonar, monkeypatch)
    for repo in (block(project="", organization="acme"), block(used=False, project="")):
        assert sonar.read(repo, None, {"sonar": {"host": "https://sonarcloud.io"}}) == repo
    assert calls.calls == []


def test_the_workspace_reader_accepts_the_optional_sonar_key(kit):
    ws = kit.docs.workspace()
    assert "sonar" not in ws                                                  # an old project: nothing to add
    ws["sonar"] = {"host": "https://sonar.example.com"}
    kit.docs.save_workspace(ws)
    again = kit.docs.workspace()
    assert again["sonar"] == {"host": "https://sonar.example.com"} and [r["name"] for r in again["repos"]]


@pytest.mark.parametrize("saved,host", [("https://sonar.example.com", "https://sonar.example.com"),
                                        ("sonar.example.com", "https://sonar.example.com"),
                                        ("https://sonar.example.com", "sonar.example.com"),
                                        ("sonar.example.com", "sonar.example.com/")])
def test_the_token_is_found_under_the_host_as_it_was_saved(lib, monkeypatch, saved, host):
    creds, sonar = lib
    creds.save(saved, "sonarqube", TOKEN)
    calls = Calls(sonar, monkeypatch)
    out = sonar.read(block(host=host), None, {})
    assert "server" in out and "connect" not in out and {c[1] for c in calls.calls} == {TOKEN}


def test_no_token_asks_to_connect_and_reads_nothing(probed, fake):
    from lib import health
    serve(fake)
    point(probed, "api", fake.host)
    snap = health.build(log=quiet)
    sonar = snap["repos"]["api"]["sonar"]
    assert sonar["connect"] is True and "server" not in sonar and "error" not in sonar and fake.lines == []
    assert snap["areas"]["code"]["state"] != "bad"
    assert snap["repos"]["api"]["coverage"] is None


# ---- failures keep the last values ----

def test_a_failing_read_keeps_the_previous_values_and_says_why(probed, fake, other):
    from lib import creds, health
    serve(fake)
    serve(other, bugs="9")
    point(probed, "api", fake.host)
    point(probed, "web", other.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    creds.save(other.host, "sonarqube", TOKEN)
    first = health.build(log=quiet)["repos"]
    fake.json("/api/measures/component", {"errors": []}, 401)
    other.json("/api/measures/component", {"component": {"measures": [{"metric": "bugs", "value": "5"}]}})
    second = health.build(log=quiet)["repos"]
    failed = second["api"]["sonar"]
    assert failed["error"] == "token no válido"
    assert failed["server"] == first["api"]["sonar"]["server"] and failed["server"]["at"]    # values and their date
    assert second["api"]["coverage"]["percent"] == 81.5 and second["api"]["coverage"]["at"] == failed["server"]["at"]
    ok = second["web"]["sonar"]
    assert "error" not in ok and ok["server"]["bugs"] == 5                     # the other repo is read as usual


def test_a_failing_first_read_has_an_error_and_no_figures(probed, fake):
    from lib import creds, health
    point(probed, "api", fake.host)                                          # the fake answers 404 for every path
    creds.save(fake.host, "sonarqube", TOKEN)
    sonar = health.build(log=quiet)["repos"]["api"]["sonar"]
    assert sonar["error"] == "proyecto no encontrado" and "server" not in sonar and "connect" not in sonar


def test_a_login_page_instead_of_json_keeps_the_previous_values(probed, fake):
    from lib import creds, health
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    before = health.build(log=quiet)["repos"]["api"]["sonar"]["server"]
    fake.routes["/api/measures/component"] = (200, "text/html", "<html><body>Log in with SSO</body></html>")
    after = health.build(log=quiet)["repos"]["api"]["sonar"]
    assert after["error"] == "respuesta no válida" and after["server"] == before


def test_an_unreachable_server_is_sin_conexion(lib, fake):
    creds, sonar = lib
    creds.save(fake.host, "sonarqube", TOKEN)
    fake.srv.shutdown()
    fake.srv.server_close()
    prev = {"sonar": {"server": {**SERVER, "at": "2026-10-20T08:00:00Z"}}}
    out = sonar.read(block(host=fake.host), prev, {})
    assert out["error"] == "sin conexión" and out["server"] == prev["sonar"]["server"]


def test_http_to_a_remote_host_is_refused_before_any_request(lib, monkeypatch):
    creds, sonar = lib
    monkeypatch.setattr(sonar._OPENER, "open", lambda *a, **k: pytest.fail("a request went out"))
    creds.save("http://sonar.example.com", "sonarqube", TOKEN)
    out = sonar.read(block(host="http://sonar.example.com"), None, {})
    assert out["error"] == "solo https" and "server" not in out


@pytest.mark.parametrize("previous", [None, {}, {"sonar": None}, {"sonar": {"server": "x"}}, {"sonar": "x"}, "x", {"sonar": {"error": "boom"}}])
def test_a_previous_snapshot_of_any_shape_is_tolerated(lib, previous, fake):
    creds, sonar = lib
    creds.save(fake.host, "sonarqube", TOKEN)                               # the fake answers 404
    out = sonar.read(block(host=fake.host), previous, {})
    assert out["error"] == "proyecto no encontrado" and "server" not in out


# ---- the token stays out, reads stay in build() ----

def test_the_token_is_nowhere_in_the_snapshot(probed, fake):
    from lib import creds, health
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    snap = health.build(log=quiet)
    assert TOKEN not in json.dumps(snap) and TOKEN not in health.SNAPSHOT.read_text(encoding="utf-8")
    r = health_cli(probed, "--json")
    assert r.returncode == 0, r.stderr
    assert TOKEN not in r.stdout and TOKEN not in r.stderr and json.loads(r.stdout)["repos"]["api"]["sonar"]["server"]


def test_load_and_the_api_never_read_sonar(probed, fake, monkeypatch):
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    from lib import creds, health, sonar
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    snap = health.build(log=quiet)
    monkeypatch.setattr(sonar, "sonar_get", lambda *a, **k: pytest.fail("Sonar was read outside build()"))
    assert health.load() == snap
    srv = ThreadingHTTPServer(("127.0.0.1", 0), probed.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/health", timeout=10) as r:
            assert json.loads(r.read()) == {"snapshot": snap}
    finally:
        srv.shutdown()
        srv.server_close()
    assert re.search(r"^\d{4}-\d\d-\d\dT[\d:]+Z$", snap["repos"]["api"]["sonar"]["server"]["at"])
