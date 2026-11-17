import shutil
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

import psycopg
import pytest

from saasx2x.domain import AccountSlug, DnsFailed, HttpResponded, HttpsObservation, ProbeId
from saasx2x.domain import parse_hostname as host
from saasx2x.store import MIGRATIONS_DIR, MigrationChanged, Store
from saasx2x.verdict import CheckResult
from saasx2x.worker import ScheduledCheck, due_checks
from tests.conftest import scratch_database

OWNER = AccountSlug("owner")
PROBE = ProbeId("test-probe")
MINUTE = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
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


def result_of(run: ScheduledCheck, observation: HttpsObservation) -> CheckResult:
    return CheckResult(
        check_id=run.check.check_id,
        account_id=run.check.account_id,
        probe_id=PROBE,
        scheduled_at=run.slot.start,
        due_at=run.due_at,
        started_at=run.due_at,
        duration_ms=12,
        observation=observation,
    )


async def due_hostnames(store: Store) -> list[str]:
    runs = await due_checks(store, PROBE, None, MINUTE + timedelta(seconds=60), MINUTE)
    return sorted(run.check.hostname for run in runs)


async def test_migrate_applies_each_file_once_and_rejects_a_changed_file(tmp_path: Path) -> None:
    with scratch_database() as url:
        async with Store.connect(url) as store:
            assert await store.migrate() == ["0001_init.sql"]
            assert await store.migrate() == []

            changed = tmp_path / "migrations"
            shutil.copytree(MIGRATIONS_DIR, changed)
            with (changed / "0001_init.sql").open("a") as file:
                file.write("\n-- edited after it was applied\n")
            with pytest.raises(MigrationChanged):
                await store.migrate(changed)


async def test_two_writes_of_one_key_leave_one_row_with_the_first_verdict(
    store: Store, database_url: str
) -> None:
    await store.register_probe(PROBE)
    await store.add_target(OWNER, host("example.com"), interval=timedelta(seconds=60))
    (run,) = await due_checks(store, PROBE, None, MINUTE + timedelta(seconds=60), MINUTE)

    await store.record_result(result_of(run, UP))
    await store.record_result(result_of(run, DnsFailed(error="not_found")))

    async with await psycopg.AsyncConnection.connect(database_url) as db:
        cursor = await db.execute(
            "SELECT verdict::text, reason::text, observation->>'outcome' FROM check_results"
        )
        assert await cursor.fetchall() == [("up", "status_ok", "http_responded")]


async def test_due_checks_excludes_a_checked_key_and_a_removed_target(store: Store) -> None:
    await store.register_probe(PROBE)
    for name in ("a.example", "b.example", "c.example"):
        await store.add_target(OWNER, host(name), interval=timedelta(seconds=60))
    runs = await due_checks(store, PROBE, None, MINUTE + timedelta(seconds=60), MINUTE)
    assert sorted(run.check.hostname for run in runs) == ["a.example", "b.example", "c.example"]

    checked = next(run for run in runs if run.check.hostname == "a.example")
    await store.record_result(result_of(checked, UP))
    assert await store.remove_target(OWNER, host("c.example"))

    assert await due_hostnames(store) == ["b.example"]


async def test_add_target_converges_and_a_removed_target_comes_back_with_its_id(
    store: Store,
) -> None:
    first = await store.add_target(OWNER, host("Example.COM."))
    again = await store.add_target(OWNER, host("example.com"), interval=timedelta(seconds=120))
    assert again.check_id == first.check_id
    assert [check.interval for check in await store.list_targets(OWNER)] == [timedelta(seconds=120)]

    assert await store.remove_target(OWNER, host("example.com"))
    assert not await store.remove_target(OWNER, host("example.com"))
    assert await store.list_targets(OWNER) == []

    back = await store.add_target(OWNER, host("example.com"))
    assert back.check_id == first.check_id


async def test_list_targets_shows_only_the_accounts_targets(store: Store) -> None:
    await store.add_target(OWNER, host("mine.example"))
    await store.add_target(AccountSlug("someone-else"), host("theirs.example"))
    assert [check.hostname for check in await store.list_targets(OWNER)] == ["mine.example"]
    assert len(await store.active_checks()) == 2
