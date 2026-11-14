"""The coding workflow's skill pack (spec §4): cam-task and its step skills reach every project in both agent hosts,
carry the steps and commands each step needs, stay inside their share of the standing context, and AGENTS.md sends
every code change to cam-task, also in a project wired by an older kit."""
from __future__ import annotations

import re

from conftest import KIT_DIR

SKILLS = KIT_DIR / "templates" / "skills"
PACK = ("cam-task", "cam-difficulty", "cam-verify", "cam-ship", "cam-retro")
MUST = {
    "cam-task": ["cam/<id>-<slug>", "worktree add ../.cw/<id>", "cam-docs-lookup", "cam-difficulty", "cam-docs-update",
                 "cam-verify", "cam-ship", "cam-retro", "brainstorming", "writing-plans", "test-driven-development",
                 "systematic-debugging", "finishing-a-development-branch", "never skipped", "Never merge",
                 "four derived files", "skip its `llms`", '":(exclude)docs/.status.json"', '":(exclude)docs/llms.txt"',
                 '":(exclude)docs/llms-full.txt"', '":(exclude)docs/.work/fresh.json"'],
    "cam-difficulty": ["repos", "contract", "migration", "auth", "messaging", "weak-docs", "open-questions", "hotspot",
                       "big-item", "0–2 low", "3–5 medium", "6+ high", "inferred", "{{CLI}} board add story", "--label draft"],
    "cam-verify": ["./mvnw", "./gradlew", "go test ./...", "cargo test", "dotnet test", "repos[].verify", "{{CLI}} check",
                   "sdk env", "rev-parse HEAD", "flaky", "not green", "four derived files"],
    "cam-ship": [".env*", "gitleaks", "{{CLI}} pr fresh", "x-confirmed", "Open the PRs?", "gh pr create --draft",
                 "glab mr create --draft", "{{CLI}} board link", "never move", "Never merge", "cam-retro",
                 "four derived files", "worktree remove ../.cw/<id>", "git -C .cw/<id> status --porcelain",
                 "`docs/.work/fresh.json`", "commit it or ask the person"],
    "cam-retro": ["{{CLI}} skills note", "--source retro", "review|board", "skill-feedback", "{{CLI}} skills notes",
                  "skills fork"],
}


def fm(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    return text, re.search(r"^name: (.*)$", head, re.M)[1], re.search(r"^description: (.*)$", head, re.M)[1]


def test_the_pack_says_what_each_step_needs():
    for name, parts in MUST.items():
        text, n, _ = fm(name)
        assert n == name
        missing = [p for p in parts if p not in text]
        assert not missing, (name, missing)


def test_descriptions_stay_inside_their_token_caps():
    for name in PACK:
        _, n, d = fm(name)
        cap = 60 if name == "cam-task" else 24
        assert (len(f"{n}: {d}") + 3) // 4 <= cap, name          # budget.tokens()


def test_agents_md_sends_every_code_change_to_cam_task():
    t = (KIT_DIR / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    block = t[t.index("<!-- camarones:start -->"):t.index("<!-- camarones:end -->")]
    line = next(l for l in block.splitlines() if "cam-task" in l)
    assert line.startswith("0. Any code change") and (len(line) + 3) // 4 <= 30
    assert "\n3. Outside a `cam-task` change, " in block               # item 3's docs flow is not cam-task's


def test_every_project_gets_the_pack_rendered_in_both_hosts(kit):
    files = kit.services.templates.kit_skill_files("Demo")
    for name in PACK:
        for host in (".claude", ".agents"):
            assert "{{" not in files[f"{host}/skills/{name}/SKILL.md"]


def test_an_old_projects_agents_md_gets_the_line_on_refresh(wired):
    f = wired.root / "AGENTS.md"
    old = [l for l in f.read_text(encoding="utf-8").splitlines() if "cam-task" not in l]
    f.write_text("\n".join(old) + "\n", encoding="utf-8")                     # what a 4.81 project has
    wired.services.templates.init_templates(log=lambda _: None)
    assert "follow skill `cam-task`" in f.read_text(encoding="utf-8")


def test_the_skills_never_commit_or_loop_on_files_check_rewrites():
    for name in ("cam-task", "cam-verify", "cam-ship"):
        text = fm(name)[0]
        assert "prints nothing)" not in text and "add -A`" not in text, name
