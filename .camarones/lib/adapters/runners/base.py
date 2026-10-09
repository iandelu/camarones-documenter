"""Shared behaviour of agent CLIs that stream JSON lines."""
from __future__ import annotations

import json

from ...common import which
from ...harness.ports import Outcome

# best guess at the CLIs' wording, matched only against the end of the output (where the CLI prints its
# error) so a unit documenting a rate-limited API isn't misread; anything else stops the loop instead
LIMIT_HINTS = ("usage limit", "rate limit", "rate_limit", "limit reached", "try again later",
               "too many requests", "resets at", "limit will reset", "quota exceeded")


class CliRunner:
    id = ""

    def exe(self) -> str | None:
        return which(self.id)

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
        return "limited" if any(h in tail[-2000:].lower() for h in LIMIT_HINTS) else "failed"
