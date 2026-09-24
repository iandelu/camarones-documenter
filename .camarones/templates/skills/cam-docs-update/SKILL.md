---
name: cam-docs-update
description: Keep {{PROJECT_NAME}}'s documentation alive — after implementing or changing behaviour in any repo, update the affected pages in cam-docs. Use at the end of every feature, fix or refactor that changes how the system works.
---

# Update the docs after a change

1. List what changed: `git diff` in the repo(s) you touched, or `{{CLI}} changes`.
2. Find affected pages: MCP `search_docs` / `doc_status`, or grep `{{CAM}}docs/` for the classes, endpoints, topics, tables you touched.
3. Edit those pages in `{{CAM}}docs/` following `{{CAM}}.camarones/CONVENTIONS.md`: keep frontmatter, update `x-sources`,
   never write `x-confirmed`, never edit `<!-- human -->` blocks or `x-owner: human` files (propose the change instead).
   A confirmed page you edit becomes `needs-reconfirm` — say so in your summary so a human re-checks it in the portal.
4. New behaviour with no page yet: add it where the conventions say, or `{{CLI}} plan add <id> "<title>"` for a bigger unit.
5. Run `{{CLI}} check` and `{{CLI}} llms`, then `{{CLI}} checkpoint "docs: <what changed>"` and
   `{{CLI}} mark-documented <repo>`.
