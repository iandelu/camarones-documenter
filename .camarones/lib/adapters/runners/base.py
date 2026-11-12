"""Shared behaviour of agent CLIs that stream JSON lines."""
from __future__ import annotations

import json

from ...common import which
from ...harness.ports import Outcome

# best guess at the CLIs' wording, matched only against the end of the output (where the CLI prints its
# error) so a unit documenting a rate-limited API isn't misread; anything else stops the loop instead
LIMIT_HINTS = ("usage limit", "rate limit", "rate_limit", "limit reached", "try again later",
               "too many requests", "resets at", "limit will reset", "quota exceeded", "-hour limit", "weekly limit")
# the server (or a proxy before it) turns requests away for a moment, which Claude Code says is not the usage limit:
# a short wait, not the quota's pause; more likely the more sessions run at once
THROTTLE_HINTS = ("not your usage limit", "temporarily limiting requests")
# the session broke for a reason that may not happen again (sleep, network, an overloaded API): worth one more try
TRANSIENT_HINTS = ("went to sleep", "socket hang up", "econnreset", "connection reset", "connection error",
                   "network error", "overloaded", "fetch failed", "503 service", "502 bad gateway")


def throttled(tail: str) -> bool:
    """A limited session that hit a rate limit passing in a minute or two, not the end of the quota."""
    end = tail[-2000:].lower()
    return any(h in end for h in THROTTLE_HINTS)


class CliRunner:
    id = ""
    label = ""
    command = ""                  # executable name looked up on PATH; defaults to the id
    own_session = False           # takes a conversation id from the kit (others say theirs in a `session` event, or have none)
    reopens_last = False          # can be sent back to its own last conversation, with no id

    def exe(self) -> str | None:
        return which(self.command or self.id)

    def available(self) -> bool:
        return bool(self.exe())

    def parse(self, line: str) -> list[dict]:
        try:
            ev = json.loads(line)
        except ValueError:
            ev = None
        if not isinstance(ev, dict):
            return [{"type": "log", "text": line, "raw": True}]
        return self.parse_event(ev)

    def parse_event(self, ev: dict) -> list[dict]:
        raise NotImplementedError

    def classify(self, rc: int, tail: str) -> Outcome:
        if rc == 0:
            return "ok"
        end = tail[-2000:].lower()
        if any(h in end for h in LIMIT_HINTS + THROTTLE_HINTS):
            return "limited"
        return "retry" if any(h in end for h in TRANSIENT_HINTS) else "failed"

    def throttled(self, tail: str) -> bool:
        return throttled(tail)
