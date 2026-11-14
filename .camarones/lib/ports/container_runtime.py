"""ContainerRuntime: what the app asks of Docker. Whether the daemon is there to use, and the self-contained build
context (Dockerfile + nginx.conf + the built site) an image of the portal is made from."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ContainerRuntime(Protocol):
    def docker_ready(self) -> tuple[bool, str]: ...

    def image_context(self) -> Path: ...
