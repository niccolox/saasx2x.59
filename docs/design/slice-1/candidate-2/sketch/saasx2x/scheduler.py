"""When each check runs, and the worker loop that runs it.

Fixed rate without drift. Every due time is computed from the epoch, never
from the end of the last run:

    slot_start(t)  = floor(t / interval_s) * interval_s
    due_at(check)  = slot_start + offset(check_id)
    offset(id)     = blake2b(id) mod (interval_s - BUDGET.total_s - 10 s)

So one check runs exactly interval_s apart forever, and every check ends
inside its own slot. The offset depends on the check id only, not the probe,
so probes in different regions observe one target at the same instant. That
keeps multi-region agreement in later slices a comparison of simultaneous
facts.

The loop works in 60-second windows aligned to the minute. At each window it
reloads active checks from the store (a target added by the CLI runs in the
next window), asks the store which keys this probe already recorded, and
starts each missing check at its due time. A semaphore bounds checks in
flight. A slow target holds one permit for at most BUDGET.total_s and never
delays a check of another target unless all permits are busy.

Crash and restart. The first window after start looks back one interval.
A missing row whose slot still has BUDGET.total_s left runs at once. A
missing row of a slot that has ended stays missing. A late observation is
not an observation of that slot.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol

from saasx2x.domain import CheckId, CheckSpec, Frozen, ProbeId, ResultKey, SlotStart
from saasx2x.probe import ProbeEnv
from saasx2x.store import Store

WINDOW = timedelta(seconds=60)
SLOT_MARGIN = timedelta(seconds=10)


class Clock(Protocol):
    """Wall clock in UTC. Tests drive a fake one."""

    def now(self) -> datetime: ...
    async def sleep_until(self, at: datetime) -> None: ...


class Due(Frozen):
    spec: CheckSpec
    key: ResultKey
    due_at: datetime


def slot_start(at: datetime, interval_s: int) -> SlotStart:
    raise NotImplementedError


def offset(check_id: CheckId, interval_s: int) -> timedelta:
    """Stable across processes and restarts. Uses blake2b, not hash()."""
    raise NotImplementedError


def plan(
    checks: Sequence[CheckSpec],
    probe_id: ProbeId,
    recorded: set[tuple[CheckId, SlotStart]],
    since: datetime,
    until: datetime,
    now: datetime,
) -> list[Due]:
    """Pure. Dues in [since, until) with no recorded row, sorted by due_at.

    Drops a due whose slot ends before now + BUDGET.total_s.
    """
    raise NotImplementedError


async def run_worker(
    store: Store,
    probe_id: ProbeId,
    env: ProbeEnv,
    clock: Clock,
    max_in_flight: int = 32,
) -> None:
    """Run until cancelled. On cancel, wait up to BUDGET.total_s for checks in flight.

    One TaskGroup for the life of the worker, so a check that runs past its
    window does not block the next window.
    """
    # TODO:
    # since = clock.now() - max interval   (the restart look-back)
    # loop:
    #   until = next minute boundary after since
    #   checks = await store.active_checks()
    #   recorded = await store.recorded(probe_id, since=since - max interval)
    #   for due in plan(checks, probe_id, recorded, since, until, clock.now()):
    #       await clock.sleep_until(due.due_at)
    #       tg.create_task(_run_one(due, store, env, permits))
    #   await clock.sleep_until(until); since = until
    raise NotImplementedError


async def _run_one(due: Due, store: Store, env: ProbeEnv, permits: object) -> None:
    # TODO: async with permits: obs = await observe(due.spec, env)
    #       await store.record(due.key, due.spec.account_id, due.due_at, obs)
    #       A store error is logged and the row is lost for this slot. The next
    #       slot runs as normal.
    raise NotImplementedError
