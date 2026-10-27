"""Known vulnerabilities of the inventory's libraries (S8), from OSV-Scanner (lib/binaries.py pins and checks it).

Offline by default: the scanner downloads OSV's per-ecosystem databases once into ~/.camarones/osv-db and matches the
repo's packages on this machine without resolving transitive dependencies (that would fetch parent poms, internal ones
included, from Maven Central), so no package name leaves it. The online API (more precise for unresolved Maven
versions) sends package coordinates to osv.dev, so it runs only when this machine opts in: `osv: {online: true}` in
~/.camarones.json. Never raises: a missing binary or a failed scan leaves the inventory without vulnerabilities."""
from __future__ import annotations

import json, os, subprocess
from datetime import datetime, timezone

from .common import HOME, PREFS, load_json, repo_dir
from . import binaries, docs

DB_DIR = HOME / ".camarones" / "osv-db"
TIMEOUT = 900                 # the first offline run downloads the databases


def online() -> bool:
    return bool((load_json(PREFS, {}).get("osv") or {}).get("online"))


def _run(argv: list[str], env: dict) -> tuple[int, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                           timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def severity(score: float | None, label: str | None) -> str:
    if score is not None:
        return "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low"
    return {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "MEDIUM": "medium", "LOW": "low"}.get(
        (label or "").upper(), "unknown")


def _fixed(vuln: dict, name: str) -> str | None:
    for aff in vuln.get("affected") or []:
        if (aff.get("package") or {}).get("name", name) != name:
            continue
        for rng in aff.get("ranges") or []:
            for ev in rng.get("events") or []:
                if ev.get("fixed"):
                    return ev["fixed"]
    return None


DETAILS_MAX = 6000            # characters of an advisory's text kept in the inventory
REFERENCES_MAX = 12
KEEP = ("id", "cve", "summary", "severity", "score", "fixed", "aliases", "details", "published", "modified", "ranges",
        "references", "cwes")


def _ranges(vuln: dict, name: str) -> list[dict]:
    """The affected versions of `name` as [{introduced, fixed | last_affected}]: why a version is flagged."""
    out = []
    for aff in vuln.get("affected") or []:
        if (aff.get("package") or {}).get("name", name) != name:
            continue
        for rng in aff.get("ranges") or []:
            cur: dict = {}
            for ev in rng.get("events") or []:
                if "introduced" in ev:
                    if cur:
                        out.append(cur)
                    cur = {"introduced": ev["introduced"]}
                elif "fixed" in ev or "last_affected" in ev:
                    cur.update({k: ev[k] for k in ("fixed", "last_affected") if k in ev})
                    out.append(cur)
                    cur = {}
            if cur:
                out.append(cur)
    return out


def parse(data: dict) -> dict[tuple[str, str], list[dict]]:
    """(ecosystem, name) → [{id, cve, summary, severity, score, fixed, version, aliases, details, published, modified,
    ranges, references, cwes}] from OSV-Scanner's JSON: the whole advisory, so it reads offline in the app."""
    out: dict[tuple[str, str], list[dict]] = {}
    for result in data.get("results") or []:
        for pkg in result.get("packages") or []:
            p = pkg.get("package") or {}
            scores = {i: g.get("max_severity") for g in pkg.get("groups") or [] for i in g.get("ids") or []}
            for v in pkg.get("vulnerabilities") or []:
                try:
                    score = float(scores.get(v.get("id")) or "")
                except ValueError:
                    score = None
                out.setdefault((p.get("ecosystem", ""), p.get("name", "")), []).append({
                    "id": v.get("id"), "cve": next((a for a in v.get("aliases") or [] if a.startswith("CVE-")), None),
                    "summary": v.get("summary") or "", "score": score,
                    "severity": severity(score, (v.get("database_specific") or {}).get("severity")),
                    "fixed": _fixed(v, p.get("name", "")), "version": p.get("version"),
                    "aliases": list(v.get("aliases") or []), "details": (v.get("details") or "")[:DETAILS_MAX],
                    "published": v.get("published"), "modified": v.get("modified"),
                    "ranges": _ranges(v, p.get("name", "")),
                    "references": [{"type": r.get("type", ""), "url": r["url"]} for r in v.get("references") or []
                                   if str(r.get("url", "")).startswith(("https://", "http://"))][:REFERENCES_MAX],
                    "cwes": list((v.get("database_specific") or {}).get("cwe_ids") or [])})
    return out


def scan_repo(exe: str, name: str) -> dict | None:
    argv = [str(exe), "scan", "source", "--format", "json", "--recursive"]
    if not online():                                     # --no-resolve: fetching a parent pom from Maven Central
        argv += ["--offline-vulnerabilities", "--download-offline-databases", "--no-resolve"]   # would send its coordinates
    argv.append(str(repo_dir(name)))
    DB_DIR.mkdir(parents=True, exist_ok=True)
    rc, stdout = _run(argv, {**os.environ, "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(DB_DIR)})
    if rc not in (0, 1, 128):                            # 1: vulnerabilities found, 128: no packages to scan
        return None
    try:
        return json.loads(stdout) if stdout.strip() else {"results": []}
    except ValueError:
        return None


def attach(rows: list[dict], log=print) -> dict | None:
    """Scan every repo and put `vulns` on each inventory row. Returns the scan's summary, or None without the binary."""
    exe = binaries.ensure("osv-scanner", log=log)
    if not exe:
        log("⚠ OSV-Scanner is not available on this machine: the inventory has no vulnerabilities")
        return None
    found: dict[tuple[str, str, str], list[dict]] = {}        # (repo, ecosystem, name): a finding stays in its repo
    failed = []
    repos = sorted({r["repo"] for r in rows} | {n for n in docs.repo_names() if repo_dir(n).is_dir()})
    for n, name in enumerate(repos, 1):                     # `[n/total]`: the desktop app's bar counts these lines
        log(f"[{n}/{len(repos)}] {name}: scanning for known vulnerabilities{' (offline database)' if not online() else ''}…")
        data = scan_repo(exe, name)
        if data is None:
            failed.append(name)
            continue
        for (eco, pkg), vulns in parse(data).items():
            found.setdefault((name, eco, pkg), []).extend(vulns)
    for row in rows:
        version = (row.get("version") or "").lstrip("v")
        hits = [v for v in found.get((row["repo"], row["ecosystem"], row["name"]), [])
                if not version or (v["version"] or "").lstrip("v") in ("", version)]
        row["vulns"] = [{k: v[k] for k in KEEP}
                        for v in {v["id"]: v for v in hits}.values()]
    vulnerable = sum(1 for r in rows if r["vulns"])
    log(f"✔ {vulnerable} libraries with known vulnerabilities" + (f" ({', '.join(failed)}: scan failed)" if failed else ""))
    return {"scanned": len(repos) - len(failed), "failed": failed, "online": online(), "vulnerable": vulnerable,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
