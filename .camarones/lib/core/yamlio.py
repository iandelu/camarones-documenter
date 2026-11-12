"""Reading YAML: through libyaml when PyYAML was built with it (its wheels for macOS, Windows and Linux are), about ten
times faster than the pure-Python parser and the same documents, errors included. Writing stays with yaml.safe_dump:
libyaml's emitter escapes emoji even with allow_unicode, so the files the kit writes would change."""
from __future__ import annotations

import yaml

Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(stream):
    return yaml.load(stream, Loader=Loader)


def safe_load_all(stream):
    return yaml.load_all(stream, Loader=Loader)
