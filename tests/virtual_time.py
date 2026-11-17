"""An asyncio event loop with virtual time, for scheduler tests.

When no callback is ready, the loop jumps its clock to the next timer instead of waiting, so
every sleep and timeout is exact and an hour of schedule runs in milliseconds. Do not use it
with real network I/O: a jump does not wait for a socket.
"""

import asyncio
import selectors
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any


class _JumpingSelector(selectors.SelectSelector):
    def __init__(self, loop: "VirtualTimeLoop") -> None:
        super().__init__()
        self._loop = loop

    def select(self, timeout: float | None = None) -> list[tuple[selectors.SelectorKey, int]]:
        events = super().select(0)
        if events:
            return events
        if timeout is None:
            raise RuntimeError("deadlock: no callback is ready and no timer is scheduled")
        self._loop.now += timeout
        return events


class VirtualTimeLoop(asyncio.SelectorEventLoop):
    def __init__(self) -> None:
        self.now = 0.0
        super().__init__(selector=_JumpingSelector(self))

    def time(self) -> float:
        return self.now


def run_virtual[T](main: Callable[[], Coroutine[Any, Any, T]]) -> T:
    loop = VirtualTimeLoop()
    try:
        return loop.run_until_complete(main())
    finally:
        loop.close()


def clock_from(start: datetime) -> Callable[[], datetime]:
    """A wall clock that reads `start` when the virtual loop starts."""
    return lambda: start + timedelta(seconds=asyncio.get_running_loop().time())
