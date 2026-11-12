---
name: cam-retro
description: Step of cam-task — notes on where the workflow got in the way.
---

# Retro: where the workflow got in the way

At the end of every change, after `cam-ship` or when the change stops.

1. Look back at the steps of `cam-task` and its step skills. Write 0–3 notes, only for friction in the workflow: a
   missing step, a wrong gate, noise, a doc that misled you. None is a fine outcome. Code problems (a bug, a hard test)
   are not skill notes.
2. One note per friction, on the skill and step where it happened, from the workspace root:
   `{{CLI}} skills note <skill> "<text>" --source retro --step <step> --change <id>`
   `<skill>` is any skill `{{CLI}} skills list` shows (`cam-task`, `cam-verify`, `cam-docs-update`…); `<step>` its
   step number or short name;
   `<text>` one sentence: what happened and what would have helped.
3. Later, when you address PR review comments or board items about the change (reopened, a bug that links it, a card
   labelled `skill-feedback`), decide per entry:
   - a code matter → fix it, no note;
   - a step that should have caught it → the same command with `--source review|board --ref <link>`.
4. Tuning, when the person asks: `{{CLI}} skills notes [<skill>]` groups the notes by skill and step. Then
   `{{CLI}} skills fork <name>` copies the kit's text to `{{CAM}}.camarones/skills/<name>/SKILL.md`; edit it there and
   propose it in a docs PR. Never edit `.claude/skills/` or `.agents/skills/`: they are rewritten on every refresh.
