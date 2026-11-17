"""Fixed-rate scheduler and the one-check pipeline. The only module that imports probe and store.

Call chain for one check: Worker.tick -> Worker._run_one -> (Prober.observe, CheckResult, Store.write).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Protocol

from domain import DueCheck, ProbeId
from probe import Prober
from settings import Settings
from store import Store


class Clock(Protocol):
    def now(self) -> datetime: ...
    async def sleep_until(self, t: datetime) -> None: ...


class SystemClock:
    """UTC wall clock. sleep_until recomputes the remaining time from the wall clock after waking,
    so it does not accumulate drift."""

    def now(self) -> datetime:
        raise NotImplementedError

    async def sleep_until(self, t: datetime) -> None:
        raise NotImplementedError


class Worker:
    """One probe process.

    Loop shape, fixed-rate on a grid of tick_s seconds (default 60):
        register probe
        loop until stop:
            tick()                                  # never raises. Logs and continues.
            sleep_until(next multiple of tick_s)    # computed from the grid, not from tick end

    tick(): ask Store.due(), skip keys already in flight, spawn one task per due check.
    The tick does not wait for the tasks. A slow target holds one semaphore slot only.
    """

    def __init__(self, store: Store, prober: Prober, probe_id: ProbeId,
                 settings: Settings, clock: Clock) -> None:
        raise NotImplementedError

    async def run(self, stop: asyncio.Event) -> None:
        """Run until stop is set. Then wait up to 25 s for in-flight tasks and return.
        A task that did not finish writes no row. The next start re-runs it if the slot is open."""
        raise NotImplementedError

    async def tick(self) -> int:
        """One scheduling pass. Returns the number of checks dispatched. Public for tests."""
        raise NotImplementedError

    async def _run_one(self, due: DueCheck) -> None:
        """Acquire the semaphore. If due.slot is no longer current, drop the check and count it.
        Else: started_at, observe, finished_at, build CheckResult, Store.write.
        A write error is logged and dropped. The next tick sees no row and runs the check again."""
        raise NotImplementedError
