"""SonarQube over HTTP, read only. The token travels in the Authorization header (lib/creds.py builds it) and nowhere
else: not in the URL, not in an error, not in a log. Failures come out as a SonarError whose text is the plain reason,
in Spanish, as the health snapshot shows it. `read` turns a repo's project key into the figures of that snapshot."""
from __future__ import annotations

import http.client, json, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

from . import creds

TIMEOUT = 10        # seconds, for each read
MAX_BYTES = 5_000_000   # of an answer: a larger one is not a Sonar answer


class SonarError(Exception):
    """str(e) is the reason: token no válido · proyecto no encontrado · sin conexión · respuesta no válida · solo https · error <status>."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):                    # a redirect would carry the Authorization header along
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def sonar_get(host: str, token: str, path: str, params: dict) -> dict:
    """GET <host><path>?<params> as JSON. `host` as saved in the keychain (path prefix included)."""
    try:
        base = creds.sonar_base(host)
    except ValueError as e:
        raise SonarError(str(e)) from None
    url = f"{base}/{path.lstrip('/')}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    req = urllib.request.Request(url, headers=creds._headers("sonarqube", token))
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as r:
            raw = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        e.close()                                            # free the connection before raising
        raise SonarError(_reason(e.code)) from None
    except (OSError, http.client.HTTPException):             # timeout, DNS, refused, reset: URLError is an OSError
        raise SonarError("sin conexión") from None
    if len(raw) > MAX_BYTES:
        raise SonarError("respuesta no válida")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):                     # includes a 200 SSO login page in HTML, and JSON nested too deep
        raise SonarError("respuesta no válida") from None
    if not isinstance(data, dict):
        raise SonarError("respuesta no válida")
    return data


def _reason(status: int) -> str:
    return {401: "token no válido", 403: "token no válido", 404: "proyecto no encontrado"}.get(status, f"error {status}")


# ---- reading a repo into the health snapshot ----

METRICS = ("coverage,bugs,vulnerabilities,security_hotspots,code_smells,sqale_index,sqale_rating,reliability_rating,"
           "security_rating")
SONARCLOUD = "https://sonarcloud.io"
RATINGS = {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"}
GATES = ("OK", "WARN", "ERROR")


def _host(repo_sonar: dict, ws: dict) -> str:
    """The server of a repo: its own `sonar.host.url`, SonarCloud when only an organization is set, else the team's
    `sonar: {host}` of workspace.yaml. "" when none applies."""
    team = ws.get("sonar") if isinstance(ws, dict) else None
    team = team.get("host") if isinstance(team, dict) else None
    return (repo_sonar.get("host") or (SONARCLOUD if repo_sonar.get("organization") else "")
            or (team if isinstance(team, str) else "")).strip()


def _shown(host: str) -> str:
    """The host as the snapshot carries it, so the screens can offer to connect to it. A host with userinfo
    (`https://user:secret@host`) is refused by `sonar_base` anyway, and a password may hold any character, so it is
    never parsed: it is not carried at all (the screens then offer to connect with no host)."""
    h = creds.sonar_host(host)
    return "" if "@" in h else h


def _token(host: str) -> str | None:
    """The token under the host as the keychain keys it, which is the exact string that was saved: with or without
    the scheme."""
    h = creds.sonar_host(host)
    bare = h.split("://", 1)[-1]
    for key in dict.fromkeys((h, bare, f"https://{bare}")):
        if token := creds.get(key):
            return token
    return None


def _number(value) -> int | float | None:
    """A measure's value as a number; anything else (absent, not a number, NaN) is None, never 0."""
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):       # OverflowError: an integer too large for a float
        return None
    return None if n != n or n in (float("inf"), float("-inf")) else int(n) if n.is_integer() else n


def _rating(value) -> str | None:
    return RATINGS.get(str(value).split(".")[0]) if value is not None else None


def _list(value) -> list:
    """`value` when it is a list, [] when absent; any other shape is not a Sonar answer."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise SonarError("respuesta no válida")
    return value


def _dict(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SonarError("respuesta no válida")
    return value


def _server(measures: dict, gate: dict, at: str, host: str) -> dict:
    """The figures of a repo from the two answers. A shape that is not Sonar's is `SonarError("respuesta no válida")`."""
    by = {}
    for m in _list(_dict(measures.get("component")).get("measures")):
        if not isinstance(m, dict) or not isinstance(m.get("metric"), str):
            raise SonarError("respuesta no válida")
        by[m["metric"]] = m.get("value")
    status = _dict(gate.get("projectStatus")).get("status")
    return {"at": at, "host": host, "gate": status if status in GATES else None, "coverage": _number(by.get("coverage")),
            "bugs": _number(by.get("bugs")), "vulnerabilities": _number(by.get("vulnerabilities")),
            "security_hotspots": _number(by.get("security_hotspots")), "code_smells": _number(by.get("code_smells")),
            "debt_minutes": _number(by.get("sqale_index")),
            "ratings": {"maintainability": _rating(by.get("sqale_rating")),
                        "reliability": _rating(by.get("reliability_rating")), "security": _rating(by.get("security_rating"))}}


class Session:
    """What one build() learns about the servers: the hosts that did not answer (their other repos are not asked, so a
    dead server costs one timeout, not one per repo) and the single line it says before the first read."""

    def __init__(self, log=None):
        self.down: set[str] = set()
        self.log, self.said = log, False

    def start(self) -> None:
        if self.log and not self.said:
            self.said = True
            self.log("reading SonarQube…")


def read(repo_sonar: dict, previous: dict | None, ws: dict, session: Session | None = None) -> dict:
    """The `sonar` block of a repo with what its SonarQube says. `previous` is the repo's block in the last snapshot.
    No project key or no host: the block as it is. Otherwise its `host` is the server the kit uses (the repo's own, SonarCloud's or the
    team's). No token: `connect` (the app offers to save one). A failed read keeps
    the previous `server`, with its own `at`, and says why in `error`; only when it came from the same project and host,
    so a renamed key or a moved server never shows the old figures."""
    key, host = repo_sonar.get("project"), _host(repo_sonar, ws)
    if not (repo_sonar.get("used") and key and host):
        return repo_sonar
    repo_sonar = {**repo_sonar, "host": _shown(host)}      # the server the kit uses, also when the repo names none itself
    token = _token(host)
    if not token:
        return {**repo_sonar, "connect": True}
    where = creds.sonar_host(host)
    old = previous.get("sonar") if isinstance(previous, dict) else None
    last = old.get("server") if isinstance(old, dict) else None
    keep = {"server": last} if isinstance(last, dict) and old.get("project") == key and last.get("host") == where else {}
    session = session or Session()
    try:
        if where in session.down:
            raise SonarError("sin conexión")
        session.start()
        measures = sonar_get(host, token, "/api/measures/component", {"component": key, "metricKeys": METRICS})
        gate = sonar_get(host, token, "/api/qualitygates/project_status", {"projectKey": key})
        server = _server(measures, gate, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), where)
    except (SonarError, ValueError) as e:                     # ValueError: sonar_base refused the host
        if str(e) == "sin conexión":
            session.down.add(where)
        return {**repo_sonar, **keep, "error": str(e)}
    return {**repo_sonar, "server": server}
