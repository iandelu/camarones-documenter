# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6", "rich>=13", "questionary>=2", "keyring>=25"]
# ///
"""🦐 Camarón — project documentation wizard + CLI. No arguments opens the wizard.

  setup [--ci]              install tools, sync repos, wire Claude Code/Codex + git hooks (idempotent)
  sync                      clone/pull repos from workspace.yaml
  detect                    add repos found in this folder to workspace.yaml
  changes                   files changed per repo since docs were last updated
  mark-documented [repo..]  record current commits as documented
  status [--json]           trust report: confirmed / draft / needs-reconfirm / orphans / translations
  check [--strict]          CI gate for docs
  confirm FILE.. --by NAME  mark pages as human-confirmed
  translated FILE..         stamp docs/i18n/<lang>/… pages as translations of the current canonical page
  llms                      regenerate docs/llms.txt
  graph                     rebuild the cross-repo code graph (.camarones/.cache/graph/graph.html)
  arch | arch-validate      live C4 editor | validate the C4 model
  portal                    export the read-only portal (docs, C4, code graphs, wikis) to .camarones/.cache/site for CI / hosting
  up [--port] [--docker|--static]   serve the portal: live editable server (default), or the export in Docker / without it
  wiki REPO.. [--init|--update] [--engine openwiki|claude|codex] [--force]   generate / refresh the OpenWiki of repos,
                            one at a time (a first wiki needs the repo's brief; --force skips that check)
  wiki REPO --open | --close    around a manual OpenWiki MCP session (real openwiki/ folder, then back to cam-docs)
  down                      stop the portal
  migrate [--yes] [--dry-run]   move an older layout into <workspace>/cam-docs and clean kit files out of the repos
  uninstall [--dry-run] [--yes] [--global] [--no-backup] [--backup-dir DIR]
                            undo the project: back up and delete cam-docs, remove every kit trace from the repos
                            and the workspace folder (--global: also ~/.camarones*, saved tokens)
  mcp [--http [--port N]]   MCP server: agents search/read the docs and the code graph, propose draft edits and
                            feedback; --http serves it on 127.0.0.1 with this machine's token (~/.camarones/mcp-token)
  ci [gitlab|github]        install the umbrella CI pipeline
  plan [sync|next|start|note|done|block|drop|add|redo] …   session work plan (docs/.work/plan.yaml)
  plan note UNIT "text"     save a progress checkpoint of a unit (a closed session resumes from it)
  plan redo UNIT [--also U…]  reopen a finished unit (e.g. an interview) to review and update it
  plan approve UNIT          close a unit that waits for a person (`approval: true` in pipeline.yaml); its
                            dependents start after this
  checkpoint ["message"]    commit docs progress locally in the umbrella repo (never pushes)
  remote [URL]              show / set the team's cam-docs repo (origin)
  share [--auto on|off]     checkpoint, pull the team's work (rebase) and push cam-docs; --auto: after every checkpoint
  feedback FILE "text" --by NAME   record a human review comment (applied by the review-fixes unit)
  stats [--json] [--months N] [--record on|off]   team usage KPIs (who consults the docs, what they find, what
                            is read most); --record: whether this machine adds its counts
  version                   kit and pinned tool versions
  prompt UNIT [--lang es|en] [--unattended]      prompt for an agent session (UNIT may be 'update')
  autopilot [--lang es|en] [--max-units N] [--poll-seconds N] [--include-interviews]
                            run ready units back to back unattended (Claude Code / Codex, waits out usage limits)
  arch-draft [--save]       quick static architecture scan → C4 draft (first look, no AI)
  radar [--json]            stack + tools the repos already use (Backstage, Sonar, linters…) → docs/overview/tooling.md
  inventory [--cves] [--json]   every repo's direct dependencies by category (framework, data, cache, security…)
                          → docs/overview/libraries.md, no AI; --cves adds known vulnerabilities (OSV-Scanner with
                          its offline database, so no package name leaves the machine); exit 1 if one is high/critical
  stack REPO [TEXT|--reset] fix a repo's stack in workspace.yaml (--reset: back to the detected one)
  interview mode [team|live]   how interviews run: team questionnaire answered offline, or live with the agent
  interview export [--lang es|en]   questionnaire → offline HTML form + Markdown copy to share with the team
  interview import FILE|DIR…   import the team's answers (form JSON or filled Markdown)
  interview status [--json]    who answered, unanswered questions, disagreements
  doctor [--local|--context [--json]]
                            check prerequisites and tool versions; --context: the tokens every agent session loads
                            before reading a page (AGENTS.md, skills, MCP schemas) against context.budget;
                            --local: propose a free local model for this machine (bounded/judge work, through
                            OpenCode) without installing anything
  run [--parallel N] [--per-runner claude=2,codex=1] [--max-units N] [--lang es|en] [--include-interviews]
      [--policy on-conflict|never] [--poll-seconds N] [--only UNIT…]
                            run ready units in parallel: discovery, repo briefs and flows each in their own copy of
                            cam-docs (merged back when done), other units one at a time. autopilot stays sequential
  runs [RUN] [--json]       what past runs did: units, outcome, merges, time, tokens and cost
  eval [list|run|draft|confirm ID…] [--runner T] [--judge T] [--all] [--json] [--by NAME]
                            golden questions (evals/questions.yaml): run asks the confirmed ones to an agent that may
                            only read the docs and scores cited pages + exact identifiers; draft adds a unit that
                            proposes questions; confirm approves them
  eval comply UNIT [--runner T] [--json]
                            run one ready unit for real and score what it wrote against the method (structure, links,
                            sources), without AI: compare playbook or prompt changes. Use the sandbox, not CI
  export pdf | print | tour FLOW | codetour FLOW | confluence | notion
                            the docs agents may read as one print-ready page (PDF with a headless Chrome), a guided
                            tour of a business flow (HTML slides, or a VS Code CodeTour in .tours/ opened at each
                            step's code), or published to Confluence/Notion (plugins: `plugins enable` first)
  history [--months 12]     docs/overview/history.md from git, no AI: hotspots, who to ask per repo, files that
                            change together, tickets that span repos, commit conventions
  repair                    put back what the kit owns in this project: its skills and agent config, the agent tools'
                            skills, the workspace and wiki links (never the team's pages)
  removed add WHAT --why WHY [--decision decisions/NNNN-x.md]
                            record something removed on purpose (docs/overview/removed.md) so agents do not recreate it
  review request PAGE [--note T] | wait ID [--timeout S] | list
                            an agent asks a person to review a page and waits for the answer (approve / changes, as
                            JSON); people answer in the portal's Review tab
  hooks [on|off]            method hooks for Claude Code in cam-docs: the plan state at session start, a check of each
                            docs page right after it is edited, a reminder to update the docs before stopping
  ab --qa "QUESTION" | --golden [--runner T] [--judge T] [--json]
                            the same question with cam-docs and without it (only the code, in a throwaway folder that
                            links the repos): tokens, time, tool calls and identifiers named, side by side
  ab --task "TASK" [--check "CMD"] | --replay [--max N]
                            a coding task twice, in throwaway worktrees of the repos (with cam-docs and without):
                            tokens, time, files changed, the diff, and whether CMD (e.g. the tests) passes in each
  ab sampling on|off        opt in on this machine to keep a sample of real prompts (needs ab.sampling.enabled in
                            workspace.yaml; stored in ~/.camarones/ab-samples/, never in the repo); --replay runs them
  fresh [--json] [--ack PAGE… --by NAME] [--plan]
                            pages whose cited code changed (suspect) or is gone (stale); agents are kept off them.
                            --ack: the page still holds for today's code; --plan: add a unit that refreshes them
  blocks [--force] [--json]  facts read from the repos, no AI: docs/repos/<repo>/reference.md (commands, env vars,
                            endpoints, topics) and every <!-- generated:… --> block in the docs. A block edited by hand
                            is kept and flagged by check; --force takes the code's version. `sync` refreshes them too
  pr fresh REPO [--base REF | --files F…] [--json] [--post] [--lang en|es]
                            what a pull request does to the docs, no AI: the pages whose cited code it changes (left
                            out of date by it, or already before). --post writes or updates one comment on the PR/MR
                            (GitHub Actions or GitLab CI); it never fails the pipeline. --head REF: the PR's commit
                            when it is not checked out
  pr propose PR_URL [--ref REF] [--base REF] [--runner R] [--dry-run [--json]] [--comment]
                            AI: an agent updates the pages the PR leaves out of date on cam-docs branch
                            docs/pr-<repo>-<n> (its own worktree); the kit commits, pushes and opens the docs PR.
                            The PR is fetched into refs/camaron/pr/<n> (your checkout is not touched); --dry-run shows
                            the plan; --comment links the docs PR on the service PR; --preview exports the docs
                            branch as a static portal in .camarones/.cache/previews/
  kpis [--json] [--months N] [--no-check] [--compare RUN_A RUN_B]
                            is it working? cost and speed of runs (the team's, per month), coverage, trust, usage;
                            --compare puts two runs side by side
  pipeline show|validate [--json]   the project's plan as units (kit pipeline + .camarones/pipeline.yaml);
                            validate exits 1 when pipeline.yaml has problems (for CI)
  plugins [--json]          plugins of the kit and of this project (.camarones/plugins/): what they provide, whether
                            they run code, and whether they are loaded (code and prompts need approval: `trust`)
  plugins add SOURCE        vendor a team plugin from a folder or git:<url>@<tag>[#subfolder]; pinned in plugins.lock
  plugins update [NAME] [--to TAG] | outdated | remove NAME | enable NAME | disable NAME
                            re-fetch (shows what changed; changed code asks trust again), newer versions, drop one
  install DEST --profile quick|full [--dry-run]   copy kit into an explicit project folder
  upgrade SOURCE [--dry-run]  update kit files with backups; preserve project configuration
  profile quick|full        change the work plan without losing checkpoints
  new NAME [--from URL]     create ./NAME/cam-docs/, register it, open it (global install); --from joins the team's repo
  join URL [FOLDER]         use the team's cam-docs repo: clone it into FOLDER/cam-docs (default: here) or reuse the
                            copy already on this machine; the wizard then only sets up this machine
  trust [--yes]             list the agent config (hooks, MCP servers, settings, skills) this machine has not approved;
                            approve it and link it into the workspace (unapproved config is never linked)
  switch                    pick a registered project to open (global install)
  self-update               git pull the central kit in place (global install only)
  unlink                    remove this project's local kit copy, keep config (moves to global install)
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

for _stream in (sys.stdout, sys.stderr):           # before the first print: a Windows pipe is cp1252, not UTF-8
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from lib import projects                            # noqa: E402 — no dependency on ROOT/common state


def _relaunch(root: Path, argv: list[str]) -> None:
    """Restart this script with CAMARONES_ROOT set, so every module that captured ROOT at import
    time (docs, env, wizard, …) sees the right project from the start. Mirrors lib/upgrade.py's
    own relaunch-after-swap trick — module-level globals can't be hot-reloaded mid-process."""
    os.environ["CAMARONES_ROOT"] = str(root)
    args = [sys.executable, __file__, *argv]
    if os.name == "nt":
        sys.exit(subprocess.run(args).returncode)
    os.execv(sys.executable, args)


def _team(fn, *args):
    """new --from / join: a clone that fails (no access, wrong URL, folder taken) is a short error, not a traceback.
    Access is checked first with plain git; a token is asked only when that fails and there is a terminal to ask in."""
    url = args[-1] if fn is projects.create else args[0]
    if url.strip() and not projects.connect(url, ask=projects.ask_token if sys.stdin.isatty() else None,
                                            log=lambda m: print(m, file=sys.stderr)):
        sys.exit(1)
    try:
        return fn(*args)
    except (ValueError, RuntimeError) as e:
        print(f"✖ {e}", file=sys.stderr)
        sys.exit(1)


_cmd0 = sys.argv[1] if len(sys.argv) > 1 else None
if _cmd0 == "new" and len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
    _from = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv[3:-1] else ""
    _dest = _team(projects.create, sys.argv[2], None, _from)
    print(f"🦐 {_dest.name} → {_dest}")
    _relaunch(_dest, [])
elif _cmd0 == "join" and len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
    # The team's cam-docs repo: cloned into <folder or cwd>/cam-docs, or reused if this machine already has it.
    # The wizard then only prepares this machine (tools, repos) — the rest is the team's, already done.
    _dest, _joined = _team(projects.join, sys.argv[2], Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else Path.cwd())
    print(f"🦐 {'joined' if _joined else 'new project, remote set'} → {_dest}")
    _relaunch(_dest, [])
elif _cmd0 == "switch":
    _dest = projects.pick(allow_new=True, here=Path.cwd())
    if _dest is None:
        sys.exit(1)
    _relaunch(_dest, [])
elif (_cmd0 == "init" and os.environ.get("CAMARONES_GLOBAL")
      and not os.environ.get("CAMARONES_ROOT") and not projects.find_marker(Path.cwd())):
    # Global install, run from inside an existing repos folder (or an empty one): adopt THIS folder as the
    # workspace — docs and agent config go to ./cam-docs, the repos stay where they are.
    _relaunch(projects.adopt(Path.cwd()), ["init"])
elif os.environ.get("CAMARONES_GLOBAL") and not os.environ.get("CAMARONES_ROOT"):
    # Only the global launcher (install-global.cmd/.sh) sets CAMARONES_GLOBAL — a project-local
    # launcher (legacy co-located kit copy) must keep resolving ROOT exactly as before (KIT.parent),
    # even on its very first run before workspace.yaml exists, with no picker involved.
    _marker = projects.find_marker(Path.cwd())
    if _marker:
        projects.touch(_marker)
    elif _cmd0 not in ("help", "version", "self-update", "mcp"):
        _dest = projects.pick(allow_new=True, here=Path.cwd())
        if _dest is None:
            sys.exit(1)
        _relaunch(_dest, sys.argv[1:])

from lib import docs, env, plan                     # noqa: E402
from lib.common import VERSIONS, PREFS, cli_cmd, ROOT, CACHE, load_json   # noqa: E402


def cmd_trust(a) -> int:
    from lib import trust
    env.refresh_agent_config()
    rows = trust.grouped(trust.pending())
    if not rows:
        env.link_workspace()
        print("✔ nothing to approve: the agent config and plugins are the kit's own or already approved on this machine")
        return 0
    print("Agent config and plugins not approved on this machine (Claude Code, Codex or the kit would load them):\n")
    for kind, label, detail, status in rows:
        print(f"  {status:<8} {kind:<8} {label}\n           {detail}")
    if not a.yes:
        if not sys.stdin.isatty():
            print(f"\nnot approved — check it, then run: {cli_cmd()} trust --yes")
            return 1
        try:
            answer = input("\nApprove all of this on this machine? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            print(f"\nnot approved — check it, then run: {cli_cmd()} trust --yes")
            return 1
        if answer.strip().lower() not in ("y", "yes", "s", "si", "sí"):
            trust.decline()
            print("not approved: nothing in the list is loaded on this machine")
            return 1
    n = trust.approve()
    env.link_workspace()
    print(f"✔ approved {n} item(s); the workspace's agents load this config")
    return 0


def main() -> int:
    if len(sys.argv) == 1:
        from lib.wizard import W
        W().run()
        return 0
    p = argparse.ArgumentParser(prog=cli_cmd(), description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("help")
    s = sp.add_parser("setup"); s.add_argument("--ci", action="store_true"); s.add_argument("--profile", choices=["quick", "full"])
    ins = sp.add_parser("install"); ins.add_argument("destination", type=Path)
    ins.add_argument("--profile", choices=["quick", "full"], default="quick"); ins.add_argument("--dry-run", action="store_true")
    upg = sp.add_parser("upgrade"); upg.add_argument("source", type=Path); upg.add_argument("--dry-run", action="store_true")
    nw = sp.add_parser("new"); nw.add_argument("name"); nw.add_argument("--from", dest="from_url", default="")
    sp.add_parser("switch")
    sp.add_parser("self-update")
    sp.add_parser("unlink")
    prof = sp.add_parser("profile"); prof.add_argument("name", choices=["quick", "full"])
    sp.add_parser("init")
    for c in ("sync", "detect", "changes", "llms", "graph", "arch", "arch-validate", "portal", "down", "wizard", "version"):
        sp.add_parser(c)
    sp.add_parser("repair")
    sp.add_parser("history").add_argument("--months", type=int, default=12)
    rmv = sp.add_parser("removed"); rmv.add_argument("action", choices=["add"]); rmv.add_argument("what")
    rmv.add_argument("--why", required=True); rmv.add_argument("--decision", default="")
    rv = sp.add_parser("review"); rv.add_argument("action", choices=["request", "wait", "list"])
    rv.add_argument("target", nargs="?"); rv.add_argument("--note", default=""); rv.add_argument("--by", default="agent")
    rv.add_argument("--timeout", type=float, default=3600)
    hk = sp.add_parser("hook"); hk.add_argument("name", choices=["session-start", "post-edit", "stop"])
    hks = sp.add_parser("hooks"); hks.add_argument("state", nargs="?", choices=["on", "off"])
    mc = sp.add_parser("mcp"); mc.add_argument("--http", action="store_true"); mc.add_argument("--port", type=int, default=8765)
    dr = sp.add_parser("doctor"); dr.add_argument("--local", action="store_true")
    dr.add_argument("--context", action="store_true"); dr.add_argument("--json", action="store_true")
    pg = sp.add_parser("plugins"); pg.add_argument("--json", action="store_true")
    pg.add_argument("action", nargs="?", default="list",
                    choices=["list", "add", "update", "outdated", "remove", "enable", "disable"])
    exp = sp.add_parser("export"); exp.add_argument("what", choices=["pdf", "print", "tour", "codetour", "confluence", "notion"])
    exp.add_argument("page", nargs="?")
    pg.add_argument("target", nargs="?"); pg.add_argument("--to", default="")
    rn = sp.add_parser("run"); rn.add_argument("--parallel", type=int, default=2); rn.add_argument("--per-runner", default="")
    rn.add_argument("--max-units", type=int); rn.add_argument("--lang", default="es")
    rn.add_argument("--include-interviews", action="store_true"); rn.add_argument("--poll-seconds", type=int, default=900)
    rn.add_argument("--policy", choices=["on-conflict", "never"], default="on-conflict")
    rn.add_argument("--only", nargs="+", default=None, help="run only these units (when they are ready)")
    ev = sp.add_parser("eval"); ev.add_argument("action", nargs="?", default="list", choices=["list", "run", "draft", "confirm", "comply"])
    ev.add_argument("ids", nargs="*"); ev.add_argument("--runner", default=""); ev.add_argument("--judge", default="")
    ev.add_argument("--all", action="store_true"); ev.add_argument("--json", action="store_true"); ev.add_argument("--by", default="")
    abp = sp.add_parser("ab"); abp.add_argument("--qa", default=""); abp.add_argument("--golden", action="store_true")
    abp.add_argument("action", nargs="?", choices=["sample", "sampling"]); abp.add_argument("state", nargs="?", choices=["on", "off"])
    abp.add_argument("--task", default=""); abp.add_argument("--check", default="")
    abp.add_argument("--replay", action="store_true"); abp.add_argument("--max", type=int, default=3)
    abp.add_argument("--runner", default=""); abp.add_argument("--judge", default=""); abp.add_argument("--json", action="store_true")
    prp = sp.add_parser("pr"); prp.add_argument("action", choices=["fresh", "propose"]); prp.add_argument("repo")
    prp.add_argument("--head", default=""); prp.add_argument("--ref", default=""); prp.add_argument("--runner", default="")
    prp.add_argument("--dry-run", action="store_true"); prp.add_argument("--comment", action="store_true")
    prp.add_argument("--preview", action="store_true")
    prp.add_argument("--base", default=""); prp.add_argument("--files", nargs="+"); prp.add_argument("--json", action="store_true")
    prp.add_argument("--post", action="store_true"); prp.add_argument("--lang", default="en", choices=["en", "es"])
    bl = sp.add_parser("blocks"); bl.add_argument("--force", action="store_true"); bl.add_argument("--json", action="store_true")
    fr = sp.add_parser("fresh"); fr.add_argument("--json", action="store_true"); fr.add_argument("--ack", nargs="+", default=[])
    fr.add_argument("--by", default=""); fr.add_argument("--plan", action="store_true")
    kp = sp.add_parser("kpis"); kp.add_argument("--json", action="store_true"); kp.add_argument("--months", type=int, default=3)
    kp.add_argument("--no-check", action="store_true"); kp.add_argument("--compare", nargs=2, metavar="RUN")
    rs = sp.add_parser("runs"); rs.add_argument("run_id", nargs="?"); rs.add_argument("--json", action="store_true")
    pp = sp.add_parser("pipeline"); pp.add_argument("action", choices=["show", "validate"]); pp.add_argument("--json", action="store_true")
    m = sp.add_parser("mark-documented"); m.add_argument("repos", nargs="*")
    s = sp.add_parser("status"); s.add_argument("--json", action="store_true")
    k = sp.add_parser("check"); k.add_argument("--strict", action="store_true")
    k.add_argument("--secrets", action="store_true", help="only the secret scan (CI gate before committing)")
    c = sp.add_parser("confirm"); c.add_argument("files", nargs="+"); c.add_argument("--by", required=True)
    t = sp.add_parser("translated"); t.add_argument("files", nargs="+")
    u = sp.add_parser("up"); u.add_argument("--port", type=int, default=8080); u.add_argument("--docker", action="store_true")
    u.add_argument("--static", "--no-docker", dest="static", action="store_true"); u.add_argument("--foreground", action="store_true")
    w = sp.add_parser("wiki"); w.add_argument("repos", nargs="+"); w.add_argument("--engine", default="")
    w.add_argument("--init", dest="mode", action="store_const", const="init", default="")
    w.add_argument("--update", dest="mode", action="store_const", const="update")
    w.add_argument("--open", dest="mode", action="store_const", const="open")
    w.add_argument("--close", dest="mode", action="store_const", const="close")
    w.add_argument("--force", action="store_true")
    mg = sp.add_parser("migrate"); mg.add_argument("--yes", action="store_true"); mg.add_argument("--dry-run", action="store_true")
    mg.add_argument("--finish", action="store_true", help=argparse.SUPPRESS)
    un = sp.add_parser("uninstall"); un.add_argument("--yes", action="store_true"); un.add_argument("--dry-run", action="store_true")
    un.add_argument("--global", dest="user_level", action="store_true"); un.add_argument("--no-backup", action="store_true")
    un.add_argument("--backup-dir", type=Path)
    ci = sp.add_parser("ci"); ci.add_argument("forge", nargs="?", choices=["gitlab", "github"])
    pl = sp.add_parser("plan"); pl.add_argument("action", nargs="?", default="show",
                                                choices=["show", "sync", "next", "start", "note", "done", "block", "drop", "add", "redo", "approve"])
    pl.add_argument("unit", nargs="?"); pl.add_argument("title", nargs="?")
    pl.add_argument("--note"); pl.add_argument("--type", default="flow"); pl.add_argument("--deps", nargs="*")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--also", nargs="*", default=[])
    cp = sp.add_parser("checkpoint"); cp.add_argument("message", nargs="?", default="progress")
    rm = sp.add_parser("remote"); rm.add_argument("url", nargs="?")
    sh = sp.add_parser("share"); sh.add_argument("--auto", choices=["on", "off"])
    tr = sp.add_parser("trust"); tr.add_argument("--yes", action="store_true")
    jn = sp.add_parser("join"); jn.add_argument("url"); jn.add_argument("folder", nargs="?", type=Path)
    us = sp.add_parser("stats"); us.add_argument("--json", action="store_true")
    us.add_argument("--months", type=int, default=3); us.add_argument("--record", choices=["on", "off"])
    fb = sp.add_parser("feedback"); fb.add_argument("file"); fb.add_argument("text"); fb.add_argument("--by", default="")
    ad = sp.add_parser("arch-draft"); ad.add_argument("--save", action="store_true"); ad.add_argument("--overwrite", action="store_true")
    rd = sp.add_parser("radar"); rd.add_argument("--json", action="store_true")
    inv = sp.add_parser("inventory"); inv.add_argument("--json", action="store_true")
    inv.add_argument("--cves", action="store_true")
    iv = sp.add_parser("interview"); iv.add_argument("action", choices=["mode", "export", "import", "status"])
    iv.add_argument("args", nargs="*"); iv.add_argument("--lang", default="es", choices=["es", "en"])
    iv.add_argument("--json", action="store_true")
    st = sp.add_parser("stack"); st.add_argument("repo"); st.add_argument("text", nargs="?", default="")
    st.add_argument("--reset", action="store_true")
    pr = sp.add_parser("prompt"); pr.add_argument("unit"); pr.add_argument("--lang", default="es")
    pr.add_argument("--unattended", action="store_true")
    ap = sp.add_parser("autopilot"); ap.add_argument("--lang", default="es"); ap.add_argument("--max-units", type=int)
    ap.add_argument("--poll-seconds", type=int, default=900); ap.add_argument("--include-interviews", action="store_true")
    a = p.parse_args()
    if a.cmd not in ("help", "mcp", "wizard"):
        from lib import usage
        usage.record(f"cli:{a.cmd}")

    if a.cmd == "help":
        print(__doc__)
    elif a.cmd in ("install", "upgrade"):
        from lib.install import install
        if a.cmd == "install":
            install(HERE.parent, a.destination, a.profile, dry_run=a.dry_run)
        else:
            install(a.source, ROOT, update=True, dry_run=a.dry_run)
    elif a.cmd == "self-update":
        from lib.upgrade import self_update
        self_update(print)
    elif a.cmd == "unlink":
        from lib.install import unlink
        removed = unlink(ROOT)
        print("Kit code removed from this project — it now resolves against the global kit."
              if removed else "Nothing to remove — this project has no local kit copy.")
    elif a.cmd == "profile":
        env.set_profile(a.name)
        plan.sync()
        print(f"Profile: {a.name}. Progress kept. Run setup to prepare the selected tools.")
    elif a.cmd == "wizard":
        from lib.wizard import W
        W().run()
    elif a.cmd == "setup":
        if a.profile:
            env.set_profile(a.profile)
        env.init_templates()
        env.setup(ci=a.ci)
        if not a.ci:
            plan.sync()
            plan.set_status("setup", "done", "cli setup")
    elif a.cmd == "init":
        env.init_templates()
        docs.save_workspace(docs.workspace())   # persist workspace.yaml even with 0 repos yet — global
        plan.sync()                             # install's marker lookup (find_project_marker) needs it on disk
    elif a.cmd == "sync":
        docs.sync_repos()
        from lib import genblocks
        if r := genblocks.refresh()["updated"]:
            print(f"✔ generated blocks refreshed in {len(r)} page(s)")
    elif a.cmd == "detect":
        ws = docs.workspace()
        known = set(docs.repo_names())
        new = [r for r in docs.detect_repos() if r["name"] not in known]
        ws["repos"] += new
        docs.save_workspace(ws)
        print(f"added {len(new)} repo(s): {', '.join(r['name'] for r in new) or '—'}")
    elif a.cmd == "changes":
        print(json.dumps(docs.changes(), indent=2))
    elif a.cmd == "mark-documented":
        print("marked documented:", ", ".join(docs.mark_documented(a.repos)))
    elif a.cmd == "status":
        rows = docs.collect()
        if a.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            icon = {"confirmed": "✅", "needs-reconfirm": "⚠️ ", "draft": "✨"}
            for r in rows:
                extra = ([f"ORPHAN({len(r['orphan_sources'])})"] if r["orphan_sources"] else []) + \
                        [f"{k}:{v}" for k, v in r["i18n"].items() if v != "current"]
                print(f"{icon[r['trust']]} {r['path']:<60} {' '.join(extra)}")
            s = docs.summary(rows)
            print(f"\n{s['total']} docs — confirmed {s['confirmed']}, needs-reconfirm {s['needs-reconfirm']}, "
                  f"draft {s['draft']}, orphans {s['orphans']}, untranslated {s['untranslated']}")
    elif a.cmd == "check":
        errors, warns = docs.check(a.strict, secrets_only=a.secrets)
        for w in warns:
            print("WARN ", w)
        for e in errors:
            print("ERROR", e)
        return 1 if errors else 0
    elif a.cmd == "confirm":
        for f in docs.confirm(a.files, a.by):
            print(f"confirmed {f} by {a.by}")
    elif a.cmd == "translated":
        for f in docs.translated(a.files):
            print("stamped", f)
    elif a.cmd == "llms":
        print(f"wrote docs/llms.txt ({docs.llms()} entries)")
    elif a.cmd == "graph":
        env.graph(rebuild=True)
    elif a.cmd == "arch":
        env.arch_start()
    elif a.cmd == "arch-validate":
        ok, msg = env.arch_validate()
        print(msg or ("✓ Valid" if ok else "invalid"))
        return 0 if ok else 1
    elif a.cmd == "portal":
        env.portal()
    elif a.cmd == "up":
        if a.foreground:
            from lib import serve
            serve.run_server(a.port, static=a.static)
        elif a.docker or a.static:
            if not (CACHE / "site" / "index.html").exists():
                env.portal()
            (env.docker_up if a.docker else env.serve_local)(a.port)
        else:
            env.serve_editor(a.port)
    elif a.cmd == "wiki":
        if a.mode in ("open", "close"):
            for r in a.repos:
                if a.mode == "open":
                    env.wiki_open(r)
                    print(f"{r}/openwiki/: real folder — run the OpenWiki MCP lifecycle, then `wiki {r} --close`")
                elif env.wiki_close(r):
                    if env.wiki_pages(r):          # a manual MCP session follows the current PLAYBOOK scope
                        env.stamp_wiki(r, mode="manual", kit=VERSIONS["kit"])
                    print(f"{r}/openwiki/: moved to cam-docs/wikis/{r}/, repo restored")
            return 0
        failed = []
        for i, r in enumerate(a.repos):
            try:
                if not env.openwiki_generate(r, a.mode, engine=a.engine, force=a.force):
                    failed.append(r)
            except env.WikiAbort as e:
                print(f"✖ {e}" + (f"\n  not started: {', '.join(a.repos[i + 1:])}" if a.repos[i + 1:] else ""), file=sys.stderr)
                return 1
            except RuntimeError as e:
                print(f"✖ {e}", file=sys.stderr)
                failed.append(r)
        return 1 if failed else 0
    elif a.cmd == "migrate":
        from lib import migrate
        return migrate.main(yes=a.yes, dry_run=a.dry_run, finish=a.finish)
    elif a.cmd == "uninstall":
        from lib import uninstall
        return uninstall.main(include_global=a.user_level, dry_run=a.dry_run, yes=a.yes, backup=not a.no_backup,
                              backup_dir=a.backup_dir)
    elif a.cmd == "history":
        from lib import history
        from lib.common import rel_file
        print(f"✔ {rel_file(history.write(a.months))}: last {a.months} months of git history")
    elif a.cmd == "repair":
        from lib import install_state
        left = install_state.repair()
        print("✔ kit files and links restored" if not left else "\n".join(
            [f"⚠ still off ({len(left)}):"] + [f"    {d['state']:<10} {d['path']}" for d in left]
            + ([f"  links held back: review the agent config with `{cli_cmd()} trust`"]
               if any(d["state"] == "not linked" for d in left) else [])))
    elif a.cmd == "removed":
        from lib import removed
        print(f"✔ {removed.add(a.what, a.why, a.decision)}: {a.what}")
    elif a.cmd == "review":
        from lib import review
        if a.action == "list":
            print(json.dumps(review.open_requests(), indent=2, ensure_ascii=False))
        elif not a.target:
            print("usage: review request PAGE [--note TEXT] | review wait ID [--timeout S]", file=sys.stderr)
            return 2
        elif a.action == "request":
            rid = review.request(a.target, by=a.by, note=a.note)
            print(json.dumps({"id": rid, "path": a.target, "next": f"{cli_cmd()} review wait {rid}"}))
        else:
            try:
                print(json.dumps(review.wait(a.target, timeout=a.timeout), ensure_ascii=False))
            except KeyError:
                print(f"✖ no review request {a.target}", file=sys.stderr)
                return 2
    elif a.cmd == "hook":
        from lib import hooks
        return hooks.main(a.name)
    elif a.cmd == "hooks":
        from lib import hooks
        if a.state:
            hooks.set_enabled(a.state == "on")
        print(f"method hooks: {'on' if hooks.enabled() else 'off'}" + (
            " — SessionStart (plan state), PostToolUse (check the page just edited), Stop (remind once to update docs)"
            if hooks.enabled() else ""))
    elif a.cmd == "mcp" and a.http:
        from lib import mcp
        srv = mcp.http_server(port=a.port)
        print(f"camarones MCP on http://127.0.0.1:{srv.server_address[1]}/mcp — header "
              f"`Authorization: Bearer <token>`, token in {mcp.TOKEN_FILE}", file=sys.stderr)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    elif a.cmd == "mcp":
        from lib import mcp
        mcp.serve_stdio()
    elif a.cmd == "down":
        env.docker_down()
    elif a.cmd == "ci":
        env.install_ci(a.forge)
    elif a.cmd == "run":
        from lib.harness import scheduler
        try:
            slots = scheduler.parse_slots(a.per_runner)
        except ValueError as e:
            print(f"✖ --per-runner {e}", file=sys.stderr)
            return 2
        scheduler.run_parallel(lang=a.lang, max_parallel=max(1, a.parallel), per_runner=slots, max_units=a.max_units,
                               poll_seconds=a.poll_seconds, include_interviews=a.include_interviews, policy=a.policy,
                               only=set(a.only) if a.only else None)
    elif a.cmd == "runs":
        return cmd_runs(a)
    elif a.cmd == "kpis":
        return cmd_kpis(a)
    elif a.cmd == "fresh":
        return cmd_fresh(a)
    elif a.cmd == "blocks":
        return cmd_blocks(a)
    elif a.cmd == "pr":
        return cmd_pr(a)
    elif a.cmd == "eval":
        return cmd_eval(a)
    elif a.cmd == "ab":
        return cmd_ab(a)
    elif a.cmd == "pipeline":
        return cmd_pipeline(a)
    elif a.cmd == "plugins" and a.action in ("enable", "disable"):
        from lib.harness import plugins
        ok = (plugins.enable if a.action == "enable" else plugins.disable)(a.target or "")
        if not ok:
            print(f"✖ no plugin called {a.target}", file=sys.stderr)
            return 2
        print(f"✔ {a.target} {'enabled' if a.action == 'enable' else 'disabled'} on this machine")
    elif a.cmd == "plugins" and a.action != "list":
        return cmd_plugin_store(a)
    elif a.cmd == "export":
        from lib import exporters
        try:
            if a.what in ("pdf", "print"):
                out = exporters.export_pdf() if a.what == "pdf" else exporters.export_print()
                print(f"✔ {out}" + ("" if out.suffix == ".pdf" or a.what == "print" else
                                    "  (no headless Chrome/Chromium/Edge found: print this page to PDF from a browser)"))
            elif a.what in ("tour", "codetour"):
                if not a.page:
                    print(f"usage: export {a.what} flows/<flow>.md", file=sys.stderr)
                    return 2
                if a.what == "tour":
                    print(f"✔ {exporters.export_tour(a.page)}  (open it; → and ← move between steps)")
                else:
                    print(f"✔ {exporters.export_codetour(a.page)}  (VS Code with the CodeTour extension: "
                          f"open the workspace folder, then CodeTour: Start Tour)")
            else:
                print(f"✔ {exporters.export_to(a.what)} page(s) published to {a.what}")
        except exporters.ExportError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
    elif a.cmd == "plugins":
        from lib.harness import plugins
        rows = plugins.rows()
        if a.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        for r in rows:
            mark = {"active": "✔", "invalid": "✖"}.get(r["status"], "·")
            print(f"{mark} {r['name']:<16} {r['version']:<8} {r['source']:<8} {', '.join(r['provides']) or '-':<22} "
                  f"{'runs code' if r['runs_code'] else 'config only':<12} {r['status']}")
            for e in r["errors"]:
                print(f"    {e}")
        if not any(r["source"] == "project" for r in rows):
            print(f"No project plugins yet: add a folder with a plugin.yaml in {plugins.PROJECT_DIR.relative_to(ROOT.parent)}")
    elif a.cmd == "doctor" and a.context:
        from lib import budget
        r = budget.standing()
        print(json.dumps(r, indent=2) if a.json else "\n".join(budget.report(r)))
    elif a.cmd == "doctor" and a.local:
        from lib.adapters.runners import local
        print("\n".join(local.report()))
    elif a.cmd == "doctor":
        for k, v in env.prerequisites().items():
            print(f"{'✔' if v['ok'] else ('✖' if v['need'] else '·')} {k:<7} {v.get('found', '')}  {'' if v['ok'] else v['hint']}")
            if v.get("note"):
                print(f"          {v['note']}")
        for tname in ("graphify", "likec4", "mmdc"):
            print(f"  {tname:<9} {env.tool_version(tname) or 'missing'} (pinned {VERSIONS[tname]})")
        from lib import install_state
        from lib.common import WS_FILE
        if WS_FILE.exists():
            off = install_state.drift()
            print("✔ kit files and links as installed" if not off else
                  f"⚠ {len(off)} kit file(s) or link(s) off — `{cli_cmd()} repair` puts them back:")
            for d in off:
                print(f"    {d['state']:<10} {d['path']}  ({d['what']})")
        print(f"  openwiki  {'ok' if env.openwiki_installed() else 'missing'} (pinned {VERSIONS['openwiki']})")
        print(f"  gitleaks  {'ok' if env.tool_ok('gitleaks') else 'missing'} (pinned {VERSIONS['gitleaks']})")
    elif a.cmd == "plan":
        return cmd_plan(a)
    elif a.cmd == "arch-draft":
        from lib import quickarch
        m = quickarch.draft()
        print((m["dir"] / "model.c4").read_text(encoding="utf-8"))
        if a.save:
            print("\n".join(quickarch.save(m, overwrite=a.overwrite)))
    elif a.cmd == "interview":
        return cmd_interview(a)
    elif a.cmd == "radar":
        from lib import radar
        page = radar.run(log=(lambda _: None) if a.json else print)
        if a.json:
            print(json.dumps(load_json(radar.CACHE_FILE, {}), indent=2, ensure_ascii=False))
        else:
            for name, r in load_json(radar.CACHE_FILE, {}).items():
                print(f"{name:<20} {r['stack']}")
                print(f"{'':<20} " + (", ".join(t["label"] for t in r["tools"]) or "-"))
            print(f"→ {page.relative_to(ROOT).as_posix()}")
    elif a.cmd == "inventory":
        from lib import inventory
        page = inventory.run(log=(lambda _: None) if a.json else print, cves=a.cves)
        data = inventory.load()
        if a.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"→ {page.relative_to(ROOT).as_posix()}")
        serious = [v for r in data["libraries"] for v in r.get("vulns") or [] if v["severity"] in ("critical", "high")]
        return 1 if a.cves and serious else 0
    elif a.cmd == "stack":
        from lib import radar
        if not a.reset and not a.text:
            p.error("stack: give the stack text or --reset")
        try:
            radar.set_stack(a.repo, None if a.reset else a.text)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        print(f"{a.repo}: " + ("stack reset to the detected one" if a.reset else a.text.strip()))
    elif a.cmd == "version":
        print(f"Camarón {VERSIONS['kit']} — " + ", ".join(f"{k} {v}" for k, v in VERSIONS.items() if k != "kit"))
    elif a.cmd == "checkpoint":
        print("✔ committed locally" if env.checkpoint_commit(a.message) else "no checkpoint commit")
    elif a.cmd == "remote":
        if a.url:
            env.set_remote(a.url)
        print(env.docs_remote() or "no remote — set one with: remote URL")
    elif a.cmd == "share" and a.auto:
        env.set_auto_share(a.auto == "on")
        print(f"auto-share: {a.auto}")
    elif a.cmd == "share":
        r = env.share()
        why = f" ({r['reason']})" if r.get("reason") else ""
        print(f"{r['status']}{why}{': ' + r['detail'] if r['detail'] else ''}")
        return 0 if r["status"] in ("pushed", "up-to-date", "nothing") else 1
    elif a.cmd == "stats" and a.record:
        usage.set_enabled(a.record == "on")
        print(f"usage stats: {a.record}")
    elif a.cmd == "stats":
        r = usage.report(months=a.months)
        print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else usage.render_md(r))
    elif a.cmd == "trust":
        return cmd_trust(a)
    elif a.cmd == "feedback":
        docs.add_feedback(a.file, a.text, a.by or os.environ.get("USER", "human"))
        plan.ensure("review-fixes", "review-fixes")
        print(f"feedback recorded in {plan._at(docs.FEEDBACK)}; unit review-fixes is ready")
    elif a.cmd == "prompt":
        print(plan.prompt(a.unit, lang=a.lang, unattended=a.unattended))
    elif a.cmd == "autopilot":
        try:
            plan.run_autopilot(lang=a.lang, max_units=a.max_units, poll_seconds=a.poll_seconds,
                               include_interviews=a.include_interviews)
        except KeyboardInterrupt:
            print("\nAutopilot interrupted — progress is saved; `plan next` shows where to resume.")
    return 0


def cmd_interview(a) -> int:
    from lib import questionnaire
    try:
        if a.action == "mode":
            if a.args:
                plan.set_interview_mode(a.args[0])
            print(docs.interview_mode())
        elif a.action == "export":
            for f in questionnaire.export(a.lang):
                print(f)
        elif a.action == "import":
            if not a.args:
                print("usage: interview import FILE|DIR …", file=sys.stderr); return 2
            results = questionnaire.import_files(a.args)
            for f, who, err in results:
                print(f"✔ {who}: {f.name}" if who else f"✖ {f.name}: {err}")
            if not results:
                print("no answers files found", file=sys.stderr)
            return 0 if results and all(who for _, who, _ in results) else 1
        else:
            s = questionnaire.status()
            if a.json:
                print(json.dumps(s, indent=2, ensure_ascii=False))
                return 0
            print(f"{s['questions']} questions · answered by: "
                  + (", ".join(f"{r['name']} ({r['answered']})" for r in s["respondents"]) or "nobody yet"))
            print("unanswered: " + (", ".join(s["unanswered"]) or "-"))
            for c in s["conflicts"]:
                print(f"disagree {c['id']}: " + "; ".join(f"{v} ← {', '.join(n)}" for v, n in c["answers"].items()))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


def cmd_runs(a) -> int:
    from lib.harness import runs
    if a.run_id:
        if a.run_id not in runs.ids():
            print(f"✖ no run {a.run_id} (see `{cli_cmd()} runs`)", file=sys.stderr)
            return 1
        d = runs.detail(a.run_id)
        if a.json:
            print(json.dumps(d, indent=2, ensure_ascii=False))
            return 0
        print(_run_line(runs.summary(a.run_id)))
        width = max((len(u["unit"]) for u in d["units"]), default=0)
        for u in d["units"]:
            print(f"  {u['unit']:<{width}}  {u['runner'] or '-':<10} {u['isolation'] or '-':<9} {u['outcome'] or 'running':<8} "
                  f"{u['status'] or '-':<8} {u['merge'] or '-':<11} {u['seconds'] or 0:>7}s  {u['tokens_in']:>8} in "
                  f"{u['tokens_out']:>7} out  ${u['cost_usd']:.2f}")
        return 0
    rows = runs.rows()
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    elif not rows:
        print(f"No runs yet: `{cli_cmd()} run` or `{cli_cmd()} autopilot` record one each time.")
    for r in rows if not a.json else []:
        print(_run_line(r))
    return 0


def cmd_eval(a) -> int:
    from lib.harness import evals
    if a.action == "comply":
        from lib.harness import comply
        if len(a.ids) != 1:
            print("usage: eval comply UNIT [--runner T] [--json]  (run it on the sandbox, not on a real project)",
                  file=sys.stderr)
            return 2
        try:
            r = comply.run(a.ids[0], runner=a.runner or None, echo=(lambda _: None) if a.json else print)
        except (KeyError, ValueError) as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        if a.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            return 0
        print(f"{r['unit']}: {r['status']} · {r['pages']} page(s) written · {r['compliant']} follow the method"
              + (f" · score {r['score']}" if r["score"] is not None else ""))
        for path, v in r["by_page"].items():
            for issue in v["issues"] + [f"missing source {s}" for s in v["orphan_sources"]]:
                print(f"  {path}: {issue}")
        return 0
    if a.action == "draft":
        u = evals.draft_unit()
        print(f"✔ unit {u['id']} added: run it from the wizard, `{cli_cmd()} run` or `{cli_cmd()} autopilot`")
        return 0
    if a.action == "confirm":
        if not a.ids or not a.by:
            print("usage: eval confirm <id>… --by <name>", file=sys.stderr)
            return 2
        try:
            print(f"✔ confirmed: {', '.join(evals.confirm(a.ids, a.by))}")
        except KeyError as e:
            print(f"✖ {e.args[0]}", file=sys.stderr)
            return 1
        return 0
    qs = evals.load()
    for p in evals.problems(qs):
        print(f"✖ evals/questions.yaml — {p}", file=sys.stderr)
    if a.action == "list":
        if a.json:
            print(json.dumps(qs, indent=2, ensure_ascii=False))
        elif not qs:
            print(f"No golden questions yet: `{cli_cmd()} eval draft` adds a unit that proposes them.")
        for q in qs if not a.json else []:
            print(f"  {'✔' if q.get('x-confirmed') else '·'} {q.get('id', '?'):<22} {q.get('q', '')}"
                  + ("" if q.get("x-confirmed") else "  (draft)"))
        return 0
    runner = a.runner
    if not runner:
        found = plan._agents(lambda _: None)
        if not found:
            print("✖ no agent installed for the questions (see `camaron doctor`)", file=sys.stderr)
            return 1
        runner = found[0]
    judge = None
    if a.judge:
        judge = a.judge if a.judge != "auto" else next(iter(plan._agents(lambda _: None, "judge")), None)
    if not (evals.confirmed(qs) or (a.all and qs)):
        print(f"No confirmed questions to ask: `{cli_cmd()} eval list`, then `{cli_cmd()} eval confirm <id> --by <name>`.")
        return 1
    r = evals.run(runner, judge=judge, include_drafts=a.all, echo=(lambda _: None) if a.json else print)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(f"Score {r['score']} over {len(r['questions'])} question(s) with {runner}"
              + (f", judge {r['judge']}" if r["judge"] is not None else "")
              + (f" — {r['drafts_skipped']} draft(s) not asked" if r["drafts_skipped"] else ""))
    return 0


def cmd_ab(a) -> int:
    from lib.harness import ab, evals
    if a.action == "sample":                        # Claude Code's UserPromptSubmit hook: silent, never fails
        ab.sample_from_hook()
        return 0
    if a.action == "sampling":
        if a.state not in ("on", "off"):
            s = ab.sampling()
            print(f"project: {'on' if s['enabled'] else 'off'} (rate {s['rate']}) · this machine: "
                  f"{'on' if load_json(PREFS, {}).get('ab_sampling') else 'off'} · samples kept: {len(ab.samples())}")
            return 0
        on = a.state == "on"
        ab.set_machine_sampling(on)
        (ab.install_hook if on else ab.remove_hook)()
        print(f"✔ sampling {'on' if on else 'off'} on this machine" + (
            "" if not on or ab.sampling()["enabled"] else
            " — the project still has it off: set `ab: {sampling: {enabled: true, rate: 0.05}}` in workspace.yaml"))
        return 0
    if a.task or a.replay:
        if not ab.enabled():
            print("✖ A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)", file=sys.stderr)
            return 1
        runner = a.runner or next(iter(plan._agents(lambda _: None)), None)
        if not runner:
            print("✖ no agent installed (see `camaron doctor`)", file=sys.stderr)
            return 1
        import shlex
        check = shlex.split(a.check) if a.check else None
        tasks = [a.task] if a.task else [s["prompt"] for s in ab.samples()[-a.max:]]
        if not tasks:
            print("No sampled prompts on this machine yet (`camaron ab sampling on`).", file=sys.stderr)
            return 1
        out = [ab.run_task(t, runner, check=check, echo=(lambda _: None) if a.json else print) for t in tasks]
        if a.json:
            print(json.dumps(out if len(out) > 1 else out[0], indent=2, ensure_ascii=False))
            return 0
        for r in out:
            print(f"\n{r['task'][:100]}")
            for side in ("with", "without"):
                s = r[side]
                print(f"  {side + ' cam-docs':<18} {s['tokens_in'] + s['tokens_cache']:>9} context tokens  {s['seconds']:>6}s  "
                      f"{s['tool_calls']:>3} tool calls  {s['files_changed']:>2} files  check: {s['check'] or '-'}")
        return 0
    if not a.qa and not a.golden:
        print('usage: ab --qa "QUESTION" | --golden | --task "TASK" [--check CMD] | --replay | sampling on|off',
              file=sys.stderr)
        return 2
    if not ab.enabled():
        print("✖ A/B runs are turned off for this project (ab.enabled: false in workspace.yaml)", file=sys.stderr)
        return 1
    questions = [{"id": "qa", "q": a.qa}] if a.qa else evals.confirmed(evals.load())
    if not questions:
        print(f"No confirmed golden questions: `{cli_cmd()} eval list`.", file=sys.stderr)
        return 1
    runner = a.runner or next(iter(plan._agents(lambda _: None)), None)
    if not runner:
        print("✖ no agent installed (see `camaron doctor`)", file=sys.stderr)
        return 1
    judge = (a.judge if a.judge != "auto" else next(iter(plan._agents(lambda _: None, "judge")), None)) if a.judge else None
    r = ab.run(questions, runner, judge=judge, echo=(lambda _: None) if a.json else print)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    w, wo = r["totals"]["with"], r["totals"]["without"]
    print(f"{'':<14}{'with cam-docs':>16}{'without':>14}")
    for k in ab.METRICS:
        if w.get(k) is not None or wo.get(k) is not None:
            print(f"{k:<14}{'-' if w.get(k) is None else w[k]:>16}{'-' if wo.get(k) is None else wo[k]:>14}")
    if r["tokens_saved_pct"] is not None:
        print(f"cam-docs read {r['tokens_saved_pct']}% less context (input + cached tokens)" if r["tokens_saved_pct"] >= 0
              else f"cam-docs read {-r['tokens_saved_pct']}% more context (input + cached tokens)")
    return 0


def cmd_plugin_store(a) -> int:
    from lib.harness import plugin_store
    try:
        if a.action == "add":
            if not a.target:
                print("usage: plugins add <folder | git:<url>@<tag>[#subfolder]>", file=sys.stderr)
                return 2
            p = plugin_store.add(a.target)
            print(f"✔ {p.name} {p.manifest.get('version')} vendored in .camarones/plugins/{p.name} (plugins.lock)")
            if p.needs_trust:
                print(f"  It {'runs code' if p.runs_code else 'steers agents'}: approve it on this machine with "
                      f"`{cli_cmd()} trust` before it is used.")
        elif a.action == "update":
            changes = plugin_store.update(a.target or None, to=a.to or None)
            for c in changes:
                f = c["files"]
                print(f"✔ {c['name']} {c['from']} → {c['to']}: +{len(f['added'])} −{len(f['removed'])} ~{len(f['changed'])}")
                for kind, mark in (("added", "+"), ("removed", "-"), ("changed", "~")):
                    for name in f[kind]:
                        print(f"    {mark} {name}")
                if c["needs_trust"]:
                    print(f"  It changed: `{cli_cmd()} trust` asks you to approve it again.")
            if not changes:
                print("✔ plugins already match their source")
        elif a.action == "outdated":
            rows = plugin_store.outdated()
            if a.json:
                print(json.dumps(rows, indent=2))
                return 0
            for r in rows:
                print(f"  {r['name']:<16} {r['version']} → {r['latest']}   ({r['source']})")
            if not rows:
                print("✔ every vendored plugin is on its latest version")
        else:
            plugin_store.remove(a.target or "")
            print(f"✔ {a.target} removed from .camarones/plugins and plugins.lock")
    except plugin_store.PluginError as e:
        print(f"✖ {e}", file=sys.stderr)
        return 2
    return 0


def cmd_pr(a) -> int:
    from lib import pr
    if a.action == "propose":
        from lib import propose
        try:
            if a.dry_run:
                p = propose.plan_for(a.repo, ref=a.ref or None, base=a.base or None, runner=a.runner or None,
                                     lang=a.lang)
                print(json.dumps(p, indent=2, ensure_ascii=False) if a.json else
                      f"branch {p['branch']} · runner {p['target']} · base {p['base']} · ref {p['ref']}\n"
                      f"fetch: {' '.join(p['fetch']) if p['fetch'] else '(already local)'}\n"
                      f"agent: {' '.join(p['argv'])}\n\n{p['prompt']}")
                return 0
            r = propose.propose(a.repo, ref=a.ref or None, base=a.base or None, runner=a.runner or None, lang=a.lang,
                                comment=a.comment, with_preview=a.preview)
        except propose.ProposeError as e:
            print(f"✖ {e}", file=sys.stderr)
            return 2
        print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else
              "\n".join(f"{k}: {v}" for k, v in r.items() if v not in ("", None)))
        return 0
    if a.repo not in docs.repo_names():
        print(f"unknown repo {a.repo}: one of {', '.join(docs.repo_names()) or '—'}", file=sys.stderr)
        return 2
    base = a.base or (None if a.files else "main")
    result = pr.impact(a.repo, base=base, files=a.files, head=a.head or None)
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    body = pr.comment(result, a.lang)
    print(body)
    if a.post:
        print(pr.post(body, affected=bool(result["pages"])))
    return 0                                     # a warning, never a failed pipeline (H27)


def cmd_blocks(a) -> int:
    from lib import genblocks
    out = {"created": genblocks.write_reference(), **genblocks.refresh(force=a.force)}
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print(f"✔ {len(out['created'])} reference page(s) created, {len(out['updated'])} page(s) refreshed")
    for e in out["edited"]:
        print(f"  · kept, edited by hand: {e}")
    for h in out["human"]:
        print(f"  · not touched, owned by a person: {h}")
    if out["edited"]:
        print(f"Fix the source in the repo, or `{cli_cmd()} blocks --force` to take the code's version.")
    return 0


def cmd_fresh(a) -> int:
    from lib.harness import freshness
    if a.ack:
        if not a.by:
            print("usage: fresh --ack PAGE… --by NAME", file=sys.stderr)
            return 2
        done = freshness.ack(a.ack, a.by)
        print(f"✔ today's code is now the reference for: {', '.join(done) or 'no known page'}")
        return 0 if done else 1
    if a.plan:
        u = freshness.refresh_unit()
        print(f"✔ unit {u['id']}: {u['notes']}")
        return 0
    states = freshness.states()
    rows = [{"path": p, **s} for p, s in sorted(states.items())]
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    old = [r for r in rows if r["state"] in freshness.OUT_OF_DATE]
    counts = {k: sum(1 for r in rows if r["state"] == k) for k in ("fresh", "suspect", "stale", "unverified")}
    print("  ".join(f"{n} {k}" for k, n in counts.items()) + f"  (agents: {freshness.policy()})")
    for r in old:
        print(f"  {r['state']:<8} {r['path']}  ← {', '.join(freshness.code_paths(r['missing'] + r['changed']))}")
    if old:
        print(f"Refresh them (`{cli_cmd()} fresh --plan` adds a unit) or, if they still hold, "
              f"`{cli_cmd()} fresh --ack <page> --by <name>`.")
    return 0


def cmd_kpis(a) -> int:
    from lib.harness import kpis, runs
    if a.compare:
        missing = [r for r in a.compare if r not in runs.ids()]
        if missing:
            print(f"✖ no run {', '.join(missing)} (see `{cli_cmd()} runs`)", file=sys.stderr)
            return 1
        c = kpis.compare(*a.compare)
        if a.json:
            print(json.dumps(c, indent=2, ensure_ascii=False))
            return 0
        print(f"{'':<18}{c['a']['run']:>26}{c['b']['run']:>26}{'change':>12}")
        for k in kpis.NUMERIC:
            va, vb = c["a"].get(k), c["b"].get(k)
            d = c["delta"].get(k)
            print(f"{k:<18}{'-' if va is None else va:>26}{'-' if vb is None else vb:>26}"
                  f"{'' if d is None else f'{d:+g}':>12}")
        return 0
    r = kpis.report(months=a.months, run_check=not a.no_check)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    print("Cost and speed (all runs of the team, per month)")
    for m in r["runs"]:
        print(f"  {m['month']}  {m['runs']} runs  {m['done']}/{m['units']} units done  {m['limited']} limited  "
              f"{m['failed']} failed  {m['hours']} h  {m['tokens_in'] + m['tokens_cache']} in (cached included) / "
              f"{m['tokens_out']} out  ${m['cost_usd']:.2f}"
              + (f"  ${m['cost_per_unit']:.2f}/unit" if m["cost_per_unit"] is not None else "")
              + (f"  ×{m['parallelism']} parallel" if m["parallelism"] else ""))
    c = r["coverage"]
    print(f"Coverage and quality\n  {c['repos_with_brief']}/{c['repos']} repos with a brief  {c['flows']} flows  "
          f"{c['c4_files']} C4 files" + ("" if c["check_errors"] is None else
                                         f"  check: {c['check_errors']} errors, {c['check_warnings']} warnings"))
    t = r["trust"]
    print(f"Trust and freshness\n  {t['pages']} pages  {t['confirmed_pct']}% confirmed  {t['draft']} drafts  "
          f"{t['needs_reconfirm']} to re-confirm  {t['repos_changed']} repos changed since documented  "
          f"plan {t['plan_done']}/{t['plan_total']}"
          + (f"\n  people changed {round(100 * t['ai_edit_avg'])}% of the AI's words before confirming "
             f"({t['ai_pages_confirmed']} page{'' if t['ai_pages_confirmed'] == 1 else 's'})" if t.get("ai_edit_avg") is not None else ""))
    u = r["usefulness"]
    print(f"Usefulness (this month)\n  {u['agent_queries'] or 0} agent queries  {u['human_queries'] or 0} portal reads  "
          f"{u['searches'] or 0} searches, {u['no_results_pct'] or 0}% with no result"
          + (f"\n  golden questions: score {u['eval_score']}" + (f", judge {u['eval_judge']}" if u["eval_judge"] is not None
                                                                else "") + f" ({str(u['eval_at'])[:10]})"
             if u.get("eval_score") is not None else f"\n  golden questions: none run yet (`{cli_cmd()} eval`)"))
    return 0


def _run_line(r: dict) -> str:
    state = "interrupted" if r["interrupted"] else ("finished" if r["finished"] else "running?")
    return (f"{r['run']}  {(r['started'] or '')[:16].replace('T', ' ')}  {r['done']}/{r['units']} done  "
            f"{r['limited']} limited  {r['failed']} failed  {r['seconds']:.0f}s  {r['tokens_in']} in / {r['tokens_out']} out"
            f"  ${r['cost_usd']:.2f}  {state}")


def cmd_pipeline(a) -> int:
    problems = plan.pipeline_problems()
    if a.action == "validate":
        for p in problems:
            print(f"✖ .camarones/pipeline.yaml — {p}")
        if not problems:
            print("✔ pipeline valid" + ("" if plan.OVERRIDE.exists() else " (kit pipeline, no .camarones/pipeline.yaml)"))
        return 1 if problems else 0
    spec, _ = plan.project_pipeline()
    units = [] if problems else plan.pipeline_units()
    if a.json:
        print(json.dumps({"pipeline": spec.get("name"), "override": plan.OVERRIDE.exists(), "problems": problems,
                          "units": units}, indent=2, ensure_ascii=False))
        return 1 if problems else 0
    print(f"Pipeline {spec.get('name')}" + (" (with .camarones/pipeline.yaml)" if plan.OVERRIDE.exists() else ""))
    for p in problems:
        print(f"✖ {p}")
    width = max((len(u["id"]) for u in units), default=0)
    for u in units:
        how = u["runner"] or u["tier"]
        print(f"  {'·' if not u['disabled'] else '-'} {u['id']:<{width}}  {u['isolation']:<9} {how:<16} "
              f"{'disabled' if u['disabled'] else ('← ' + ', '.join(u['needs']) if u['needs'] else '')}")
    return 1 if problems else 0


def cmd_plan(a) -> int:
    for problem in plan.pipeline_problems():
        print(f"✖ .camarones/pipeline.yaml — {problem} (the plan is left as it was)", file=sys.stderr)
    if a.action == "sync" or not plan.PLAN.exists():
        plan.sync()
    if a.action in ("show", "sync"):
        data = plan.load()
        print(json.dumps(data, indent=2, ensure_ascii=False) if a.json else plan.render(data))
    elif a.action == "next":
        ready = plan.available()
        if a.json:
            print(json.dumps(ready, indent=2, ensure_ascii=False))
        elif not ready:
            print("Plan complete 🦐 — use `prompt update` after code changes.")
        else:
            d, t = plan.progress()
            print(f"Progress {d}/{t}. Ready next:")
            for i, u in enumerate(ready[:6], 1):
                print(f"  {i}. {u['id']:<28} {u['title']}{'  [in progress]' if u['status'] == 'doing' else ''}"
                      f"{'  [wizard]' if u['runner'] == 'wizard' else ''}")
                if u["status"] == "doing" and plan.last_note(u["id"]):
                    print(f"       last checkpoint: {plan.last_note(u['id'])}")
    elif a.action == "note":
        if not a.unit or not (a.title or a.note):
            print('usage: plan note <unit> "what is done / what is next"'); return 2
        f = plan.note(a.unit, a.title or a.note)
        print(f"checkpoint saved → {plan._at(f)}")
    elif a.action in ("start", "done", "block", "drop"):
        if not a.unit:
            print("unit id required"); return 2
        status = {"start": "doing", "done": "done", "block": "blocked", "drop": "dropped"}[a.action]
        u = plan.set_status(a.unit, status, a.note)
        print(f"{u['id']} → {u['status']}" + (f": {u['notes']}" if plan.awaiting(u) else ""))
        if u.get("reopened"):
            print("reopened to refine with what it settled: " + ", ".join(u["reopened"]))
        if status != "doing" and env.checkpoint_commit(f"{u['id']} {u['status']}"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "approve":
        if not a.unit:
            print("usage: plan approve <unit>"); return 2
        from lib.common import out
        try:
            u = plan.approve(a.unit, by=out(["git", "-C", str(ROOT), "config", "user.name"]) or "cli")
        except ValueError as e:
            print(f"✖ {e}", file=sys.stderr); return 2
        print(f"{u['id']} → done ({u['notes']})")
        if env.checkpoint_commit(f"{u['id']} approved"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "redo":
        if not a.unit:
            print("usage: plan redo <unit> [--also <dependent> …]"); return 2
        for u in plan.redo(a.unit, a.also):
            print(f"{u['id']} → todo (redo; was done {str(u['redo'])[:10]})")
        still = plan.dependents(plan.load(), a.unit)
        if still:
            print("Still done, built on it (reopen with --also if they need redoing): " + ", ".join(u["id"] for u in still))
        if env.checkpoint_commit(f"redo {a.unit}"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "add":
        if not a.unit or not a.title:
            print('usage: plan add <id> "<title>" [--type flow] [--deps a b]'); return 2
        u = plan.add(a.unit, a.title, a.type, a.deps)
        print(f"added {u['id']} ({u['type']}) deps={u['deps']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, KeyError, ValueError, OSError) as e:
        print(f"🦐✖ {e}", file=sys.stderr)
        sys.exit(1)
