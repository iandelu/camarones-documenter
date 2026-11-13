"""What a route handler receives and returns. The server builds the Request (tokens, host, body) once; a handler only
reads it and answers with a Response, which the server writes."""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, BinaryIO


@dataclass(frozen=True)
class Request:
    method: str                                   # "GET" (HEAD too) or "POST" (PUT too)
    path: str                                     # GET: percent-decoded; POST: as sent (a handler unquotes a param)
    query: dict[str, str] = field(default_factory=dict)     # the first value of each key (GET)
    headers: Mapping[str, str] = field(default_factory=dict)
    raw: bytes = b""                              # the POST body as read
    body: Any = None                              # the POST body parsed as JSON; {} for a GET
    params: dict[str, str] = field(default_factory=dict)
    by: str = ""                                  # who acts: the body's `by`, else the git user (routes with by=True)
    is_app: bool = False                          # carries the desktop app's token
    can_write: bool = False                       # the app's token or the portal's
    foreign: bool = False                         # Host is not this server (checked only once a token is set)
    marked: bool = False                          # X-Camarones: 1
    static: bool = False                          # `up --static`: the exported site


@dataclass(frozen=True)
class Response:
    status: int = 200
    body: bytes = b""
    ctype: str | None = "text/plain"              # None: neither Content-Type nor Content-Length (a stopped run's 204)
    headers: Mapping[str, str] = field(default_factory=dict)
    stream: Callable[[BinaryIO], None] | None = None        # server-sent events, written after the headers


def json_response(data, status: int = 200) -> Response:
    return Response(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")


def not_found() -> Response:
    return Response(404, b"not found", "text/plain")


def redirect(status: int, location: str) -> Response:
    return Response(status, b"", "text/plain", {"Location": location})


def event_stream(write: Callable[[BinaryIO], None]) -> Response:
    return Response(stream=write)
