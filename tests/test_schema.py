from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg import errors, sql

from saasx2x.domain import AccountSlug, CheckKind, ProbeId, parse_hostname
from saasx2x.store import Store
from saasx2x.verdict import Reason, Verdict

PROBE = ProbeId("test-probe")
SLOT = datetime(2026, 1, 1, tzinfo=UTC)


async def enum_values(db: psycopg.AsyncConnection[Any], name: str) -> list[str]:
    query = sql.SQL("SELECT enum_range(NULL::{})::text[]").format(sql.Identifier(name))
    cursor = await db.execute(query)
    row = await cursor.fetchone()
    assert row is not None
    return row[0]


async def insert_result(
    db: psycopg.AsyncConnection[Any],
    check_id: UUID,
    account_id: UUID,
    verdict: str,
    reason: str,
    slot: datetime = SLOT,
) -> None:
    await db.execute(
        """INSERT INTO check_results (check_id, scheduled_at, probe_id, account_id, due_at,
                                      started_at, duration_ms, verdict, reason, rules_version,
                                      observation)
           VALUES (%s, %s, %s, %s, %s, %s, 1, %s::verdict, %s::reason, 1,
                   '{"outcome": "probe_failed"}')""",
        (check_id, slot, PROBE, account_id, slot, slot, verdict, reason),
    )


async def test_sql_enums_equal_the_python_enums(store: Store, database_url: str) -> None:
    async with await psycopg.AsyncConnection.connect(database_url) as db:
        assert await enum_values(db, "verdict") == [verdict.value for verdict in Verdict]
        assert await enum_values(db, "reason") == [reason.value for reason in Reason]
        assert await enum_values(db, "check_kind") == [kind.value for kind in CheckKind]


async def test_the_verdict_reason_check_accepts_exactly_the_python_pairs(
    store: Store, database_url: str
) -> None:
    await store.register_probe(PROBE)
    check = await store.add_target(AccountSlug("owner"), parse_hostname("example.com"))
    accepted: set[tuple[Verdict, Reason]] = set()
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
        for index, (verdict, reason) in enumerate((v, r) for v in Verdict for r in Reason):
            slot = SLOT + index * timedelta(minutes=5)
            try:
                await insert_result(db, check.check_id, check.account_id, verdict, reason, slot)
            except errors.CheckViolation:
                continue
            accepted.add((verdict, reason))

    assert accepted == {(reason.verdict, reason) for reason in Reason}


async def test_a_result_with_the_account_of_a_different_check_is_rejected(
    store: Store, database_url: str
) -> None:
    await store.register_probe(PROBE)
    mine = await store.add_target(AccountSlug("owner"), parse_hostname("mine.example"))
    theirs = await store.add_target(AccountSlug("other"), parse_hostname("theirs.example"))
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
        await insert_result(db, mine.check_id, mine.account_id, "inconclusive", "probe_failed")
        next_slot = SLOT + timedelta(minutes=5)
        with pytest.raises(errors.ForeignKeyViolation):
            await insert_result(
                db, mine.check_id, theirs.account_id, "inconclusive", "probe_failed", next_slot
            )
