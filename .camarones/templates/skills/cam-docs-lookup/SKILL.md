---
name: cam-docs-lookup
description: Look up {{PROJECT_NAME}}'s documentation and code graph before implementing or answering questions about the system — architecture, domain, flows, data, repos, decisions. Use it before touching code in any repo of the workspace.
---

# Look up the project docs

1. Search first: MCP tool `search_docs` (server `camarones`) with the feature's key terms; open hits with `read_doc`.
   Without MCP: read `{{CAM}}docs/llms.txt` (index with trust per page) and grep `{{CAM}}docs/`.
2. Weigh trust: `confirmed` = verified by a human, the source of truth; `draft` = AI-written, verify against the code;
   `needs-reconfirm` = was confirmed, then edited.
3. For code structure use the graph instead of broad greps: MCP `repo_graph` or
   `graphify query "<question>" --graph {{CAM}}graph/<repo>/graph.json`.
4. Report what the docs say, with page paths, and flag any contradiction with the code you find.
