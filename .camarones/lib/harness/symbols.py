"""Where a named symbol sits in a source file (freshness L2, the CodeIndexer `symbols` port): `place`, `OrderService`
or `OrderService.place`. Deterministic and offline: indentation for Python, braces for the C-family languages, block
braces for LikeC4 elements. Good enough to follow code that moved; when a symbol is not found the page is stale."""
from __future__ import annotations

import re

PY = (".py",)
BRACES = (".java", ".kt", ".kts", ".scala", ".groovy", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".cs",
          ".rs", ".php", ".dart", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".c4")
DECL = r"(?:class|interface|enum|record|object|struct|trait|fun|func|function|def|type|module|namespace)"


def _py_block(lines: list[str], name: str, start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    end = len(lines) if end is None else end
    pat = re.compile(rf"^(\s*)(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b")
    for i in range(start, end):
        m = pat.match(lines[i])
        if not m:
            continue
        indent, j = len(m.group(1)), i + 1
        while j < end and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
            j += 1
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1
        return i, j - 1
    return None


def _strip(line: str) -> str:
    """The line without string literals and comments, so braces inside them do not count."""
    line = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', '""', line)
    return re.sub(r"//.*$|/\*.*?\*/", "", line)


def _brace_end(lines: list[str], i: int, end: int) -> int:
    depth, opened, block_comment = 0, False, False
    for j in range(i, end):
        text = lines[j]
        if block_comment:
            if "*/" not in text:
                continue
            text, block_comment = text.split("*/", 1)[1], False
        if "/*" in text and "*/" not in text.split("/*", 1)[1]:
            text, block_comment = text.split("/*", 1)[0], True
        for ch in _strip(text):
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return j
        if not opened and j > i and ";" in _strip(lines[j]):
            return j
    return i


def _brace_block(lines: list[str], name: str, start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    end = len(lines) if end is None else end
    n = re.escape(name)
    pats = [re.compile(rf"\b{DECL}\s+{n}\b"),
            re.compile(rf"\b(?:const|let|var|val)\s+{n}\s*[:=]"),
            re.compile(rf"(?:^|\s)\b{n}\s*=\s*\w+"),                                       # LikeC4: `orders = service`
            re.compile(rf"(?<![\w.]){n}\s*(?:<[^>]*>)?\s*\(")]                               # method or function
    for pat in pats:
        for i in range(start, end):
            code = _strip(lines[i])
            if not pat.search(code) or re.match(r"\s*(return|new|throw|await|yield|if|for|while|switch)\b", code):
                continue
            tail = "".join(_strip(l) for l in lines[i:min(i + 4, end)])
            brace, semi = tail.find("{"), tail.find(";")
            if pat is pats[3] and (brace < 0 or (0 <= semi < brace)):
                continue                                                                     # a call, not a declaration
            return i, _brace_end(lines, i, end)
    return None


def locate(lines: list[str], symbol: str, suffix: str) -> tuple[int, int] | None:
    """0-based inclusive line range of `symbol` (dotted names nest: Class.method), or None."""
    finder = _py_block if suffix.lower() in PY else _brace_block if suffix.lower() in BRACES else None
    if not finder:
        return None
    start, end = 0, len(lines)
    found = None
    for part in symbol.split("."):
        found = finder(lines, part, start, end)
        if not found:
            return None
        start, end = found[0] + 1, found[1] + 1
    return found
