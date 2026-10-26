"""SonarQube over HTTP, read only. The token travels in the Authorization header (lib/creds.py builds it) and nowhere
else: not in the URL, not in an error, not in a log. Failures come out as a SonarError whose text is the plain reason,
in Spanish, as the health snapshot shows it."""
from __future__ import annotations

import http.client, json, urllib.error, urllib.parse, urllib.request

from . import creds

TIMEOUT = 10        # seconds, for each read


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
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise SonarError(_reason(e.code)) from None
    except (OSError, http.client.HTTPException):             # timeout, DNS, refused, reset: URLError is an OSError
        raise SonarError("sin conexión") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:                                       # includes a 200 SSO login page in HTML
        raise SonarError("respuesta no válida") from None
    if not isinstance(data, dict):
        raise SonarError("respuesta no válida")
    return data


def _reason(status: int) -> str:
    return {401: "token no válido", 403: "token no válido", 404: "proyecto no encontrado"}.get(status, f"error {status}")
