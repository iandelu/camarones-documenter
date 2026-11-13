"""Environment: templates, prerequisites, pinned tools, repo wiring, code graph, C4, portal, docker, CI."""
from __future__ import annotations

from .harness.locks import pid_alive  # noqa: F401  (pid_alive re-exported)
from .projects import git_failure  # noqa: F401  (git_failure re-exported)
