"""Git hosting credentials (GitLab / GitHub tokens) — kept out of the project and out of AI sessions.

* The token is stored in the OS secret store: macOS Keychain, Windows Credential Manager, Linux Secret Service
  (fallback: ~/.camarones/credentials.json with 0600 permissions). Never in the project, never in git config.
* It is injected only into the environment of the git / API calls Camarones itself makes (GIT_CONFIG_* variables),
  so it is not written to .git/config and is NOT present in the environment of Claude Code / Codex sessions.
"""
from __future__ import annotations

import base64, json, os, re, urllib.parse, urllib.request
from pathlib import Path

from .common import HOME, load_json, save_json

SERVICE = "camarones-documenter"
META = HOME / ".camarones" / "hosts.json"            # non-secret: host → kind/user
FALLBACK = HOME / ".camarones" / "credentials.json"  # only when no OS keyring is available


# ---------- storage ----------
def _keyring():
    try:
        import keyring
        from keyring.backends import fail
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
        return keyring
    except Exception:  # noqa: BLE001
        return None


def backend_name() -> str:
    kr = _keyring()
    return type(kr.get_keyring()).__name__ if kr else f"file {FALLBACK} (0600)"


def hosts() -> dict:
    return load_json(META, {})


def get(host: str) -> str | None:
    kr = _keyring()
    if kr:
        try:
            v = kr.get_password(SERVICE, host)
            if v:
                return v
        except Exception:  # noqa: BLE001
            pass
    return load_json(FALLBACK, {}).get(host)


def save(host: str, kind: str, token: str, user: str = "") -> str:
    kr = _keyring()
    where = "keyring"
    try:
        if not kr:
            raise RuntimeError
        kr.set_password(SERVICE, host, token)
    except Exception:  # noqa: BLE001
        data = load_json(FALLBACK, {})
        data[host] = token
        FALLBACK.parent.mkdir(parents=True, exist_ok=True)
        FALLBACK.write_text(json.dumps(data), encoding="utf-8")
        try:
            os.chmod(FALLBACK, 0o600)
        except OSError:
            pass
        where = "file"
    meta = hosts()
    meta[host] = {"kind": kind, "user": user}
    save_json(META, meta)
    return where


def delete(host: str) -> None:
    kr = _keyring()
    if kr:
        try:
            kr.delete_password(SERVICE, host)
        except Exception:  # noqa: BLE001
            pass
    data = load_json(FALLBACK, {})
    if host in data:
        del data[host]
        FALLBACK.write_text(json.dumps(data), encoding="utf-8")
    meta = hosts()
    meta.pop(host, None)
    save_json(META, meta)


# ---------- helpers ----------
def host_of(url: str) -> str | None:
    if not url:
        return None
    m = re.match(r"^[\w.+-]+@([^:/]+)[:/]", url)          # git@host:group/repo.git
    if m:
        return m.group(1)
    p = urllib.parse.urlparse(url)
    return p.hostname


def guess_kind(host: str) -> str:
    return "github" if "github" in host else "gitlab"


def api_base(host: str, kind: str) -> str:
    if kind == "github":
        return "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
    return f"https://{host}/api/v4"


def _headers(kind: str, token: str) -> dict:
    if kind == "github":
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "camarones"}
    return {"PRIVATE-TOKEN": token, "User-Agent": "camarones"}


def _get(url: str, kind: str, token: str):
    req = urllib.request.Request(url, headers=_headers(kind, token))
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def verify(host: str, kind: str, token: str) -> tuple[bool, str]:
    try:
        me = _get(f"{api_base(host, kind)}/user", kind, token)
        return True, me.get("username") or me.get("login") or "?"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def list_projects(host: str, kind: str, token: str, scope: str = "") -> list[dict]:
    """Projects visible with the token. scope = GitLab group path / GitHub org (empty = everything you are member of)."""
    base, out = api_base(host, kind), []
    for page in range(1, 11):
        if kind == "github":
            url = (f"{base}/orgs/{urllib.parse.quote(scope)}/repos?per_page=100&page={page}" if scope
                   else f"{base}/user/repos?per_page=100&sort=updated&page={page}")
            items = _get(url, kind, token)
            out += [{"name": i["name"], "path": i["full_name"], "url": i["clone_url"],
                     "branch": i.get("default_branch") or "main", "archived": i.get("archived", False)} for i in items]
        else:
            url = (f"{base}/groups/{urllib.parse.quote(scope, safe='')}/projects?include_subgroups=true&simple=true"
                   f"&per_page=100&page={page}" if scope else
                   f"{base}/projects?membership=true&simple=true&order_by=last_activity_at&per_page=100&page={page}")
            items = _get(url, kind, token)
            out += [{"name": i["path"], "path": i["path_with_namespace"], "url": i["http_url_to_repo"],
                     "branch": i.get("default_branch") or "main", "archived": i.get("archived", False)} for i in items]
        if len(items) < 100:
            break
    return [p for p in out if not p["archived"]]


def git_env(url: str) -> dict:
    """Env vars for ONE git subprocess: auth header + ssh→https rewrite for that host. Empty if no token saved."""
    host = host_of(url)
    if not host:
        return {"GIT_TERMINAL_PROMPT": "0"}
    token = get(host)
    if not token:
        return {"GIT_TERMINAL_PROMPT": "0"}
    kind = hosts().get(host, {}).get("kind") or guess_kind(host)
    user = "x-access-token" if kind == "github" else "oauth2"
    basic = base64.b64encode(f"{user}:{token}".encode()).decode()
    return {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": f"http.https://{host}/.extraheader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        "GIT_CONFIG_KEY_1": f"url.https://{host}/.insteadOf",
        "GIT_CONFIG_VALUE_1": f"git@{host}:",
    }
