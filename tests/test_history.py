"""X11: the repos' git history read without AI — hotspots, who knows each repo, files that change together (and work
that spans repos through a shared ticket key), commit conventions — into docs/overview/history.md."""
from __future__ import annotations

import os, subprocess, sys

from conftest import KIT_DIR


def commit(repo, author, files, msg):
    for rel, text in files.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "-c", f"user.name={author}", "-c", "user.email=x@example.com", "commit", "-q", "-m", msg],
                   cwd=repo, check=True, capture_output=True)


def history_repos(kit):
    api, web = kit.ws / "api", kit.ws / "web"
    commit(api, "Ana", {"src/Order.java": "1", "src/OrderService.java": "1"}, "feat(orders): place order ORD-12")
    commit(api, "Ana", {"src/Order.java": "2", "src/OrderService.java": "2"}, "fix(orders): empty cart ORD-13")
    commit(api, "Bob", {"src/Payment.java": "1", "package-lock.json": "{}"}, "feat(pay): charge PAY-3")
    commit(api, "Bob", {"src/Order.java": "3"}, "fix: order rounding")
    commit(api, "dependabot[bot]", {"pom.xml": "<x/>"}, "chore(deps): bump")
    commit(web, "Cleo", {"src/cart.tsx": "1"}, "feat(cart): show order ORD-12")
    commit(web, "Cleo", {"src/cart.tsx": "2"}, "update stuff")


def test_mining_finds_hotspots_owners_and_co_change(kit):
    history_repos(kit)
    from lib import history
    h = history.mine(months=12)
    api = h["repos"]["api"]
    assert api["hotspots"][0] == ("src/Order.java", 3)
    assert all(f != "package-lock.json" for f, _ in api["hotspots"])                  # lockfiles are noise
    assert [a for a, _ in api["owners"]][:2] == ["Ana", "Bob"]
    assert not any("bot" in a for a, _ in api["owners"])
    assert (("src/Order.java", "src/OrderService.java"), 2) in api["co_change"]
    assert api["conventional"] == (4, 5)                                             # bot excluded, 'initial' is not
    assert h["across"] == [("ORD-12", ["api", "web"])]


def test_the_page_reads_well_and_passes_the_structure_check(kit):
    history_repos(kit)
    from lib import history
    page = history.write(months=12)
    text = page.read_text(encoding="utf-8")
    assert page == kit.root / "docs" / "overview" / "history.md"
    for s in ("## Hotspots", "## Who to ask", "## Changed together", "## Commit conventions", "Ana", "ORD-12"):
        assert s in text, s
    assert "x@example.com" not in text                                              # names only
    _, warns = kit.quality.check_structure(kit.docs.collect())
    assert not [w for w in warns if "history.md" in w], warns


def test_cli(kit):
    history_repos(kit)
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "history", "--months", "6"], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "history.md" in r.stdout, r.stderr


def test_no_history_says_so(kit):
    from lib import history
    text = history.render(history.mine(months=1, top=10) | {"repos": {}})
    assert "No repo with git history" in text and "| Repo |" not in text


def test_spanish_twin_and_folders(kit):
    history_repos(kit)
    ws = kit.docs.workspace(); ws["project"]["translations"] = ["es"]; kit.docs.save_workspace(ws)
    from lib import history
    assert history.mine(12)["repos"]["api"]["areas"]["Ana"] == "src"
    history.write(12)
    es = (kit.root / "docs" / "i18n" / "es" / "overview" / "history.md").read_text(encoding="utf-8")
    assert "## A quién preguntar" in es
    row = next(r for r in kit.docs.collect() if r["path"] == "overview/history.md")
    assert row["i18n"] == {"es": "current"}


def test_commits_are_public_and_empty_without_history(kit):
    history_repos(kit)
    from lib import history
    api = history.commits("api", 12)
    assert [c["subject"] for c in api][:2] == ["fix: order rounding", "feat(pay): charge PAY-3"]
    assert all("dependabot[bot]" != c["author"] for c in api) and api[0]["files"] == ["src/Order.java"]
    assert history.commits("nowhere", 12) == []


def test_the_newest_commit_of_a_repo_is_read(kit):
    history_repos(kit)
    from lib import history
    assert [c["subject"] for c in history.commits("web", 12)] == ["update stuff", "feat(cart): show order ORD-12", "initial"]
    assert history.mine(months=12)["repos"]["web"]["commits"] == 3
