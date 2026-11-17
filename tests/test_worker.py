import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from uuid import uuid4

from saasx2x.domain import (
    AccountId,
    ActiveCheck,
    CheckId,
    HttpResponded,
    HttpsObservation,
    ProbeId,
    Slot,
    parse_hostname,
)
from saasx2x.store import ResultKey
from saasx2x.verdict import CheckResult
from saasx2x.worker import offset, run_worker
from tests.virtual_time import clock_from, run_virtual

HOUR = datetime(2026, 1, 1, tzinfo=UTC)
PROBE = ProbeId("local-1")
CHECK_TIME = timedelta(seconds=30)
UP = HttpResponded(
    ip=ip_address("192.0.2.1"),
    dns_ms=1,
    tcp_connect_ms=1,
    tls_handshake_ms=1,
    http_ms=1,
    status=200,
    server=None,
    cf_mitigated=None,
    cf_ray=None,
    body_head=None,
)

type Observe = Callable[[ActiveCheck], Awaitable[HttpsObservation]]


class MemoryStore:
    def __init__(self, checks: Sequence[ActiveCheck]) -> None:
        self.checks = list(checks)
        self.rows: dict[tuple[ResultKey, ProbeId], CheckResult] = {}

    async def active_checks(self) -> list[ActiveCheck]:
        return list(self.checks)

    async def recorded(self, probe_id: ProbeId, keys: Sequence[ResultKey]) -> set[ResultKey]:
        return {key for key in keys if (key, probe_id) in self.rows}

    async def record_result(self, result: CheckResult) -> None:
        self.rows.setdefault(((result.check_id, result.scheduled_at), result.probe_id), result)

    def results(self, check: ActiveCheck, probe_id: ProbeId = PROBE) -> list[CheckResult]:
        rows = [
            row
            for row in self.rows.values()
            if row.check_id == check.check_id and row.probe_id == probe_id
        ]
        return sorted(rows, key=lambda row: row.scheduled_at)


def a_check(interval_s: int = 60, name: str = "example.com") -> ActiveCheck:
    return ActiveCheck(
        check_id=CheckId(uuid4()),
        account_id=AccountId(uuid4()),
        hostname=parse_hostname(name),
        port=443,
        interval=timedelta(seconds=interval_s),
    )


def taking(duration: timedelta) -> Observe:
    async def observe(check: ActiveCheck) -> HttpsObservation:
        await asyncio.sleep(duration.total_seconds())
        return UP

    return observe


def run_workers(
    store: MemoryStore,
    observe: Observe,
    *,
    start: datetime,
    duration: timedelta,
    probes: Sequence[ProbeId] = (PROBE,),
) -> None:
    async def main() -> None:
        clock = clock_from(start)
        workers = [
            asyncio.create_task(
                run_worker(store, probe, observe, max_concurrency=1000, clock=clock)
            )
            for probe in probes
        ]
        await asyncio.sleep(duration.total_seconds())
        for worker in workers:
            worker.cancel()
        for worker in workers:
            with suppress(asyncio.CancelledError):
                await worker

    run_virtual(main)


def test_due_times_come_from_the_epoch_and_do_not_drift_over_many_slots() -> None:
    check = a_check(interval_s=60)
    store = MemoryStore([check])

    run_workers(store, taking(timedelta(seconds=7)), start=HOUR, duration=timedelta(minutes=100))

    rows = store.results(check)[:100]
    assert [row.scheduled_at for row in rows] == [
        HOUR + k * timedelta(minutes=1) for k in range(100)
    ]
    offsets = {row.due_at - row.scheduled_at for row in rows}
    assert len(offsets) == 1
    assert all(abs(row.started_at - row.due_at) < timedelta(milliseconds=1) for row in rows)


def test_every_offset_is_inside_its_slot_with_room_for_a_30_second_check() -> None:
    checks = [a_check(interval_s) for interval_s in (60, 300, 3600) for _ in range(20)]
    store = MemoryStore(checks)

    run_workers(store, taking(CHECK_TIME), start=HOUR, duration=timedelta(hours=2))

    for check in checks:
        rows = store.results(check)
        assert len(rows) == timedelta(hours=2) // check.interval
        for row in rows:
            assert row.scheduled_at <= row.due_at
            assert (
                row.due_at + CHECK_TIME + timedelta(seconds=10) <= row.scheduled_at + check.interval
            )


def test_a_check_still_running_at_slot_end_is_cancelled_and_writes_no_row() -> None:
    slow, fast = a_check(name="slow.example"), a_check(name="fast.example")
    store = MemoryStore([slow, fast])
    clock = clock_from(HOUR)
    cancelled_at: list[datetime] = []

    async def observe(check: ActiveCheck) -> HttpsObservation:
        if check is fast:
            return UP
        try:
            await asyncio.Event().wait()
        finally:
            cancelled_at.append(clock())
        raise AssertionError("unreachable")

    run_workers(store, observe, start=HOUR, duration=timedelta(minutes=10))

    assert store.results(slow) == []
    assert len(store.results(fast)) == 10
    slot_ends = [HOUR + k * timedelta(minutes=1) for k in range(1, 11)]
    assert len(cancelled_at) == 10
    assert all(
        abs(at - end) < timedelta(milliseconds=1)
        for at, end in zip(cancelled_at, slot_ends, strict=True)
    )


def check_with_offset_below(limit: timedelta, interval_s: int = 300) -> ActiveCheck:
    while True:
        check = a_check(interval_s)
        if offset(check.check_id, check.interval) < limit:
            return check


def test_a_restart_runs_a_missing_check_of_the_current_slot_at_once_if_the_slot_has_room() -> None:
    slot = Slot(start=HOUR, interval=timedelta(seconds=300))
    missing, recorded = (check_with_offset_below(timedelta(seconds=240)) for _ in range(2))
    store = MemoryStore([missing, recorded])
    earlier = CheckResult(
        check_id=recorded.check_id,
        account_id=recorded.account_id,
        probe_id=PROBE,
        scheduled_at=slot.start,
        due_at=slot.start + offset(recorded.check_id, recorded.interval),
        started_at=slot.start,
        duration_ms=1,
        observation=UP,
    )
    store.rows[((recorded.check_id, slot.start), PROBE)] = earlier
    restart = slot.start + timedelta(seconds=250)

    run_workers(store, taking(timedelta(seconds=1)), start=restart, duration=timedelta(seconds=5))

    (caught_up,) = store.results(missing)
    assert (caught_up.scheduled_at, caught_up.started_at) == (slot.start, restart)
    assert store.results(recorded) == [earlier]


def test_a_restart_skips_the_current_slot_when_less_than_30_seconds_are_left() -> None:
    slot = Slot(start=HOUR, interval=timedelta(seconds=300))
    check = check_with_offset_below(timedelta(seconds=240))
    store = MemoryStore([check])
    restart = slot.end - timedelta(seconds=20)

    run_workers(store, taking(timedelta(seconds=1)), start=restart, duration=timedelta(minutes=6))

    assert store.results(check)[0].scheduled_at == slot.end


def test_two_probes_check_one_target_at_the_same_instant() -> None:
    check = a_check(interval_s=60)
    store = MemoryStore([check])
    probes = (ProbeId("eu-1"), ProbeId("us-1"))

    run_workers(
        store,
        taking(timedelta(seconds=2)),
        start=HOUR,
        duration=timedelta(minutes=5),
        probes=probes,
    )

    eu, us = (store.results(check, probe) for probe in probes)
    assert len(eu) == len(us) == 5
    assert [row.started_at for row in eu] == [row.started_at for row in us]
