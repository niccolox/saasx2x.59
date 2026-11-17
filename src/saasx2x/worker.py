"""The schedule. This module is the only one that calls the check, the verdict and the store
together. It holds no state between windows. Postgres holds all state.

Each due time comes from the epoch, never from the end of the last run:

    slot start = floor(t / interval) * interval
    due_at     = slot start + offset(check id)
    offset     = blake2b(check id) mod (interval - CHECK_BUDGET - SLOT_MARGIN)

The offset depends on the check only, not on the probe, so later probes in other regions
check one target at the same instant.
"""

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from saasx2x.domain import ActiveCheck, CheckId, HttpsObservation, ProbeId, Slot
from saasx2x.https_check import Timeouts
from saasx2x.store import ResultKey, StoreUnavailable
from saasx2x.verdict import CheckResult

CHECK_BUDGET: Final = timedelta(seconds=Timeouts().total_s)
SLOT_MARGIN: Final = timedelta(seconds=10)
WINDOW: Final = timedelta(seconds=60)
"""The worker reads the active checks once in each window, so a new target starts within it."""

log = logging.getLogger(__name__)

type Observe = Callable[[ActiveCheck], Awaitable[HttpsObservation]]
type Clock = Callable[[], datetime]


class WorkerStore(Protocol):
    async def active_checks(self) -> list[ActiveCheck]: ...
    async def recorded(self, probe_id: ProbeId, keys: Sequence[ResultKey]) -> set[ResultKey]: ...
    async def record_result(self, result: CheckResult) -> None: ...


@dataclass(frozen=True)
class ScheduledCheck:
    check: ActiveCheck
    slot: Slot
    due_at: datetime

    @property
    def key(self) -> ResultKey:
        return (self.check.check_id, self.slot.start)


def offset(check_id: CheckId, interval: timedelta) -> timedelta:
    """A stable point inside each slot, in [0, interval - CHECK_BUDGET - SLOT_MARGIN)."""
    span_ms = (interval - CHECK_BUDGET - SLOT_MARGIN) // timedelta(milliseconds=1)
    digest = int.from_bytes(hashlib.blake2b(check_id.bytes, digest_size=8).digest())
    return timedelta(milliseconds=digest % span_ms)


def plan(
    checks: Sequence[ActiveCheck], since: datetime | None, until: datetime, now: datetime
) -> list[ScheduledCheck]:
    """Each run with a due time in [since, until) whose slot still has room for the check.

    `since` is None for the first window after a start. Each check then starts from its
    current slot, so a restart runs a missing check of that slot at once if it has room.
    """
    scheduled: list[ScheduledCheck] = []
    for check in checks:
        check_offset = offset(check.check_id, check.interval)
        slot = Slot.containing(now if since is None else since - check_offset, check.interval)
        while (due_at := slot.start + check_offset) < until:
            on_time = since is None or due_at >= since
            if on_time and slot.end - max(due_at, now) >= CHECK_BUDGET:
                scheduled.append(ScheduledCheck(check, slot, due_at))
            slot = slot.next()
    return sorted(scheduled, key=lambda run: run.due_at)


async def due_checks(
    store: WorkerStore, probe_id: ProbeId, since: datetime | None, until: datetime, now: datetime
) -> list[ScheduledCheck]:
    """The runs of `plan` that have no row from this probe. The reconcile step after a crash."""
    candidates = plan(await store.active_checks(), since, until, now)
    recorded = await store.recorded(probe_id, [run.key for run in candidates])
    return [run for run in candidates if run.key not in recorded]


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def run_worker(
    store: WorkerStore,
    probe_id: ProbeId,
    observe: Observe,
    *,
    max_concurrency: int,
    clock: Clock = _utc_now,
) -> None:
    """Run windows until cancelled.

    Each check runs in its own task, so a slow target does not delay a different target.
    A semaphore bounds the checks in flight. A check that is not done at the end of its slot is
    cancelled and writes no row.
    """
    permits = asyncio.Semaphore(max_concurrency)
    since: datetime | None = None
    async with asyncio.TaskGroup() as tasks:
        while True:
            now = clock()
            until = Slot.containing(now, WINDOW).end
            try:
                due = await due_checks(store, probe_id, since, until, now)
            except StoreUnavailable as error:
                log.error("no plan until %s, Postgres unavailable: %s", until.isoformat(), error)
            else:
                for run in due:
                    tasks.create_task(_run_one(run, store, probe_id, observe, permits, clock))
                since = until
            await _sleep_until(until, clock)


async def _run_one(
    run: ScheduledCheck,
    store: WorkerStore,
    probe_id: ProbeId,
    observe: Observe,
    permits: asyncio.Semaphore,
    clock: Clock,
) -> None:
    name = f"{run.check.hostname}:{run.check.port} slot {run.slot.start.isoformat()}"
    await _sleep_until(run.due_at, clock)
    loop = asyncio.get_running_loop()
    try:
        async with asyncio.timeout(_seconds_until(run.slot.end, clock)), permits:
            started_at = clock()
            started = loop.time()
            observation = await observe(run.check)
    except TimeoutError:
        log.warning("%s: not done at slot end, cancelled, no row", name)
        return
    result = CheckResult(
        check_id=run.check.check_id,
        account_id=run.check.account_id,
        probe_id=probe_id,
        scheduled_at=run.slot.start,
        due_at=run.due_at,
        started_at=started_at,
        duration_ms=(loop.time() - started) * 1000,
        observation=observation,
    )
    try:
        await store.record_result(result)
    except StoreUnavailable as error:
        log.error("%s: row lost, Postgres unavailable: %s", name, error)
        return
    log.info("%s: %s (%s) %.0f ms", name, result.verdict, result.reason, result.duration_ms)


def _seconds_until(at: datetime, clock: Clock) -> float:
    return max(0.0, (at - clock()).total_seconds())


async def _sleep_until(at: datetime, clock: Clock) -> None:
    await asyncio.sleep(_seconds_until(at, clock))
