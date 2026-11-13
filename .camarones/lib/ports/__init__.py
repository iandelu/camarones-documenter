"""What the app needs from the outside world, as typing.Protocol: one module per port; an adapter module satisfies
it."""
from __future__ import annotations

from typing import Callable

Log = Callable[[str], None]
