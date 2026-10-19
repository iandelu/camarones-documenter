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
  mcp                       stdio MCP server: agents search/read the docs and the code graph
  ci [gitlab|github]        install the umbrella CI pipeline
  plan [sync|next|start|note|done|block|drop|add|redo] …   session work plan (docs/.work/plan.yaml)
  plan note UNIT "text"     save a progress checkpoint of a unit (a closed session resumes from it)
  plan redo UNIT [--also U…]  reopen a finished unit (e.g. an interview) to review and update it
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
  stack REPO [TEXT|--reset] fix a repo's stack in workspace.yaml (--reset: back to the detected one)
  interview mode [team|live]   how interviews run: team questionnaire answered offline, or live with the agent
  interview export [--lang es|en]   questionnaire → offline HTML form + Markdown copy to share with the team
  interview import FILE|DIR…   import the team's answers (form JSON or filled Markdown)
  interview status [--json]    who answered, unanswered questions, disagreements
  doctor [--local]          check prerequisites and tool versions; --local: propose a free local model for this
                            machine (bounded/judge work, through OpenCode) without installing anything
  run [--parallel N] [--per-runner claude=2,codex=1] [--max-units N] [--lang es|en] [--include-interviews]
      [--policy on-conflict|never] [--poll-seconds N]
                            run ready units in parallel: discovery, repo briefs and flows each in their own copy of
                            cam-docs (merged back when done), other units one at a time. autopilot stays sequential
  runs [RUN] [--json]       what past runs did: units, outcome, merges, time, tokens and cost
  eval [list|run|draft|confirm ID…] [--runner T] [--judge T] [--all] [--json] [--by NAME]
                            golden questions (evals/questions.yaml): run asks the confirmed ones to an agent that may
                            only read the docs and scores cited pages + exact identifiers; draft adds a unit that
                            proposes questions; confirm approves them
  ab --qa "QUESTION" | --golden [--runner T] [--judge T] [--json]
                            the same question with cam-docs and without it (only the code, in a throwaway folder that
                            links the repos): tokens, time, tool calls and identifiers named, side by side
  fresh [--json] [--ack PAGE… --by NAME] [--plan]
                            pages whose cited code changed (suspect) or is gone (stale); agents are kept off them.
                            --ack: the page still holds for today's code; --plan: add a unit that refreshes them
  blocks [--force] [--json]  facts read from the repos, no AI: docs/repos/<repo>/reference.md (commands, env vars,
                            endpoints, topics) and every <!-- generated:… --> block in the docs. A block edited by hand
                            is kept and flagged by check; --force takes the code's version. `sync` refreshes them too
  pr fresh REPO [--base REF | --files F…] [--json] [--post] [--lang en|es]
                            what a pull request does to the docs, no AI: the pages whose cited code it changes (left
                            out of date by it, or already before). --post writes or updates one comment on the PR/MR
                            (GitHub Actions or GitLab CI); it never fails the pipeline
  kpis [--json] [--months N] [--no-check] [--compare RUN_A RUN_B]
                            is it working? cost and speed of runs (the team's, per month), coverage, trust, usage;
                            --compare puts two runs side by side
  pipeline show|validate [--json]   the project's plan as units (kit pipeline + .camarones/pipeline.yaml);
                            validate exits 1 when pipeline.yaml has problems (for CI)
  plugins [--json]          plugins of the kit and of this project (.camarones/plugins/): what they provide, whether
                            they run code, and whether they are loaded (code needs approval first)
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
from lib.common import VERSIONS, cli_cmd, ROOT, CACHE, load_json   # noqa: E402


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
    for c in ("sync", "detect", "changes", "llms", "graph", "arch", "arch-validate", "portal", "down", "wizard", "version",
              "mcp"):
        sp.add_parser(c)
    dr = sp.add_parser("doctor"); dr.add_argument("--local", action="store_true")
    pg = sp.add_parser("plugins"); pg.add_argument("--json", action="store_true")
    rn = sp.add_parser("run"); rn.add_argument("--parallel", type=int, default=2); rn.add_argument("--per-runner", default="")
    rn.add_argument("--max-units", type=int); rn.add_argument("--lang", default="es")
    rn.add_argument("--include-interviews", action="store_true"); rn.add_argument("--poll-seconds", type=int, default=900)
    rn.add_argument("--policy", choices=["on-conflict", "never"], default="on-conflict")
    ev = sp.add_parser("eval"); ev.add_argument("action", nargs="?", default="list", choices=["list", "run", "draft", "confirm"])
    ev.add_argument("ids", nargs="*"); ev.add_argument("--runner", default=""); ev.add_argument("--judge", default="")
    ev.add_argument("--all", action="store_true"); ev.add_argument("--json", action="store_true"); ev.add_argument("--by", default="")
    abp = sp.add_parser("ab"); abp.add_argument("--qa", default=""); abp.add_argument("--golden", action="store_true")
    abp.add_argument("--runner", default=""); abp.add_argument("--judge", default=""); abp.add_argument("--json", action="store_true")
    prp = sp.add_parser("pr"); prp.add_argument("action", choices=["fresh"]); prp.add_argument("repo")
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
                                                choices=["show", "sync", "next", "start", "note", "done", "block", "drop", "add", "redo"])
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
                               poll_seconds=a.poll_seconds, include_interviews=a.include_interviews, policy=a.policy)
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
        print(f"feedback recorded in {docs.FEEDBACK.relative_to(ROOT).as_posix()}; unit review-fixes is ready")
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
    if not a.qa and not a.golden:
        print('usage: ab --qa "QUESTION" | --golden [--runner T] [--judge T] [--json]', file=sys.stderr)
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


def cmd_pr(a) -> int:
    from lib import pr
    if a.repo not in docs.repo_names():
        print(f"unknown repo {a.repo}: one of {', '.join(docs.repo_names()) or '—'}", file=sys.stderr)
        return 2
    base = a.base or (None if a.files else "main")
    result = pr.impact(a.repo, base=base, files=a.files)
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
        print(f"checkpoint saved → {f.relative_to(ROOT).as_posix()}")
    elif a.action in ("start", "done", "block", "drop"):
        if not a.unit:
            print("unit id required"); return 2
        status = {"start": "doing", "done": "done", "block": "blocked", "drop": "dropped"}[a.action]
        u = plan.set_status(a.unit, status, a.note)
        print(f"{u['id']} → {status}")
        if status != "doing" and env.checkpoint_commit(f"{u['id']} {status}"):
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
