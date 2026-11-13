"""The decisions API of the desktop app (`/api/app/adr…`, app token only): a thin layer over `lib/adr.py`. It checks the
shape of each body (text is text, lists are lists of text, with lib/interfaces/http/inputs.py), passes the work to `adr`
and maps its errors to the status the app acts on: bad input 400, an unknown ADR 404, a save made from a file that has
changed since 409 (with the sha the file has now, so the app reloads) and so is a write that waited too long for the ADR
lock. The decisions a doc page lists (`covering`) live in lib/app/portal_views.py."""
from __future__ import annotations

import re
from collections.abc import Callable

from lib import adr
from lib.core.locks import LockBusy
from lib.interfaces.http import inputs
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


BUSY = "another change to this ADR is being saved: try again"
_ONE = re.compile(r"adr/([^/]+)(/pack)?")


def _id(b: dict) -> str:
    return inputs.text(b, "id", True)


def _answer(run: Callable[[], dict | None]) -> tuple[dict | None, int]:
    try:
        return run(), 200
    except adr.AdrConflict as e:                            # before AdrError, which it is
        return {"error": str(e), "sha": e.sha}, 409
    except LockBusy:
        return {"error": BUSY}, 409
    except KeyError as e:
        return {"error": f"no ADR {e.args[0] if e.args else ''}"}, 404
    except ValueError as e:                                 # AdrError is one
        return {"error": str(e)}, 400


# ---------- reading ----------
def get(name: str, q: dict) -> tuple[dict, int]:
    """GET /api/app/<name> for `adr`, `adr/candidates`, `adr/<NNNN>` and `adr/<NNNN>/pack`."""
    if name == "adr":
        return _answer(lambda: {"adrs": adr.list_adrs(), "next": adr.next_id()})
    if name == "adr/candidates":
        from lib import adr_pack
        return _answer(lambda: {"candidates": adr_pack.candidates()})
    found = _ONE.fullmatch(name)
    if not found:
        return {"error": "not found"}, 404
    id, pack = found.group(1), found.group(2)
    if not pack:
        return _answer(lambda: adr.get(id))
    body, code = _answer(lambda: adr.read_pack(id))
    if code == 200 and body is None:
        return {"error": f"no evidence pack for ADR {id}: gather it first"}, 404
    return body, code


# ---------- acting ----------
def _new(b: dict, by: str) -> dict:
    return adr.new({**{key: inputs.text(b, key) for key in ("title", "kind", "problem", "supersedes")},
                    **{key: inputs.text_list(b, key) for key in ("drivers", "constraints", "options_hint", "touches")}})


def _options(b: dict) -> list[dict] | None:
    given = b.get("options")
    if given is None:
        return None
    if not isinstance(given, list) or not all(isinstance(o, dict) for o in given):
        raise ValueError("options must be a list of objects")
    return [{"name": inputs.text(o, "name"), "pros": inputs.text_list(o, "pros"), "cons": inputs.text_list(o, "cons")} for o in given]


def _part(b: dict, by: str) -> dict:
    return adr.part(_id(b), inputs.text(b, "part", True), inputs.text(b, "action", True), inputs.text(b, "text"),
                    inputs.text(b, "base_sha", True))


def _point(b: dict, by: str) -> dict:
    data = {key: inputs.text(b, key) for key in ("question", "point", "chosen", "other", "rationale")}
    data["options"] = _options(b)
    return adr.point(_id(b), inputs.text(b, "op", True), {k: v for k, v in data.items() if v is not None},
                     inputs.text(b, "base_sha", True))


def _attendees(b: dict, by: str) -> dict:
    if b.get("attendees") is None:                          # clearing them is an empty list, said explicitly
        raise ValueError("attendees must be a list of text")
    return adr.set_attendees(_id(b), inputs.text_list(b, "attendees"))


def _accept(b: dict, by: str) -> dict:
    attendees = None if b.get("attendees") is None else inputs.text_list(b, "attendees")     # none: the review's stay
    return adr.accept(_id(b), by, attendees, inputs.text(b, "base_sha", True))


def _reject(b: dict, by: str) -> dict:
    return adr.reject(_id(b), inputs.text(b, "why"), by, inputs.text(b, "base_sha", True))


POST: dict[str, Callable[[dict, str], dict]] = {
    "new": _new,
    "pack": lambda b, by: adr.pack(_id(b)),
    "write": lambda b, by: adr.write_without_ai(_id(b)),
    "review": lambda b, by: adr.start_review(_id(b)),
    "part": _part,
    "point": _point,
    "attendees": _attendees,
    "accept": _accept,
    "reject": _reject,
}


def post(action: str, b: dict, by: str) -> tuple[dict, int]:
    """POST /api/app/adr/<action>; `by` is who is acting (the body's `by`, else the git user)."""
    run = POST.get(action)
    if run is None:
        return {"error": "not found"}, 404
    if not isinstance(b, dict):
        return {"error": "the request must be an object"}, 400
    return _answer(lambda: run(b, by))


@route("GET", "/api/app/adr{rest:(?:/.*)?}", access=Access.APP)
def get_adr(req: Request) -> Response:
    return json_response(*get("adr" + req.params["rest"], req.query))


@route("POST", "/api/app/adr/{action:[a-z]+}", access=Access.APP)
def post_adr(req: Request) -> Response:
    return json_response(*post(req.params["action"], req.body, req.by))
