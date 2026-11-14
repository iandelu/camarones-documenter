"""DiagramEngine: what the app asks of LikeC4, the C4 modelling tool. Where the model lives, whether it is valid (the
`likec4 validate` check), the live editor (`likec4 start`) and the views the model declares."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DiagramEngine(Protocol):
    def arch_dir(self) -> Path: ...

    def arch_validate(self) -> tuple[bool, str]: ...

    def arch_start(self) -> None: ...

    def c4_views(self) -> list[dict]: ...
