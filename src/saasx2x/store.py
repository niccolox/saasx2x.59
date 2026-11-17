"""All Postgres access. Only this module imports `psycopg` and contains SQL.

Callers pass and receive domain types. No row, cursor or connection leaves this module.
Each write converges, so a caller can repeat each method after a crash.
"""

import hashlib
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

import psycopg
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from saasx2x.domain import (
    AccountId,
    AccountSlug,
    ActiveCheck,
    CheckId,
    CheckKind,
    Hostname,
    ProbeId,
)
from saasx2x.verdict import CheckResult, Reason

MIGRATIONS_DIR: Final = Path(__file__).resolve().parents[2] / "migrations"
_MIGRATION_LOCK: Final = 0x5AA5_0001

type _Connection = psycopg.AsyncConnection[tuple[Any, ...]]
type _Pool = AsyncConnectionPool[_Connection]
type ResultKey = tuple[CheckId, datetime]
"""(check id, slot start). With a probe id, the key of one result row."""


class StoreUnavailable(Exception):
    """Postgres did not answer. The caller can try again later."""


class MigrationChanged(Exception):
    """An applied migration file is different from the file that the database applied."""


_ACTIVE_CHECKS: Final = """
    SELECT c.id, c.account_id, t.hostname, c.port, c.interval_s
      FROM checks c JOIN targets t ON t.id = c.target_id
     WHERE t.removed_at IS NULL
"""


@asynccontextmanager
async def _open_pool(database_url: str, *, read_only: bool) -> AsyncGenerator[_Pool]:
    """Open a small connection pool. Close it on exit. Raise StoreUnavailable with no connection.

    In a read-only pool, Postgres refuses a write on each connection, whatever SQL a later edit
    adds.
    """
    kwargs: dict[str, Any] = {"autocommit": True}
    if read_only:
        kwargs["options"] = "-c default_transaction_read_only=on"
    pool = AsyncConnectionPool[_Connection](
        database_url, min_size=1, max_size=5, timeout=5, open=False, kwargs=kwargs
    )
    try:
        await pool.open(wait=True, timeout=5)
    except PoolTimeout as error:
        await pool.close()
        raise StoreUnavailable(f"no connection to Postgres: {error}") from error
    try:
        yield pool
    finally:
        await pool.close()


@asynccontextmanager
async def _borrow(pool: _Pool) -> AsyncGenerator[_Connection]:
    try:
        async with pool.connection() as connection:
            yield connection
    except (psycopg.OperationalError, PoolTimeout) as error:
        raise StoreUnavailable(str(error)) from error


class Store:
    def __init__(self, pool: _Pool) -> None:
        self._pool = pool

    @classmethod
    @asynccontextmanager
    async def connect(cls, database_url: str) -> AsyncGenerator["Store"]:
        """Open a small connection pool. Close it on exit."""
        async with _open_pool(database_url, read_only=False) as pool:
            yield cls(pool)

    def _connection(self) -> AbstractAsyncContextManager[_Connection]:
        return _borrow(self._pool)

    async def migrate(self, directory: Path = MIGRATIONS_DIR) -> list[str]:
        """Apply each `*.sql` file that the database does not have, in name order.

        Return the names applied. A second run applies nothing. Raise MigrationChanged when an
        applied file changed.
        """
        files = _read_migrations(directory)
        async with self._connection() as connection:
            await connection.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK,))
            try:
                await connection.execute(
                    """CREATE TABLE IF NOT EXISTS schema_migrations (
                           name        text PRIMARY KEY,
                           sha256      text NOT NULL,
                           applied_at  timestamptz NOT NULL DEFAULT now())"""
                )
                cursor = await connection.execute("SELECT name, sha256 FROM schema_migrations")
                applied: dict[str, str] = dict(await cursor.fetchall())
                done: list[str] = []
                for name, content in files:
                    digest = hashlib.sha256(content).hexdigest()
                    if name in applied:
                        if applied[name] != digest:
                            raise MigrationChanged(f"{name} changed after it was applied")
                        continue
                    async with connection.transaction():
                        await connection.execute(content)
                        await connection.execute(
                            "INSERT INTO schema_migrations (name, sha256) VALUES (%s, %s)",
                            (name, digest),
                        )
                    done.append(name)
                return done
            finally:
                await connection.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK,))

    async def add_target(
        self,
        account: AccountSlug,
        hostname: Hostname,
        *,
        port: int = 443,
        interval: timedelta = timedelta(seconds=300),
    ) -> ActiveCheck:
        """Make sure the account has an active target with one HTTPS check on `port`.

        A second call changes nothing except the interval. A call after `remove_target` makes
        the same target row active again, so the target keeps its id and its results.
        """
        interval_s = int(interval.total_seconds())
        async with self._connection() as connection, connection.transaction():
            await connection.execute(
                "INSERT INTO accounts (slug) VALUES (%s) ON CONFLICT (slug) DO NOTHING", (account,)
            )
            cursor = await connection.execute(
                """INSERT INTO targets (account_id, hostname)
                   SELECT id, %s FROM accounts WHERE slug = %s
                   ON CONFLICT (account_id, hostname) DO UPDATE SET removed_at = NULL
                   RETURNING id, account_id""",
                (hostname, account),
            )
            target_id, account_id = await _one(cursor)
            cursor = await connection.execute(
                """INSERT INTO checks (target_id, account_id, kind, port, interval_s)
                   VALUES (%s, %s, %s::check_kind, %s, %s)
                   ON CONFLICT (target_id, kind, port)
                   DO UPDATE SET interval_s = EXCLUDED.interval_s
                   RETURNING id""",
                (target_id, account_id, CheckKind.HTTPS.value, port, interval_s),
            )
            (check_id,) = await _one(cursor)
        return ActiveCheck(
            check_id=CheckId(check_id),
            account_id=AccountId(account_id),
            hostname=hostname,
            port=port,
            interval=timedelta(seconds=interval_s),
        )

    async def remove_target(self, account: AccountSlug, hostname: Hostname) -> bool:
        """Stop all checks of the target. Keep its results. Return False if none was active."""
        async with self._connection() as connection:
            cursor = await connection.execute(
                """UPDATE targets SET removed_at = now()
                    WHERE hostname = %s AND removed_at IS NULL
                      AND account_id = (SELECT id FROM accounts WHERE slug = %s)""",
                (hostname, account),
            )
            return cursor.rowcount > 0

    async def list_targets(self, account: AccountSlug) -> list[ActiveCheck]:
        """Return the active checks of the account, in hostname and port order."""
        async with self._connection() as connection:
            cursor = await connection.execute(
                _ACTIVE_CHECKS
                + """ AND c.account_id = (SELECT id FROM accounts WHERE slug = %s)
                    ORDER BY t.hostname, c.port""",
                (account,),
            )
            return [_active_check(row) for row in await cursor.fetchall()]

    async def active_checks(self) -> list[ActiveCheck]:
        """Return each check of each target that is not removed, for all accounts."""
        async with self._connection() as connection:
            cursor = await connection.execute(_ACTIVE_CHECKS)
            return [_active_check(row) for row in await cursor.fetchall()]

    async def register_probe(self, probe_id: ProbeId) -> None:
        async with self._connection() as connection:
            await connection.execute(
                "INSERT INTO probes (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (probe_id,)
            )

    async def recorded(self, probe_id: ProbeId, keys: Sequence[ResultKey]) -> set[ResultKey]:
        """Return the keys in `keys` that already have a row from this probe."""
        if not keys:
            return set()
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT r.check_id, r.scheduled_at
                     FROM check_results r
                     JOIN unnest(%s::uuid[], %s::timestamptz[]) AS k (check_id, scheduled_at)
                       ON r.check_id = k.check_id AND r.scheduled_at = k.scheduled_at
                    WHERE r.probe_id = %s""",
                ([key[0] for key in keys], [key[1] for key in keys], probe_id),
            )
            return {(CheckId(check_id), slot) for check_id, slot in await cursor.fetchall()}

    async def record_result(self, result: CheckResult) -> None:
        """Insert one result row. If the row exists, keep the first row and do nothing."""
        async with self._connection() as connection:
            await connection.execute(
                """INSERT INTO check_results (check_id, scheduled_at, probe_id, account_id, due_at,
                                              started_at, duration_ms, verdict, reason,
                                              rules_version, observation)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::verdict, %s::reason, %s, %s::jsonb)
                   ON CONFLICT (check_id, scheduled_at, probe_id) DO NOTHING""",
                (
                    result.check_id,
                    result.scheduled_at,
                    result.probe_id,
                    result.account_id,
                    result.due_at,
                    result.started_at,
                    result.duration_ms,
                    result.verdict.value,
                    result.reason.value,
                    result.rules_version,
                    result.observation.model_dump_json(),
                ),
            )


# The read types below are frozen dataclasses, not Pydantic models. Postgres already made each
# value valid (enum types, foreign keys), and one request can read 30,000 of them.


@dataclass(frozen=True, slots=True)
class NewestRows:
    """The rows of the newest slot of one check that has a row. One reason for each probe."""

    scheduled_at: datetime
    """The slot start."""
    finished_at: datetime
    """The latest `started_at + duration_ms` of these rows. The worker inserts a row at once
    after the check ends, so this is the time of the write."""
    reasons: tuple[Reason, ...]


@dataclass(frozen=True, slots=True)
class MonitoredCheck:
    """One check of a target that is not removed, with what the dashboard needs to judge it."""

    check: ActiveCheck
    kind: CheckKind
    created_at: datetime
    newest: NewestRows | None
    """None: no probe wrote a row for this check."""


@dataclass(frozen=True, slots=True)
class EvidenceWindow:
    """The rows of one check with `since <= scheduled_at < until`."""

    since: datetime
    until: datetime


@dataclass(frozen=True, slots=True)
class ReadWindows:
    """What `ReadStore.dashboard_rows` reads for one check."""

    slots: EvidenceWindow
    """Return the evidence of each slot in this window that has a row."""
    counts: EvidenceWindow
    """Return only the number of slots in this window for each kind of evidence."""


type WindowPlan = Callable[[MonitoredCheck], ReadWindows]
"""A pure rule of the caller. The store calls it inside its snapshot, so the windows and the
rows come from one state of the database."""


@dataclass(frozen=True, slots=True)
class SlotEvidence:
    """All rows of one slot of one check. One reason for each probe that wrote a row."""

    check_id: CheckId
    scheduled_at: datetime
    reasons: tuple[Reason, ...]
    """Never empty. A slot with no row has no SlotEvidence."""


@dataclass(frozen=True, slots=True)
class EvidenceCount:
    """`slots` slots of one check have the same evidence."""

    check_id: CheckId
    reasons: tuple[Reason, ...]
    """One reason for each probe, in the order of `Reason`."""
    slots: int


@dataclass(frozen=True, slots=True)
class DashboardRows:
    """What `ReadStore.dashboard_rows` read in one snapshot."""

    checks: tuple[MonitoredCheck, ...]
    """In hostname and port order."""
    slots: tuple[SlotEvidence, ...]
    """In check and slot order."""
    counts: tuple[EvidenceCount, ...]


_MONITORED_CHECKS: Final = """
    SELECT c.id, c.account_id, t.hostname, c.port, c.interval_s, c.kind::text, c.created_at,
           newest.scheduled_at, newest.finished_at, newest.reasons
      FROM checks c
      JOIN targets t ON t.id = c.target_id
      LEFT JOIN LATERAL (
            SELECT r.scheduled_at,
                   max(r.started_at + r.duration_ms * interval '1 millisecond') AS finished_at,
                   array_agg(r.reason::text ORDER BY r.reason) AS reasons
              FROM check_results r
             WHERE r.check_id = c.id
               AND r.scheduled_at = (SELECT max(scheduled_at)
                                       FROM check_results WHERE check_id = c.id)
             GROUP BY r.scheduled_at
           ) newest ON true
     WHERE t.removed_at IS NULL
       AND c.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
     ORDER BY t.hostname, c.port
"""

_SLOTS_IN_WINDOWS: Final = """
    SELECT r.check_id, r.scheduled_at, array_agg(r.reason::text ORDER BY r.reason) AS reasons
      FROM check_results r
      JOIN unnest(%(check_ids)s::uuid[], %(since)s::timestamptz[], %(until)s::timestamptz[])
           AS w (check_id, since, until)
        ON r.check_id = w.check_id AND r.scheduled_at >= w.since AND r.scheduled_at < w.until
     WHERE r.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
     GROUP BY r.check_id, r.scheduled_at
"""

_SLOT_EVIDENCE: Final = _SLOTS_IN_WINDOWS + " ORDER BY r.check_id, r.scheduled_at"

# Postgres counts equal evidence. It gives no verdict to a slot: `fold_probes` does.
_EVIDENCE_COUNTS: Final = f"""
    SELECT slot.check_id, slot.reasons, count(*) AS slots
      FROM ({_SLOTS_IN_WINDOWS}) slot
     GROUP BY slot.check_id, slot.reasons
"""


class ReadStore:
    """Read access for the dashboard. No method writes."""

    def __init__(self, pool: _Pool) -> None:
        self._pool = pool

    @classmethod
    @asynccontextmanager
    async def connect(cls, database_url: str) -> AsyncGenerator["ReadStore"]:
        """Open a small read-only pool. Close it on exit. Raise StoreUnavailable with no
        connection."""
        async with _open_pool(database_url, read_only=True) as pool:
            yield cls(pool)

    def _connection(self) -> AbstractAsyncContextManager[_Connection]:
        return _borrow(self._pool)

    async def dashboard_rows(self, account: AccountSlug, windows: WindowPlan) -> DashboardRows:
        """Read the active checks of the account, then the rows in the windows of each check.

        Three statements in one REPEATABLE READ READ ONLY transaction, so the strip, the counts
        and the newest rows describe one state of the database. A row of a different account
        is never returned. Raise StoreUnavailable when Postgres does not answer or has no
        schema.
        """
        try:
            async with self._connection() as connection, connection.transaction():
                await connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                cursor = await connection.execute(_MONITORED_CHECKS, {"account": account})
                checks = tuple(_monitored_check(row) for row in await cursor.fetchall())
                plans = [(check.check.check_id, windows(check)) for check in checks]
                cursor = await connection.execute(
                    _SLOT_EVIDENCE, _window_arrays(account, [(i, w.slots) for i, w in plans])
                )
                slots = tuple(
                    SlotEvidence(CheckId(check_id), scheduled_at, _reasons(reasons))
                    for check_id, scheduled_at, reasons in await cursor.fetchall()
                )
                cursor = await connection.execute(
                    _EVIDENCE_COUNTS, _window_arrays(account, [(i, w.counts) for i, w in plans])
                )
                counts = tuple(
                    EvidenceCount(CheckId(check_id), _reasons(reasons), count)
                    for check_id, reasons, count in await cursor.fetchall()
                )
        except psycopg.errors.UndefinedTable as error:
            raise StoreUnavailable(
                "the database has no SaaSX2X tables. Run: saasx2x migrate"
            ) from error
        return DashboardRows(checks, slots, counts)


def _window_arrays(
    account: AccountSlug, windows: Sequence[tuple[CheckId, EvidenceWindow]]
) -> dict[str, Any]:
    return {
        "account": account,
        "check_ids": [check_id for check_id, _ in windows],
        "since": [window.since for _, window in windows],
        "until": [window.until for _, window in windows],
    }


def _reasons(values: Sequence[str]) -> tuple[Reason, ...]:
    return tuple(Reason(value) for value in values)


def _monitored_check(row: tuple[Any, ...]) -> MonitoredCheck:
    *active, kind, created_at, newest_slot, finished_at, reasons = row
    newest = None
    if newest_slot is not None:
        newest = NewestRows(newest_slot, finished_at, _reasons(reasons))
    return MonitoredCheck(_active_check(tuple(active)), CheckKind(kind), created_at, newest)


def _read_migrations(directory: Path) -> list[tuple[str, bytes]]:
    return [(path.name, path.read_bytes()) for path in sorted(directory.glob("*.sql"))]


async def _one(cursor: psycopg.AsyncCursor[tuple[Any, ...]]) -> tuple[Any, ...]:
    row = await cursor.fetchone()
    if row is None:
        raise LookupError("the statement returned no row")
    return row


def _active_check(row: tuple[Any, ...]) -> ActiveCheck:
    check_id, account_id, hostname, port, interval_s = row
    return ActiveCheck(
        check_id=CheckId(check_id),
        account_id=AccountId(account_id),
        hostname=Hostname(hostname),
        port=port,
        interval=timedelta(seconds=interval_s),
    )
