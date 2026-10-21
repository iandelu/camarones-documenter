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
    """Mirror of resolve() in portal/app/public/legacy/doc.js: relative to the page's logical folder."""
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
    """Broken page links are errors; a `#anchor` the target page has no heading for is a WARN (ERROR with --strict).
    Anchors resolve like the portal: docs.slug() of the heading. Translations are skipped for anchors."""
    known = {r["path"]: ROOT / r["file"] for r in rows}
    slugs: dict[str, set[str]] = {}

    def anchors(path: str) -> set[str]:
        if path not in slugs:
            body = docs.split_fm(known[path].read_text(encoding="utf-8", errors="replace"))[1]
            slugs[path] = {h["slug"] for h in docs.headings(body)}
        return slugs[path]
    errors, warns = [], []
    for logical, f, lang in pages(rows):
        for n, line in prose_lines(f.read_text(encoding="utf-8", errors="replace")):
            for href in LINK_RE.findall(line) + REF_DEF_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:|^/", href, re.I):          # external, absolute: skipped
                    continue
                target, _, anchor = unquote(href.split("?", 1)[0]).partition("#")
                if target and not target.endswith(".md"):
                    continue
                page = resolve(logical, target) if target else logical
                if target and page not in known:
                    errors.append(f"{rel_file(f)}:{n}: broken link → {href}")
                elif (anchor and anchor != "top" and not lang and page in known
                      and docs.slug(anchor) not in anchors(page)):
                    warns.append(f"{rel_file(f)}:{n}: no heading for #{anchor} in {page}")
    return (errors + warns, []) if strict else (errors, warns)


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


# ---------- diagrams the page type calls for (CONVENTIONS §5) ----------
DIAGRAM_RE = re.compile(r"^\s*(?:```|~~~)\s*(mermaid|likec4-view)\b[^\n]*\n\s*(\w[\w-]*)?", re.M)
LIFECYCLE_RE = re.compile(r"\b(status|state|states|lifecycle|transitions?|estado|estados|ciclo de vida)\b", re.I)
NEEDS_DIAGRAM = {"data-model": "an erDiagram (or a flowchart of keys and TTLs for a cache)",
                 "domain": "a diagram (context map or relationships)",
                 "deployment": "a diagram (or a likec4-view of the deployment)"}


def check_diagrams(rows: list[dict], strict: bool = False) -> Issues:
    """Warnings only: a flow without its sequence, a lifecycle told in prose, a structure page with no picture."""
    warns = []
    for r in rows:
        if r.get("space", "docs") != "docs" or r["path"].endswith("index.md"):
            continue
        f = ROOT / r["file"]
        text = f.read_text(encoding="utf-8", errors="replace")
        kinds = {(m.group(2) or "") if m.group(1) == "mermaid" else "likec4" for m in DIAGRAM_RE.finditer(text)}
        kind, where = r["type"], rel_file(f)
        if kind == "business-flow" and "sequenceDiagram" not in kinds:
            warns.append(f"{where}: business flow without a sequenceDiagram")
        elif kind in NEEDS_DIAGRAM and not kinds:
            warns.append(f"{where}: {kind} page without {NEEDS_DIAGRAM[kind]}")
        elif r["path"] == "overview/system.md" and not kinds:
            warns.append(f"{where}: system overview without a diagram (embed the C4 context: likec4-view index)")
        prose = " ".join(line for _, line in prose_lines(text))
        if (kind in ("business-flow", "domain", "data-model") and "stateDiagram-v2" not in kinds
                and len(LIFECYCLE_RE.findall(prose)) >= 3):
            warns.append(f"{where}: describes a lifecycle (status/state) without a stateDiagram-v2")
    return [], warns


def check_fresh(rows: list[dict], strict: bool = False) -> Issues:
    """Pages whose cited code changed or disappeared since they were written (agents are kept off them)."""
    from .harness.freshness import code_paths
    warns = []
    for r in rows:
        st = r.get("freshness") or {}
        if r.get("fresh") == "suspect":
            warns.append(f"{r['file']}: its code changed since it was written ({', '.join(code_paths(st.get('changed', [])))}) "
                         "— refresh it, or `fresh --ack` if it still holds")
        elif r.get("fresh") == "stale":
            warns.append(f"{r['file']}: its code is gone ({', '.join(code_paths(st.get('missing', [])))}) — refresh it")
    return ([], warns) if not strict else (warns, [])




# ---------- structure: pages written for agents first (CONVENTIONS §11) ----------
TYPES = ("overview", "architecture", "domain", "glossary", "business-flow", "data-model", "deployment", "decision",
         "quality", "guide", "interview")
EXEMPT_TYPES = ("interview", "guide")          # working notes and the human guides keep their own shape
DESCRIPTION = (40, 300)                        # characters: a line in llms.txt and in search results
PAGE_WORDS, SECTION_WORDS = 1500, 400          # prose only, tables and code left out
VAGUE = re.compile(r"\b(see (above|below)|as (mentioned|said|stated) (above|before|earlier)|click here|ver (arriba|abajo)|como se (mencion[óo]|dijo) (arriba|antes)|haz clic aqu[íi])\b", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*(<!--\s*optional\s*-->)?\s*$")
TLDR = re.compile(r"^>\s*\*\*TL;DR:?\*\*", re.I)


def _norm_heading(text: str) -> str:
    return re.sub(r"[^\w ]+", "", re.sub(r"<!--.*?-->", "", text)).strip().lower()


def skeleton_dirs() -> list[Path]:
    """The project's copy first (the team may adapt it), then the kit's."""
    from .common import KIT
    return [ROOT / ".camarones" / "skeletons", KIT / "templates" / "skeletons"]


def skeletons() -> list[dict]:
    """[{name, type, for, required}] — `x-skeleton-for` (a path glob) wins over `type`."""
    seen, out = set(), []
    for d in skeleton_dirs():
        for f in sorted(d.glob("*.md")) if d.is_dir() else []:
            if f.name in seen or f.name == "README.md":
                continue
            seen.add(f.name)
            fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
            required = [_norm_heading(m.group(2)) for line in body.splitlines()
                        if (m := HEADING.match(line)) and len(m.group(1)) == 2 and not m.group(3)]
            out.append({"name": f.stem, "type": fm.get("type"), "for": fm.get("x-skeleton-for"), "required": required})
    return out


def skeleton_for(path: str, page_type: str, known: list[dict]) -> dict | None:
    from fnmatch import fnmatch
    by_path = next((s for s in known if s["for"] and fnmatch(path, s["for"])), None)
    return by_path or next((s for s in known if not s["for"] and s["type"] == page_type), None)


def structure_issues(path: str, text: str, known: list[dict]) -> list[str]:
    fm, body = docs.split_fm(text)
    kind, out = fm.get("type"), []
    if kind not in TYPES:
        out.append(f"type '{kind}' is not one of {', '.join(TYPES)}" if kind else "no type in the frontmatter")
    if not fm.get("title"):
        out.append("no title in the frontmatter")
    desc = str(fm.get("description") or "")
    if not DESCRIPTION[0] <= len(desc) <= DESCRIPTION[1]:
        out.append(f"description should say in {DESCRIPTION[0]}–{DESCRIPTION[1]} characters which question the page "
                   f"answers (it has {len(desc)})")
    heads, prev, fence = [], 1, None
    for line in body.splitlines():
        if FENCE_RE.match(line):
            fence = None if fence else True
            continue
        m = None if fence else HEADING.match(line)
        if m:
            level = len(m.group(1))
            if heads and level > prev + 1:
                out.append(f"heading '{m.group(2)}' skips a level (h{prev} → h{level})")
            heads.append((level, _norm_heading(m.group(2))))
            prev = level
    if sum(1 for lv, _ in heads if lv == 1) != 1:
        out.append(f"{sum(1 for lv, _ in heads if lv == 1)} H1 headings (one per page)")
    after_h1 = body.split("\n", 1)[1] if body.lstrip().startswith("# ") else body
    first = next((l for l in after_h1.splitlines() if l.strip()), "")
    if not TLDR.match(first.strip()):
        out.append("no `> **TL;DR:** …` right under the H1 (agents decide from it whether to read on)")
    sk = skeleton_for(path, kind, known)
    if sk:
        have = {h for lv, h in heads if lv == 2}
        missing = [h for h in sk["required"] if h not in have]
        if missing:
            out.append(f"missing sections from the {sk['name']} skeleton: {', '.join(missing)}")
    words, section, section_words = 0, None, {}
    for _, line in prose_lines(text):
        m = HEADING.match(line)
        if m:
            section = m.group(2) if len(m.group(1)) == 2 else section
            continue
        if line.lstrip().startswith("|"):
            continue
        n = len(line.split())
        words += n
        if section:
            section_words[section] = section_words.get(section, 0) + n
        if VAGUE.search(line):
            out.append(f"vague reference '{VAGUE.search(line).group(0)}': name the thing instead (sections are read alone)")
    if words > PAGE_WORDS:
        out.append(f"{words} words of prose (budget {PAGE_WORDS}): split the page")
    out += [f"section '{s}' has {n} words of prose (budget {SECTION_WORDS})" for s, n in section_words.items()
            if n > SECTION_WORDS]
    return out


def check_structure(rows: list[dict], strict: bool = False) -> Issues:
    """Pages written for agents first: answer first, sections that stand alone, the skeleton's sections, budgets."""
    known, issues = skeletons(), []
    for r in rows:
        if r.get("space", "docs") != "docs" or r.get("type") in EXEMPT_TYPES or r.get("owner") == "human":
            continue
        f = ROOT / r["file"]
        for i in structure_issues(r["path"], f.read_text(encoding="utf-8", errors="replace"), known):
            issues.append(f"{rel_file(f)}: {i}")
    return (issues, []) if strict else ([], issues)


def check_plugins(rows: list[dict], strict: bool = False) -> Issues:
    """Team plugins against .camarones/plugins.lock (R37): hand edits, unknown folders, locked plugins gone."""
    from .harness import plugin_store
    found = plugin_store.issues()
    return (found, []) if strict else ([], found)


def check_generated(rows: list[dict], strict: bool = False) -> Issues:
    """Generated blocks (X3) edited by hand or behind the code."""
    from . import genblocks
    return genblocks.check(rows, strict)


CHECKS = (check_links, check_mermaid, check_secrets, check_terms, check_diagrams, check_fresh,
          check_structure, check_generated, check_plugins)
