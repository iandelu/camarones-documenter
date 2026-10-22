---
name: cam-docs-unit
description: Run the next documentation unit of {{PROJECT_NAME}}'s work plan (discovery, interviews, architecture, flows, reviews…). Use when asked to continue, resume or advance the documentation.
---

# Run a documentation unit

1. `{{CLI}} plan next` — pick the unit marked `[in progress]` first (resume from `{{CAM}}docs/.work/units/`), else the first ready one.
2. `{{CLI}} prompt <unit>` prints the full session brief; follow it (playbook: `{{CAM}}.camarones/PLAYBOOK.md`).
3. Checkpoint often with `{{CLI}} plan note <unit> "…"`; finish with `plan done`, the handoff and `checkpoint`.
