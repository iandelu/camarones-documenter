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
    assert sonar["server"].pop("at") and sonar["server"].pop("host") == fake.host and sonar["server"] == SERVER
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


def test_a_repo_without_a_token_carries_the_host_the_kit_would_use(lib, monkeypatch):
    creds, sonar = lib
    calls = Calls(sonar, monkeypatch)
    ws = {"sonar": {"host": "https://team.example.com/"}}
    cloud = sonar.read(block(organization="acme"), None, ws)                       # SonarCloud by organization
    team = sonar.read(block(), None, ws)                                            # the team's host
    own = sonar.read(block(host="https://repo.example.com"), None, ws)
    assert (cloud["host"], cloud["connect"]) == ("https://sonarcloud.io", True)
    assert (team["host"], team["connect"]) == ("https://team.example.com", True)
    assert (own["host"], own["connect"]) == ("https://repo.example.com", True)
    assert calls.calls == []


def test_the_host_of_the_block_is_filled_on_success_and_on_error_and_never_carries_userinfo(lib, monkeypatch):
    creds, sonar = lib
    creds.save("https://team.example.com", "sonarqube", TOKEN)
    calls = Calls(sonar, monkeypatch)
    ws = {"sonar": {"host": "https://team.example.com"}}
    assert sonar.read(block(), None, ws)["host"] == "https://team.example.com"
    monkeypatch.setattr(sonar, "sonar_get", lambda *a, **k: (_ for _ in ()).throw(sonar.SonarError("sin conexión")))
    assert sonar.read(block(), None, ws)["host"] == "https://team.example.com"
    for given in ("https://u:p@h", "https://u:pa/ss@host.com/x", "u:pa/ss@host.com", "me:secret@sonar.example.com"):
        shown = sonar.read(block(host=given), None, {})
        assert shown["host"] == "" and "ss@" not in str(shown) and "secret" not in str(shown) and "u:p" not in str(shown)


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
    prev = {"sonar": {"project": "acme_api", "server": {**SERVER, "at": "2026-10-20T08:00:00Z", "host": fake.host}}}
    out = sonar.read(block(host=fake.host), prev, {})
    assert out["error"] == "sin conexión" and out["server"] == prev["sonar"]["server"]


def kept(host, **over):
    return {"sonar": {"project": "acme_api", "server": {**SERVER, "at": "2026-10-20T08:00:00Z", "host": host}, **over}}


@pytest.mark.parametrize("answer", [{"component": "x"}, {"component": {"measures": 5}}, {"component": {"measures": [1]}},
                                    {"component": {"measures": [{"metric": ["bugs"], "value": "1"}]}},
                                    {"component": []}], ids=["component string", "measures number", "measure a number",
                                                            "metric a list", "component list"])
def test_a_measures_answer_of_the_wrong_shape_is_respuesta_no_valida(lib, fake, answer):
    creds, sonar = lib
    creds.save(fake.host, "sonarqube", TOKEN)
    fake.json("/api/measures/component", answer)
    fake.json("/api/qualitygates/project_status", {"projectStatus": {"status": "OK"}})
    prev = kept(fake.host)
    out = sonar.read(block(host=fake.host, link="https://x"), prev, {})
    assert out == {**block(host=fake.host, link="https://x"), "server": prev["sonar"]["server"], "error": "respuesta no válida"}


@pytest.mark.parametrize("gate", [{"projectStatus": [1]}, {"projectStatus": "OK"}])
def test_a_gate_answer_of_the_wrong_shape_is_respuesta_no_valida(lib, fake, gate):
    creds, sonar = lib
    creds.save(fake.host, "sonarqube", TOKEN)
    fake.json("/api/measures/component", {"component": {"measures": []}})
    fake.json("/api/qualitygates/project_status", gate)
    out = sonar.read(block(host=fake.host), kept(fake.host), {})
    assert out["error"] == "respuesta no válida" and out["server"]["bugs"] == 3 and out["project"] == "acme_api"


def test_json_nested_too_deep_is_respuesta_no_valida(probed, fake):
    from lib import creds, health
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    before = health.build(log=quiet)["repos"]["api"]["sonar"]
    fake.routes["/api/measures/component"] = (200, "application/json", "[" * 200_000)
    after = health.build(log=quiet)["repos"]["api"]["sonar"]
    assert after["error"] == "respuesta no válida" and after["server"] == before["server"]
    assert after["used"] is True and after["project"] == "acme_api" and after["link"] == before["link"]


def test_an_oversized_answer_is_refused(lib, fake, monkeypatch):
    creds, sonar = lib
    monkeypatch.setattr(sonar, "MAX_BYTES", 100)
    creds.save(fake.host, "sonarqube", TOKEN)
    fake.routes["/api/x"] = (200, "application/json", json.dumps({"pad": "x" * 200}))
    with pytest.raises(sonar.SonarError, match="^respuesta no válida$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/x", {})
    fake.routes["/api/x"] = (200, "application/json", json.dumps({"pad": "x"}))
    assert sonar.sonar_get(fake.host, TOKEN, "/api/x", {}) == {"pad": "x"}


def test_a_host_that_does_not_answer_is_asked_once_per_build(probed, fake, monkeypatch):
    from lib import creds, health, sonar
    for r in ("api", "web"):
        point(probed, r, fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    serve(fake)
    first = health.build(log=quiet)["repos"]
    fake.srv.shutdown()
    fake.srv.server_close()
    attempts, real = [], sonar.sonar_get
    monkeypatch.setattr(sonar, "sonar_get", lambda *a, **k: attempts.append(a[2]) or real(*a, **k))
    second = health.build(log=quiet)["repos"]
    assert attempts == ["/api/measures/component"]                           # one connection attempt for both repos
    for r in ("api", "web"):
        assert second[r]["sonar"]["error"] == "sin conexión"
        assert second[r]["sonar"]["server"] == first[r]["sonar"]["server"]


def test_the_build_says_once_that_it_reads_sonar_and_never_the_token_or_the_query(probed, fake):
    from lib import creds, health
    for r in ("api", "web"):
        point(probed, r, fake.host)
    creds.save(fake.host, "sonarqube", TOKEN)
    serve(fake)
    said = []
    health.build(log=said.append)
    assert said.count("reading SonarQube…") == 1
    assert not any(TOKEN in m or "component=" in m for m in said)


def test_no_sonar_line_when_no_repo_is_read(probed):
    from lib import health
    said = []
    health.build(log=said.append)
    assert "reading SonarQube…" not in said


@pytest.mark.parametrize("what", ["key", "host"])
def test_figures_of_another_project_or_host_are_not_kept(lib, fake, what):
    creds, sonar = lib
    creds.save(fake.host, "sonarqube", TOKEN)                               # the fake answers 404
    prev = kept(fake.host + "/other" if what == "host" else fake.host)
    repo = block(host=fake.host, project="renamed" if what == "key" else "acme_api")
    out = sonar.read(repo, prev, {})
    assert out["error"] == "proyecto no encontrado" and "server" not in out


def test_a_bool_is_not_a_number(lib):
    _, sonar = lib
    assert sonar._number(True) is None and sonar._number(False) is None and sonar._number("0") == 0
    out = sonar._server({"component": {"measures": [{"metric": "bugs", "value": True}]}}, {}, "t", "h")
    assert out["bugs"] is None


def test_a_huge_integer_metric_is_none_and_keeps_the_block(lib, fake):
    creds, sonar = lib
    assert sonar._number(10**400) is None
    out = sonar._server({"component": {"measures": [{"metric": "bugs", "value": 10**400}, {"metric": "coverage", "value": "5"}]}},
                        {}, "t", "h")
    assert out["bugs"] is None and out["coverage"] == 5
    creds.save(fake.host, "sonarqube", TOKEN)
    fake.routes["/api/measures/component"] = (200, "application/json", '{"component": {"measures": [{"metric": "bugs", "value": 1'
                                              + "0" * 400 + "}]}}")
    fake.json("/api/qualitygates/project_status", {"projectStatus": {"status": "OK"}})
    got = sonar.read(block(host=fake.host), None, {})
    assert got["server"]["bugs"] is None and got["server"]["gate"] == "OK" and "error" not in got


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


# ---- credentials in the host a repo names ----

@pytest.mark.parametrize("named", ["https://me:secret@sonar.example.com", "me:secret@sonar.example.com",
                                   "https://me:sec/ret@sonar.example.com/x", "https://secret@sonar.example.com"])
@pytest.mark.parametrize("key", ["acme_api", None])
def test_credentials_in_a_named_host_reach_no_block_snapshot_or_page(probed, lib, named, key):
    from lib import health, radar
    creds, sonar = lib
    props = (f"sonar.projectKey={key}\n" if key else "") + f"sonar.organization=acme\nsonar.host.url={named}\n"
    repo = probed.common.repo_dir("api")
    put(repo, "sonar-project.properties", props)
    info = radar.read_sonar(repo / "sonar-project.properties")
    assert "host" not in info and "link" not in info and info.get("organization") == "acme"     # kept: project, organization
    assert info.get("project", "") == (key or "")
    shown = sonar.read({"used": True, "organization": "acme", "project": key or "", "host": info.get("host", ""),
                        "link": info.get("link", "")}, None, {})
    snap = health.build(log=quiet)
    radar.run(log=quiet)
    everything = (json.dumps(info) + json.dumps(shown) + json.dumps(snap) + health.SNAPSHOT.read_text(encoding="utf-8")
                  + radar.PAGE.read_text(encoding="utf-8"))
    for part in ("secret", "me:", "ret@", "@sonar"):
        assert part not in everything
    assert snap["repos"]["api"]["sonar"]["used"] is True


# ---- only a SonarQube token goes to Sonar ----

def test_a_token_saved_for_another_kind_of_host_is_never_sent(probed, fake):
    from lib import creds, health
    serve(fake)
    point(probed, "api", fake.host)
    creds.save(fake.host, "gitlab", "glpat-not-for-sonar")
    sonar = health.build(log=quiet)["repos"]["api"]["sonar"]
    assert sonar["connect"] is True and "server" not in sonar and "error" not in sonar
    assert fake.lines == [] and fake.headers == []                       # nothing was sent, so no Authorization either


def test_the_next_form_of_the_host_holds_the_sonarqube_token(lib, monkeypatch):
    creds, sonar = lib
    creds.save("https://sonar.example.com", "gitlab", "glpat-not-for-sonar")
    creds.save("sonar.example.com", "sonarqube", TOKEN)                      # the form after the scheme-ful one
    calls = Calls(sonar, monkeypatch)
    out = sonar.read(block(host="https://sonar.example.com"), None, {})
    assert "server" in out and {c[1] for c in calls.calls} == {TOKEN}
