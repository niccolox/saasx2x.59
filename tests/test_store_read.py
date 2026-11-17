"""`ReadStore` against the Compose Postgres, in a scratch database."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from saasx2x.domain import AccountSlug, ActiveCheck, CheckKind, DnsFailed, ProbeId
from saasx2x.domain import parse_hostname as host
from saasx2x.store import (
    EvidenceCount,
    EvidenceWindow,
    MonitoredCheck,
    NewestRows,
    ReadStore,
    ReadWindows,
    SlotEvidence,
    Store,
    StoreUnavailable,
)
from saasx2x.verdict import Reason
from tests.conftest import scratch_database
from tests.results import (
    DURATION,
    PROBE,
    STARTED_AFTER,
    TCP_REFUSED,
    UP,
    make_check_older,
    result_at,
)

OWNER = AccountSlug("owner")
SECOND_PROBE = ProbeId("test-probe-2")
SLOT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
AROUND_SLOT = EvidenceWindow(SLOT - timedelta(days=1), SLOT + timedelta(days=1))


def around_slot(_: MonitoredCheck) -> ReadWindows:
    return ReadWindows(slots=AROUND_SLOT, counts=AROUND_SLOT)


@pytest.fixture
async def read_store(store: Store, database_url: str) -> AsyncIterator[ReadStore]:
    async with ReadStore.connect(database_url) as read:
        yield read


async def minute_check(store: Store, name: str = "example.com") -> ActiveCheck:
    await store.register_probe(PROBE)
    return await store.add_target(OWNER, host(name), interval=MINUTE)


async def test_two_probes_for_one_slot_give_one_slot_with_two_reasons(
    store: Store, read_store: ReadStore
) -> None:
    check = await minute_check(store)
    await store.register_probe(SECOND_PROBE)
    await store.record_result(result_at(check, SLOT, UP))
    await store.record_result(result_at(check, SLOT, TCP_REFUSED, SECOND_PROBE))
    await store.record_result(result_at(check, SLOT + MINUTE, UP))

    rows = await read_store.dashboard_rows(OWNER, around_slot)

    assert rows.slots == (
        SlotEvidence(check.check_id, SLOT, (Reason.STATUS_OK, Reason.TCP_FAILED)),
        SlotEvidence(check.check_id, SLOT + MINUTE, (Reason.STATUS_OK,)),
    )
    assert sorted(rows.counts, key=lambda count: count.reasons) == [
        EvidenceCount(check.check_id, (Reason.STATUS_OK,), 1),
        EvidenceCount(check.check_id, (Reason.STATUS_OK, Reason.TCP_FAILED), 1),
    ]


async def test_the_counts_are_the_slots_of_the_same_window_grouped_by_evidence(
    store: Store, read_store: ReadStore
) -> None:
    check = await minute_check(store)
    not_found = DnsFailed(error="not_found")
    for n, observation in enumerate([UP, UP, TCP_REFUSED, UP, not_found, UP, TCP_REFUSED]):
        await store.record_result(result_at(check, SLOT + n * MINUTE, observation))

    rows = await read_store.dashboard_rows(OWNER, around_slot)

    assert len(rows.slots) == 7
    assert {count.reasons: count.slots for count in rows.counts} == {
        (Reason.STATUS_OK,): 4,
        (Reason.TCP_FAILED,): 2,
        (Reason.DNS_NOT_FOUND,): 1,
    }


async def test_each_window_limits_the_rows_of_its_own_check(
    store: Store, read_store: ReadStore
) -> None:
    a, b = await minute_check(store, "a.example"), await minute_check(store, "b.example")
    for check in (a, b):
        for n in range(4):
            await store.record_result(result_at(check, SLOT + n * MINUTE))

    def windows(check: MonitoredCheck) -> ReadWindows:
        if check.check.check_id == a.check_id:
            return ReadWindows(
                slots=EvidenceWindow(SLOT + MINUTE, SLOT + 3 * MINUTE),
                counts=EvidenceWindow(SLOT, SLOT + MINUTE),
            )
        return ReadWindows(slots=EvidenceWindow(SLOT, SLOT), counts=AROUND_SLOT)

    rows = await read_store.dashboard_rows(OWNER, windows)

    assert [(slot.check_id, slot.scheduled_at) for slot in rows.slots] == [
        (a.check_id, SLOT + MINUTE),
        (a.check_id, SLOT + 2 * MINUTE),
    ]
    assert {(count.check_id, count.slots) for count in rows.counts} == {
        (a.check_id, 1),
        (b.check_id, 4),
    }


async def test_the_checks_are_the_active_checks_of_the_account_with_their_newest_slot(
    store: Store, read_store: ReadStore, database_url: str
) -> None:
    old = await minute_check(store, "b.example")
    new = await minute_check(store, "a.example")
    removed = await minute_check(store, "c.example")
    theirs = await store.add_target(AccountSlug("someone-else"), host("d.example"))
    made = SLOT - timedelta(days=10)
    await make_check_older(database_url, old, made)
    three_days_ago = SLOT - timedelta(days=3)
    await store.record_result(result_at(old, three_days_ago - MINUTE, TCP_REFUSED))
    await store.record_result(result_at(old, three_days_ago, UP))
    await store.record_result(result_at(removed, SLOT))
    await store.record_result(result_at(theirs, SLOT))
    assert await store.remove_target(OWNER, host("c.example"))

    rows = await read_store.dashboard_rows(OWNER, around_slot)

    assert [monitored.check for monitored in rows.checks] == [new, old]
    first, second = rows.checks
    assert first.newest is None
    assert (second.kind, second.created_at) == (CheckKind.HTTPS, made)
    assert second.newest == NewestRows(
        three_days_ago, three_days_ago + STARTED_AFTER + DURATION, (Reason.STATUS_OK,)
    )
    assert (rows.slots, rows.counts) == ((), ())


async def test_the_three_reads_see_one_state_of_the_database(
    store: Store, read_store: ReadStore, database_url: str
) -> None:
    check = await minute_check(store)
    await store.record_result(result_at(check, SLOT))
    late = result_at(check, SLOT + MINUTE)

    def write_between_the_reads(_: MonitoredCheck) -> ReadWindows:
        with psycopg.connect(database_url, autocommit=True) as db:
            db.execute(
                """INSERT INTO check_results (check_id, scheduled_at, probe_id, account_id,
                                              due_at, started_at, duration_ms, verdict, reason,
                                              rules_version, observation)
                   VALUES (%s, %s, %s, %s, %s, %s, 250, 'up', 'status_ok', 1,
                           '{"outcome": "http_responded"}')""",
                (
                    late.check_id,
                    late.scheduled_at,
                    late.probe_id,
                    late.account_id,
                    late.due_at,
                    late.started_at,
                ),
            )
        return around_slot(_)

    during = await read_store.dashboard_rows(OWNER, write_between_the_reads)
    after = await read_store.dashboard_rows(OWNER, around_slot)

    assert [slot.scheduled_at for slot in during.slots] == [SLOT]
    assert [count.slots for count in during.counts] == [1]
    assert [slot.scheduled_at for slot in after.slots] == [SLOT, SLOT + MINUTE]


async def test_postgres_refuses_a_write_on_a_read_store_connection(read_store: ReadStore) -> None:
    async with read_store._connection() as connection:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            await connection.execute("INSERT INTO probes (id) VALUES ('intruder')")


async def test_a_database_with_no_schema_is_unavailable_with_the_command_to_fix_it() -> None:
    with scratch_database() as url:
        async with ReadStore.connect(url) as read:
            with pytest.raises(StoreUnavailable, match="saasx2x migrate"):
                await read.dashboard_rows(OWNER, around_slot)
