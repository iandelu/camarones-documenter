"""The project server's routes: each one declared beside its handler with who may call it (`@route`) and found by
scanning `routes/` (docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md §4.2).

A pattern is a path with parameters: `{name}` is one segment, `{name:regex}` whatever the regex takes. The most
specific route wins (longest literal start, then one without parameters), and a path under /api/ only ever matches an
/api/ route, so an unknown API path stays a JSON 404 instead of the portal's page."""
from __future__ import annotations

import functools
import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from .messages import Request, Response

PACKAGE = "lib.interfaces.http.routes"
METHODS = ("GET", "POST")                     # HEAD is served as GET, PUT as POST
API, APP_API = "/api/", "/api/app/"
APP_ONLY_MSG = "this runs on your machine: open it in the desktop app (`camaron app`)"
_PARAM = re.compile(r"\{(\w+)(?::([^{}]*))?\}")

Handler = Callable[[Request], Response]


class Access:
    PUBLIC = "public"       # the portal reading (and what any page on this machine may ask)
    PORTAL = "portal"       # a writing token: the portal's from `camaron up`, or the app's
    APP = "app"             # the desktop app's token: what runs on the machine
    ALL = (PUBLIC, PORTAL, APP)


def _compile(method: str, pattern: str) -> tuple[re.Pattern, str, bool]:
    """The pattern's regex, its literal start (the text before the first parameter) and whether it has parameters."""
    if "{" in _PARAM.sub("", pattern) or "}" in _PARAM.sub("", pattern):
        raise ValueError(f"route {method} {pattern}: unbalanced or nested braces")
    parts, pos, first = [], 0, None
    for m in _PARAM.finditer(pattern):
        parts += [re.escape(pattern[pos:m.start()]), f"(?P<{m[1]}>{'[^/]+' if m[2] is None else m[2]})"]
        pos, first = m.end(), m.start() if first is None else first
    parts.append(re.escape(pattern[pos:]))
    try:
        rx = re.compile("".join(parts))
    except re.error as e:
        raise ValueError(f"route {method} {pattern}: {e}") from None
    return rx, pattern if first is None else pattern[:first], first is not None


@dataclass(frozen=True)
class Route:
    method: str
    pattern: str
    access: str
    handler: Handler
    refusal: str = ""           # a PORTAL route's 403 message
    by: bool = True             # POST: resolve who acts before the handler (today's order); False for typed keys
    static: bool = False        # GET: served in static mode too
    regex: re.Pattern = field(init=False, repr=False, compare=False)
    prefix: str = field(init=False, repr=False, compare=False)
    has_params: bool = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        rx, prefix, has_params = _compile(self.method, self.pattern)
        object.__setattr__(self, "regex", rx)
        object.__setattr__(self, "prefix", prefix)
        object.__setattr__(self, "has_params", has_params)


@dataclass(frozen=True)
class Match:
    route: Route
    params: dict[str, str]


def route(method: str, pattern: str, *, access: str = Access.PUBLIC, refusal: str = "", by: bool = True,
          static: bool = False) -> Callable[[Handler], Handler]:
    def bad(why: str) -> ValueError:
        return ValueError(f"route {method} {pattern}: {why}")
    if method not in METHODS:
        raise bad(f"method is one of {', '.join(METHODS)}")
    if access not in Access.ALL:
        raise bad(f"access is one of {', '.join(Access.ALL)}")
    if not pattern.startswith("/"):
        raise bad("a pattern starts with /")
    if pattern.startswith(APP_API) and access != Access.APP:
        raise bad(f"everything under {APP_API} needs the app token (access=Access.APP)")
    if (access == Access.PORTAL) != bool(refusal):
        raise bad("a portal route says why it refuses (refusal), and only a portal route does")
    if method == "GET" and not by:
        raise bad("by=False is for POST routes")
    if method == "POST" and static:
        raise bad("static=True is for GET routes")
    _compile(method, pattern)

    def mark(fn: Handler) -> Handler:
        fn.__dict__.setdefault("__routes__", []).append(Route(method, pattern, access, fn, refusal, by, static))
        return fn
    return mark


class Router:
    def __init__(self, routes: Iterable[Route]) -> None:
        self.routes: tuple[Route, ...] = tuple(routes)
        seen: set[tuple[str, str]] = set()
        for r in self.routes:
            if (r.method, r.pattern) in seen:
                raise ValueError(f"route {r.method} {r.pattern} is declared twice")
            seen.add((r.method, r.pattern))
        order = sorted(range(len(self.routes)),
                       key=lambda i: (-len(self.routes[i].prefix), self.routes[i].has_params, i))
        self._ordered = [self.routes[i] for i in order]

    def _matches(self, method: str, path: str) -> Iterator[Match]:
        api = path.startswith(API)
        for r in self._ordered:
            if r.method != method or (api and not r.pattern.startswith(API)):
                continue
            if m := r.regex.fullmatch(path):
                yield Match(r, m.groupdict())

    def candidates(self, method: str, path: str) -> list[Match]:
        return list(self._matches(method, path))

    def match(self, method: str, path: str) -> Match | None:
        return next(self._matches(method, path), None)

    def table(self) -> list[dict]:
        return sorted(({"method": r.method, "pattern": r.pattern, "access": r.access} for r in self.routes),
                      key=lambda d: (d["pattern"], d["method"]))


@functools.cache
def load() -> Router:
    """Every route of every module in `routes/`, modules by name and routes in source order."""
    found: list[Route] = []
    package = importlib.import_module(PACKAGE)
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda i: i.name):
        module = importlib.import_module(f"{PACKAGE}.{info.name}")
        for obj in vars(module).values():
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                found += getattr(obj, "__routes__", [])
    return Router(found)
