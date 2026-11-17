"""The schedule. This module is the only one that calls the check, the verdict and the store
together. It holds no state between slots. Postgres holds all state.
"""

from pydantic import BaseModel, ConfigDict

from saasx2x.config import Settings
from saasx2x.domain import ProbeId, Slot
from saasx2x.https_check import Timeouts, TlsContext
from saasx2x.store import Store, StoreUnavailable


class SlotSummary(BaseModel):
    """The counts of one slot, for the one log line that each slot writes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_start: str
    due: int
    recorded: int
    unfinished: int
    """Checks that the end of the slot cancelled. They have no row. A missing row means
    "no data", not "down"."""


async def run_worker(store: Store, settings: Settings) -> None:
    """Run slots until cancelled. Fixed rate: the wall clock gives each slot.

    Start: do the current slot immediately, so a restart fills the slot that the crash left.
    A slot that the worker did not see (suspend, long crash) stays empty. The worker does not
    check the past.
    """
    # probe_id = await store.register_probe(settings.probe_name)
    # tls = tls_context(settings.ca_file)
    # while True:
    #     slot = Slot.containing(datetime.now(UTC), settings.interval)
    #     try:
    #         summary = await run_slot(slot, store=store, probe_id=probe_id, tls=tls, ...)
    #         log(summary)
    #     except StoreUnavailable:
    #         log the error. The slot stays empty. Do not stop the worker.
    #     await asyncio.sleep(max(0, (slot.end - datetime.now(UTC)).total_seconds()))
    raise NotImplementedError


async def run_slot(
    slot: Slot,
    *,
    store: Store,
    probe_id: ProbeId,
    tls: TlsContext,
    timeouts: Timeouts,
    max_concurrency: int,
) -> SlotSummary:
    """Make each active check have one result for `slot`. Return before `slot.end`.

    Idempotent. A second run for the same slot checks only what has no row.
    Each check runs in its own task, so a slow target does not delay a different target.
    A semaphore of `max_concurrency` bounds the open connections.
    Each task records its row immediately, so a crash loses only the checks in flight.
    """
    # due = await store.due_checks(probe_id, slot)
    # async with asyncio.timeout_at(<loop time of slot.end>):   # cancels unfinished checks
    #     async with asyncio.TaskGroup() as group:
    #         for check in due: group.create_task(one(check))
    #
    # async def one(check):
    #     async with semaphore:
    #         started_at = datetime.now(UTC); t0 = perf_counter()
    #         observation = await check_https(check.hostname, check.port, tls=tls, timeouts=timeouts)
    #         await store.record_result(CheckResult(
    #             check_id=check.check_id, probe_id=probe_id, scheduled_at=slot.start,
    #             started_at=started_at, duration_ms=..., observation=observation))
    raise NotImplementedError
