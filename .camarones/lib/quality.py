"""Quality gate beyond frontmatter/trust: internal links, Mermaid diagrams (mermaid-cli), secrets (gitleaks) and
glossary terms. Checks take docs.collect() rows and return (errors, warns); a missing optional tool is one WARN."""
from __future__ import annotations

import hashlib, os, re, sys, tempfile
from pathlib import Path
from urllib.parse import unquote

from .common import ROOT, DOCS, CACHE, IS_WIN, run, which, load_json, save_json, rel_file
from . import binaries, docs

Issues = tuple[list[str], list[str]]
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
MERMAID_RE = re.compile(r"^\s*(```|~~~)\s*mermaid\b", re.M)
MERMAID_CACHE = CACHE / "mermaid-validated.json"
BROWSER_DOWN = re.compile(r"Failed to launch the browser|Could not find (Chrome|Chromium|expected browser)|"
                          r"error while loading shared libraries|browser process", re.I)


def pages(rows: list[dict]) -> list[tuple[str, Path, str]]:
    """(logical path, file, lang) for every published page: canonical docs + wikis, and each translation, which the
    portal shows under the canonical logical path (so its relative links resolve against that path too)."""
    out = [(r["path"], ROOT / r["file"], "") for r in rows]
    for lang in docs.workspace()["project"].get("translations", []):
        out += [(r["path"], f, lang) for r in rows if (f := DOCS / "i18n" / lang / r["path"]).is_file()]
    return out


def prose_lines(text: str):
    """(line number, text) outside frontmatter and code, inline code blanked — what a reader sees as prose."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    fence = None
    for i in range(start, len(lines)):
        m = FENCE_RE.match(lines[i])
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            yield i + 1, INLINE_CODE_RE.sub(lambda c: " " * len(c.group(0)), lines[i])


def resolve(base: str, href: str) -> str:
    """Mirror of resolve() in portal/live/app.js: relative to the page's logical folder."""
    parts = base.split("/")[:-1]
    for p in href.split("/"):
        if p == "..":
            if parts:
                parts.pop()
        elif p and p != ".":
            parts.append(p)
    return "/".join(parts)


# ---------- H1: internal links ----------
def check_links(rows: list[dict], strict: bool = False) -> Issues:
    known = {r["path"] for r in rows}
    errors = []
    for logical, f, _ in pages(rows):
        for n, line in prose_lines(f.read_text(encoding="utf-8", errors="replace")):
            for href in LINK_RE.findall(line) + REF_DEF_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", href, re.I):     # external, anchor-only, absolute: skipped
                    continue
                target = unquote(href.split("#", 1)[0].split("?", 1)[0])
                if target.endswith(".md") and resolve(logical, target) not in known:
                    errors.append(f"{rel_file(f)}:{n}: broken link → {href}")
    return errors, []


# ---------- G1: Mermaid diagrams ----------
def _puppeteer_config(tmp: Path) -> list[str]:
    """Chromium refuses to start as root without --no-sandbox (CI containers)."""
    if IS_WIN or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return []
    cfg = tmp / "puppeteer.json"
    cfg.write_text('{"args": ["--no-sandbox"]}', encoding="utf-8")
    return ["-p", str(cfg)]


def _mmdc_error(r) -> str:
    lines = [l.strip() for l in ((r.stderr or "") + "\n" + (r.stdout or "")).splitlines() if l.strip()]
    hit = next((i for i, l in enumerate(lines) if re.search(r"error", l, re.I)), None)
    return " ".join(lines[hit:hit + 2])[:300] if hit is not None else (lines[-1][:300] if lines else f"exit {r.returncode}")


def check_mermaid(rows: list[dict], strict: bool = False) -> Issues:
    todo = []
    for _, f, _ in pages(rows):
        text = f.read_text(encoding="utf-8", errors="replace")
        if MERMAID_RE.search(text):
            todo.append((f, hashlib.sha256(text.encode()).hexdigest()[:16]))
    if not todo:
        return [], []
    if not which("mmdc"):
        return [], [f"mermaid-cli (mmdc) not installed — {len(todo)} page(s) with diagrams not validated "
                    f"(install the 'quality' component: setup --profile full)"]
    cache, fresh, errors, warns = load_json(MERMAID_CACHE, {}), {}, [], []
    for f, sha in todo:
        key = rel_file(f)
        if cache.get(key) == sha:          # unchanged since it last validated: skip the Chromium start-up
            fresh[key] = sha
            continue
        with tempfile.TemporaryDirectory() as tmp:
            r = run(["mmdc", "-q", "-i", str(f), "-o", str(Path(tmp) / "out.md"), *_puppeteer_config(Path(tmp))],
                    check=False, capture=True)
        if r.returncode == 0:
            fresh[key] = sha
        elif BROWSER_DOWN.search((r.stderr or "") + (r.stdout or "")):   # the tool is broken, not the diagram
            warns.append(f"mermaid-cli could not start its browser — diagrams not validated ({_mmdc_error(r)})")
            break
        else:
            errors.append(f"{key}: invalid Mermaid diagram — {_mmdc_error(r)}")
    try:
        save_json(MERMAID_CACHE, fresh)
    except OSError:
        pass
    return errors, warns


# ---------- H5: secrets ----------
def _gitleaks(args: list[str], cwd: Path | None = None) -> list[dict] | None:
    exe = binaries.bin_path("gitleaks")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        run([str(exe), *args, "--no-banner", "--redact", "--log-level", "error", "--exit-code", "0",
             "--report-format", "json", "--report-path", str(report)], cwd=cwd, check=False, quiet=True)
        return load_json(report, [])


def scan_targets() -> list[Path]:
    """What gets committed and published: docs/ (incl. translations and working notes) and every repo wiki."""
    return [d for d in [DOCS, *(docs.wiki_dir(n) for n in docs.repo_names())] if d.is_dir()]


def scan_dirs() -> list[dict] | None:
    found: list[dict] | None = None
    for d in scan_targets():
        hits = _gitleaks(["dir", str(d)])
        if hits is None:
            return None
        found = (found or []) + hits
    return found or []


def describe(findings: list[dict], base: Path | None = None) -> list[str]:
    """file:line (rule) — never the secret itself (gitleaks already redacts it; it is not printed anyway)."""
    out = []
    for h in findings:
        p = Path(h.get("File", "?"))
        if base and not p.is_absolute():
            p = base / p
        out.append(f"{rel_file(p) if p.is_absolute() else p.as_posix()}:{h.get('StartLine', '?')}: "
                   f"possible secret ({h.get('RuleID', 'secret')})")
    return out


def check_secrets(rows: list[dict] | None = None, strict: bool = False) -> Issues:
    found = scan_dirs()
    if found is None:
        return [], ["gitleaks not installed — secret scan skipped (install the 'quality' component: setup --profile full)"]
    return [f"{d} — remove it or use a placeholder" for d in describe(found)], []


def staged_secrets() -> list[str]:
    """Findings in what is staged in cam-docs (checkpoint commits). [] when clean or gitleaks is not installed."""
    found = _gitleaks(["git", "--staged", "."], cwd=ROOT)
    if found is None:
        print("⚠ gitleaks not installed — checkpoint not scanned for secrets", file=sys.stderr)
        return []
    return describe(found, ROOT)


def assert_no_secrets() -> None:
    """Hard gate before publishing: raises with the findings (never the values)."""
    found = scan_dirs()
    if found is None:
        print("⚠ gitleaks not installed — export not scanned for secrets", file=sys.stderr)
        return
    if found:
        raise RuntimeError("possible secrets in the docs — not exported:\n  " + "\n  ".join(describe(found)))


# ---------- H3: glossary terms ----------
def _cells(line: str) -> list[str]:
    return [re.sub(r"[*_`]", "", c).strip() for c in line.strip().strip("|").split("|")]


def glossary(f: Path) -> list[tuple[list[str], list[str]]]:
    """[(preferred terms, words to avoid)] from the glossary table's optional "avoid"/"evitar" column."""
    if not f.is_file():
        return []
    rows = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip().startswith("|")]
    if len(rows) < 3:
        return []
    head = [h.lower() for h in _cells(rows[0])]
    col = next((i for i, h in enumerate(head) if h.startswith(("avoid", "evitar"))), None)
    if col is None:
        return []
    rules = []
    for row in rows[2:]:
        c = _cells(row)
        avoid = [a.strip() for a in c[col].split(",")] if col < len(c) else []
        avoid = [a for a in avoid if a and a not in ("-", "—")]
        if avoid and c[0]:
            rules.append(([c[0]] + ([c[2]] if len(c) > 2 and c[2] else []), avoid))
    return rules


def check_terms(rows: list[dict], strict: bool = False) -> Issues:
    by_lang = {"": glossary(DOCS / "domain" / "glossary.md")}
    for lang in docs.workspace()["project"].get("translations", []):
        by_lang[lang] = glossary(DOCS / "i18n" / lang / "domain" / "glossary.md")
    if not any(by_lang.values()):
        return [], []
    skip = {r["path"] for r in rows if r["type"] in ("glossary", "interview")} | {"domain/glossary.md"}
    found = []
    for logical, f, lang in pages(rows):
        rules = by_lang.get(lang) or []
        if not rules or logical in skip:
            continue
        for n, line in prose_lines(f.read_text(encoding="utf-8", errors="replace")):
            for preferred, avoid in rules:
                text = line
                for p in preferred:      # "Customer Order" must not trip the rule that bans a bare "Order"
                    text = re.sub(rf"(?<!\w){re.escape(p)}(?!\w)", " ", text, flags=re.I)
                for a in avoid:
                    if re.search(rf"(?<!\w){re.escape(a)}(?!\w)", text, re.I):
                        found.append(f'{rel_file(f)}:{n}: "{a}" → use "{preferred[0]}" (glossary)')
    return (found, []) if strict else ([], found)


CHECKS = (check_links, check_mermaid, check_secrets, check_terms)
