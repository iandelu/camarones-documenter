"""SonarQube over HTTP (lib/sonar.py) and its tokens in the keychain (lib/creds.py, kind `sonarqube`), against a fake
Sonar on a port the OS picks. The token travels in the Authorization header only: never in a URL, an error or hosts.json."""
from __future__ import annotations

import base64, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

TOKEN = "squ_s3cr3t-token"
BASIC = "Basic " + base64.b64encode(f"{TOKEN}:".encode()).decode()


class Fake:
    """A Sonar that records every request line and header set, and answers from `routes` (path → status, type, body)."""

    def __init__(self):
        self.lines, self.headers, self.routes, self.delay = [], [], {}, 0
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                fake.lines.append(self.requestline)
                fake.headers.append(dict(self.headers))
                time.sleep(fake.delay)
                status, ctype, body = fake.routes.get(self.path.split("?")[0], (404, "application/json", "{}"))
                raw = body.encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except OSError:                       # the client gave up (the timeout test)
                    pass

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def json(self, path, body, status=200):
        self.routes[path] = (status, "application/json", json.dumps(body))


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.srv.shutdown()
    f.srv.server_close()


@pytest.fixture
def lib(kit, monkeypatch):
    from lib import creds, sonar
    monkeypatch.setattr(creds, "_keyring", lambda: None)             # the fallback file in the test's HOME
    return creds, sonar


def test_valid_token_is_saved_and_only_the_header_carries_it(lib, fake):
    creds, sonar = lib
    fake.json("/api/authentication/validate", {"valid": True})
    assert creds.verify(fake.host, "sonarqube", TOKEN) == (True, "")
    creds.save(fake.host, "sonarqube", TOKEN, "")
    assert creds.get(fake.host) == TOKEN
    assert fake.lines == ["GET /api/authentication/validate HTTP/1.1"]
    assert TOKEN not in fake.lines[0] and fake.headers[0]["Authorization"] == BASIC
    assert not any(TOKEN in v for k, v in fake.headers[0].items() if k != "Authorization")
    assert TOKEN not in creds.META.read_text(encoding="utf-8")
    assert creds.hosts()[fake.host]["kind"] == "sonarqube"


def test_an_invalid_token_is_refused(lib, fake):
    creds, _ = lib
    fake.json("/api/authentication/validate", {"valid": False})
    assert creds.verify(fake.host, "sonarqube", TOKEN) == (False, "token no válido")


@pytest.mark.parametrize("status", [401, 403])
def test_sonar_get_401_403_is_token_no_valido(lib, fake, status):
    _, sonar = lib
    fake.json("/api/measures/component", {"errors": []}, status)
    with pytest.raises(sonar.SonarError) as e:
        sonar.sonar_get(fake.host, TOKEN, "/api/measures/component", {"component": "p"})
    assert str(e.value) == "token no válido" and TOKEN not in repr(e.value)


def test_sonar_get_404_is_proyecto_no_encontrado(lib, fake):
    _, sonar = lib
    with pytest.raises(sonar.SonarError, match="^proyecto no encontrado$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/measures/component", {"component": "nope"})


def test_sonar_get_other_status_names_it(lib, fake):
    _, sonar = lib
    fake.json("/api/x", {}, 500)
    with pytest.raises(sonar.SonarError, match="^error 500$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/x", {})


def test_sonar_get_timeout_is_sin_conexion(lib, fake, monkeypatch):
    _, sonar = lib
    monkeypatch.setattr(sonar, "TIMEOUT", 0.2)
    fake.delay = 1
    fake.json("/api/x", {})
    with pytest.raises(sonar.SonarError, match="^sin conexión$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/x", {})


def test_sonar_get_refused_connection_is_sin_conexion(lib, fake):
    _, sonar = lib
    host = fake.host
    fake.srv.shutdown()
    fake.srv.server_close()
    with pytest.raises(sonar.SonarError, match="^sin conexión$"):
        sonar.sonar_get(host, TOKEN, "/api/x", {})


def test_a_200_html_page_is_respuesta_no_valida(lib, fake):
    _, sonar = lib
    fake.routes["/api/x"] = (200, "text/html", "<html><body>Log in with SSO</body></html>")
    with pytest.raises(sonar.SonarError, match="^respuesta no válida$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/x", {})


def test_a_redirect_is_not_followed_so_the_token_never_leaves(lib, fake):
    _, sonar = lib
    fake.routes["/api/x"] = (302, "text/html", "")
    with pytest.raises(sonar.SonarError, match="^error 302$"):
        sonar.sonar_get(fake.host, TOKEN, "/api/x", {})
    assert len(fake.lines) == 1


def test_sonar_get_returns_the_json_and_keeps_the_token_out_of_the_url(lib, fake):
    _, sonar = lib
    fake.json("/api/measures/component", {"component": {"key": "p"}})
    out = sonar.sonar_get(fake.host, TOKEN, "/api/measures/component", {"component": "p", "metricKeys": "coverage"})
    assert out == {"component": {"key": "p"}}
    assert fake.lines == ["GET /api/measures/component?component=p&metricKeys=coverage HTTP/1.1"]
    assert fake.headers[0]["Authorization"] == BASIC


def test_a_path_prefix_in_the_host_is_kept(lib, fake):
    _, sonar = lib
    fake.json("/sonar/api/x", {"ok": 1})
    assert sonar.sonar_get(fake.host + "/sonar/", TOKEN, "/api/x", {}) == {"ok": 1}


def test_http_is_refused_before_any_request_unless_local(lib, fake, monkeypatch):
    creds, sonar = lib
    monkeypatch.setattr(sonar._OPENER, "open", lambda *a, **k: pytest.fail("a request went out"))
    assert creds.verify("http://sonar.example.com", "sonarqube", TOKEN) == (False, "solo https")
    with pytest.raises(sonar.SonarError, match="^solo https$"):
        sonar.sonar_get("http://sonar.example.com", TOKEN, "/api/x", {})
    with pytest.raises(ValueError):
        creds.api_base("http://sonar.example.com", "sonarqube")


@pytest.mark.parametrize("host,base", [
    ("sonar.example.com", "https://sonar.example.com"),
    ("https://sonar.example.com", "https://sonar.example.com"),
    ("https://sonar.example.com/sonar/", "https://sonar.example.com/sonar"),
    ("http://localhost:9000", "http://localhost:9000"),
    ("http://127.0.0.1:9000", "http://127.0.0.1:9000"),
    ("http://[::1]:9000", "http://[::1]:9000"),
])
def test_api_base_accepts_these_host_forms(lib, host, base):
    creds, _ = lib
    assert creds.api_base(host, "sonarqube") == base


@pytest.mark.parametrize("host", ["ftp://sonar.example.com", "https://user:pw@sonar.example.com", "",
                                  "http://localhost.evil.com", "http://127.0.0.1@evil.com"])
def test_api_base_refuses_a_host_it_cannot_use(lib, host):
    creds, _ = lib
    with pytest.raises(ValueError):
        creds.api_base(host, "sonarqube")


def test_gitlab_and_github_hosts_still_work(lib):
    creds, _ = lib
    assert creds.api_base("gitlab.example.com", "gitlab") == "https://gitlab.example.com/api/v4"
    assert creds.host_of("git@gitlab.example.com:g/r.git") == "gitlab.example.com"
    assert creds.host_of("https://gitlab.example.com/g/r.git") == "gitlab.example.com"


def test_a_sonar_host_never_counts_as_a_git_forge(lib, kit, monkeypatch):
    creds, _ = lib
    creds.save("https://sonar.example.com/sonar", "sonarqube", TOKEN, "")
    creds.save("sonar.example.com", "sonarqube", TOKEN, "")
    creds.save("gitlab.example.com", "gitlab", "gl-token", "me")
    assert creds.forge_hosts() == ["gitlab.example.com"]
    shown = []
    W = kit.wizard.W
    monkeypatch.setattr(W, "sel", lambda self, msg, choices, back=True, default=None: shown.append([c.value for c in choices]))
    W().add_remote({"repos": []})
    assert shown == [["gitlab.example.com", "__new__"]]


def test_forge_calls_refuse_the_sonar_kind_without_a_request(lib, monkeypatch):
    creds, sonar = lib
    monkeypatch.setattr(creds.urllib.request, "urlopen", lambda *a, **k: pytest.fail("a request went out"))
    with pytest.raises(ValueError):
        creds.list_projects("sonar.example.com", "sonarqube", TOKEN)
    with pytest.raises(ValueError):
        creds._get("https://sonar.example.com/api/x", "sonarqube", TOKEN)


def test_git_never_gets_a_sonar_token_even_on_the_same_host(lib):
    creds, _ = lib
    creds.save("sonar.example.com", "sonarqube", TOKEN, "")
    assert creds.git_env("https://sonar.example.com/g/r.git") == {"GIT_TERMINAL_PROMPT": "0"}


@pytest.mark.parametrize("host", ["https://sonar.example.com?x", "https://sonar.example.com#x",
                                  "https://sonar.example.com;x", "https://sonar.example.com/a b", "sonar.example .com",
                                  "https://evil.io#.sonar.empresa.com", "https://evil.io?.sonar.empresa.com",
                                  "https://evil.io;.sonar.empresa.com", "sonar.example.com\tx"])
def test_a_host_with_a_query_fragment_params_or_whitespace_is_refused_before_any_request(lib, host, monkeypatch):
    creds, sonar = lib
    monkeypatch.setattr(sonar._OPENER, "open", lambda *a, **k: pytest.fail("a request went out"))
    with pytest.raises(ValueError, match="^host no válido$"):
        creds.sonar_base(host)
    assert creds.verify(host, "sonarqube", TOKEN) == (False, "host no válido")
    with pytest.raises(sonar.SonarError, match="^host no válido$"):
        sonar.sonar_get(host, TOKEN, "/api/x", {})
