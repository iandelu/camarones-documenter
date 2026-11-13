"""The Plan canvas's terminals and agent sessions (`/api/app/`, app token only): open a session, type into a terminal,
resize or close it, take a unit from the autopilot and give it back, and one event stream with every terminal. This
module is the HTTP layer's only user of lib/terminals.py: `unit_terminals` and `shutdown` serve the runs area and the
server."""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.parse
from typing import BinaryIO

from lib.interfaces.http import inputs
from lib.interfaces.http.messages import Request, Response, event_stream, json_response
from lib.interfaces.http.router import Access, route
from lib.interfaces.http.routes.machine import sessions_setting


STREAM_FROM = re.compile(r"(t-[\w.-]+-\d+):(\d+)")     # one piece of the terminal stream's `from`
CHUNK = 64 * 1024                            # bytes of a terminal per stream message, at most
KEEP_ALIVE = 15.0                            # seconds a stream may stay silent: a write is how it finds the client gone


def app_session(b: dict) -> tuple[dict, int]:
    """POST /api/app/terminals (and its old name, /api/app/agent): a unit's session or the docs update, on the canvas or
    in a window as this machine's `sessions` setting says. Every field is checked first: launch_* moves the unit before
    the terminal refuses a bad size. Already open, or no room on the canvas, is a 409 that says which or how many."""
    from lib import agents, terminals
    unit, agent = inputs.text(b, "unit", True), inputs.text(b, "agent", True)
    lang, mode = inputs.text(b, "lang") or "es", inputs.text(b, "mode") or "new"
    if mode not in ("new", "continue", "restart"):
        raise ValueError("mode: new, continue or restart")
    size = (inputs.dim(b, "cols", terminals.COLS, 80), inputs.dim(b, "rows", terminals.ROWS, 24))
    where = sessions_setting()
    try:
        if unit == "update":
            return agents.launch_update(agent, lang, where=where, size=size), 200
        return agents.launch_unit(unit, agent, lang, mode, where=where, size=size), 200
    except agents.AlreadyOpen as e:
        return {"error": str(e), "terminal": e.terminal}, 409
    except agents.AtWork as e:
        return {"error": str(e), "code": "at-work"}, 409
    except terminals.Limit:
        return {"error": f"{terminals.MAX_LIVE} terminals are open: close one first", "limit": terminals.MAX_LIVE}, 409


def app_terminal(tid: str, action: str, b: dict) -> tuple[dict, int]:
    """POST /api/app/terminals/<id>/<action>: keys typed (`input`), a new size (`resize`) or `close`. A bad body is a
    400 before the terminal is touched, an unknown terminal a 404, input to one that ended or does not take it a 409."""
    from lib import terminals
    try:
        if action == "input":
            data = inputs.text(b, "data", True)
            if len(data.encode("utf-8")) > terminals.INPUT_MAX:
                raise ValueError(f"data: at most {terminals.INPUT_MAX} bytes a request")
            terminals.write(tid, data)
            return {"ok": True}, 200
        if action == "resize":
            return terminals.resize(tid, inputs.dim(b, "cols", terminals.COLS), inputs.dim(b, "rows", terminals.ROWS)), 200
        return terminals.close(tid), 200
    except KeyError:
        return {"error": f"no terminal {tid}"}, 404
    except terminals.Ended:
        return {"error": f"{tid} has ended"}, 409
    except TimeoutError as e:
        return {"error": str(e)}, 409


def app_unit(uid: str, action: str, b: dict) -> tuple[dict, int]:
    """POST /api/app/units/<uid>/<action>: take a unit from the autopilot, hand it back or stop it (lib/takeover.py). A
    bad size is a 400 before anything moves, an unknown unit a 404. What the run's state refuses is a 409: `code` for the
    app, or the terminal it already has, or the limit it reached."""
    from lib import agents, takeover, terminals
    try:
        if action == "takeover":
            size = (inputs.dim(b, "cols", terminals.COLS, 80), inputs.dim(b, "rows", terminals.ROWS, 24))
            return takeover.take(uid, inputs.text(b, "lang") or "es", size), 200
        return (takeover.hand_back if action == "handback" else takeover.stop)(uid), 200
    except KeyError:
        return {"error": f"no unit {uid}"}, 404
    except agents.AlreadyOpen as e:
        return {"error": str(e), "terminal": e.terminal}, 409
    except terminals.Limit:
        return {"error": f"{terminals.MAX_LIVE} terminals are open: close one first", "limit": terminals.MAX_LIVE}, 409
    except takeover.Refused as e:
        return {"error": str(e), "code": e.code}, 409


def unit_terminals() -> dict[str, str]:
    """Each unit with a live terminal on this server: unit id → terminal id (the Pipeline view's `terminal`)."""
    from lib import terminals
    return {m["unit"]: m["id"] for m in terminals.listing() if m["kind"] == "unit" and m["ended"] is None}


def shutdown() -> None:
    """Ends every terminal of this server: no agent outlives its server."""
    from lib import terminals
    terminals.shutdown()


def follow_terminals(out: BinaryIO, offsets: dict[str, int]) -> None:
    """The stream's loop: replays each terminal from its offset, then follows them all until the client goes."""
    from lib import terminals
    told, gen, beat = set(), -1, time.monotonic()           # told: the ended terminals whose end went out
    try:
        while True:
            gen = terminals.wait(gen, max(0.0, beat + KEEP_ALIVE - time.monotonic()))
            wrote = False
            for meta in terminals.listing():
                t = meta["id"]
                if t in told or (meta["closed"] and meta["ended"] is None):
                    continue
                try:
                    data, end = terminals.read(t, offsets.get(t, 0))
                except KeyError:                            # forgotten since the listing
                    continue
                if meta["closed"]:                          # closed by the person: never shown again
                    data = b""
                o = end - len(data)
                for i in range(0, len(data), CHUNK):
                    o += len(chunk := data[i:i + CHUNK])
                    msg = json.dumps({"t": t, "d": base64.b64encode(chunk).decode("ascii"), "o": o})
                    out.write(f"id: {t}:{o}\ndata: {msg}\n\n".encode("utf-8"))
                offsets[t], wrote = end, wrote or bool(data)
                if meta["ended"] is not None:               # listed before the read: its last bytes went first
                    msg = json.dumps({"t": t, "end": meta["code"], "o": end})
                    out.write(f"data: {msg}\n\n".encode("utf-8"))
                    told.add(t)
                    wrote = True
            if not wrote and time.monotonic() - beat < KEEP_ALIVE:
                continue
            if not wrote:
                out.write(b": keep-alive\n\n")
            out.flush()
            beat = time.monotonic()
    except OSError:                 # the client went: a broken pipe, a reset, Windows' abort, macOS' EPROTOTYPE
        return


@route("GET", "/api/app/terminals/stream", access=Access.APP)
def get_stream(req: Request) -> Response:
    """Server-sent events of every terminal of this server on one connection (Chromium allows six per host). Each is
    replayed from its offset in `from` (`<id>:<offset>,…`, 0 when not named), then followed: `{t, d, o}` per CHUNK at
    most, `d` the raw bytes in base64 (a read can split a UTF-8 character), `o` the offset after them and the id
    `<t>:<o>`; after an ended one's last bytes, `{t, end, o}` once. One the person closed sends that end alone, once it
    ended. Terminals opened later join. It ends when the client goes, which only a write finds out: a keep-alive after
    KEEP_ALIVE s of nothing else."""
    offsets = {}
    q = req.query
    for piece in q["from"].split(",") if q.get("from") else []:
        if not (m := STREAM_FROM.fullmatch(piece)):
            return json_response({"error": "from: <terminal>:<offset>, separated by commas"}, 400)
        offsets[m[1]] = int(m[2])
    return event_stream(lambda out: follow_terminals(out, offsets))


@route("GET", "/api/app/terminals", access=Access.APP)
def get_terminals(req: Request) -> Response:
    from lib import terminals
    return json_response({"terminals": terminals.listing(), "available": terminals.available(),
                          "limit": terminals.MAX_LIVE})


@route("GET", "/api/app/agents", access=Access.APP)
def get_agents(req: Request) -> Response:
    from lib import agents
    from lib.core.fsutil import load_json
    from lib.core.paths import PREFS
    return json_response({"agents": agents.installed(), "last": load_json(PREFS, {}).get("last_agent")})


@route("POST", "/api/app/terminals", access=Access.APP)
@route("POST", "/api/app/agent", access=Access.APP)          # /agent: its old name
def post_session(req: Request) -> Response:
    return json_response(*app_session(req.body))


@route("POST", "/api/app/terminals/{tid:t-[\\w.-]+-\\d+}/{action:input|resize|close}", access=Access.APP, by=False)
def post_terminal(req: Request) -> Response:                # keys as they are typed: never wait on `by`, which runs git
    return json_response(*app_terminal(req.params["tid"], req.params["action"], req.body))


@route("POST", "/api/app/units/{uid}/{action:takeover|handback|stop}", access=Access.APP, by=False)
def post_unit(req: Request) -> Response:
    return json_response(*app_unit(urllib.parse.unquote(req.params["uid"]), req.params["action"], req.body))
