"""Stack + tooling radar: a static scan (no AI, no network) of each repo for the tools the team already uses.

Detection is file-based only: marker files (catalog-info.yaml, sonar-project.properties, .storybook/, Dockerfile…) and
dependency names in the manifests (pom.xml, package.json, CI files…). The result is written to docs/overview/tooling.md
as an AI draft whose `x-sources` are the evidence files, so `check` flags a tool that disappeared from a repo.
A repo's stack comes from the first-look guess (quickarch.stack) unless workspace.yaml fixes it (`repos[i].stack`).
"""
from __future__ import annotations

import os, re
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from .common import CACHE, DOCS, repo_dir, save_json
from . import docs, quickarch

MAX_ENTRIES, MAX_BYTES, MAX_EVIDENCE = 20_000, 300_000, 5
PAGE = DOCS / "overview" / "tooling.md"
CACHE_FILE = CACHE / "radar.json"
MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "package.json",
             "pyproject.toml", "requirements*.txt", "setup.cfg", "Pipfile", "go.mod", ".gitlab-ci.yml", "Jenkinsfile",
             "azure-pipelines.y*ml", ".github/workflows/*.y*ml")

CATEGORIES = {
    "catalog": "Catalog", "quality": "Code quality", "ui": "UI / components", "lint": "Lint / format",
    "contracts": "API contracts", "tests": "Tests", "build": "Build / toolchain", "deploy": "Deploy / CI",
    "data": "DB migrations", "deps": "Dependency updates", "observability": "Observability",
}


def _yaml_docs(f: Path) -> list:
    try:
        return [d for d in yaml.safe_load_all(f.read_text(encoding="utf-8", errors="ignore")) if isinstance(d, dict)]
    except (yaml.YAMLError, OSError):
        return []


def read_backstage(f: Path) -> dict:
    for d in _yaml_docs(f):
        meta, spec = d.get("metadata") or {}, d.get("spec") or {}
        if not isinstance(meta, dict) or not isinstance(spec, dict):
            continue
        info = {"name": meta.get("name"), "type": spec.get("type"), "owner": spec.get("owner"),
                "system": spec.get("system"), "lifecycle": spec.get("lifecycle")}
        return {k: str(v) for k, v in info.items() if v}
    return {}


SONAR_PROPS = (r"^\s*sonar\.([\w.]+)\s*[=:]\s*(\S+)",                              # sonar-project.properties
               r"<sonar\.([\w.]+)>\s*([^<\s]+)\s*</sonar\.",                          # pom.xml <properties>
               r"property\s*\(?\s*[\"']sonar\.([\w.]+)[\"']\s*,\s*[\"']([^\"']+)")    # build.gradle(.kts)


def read_sonar(f: Path) -> dict:
    """Project key, organization and a dashboard link from sonar-project.properties, pom.xml or build.gradle."""
    text = read_small(f)
    props = {}
    for pat in SONAR_PROPS:
        for k, v in re.findall(pat, text, re.M):
            props.setdefault(k, v)
    key, org = props.get("projectKey", ""), props.get("organization", "")
    host = props.get("host.url", "").rstrip("/") or ("https://sonarcloud.io" if org else "")
    link = (f"{host}/dashboard?id={key}" if host and key else
            f"{host}/organizations/{org}/projects" if org and "sonarcloud.io" in host else "")
    info = {"project": key, "organization": org, "link": link}
    return {k: v for k, v in info.items() if v}


def rule(id_: str, label: str, cat: str, paths=(), deps=(), contains: str | None = None, read=None) -> dict:
    return {"id": id_, "label": label, "category": cat, "paths": paths, "deps": deps, "contains": contains, "read": read}


RULES = [
    rule("backstage", "Backstage catalog", "catalog", ["catalog-info.yaml", "catalog-info.yml"], read=read_backstage),
    rule("sonar", "SonarQube / SonarCloud", "quality", ["sonar-project.properties"],
         ["org.sonarqube", "sonar-maven-plugin", "sonar-scanner", "sonarqube", "sonarcloud", "sonar.projectkey",
          "sonar.organization", "sonar.host.url"], read=read_sonar),
    rule("jacoco", "JaCoCo coverage", "quality", deps=["jacoco"]),
    rule("storybook", "Storybook", "ui", [".storybook"], ["@storybook/"]),
    rule("mui", "Material UI", "ui", deps=["@mui/material"]),
    rule("antd", "Ant Design", "ui", deps=['"antd"']),
    rule("angular-material", "Angular Material", "ui", deps=["@angular/material"]),
    rule("primeng", "PrimeNG", "ui", deps=['"primeng"']),
    rule("chakra", "Chakra UI", "ui", deps=["@chakra-ui/"]),
    rule("tailwind", "Tailwind CSS", "ui", ["tailwind.config.*"], ['"tailwindcss"']),
    rule("shadcn", "shadcn/ui", "ui", ["components.json"], contains="shadcn"),
    rule("eslint", "ESLint", "lint", [".eslintrc*", "eslint.config.*"], ['"eslint"']),
    rule("prettier", "Prettier", "lint", [".prettierrc*", "prettier.config.*"], ['"prettier"']),
    rule("checkstyle", "Checkstyle", "lint", ["checkstyle*.xml"], ["checkstyle"]),
    rule("spotless", "Spotless", "lint", deps=["spotless"]),
    rule("pmd", "PMD", "lint", deps=["maven-pmd-plugin"]),
    rule("spotbugs", "SpotBugs", "lint", deps=["spotbugs"]),
    rule("ktlint", "ktlint", "lint", deps=["ktlint"]),
    rule("detekt", "detekt", "lint", deps=["detekt"]),
    rule("ruff", "Ruff", "lint", ["ruff.toml", ".ruff.toml"], ["ruff"]),
    rule("black", "Black", "lint", deps=["[tool.black]", '"black"', "black=="]),
    rule("golangci", "golangci-lint", "lint", [".golangci.y*ml", ".golangci.toml"]),
    rule("openapi", "OpenAPI spec", "contracts", ["openapi*.y*ml", "openapi*.json", "swagger*.y*ml", "swagger*.json",
                                                  "*.openapi.y*ml"]),
    rule("springdoc", "springdoc-openapi (OpenAPI from code)", "contracts", deps=["springdoc-openapi", "springfox"]),
    rule("asyncapi", "AsyncAPI spec", "contracts", ["asyncapi*.y*ml", "asyncapi*.json"]),
    rule("springwolf", "Springwolf (AsyncAPI from code)", "contracts", deps=["springwolf"]),
    rule("protobuf", "Protocol Buffers", "contracts", ["*.proto"]),
    rule("graphql", "GraphQL schema", "contracts", ["*.graphqls", "*.graphql", "schema.gql"]),
    rule("junit", "JUnit", "tests", deps=["junit"]),
    rule("testcontainers", "Testcontainers", "tests", deps=["testcontainers"]),
    rule("jest", "Jest", "tests", ["jest.config.*"], ['"jest"']),
    rule("vitest", "Vitest", "tests", ["vitest.config.*"], ['"vitest"']),
    rule("playwright", "Playwright", "tests", ["playwright.config.*"], ["@playwright/test"]),
    rule("cypress", "Cypress", "tests", ["cypress.config.*"], ['"cypress"']),
    rule("pytest", "pytest", "tests", ["pytest.ini", "conftest.py"], ["pytest"]),
    rule("pact", "Pact (contract tests)", "tests", deps=["au.com.dius.pact", "@pact-foundation", "pact-python"]),
    rule("maven-wrapper", "Maven wrapper", "build", ["mvnw"]),
    rule("gradle-wrapper", "Gradle wrapper", "build", ["gradlew"]),
    rule("sdkman", "SDKMAN (.sdkmanrc)", "build", [".sdkmanrc"]),
    rule("toolchain-pins", "Toolchain pins", "build", [".java-version", ".nvmrc", ".node-version", ".python-version",
                                                        ".tool-versions"]),
    rule("docker", "Dockerfile", "build", ["Dockerfile", "Dockerfile.*", "*.Dockerfile"]),
    rule("compose", "Docker Compose", "build", ["docker-compose*.y*ml", "compose.y*ml", "compose.*.y*ml"]),
    rule("helm", "Helm chart", "deploy", ["Chart.yaml"]),
    rule("kustomize", "Kustomize", "deploy", ["kustomization.y*ml"]),
    rule("argocd", "Argo CD", "deploy", ["*.y*ml"], contains="argoproj.io"),
    rule("terraform", "Terraform", "deploy", ["*.tf"]),
    rule("gitlab-ci", "GitLab CI", "deploy", [".gitlab-ci.yml"]),
    rule("github-actions", "GitHub Actions", "deploy", [".github/workflows/*.y*ml"]),
    rule("jenkins", "Jenkins", "deploy", ["Jenkinsfile"]),
    rule("azure-pipelines", "Azure Pipelines", "deploy", ["azure-pipelines.y*ml"]),
    rule("liquibase", "Liquibase", "data", ["db.changelog*"], ["liquibase"]),
    rule("flyway", "Flyway", "data", ["V*__*.sql"], ["flyway"]),
    rule("renovate", "Renovate", "deps", ["renovate.json", "renovate.json5", ".renovaterc*"]),
    rule("dependabot", "Dependabot", "deps", [".github/dependabot.y*ml"]),
    rule("opentelemetry", "OpenTelemetry", "observability", deps=["opentelemetry"]),
    rule("prometheus", "Prometheus / Micrometer", "observability", deps=["micrometer-registry-prometheus",
                                                                       "prometheus-client", "prom-client"]),
]


def matches(rel: str, pattern: str) -> bool:
    """A pattern with a `/` matches the whole repo-relative path; otherwise just the file or folder name."""
    return fnmatchcase(rel, pattern) if "/" in pattern else fnmatchcase(rel.rsplit("/", 1)[-1], pattern)


def entries(repo: Path) -> list[str]:
    """Repo-relative POSIX paths of files and folders, skipping build output, dependencies and VCS folders."""
    found: list[str] = []
    for top, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in quickarch.SKIP_DIRS)
        base = Path(top).relative_to(repo)
        for name in [*dirs, *sorted(files)]:
            found.append((base / name).as_posix())
            if len(found) >= MAX_ENTRIES:
                return found
    return found


def read_small(f: Path) -> str:
    try:
        return f.read_text(encoding="utf-8", errors="ignore") if f.stat().st_size <= MAX_BYTES else ""
    except OSError:
        return ""


def scan_repo(name: str, repo: Path) -> list[dict]:
    paths = entries(repo)
    manifests = {rel: read_small(repo / rel).lower() for rel in paths
                 if any(matches(rel, m) for m in MANIFESTS) and (repo / rel).is_file()}
    tools = []
    for r in RULES:
        hits = [rel for rel in paths if any(matches(rel, p) for p in r["paths"])]
        if r["contains"]:
            hits = [rel for rel in hits if (repo / rel).is_file() and r["contains"] in read_small(repo / rel)]
        evidence = hits[:MAX_EVIDENCE]
        if not evidence:
            evidence = [rel for rel, text in manifests.items() if any(d.lower() in text for d in r["deps"])][:1]
        if not evidence:
            continue
        info = {}
        if r["read"] and (repo / evidence[0]).is_file():
            info = r["read"](repo / evidence[0])
        tools.append({"id": r["id"], "label": r["label"], "category": r["category"],
                      "evidence": [f"{name}:{rel}" for rel in evidence], "info": info})
    return tools


def scan() -> dict:
    """{repo: {stack, detected_stack, kind, tools: [{id, label, category, evidence: ["repo:path"], info}]}}."""
    out = {}
    for r in docs.workspace()["repos"]:
        repo = repo_dir(r["name"])
        if not repo.is_dir():
            continue
        detected = quickarch.stack(repo, quickarch.repo_blob(repo))
        out[r["name"]] = {"stack": r.get("stack") or detected, "detected_stack": detected,
                          "kind": r.get("kind", "service"), "tools": scan_repo(r["name"], repo)}
    return out


def set_stack(repo: str, text: str | None) -> None:
    """Fix a repo's stack in workspace.yaml (None or empty → back to the detected one)."""
    ws = docs.workspace()
    row = next((r for r in ws["repos"] if r["name"] == repo), None)
    if row is None:
        raise ValueError(f"Unknown repo: {repo}")
    if text and text.strip():
        row["stack"] = text.strip()
    else:
        row.pop("stack", None)
    docs.save_workspace(ws)


def describe(t: dict) -> str:
    info = t["info"]
    if t["id"] == "backstage":
        extra = ", ".join(f"{k} {info[k]}" for k in ("owner", "system", "lifecycle", "type") if info.get(k))
    elif t["id"] == "sonar":
        extra = f"[dashboard]({info['link']})" if info.get("link") else info.get("project") or info.get("organization", "")
    else:
        extra = ""
    return t["label"] + (f" — {extra}" if extra else "")


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def render(result: dict) -> str:
    fm = {"type": "overview", "title": "Stack and tooling",
          "description": "Each repository's stack and the tools the team already uses (catalog, code quality, UI "
                         "components, linters, contracts, tests, CI/deploy). Static scan of the repos, no AI.",
          "tags": ["stack", "tooling"],
          "x-sources": list(dict.fromkeys(e for r in result.values() for t in r["tools"] for e in t["evidence"])),
          "x-owner": "ai"}
    lines = ["# Stack and tooling", "",
             "Static scan of the repositories (no AI): each repo's stack and the tools the team already uses. "
             "Discovery reads this page first and verifies it. Fix a wrong stack with "
             "`camaron stack <repo> \"<stack>\"`, then `camaron radar` to refresh the page.", ""]
    for name, r in result.items():
        lines += [f"## {name}", "", f"**Stack:** {r['stack']}" +
                  (f" (detected: {r['detected_stack']})" if r["stack"] != r["detected_stack"] else ""), ""]
        if not r["tools"]:
            lines += ["No tools detected.", ""]
            continue
        lines += ["| Area | Tool | Evidence |", "|---|---|---|"]
        order = list(CATEGORIES)
        for t in sorted(r["tools"], key=lambda t: order.index(t["category"])):
            ev = ", ".join(f"`{e.split(':', 1)[1]}`" for e in t["evidence"])
            lines.append(f"| {CATEGORIES[t['category']]} | {cell(describe(t))} | {ev} |")
        lines.append("")
    return docs.join_fm(fm, "\n".join(lines))


def run(log=print) -> Path:
    """Scan every repo, write docs/overview/tooling.md and the cache the wizard reads. Returns the page."""
    result = scan()
    save_json(CACHE_FILE, result)
    old = docs.split_fm(PAGE.read_text(encoding="utf-8"))[0] if PAGE.exists() else {}
    if old.get("x-owner") == "human":           # a human took the page over: never rewrite it
        log(f"· {PAGE.name} is owned by a human: not rewritten")
        return PAGE
    text = render(result)
    if old.get("x-confirmed"):                  # keep the confirmation: a changed body then reads as needs-reconfirm
        fm, body = docs.split_fm(text)
        text = docs.join_fm({**fm, "x-confirmed": old["x-confirmed"]}, body)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    log(f"✔ {sum(len(r['tools']) for r in result.values())} tools found in {len(result)} repos")
    return PAGE
