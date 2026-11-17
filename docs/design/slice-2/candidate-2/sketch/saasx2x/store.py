"""Slice 2 additions to `store.py`. The slice 1 code stays. Only the new names are here.

`store.py` stays the only module that imports `psycopg` and holds SQL. The new class
`DashboardReader` is the only database access of the web process. It has no write method, and
Postgres also makes each of its sessions read-only, so a write fails two times over: pyright
rejects the call, and Postgres rejects the statement.

The reader asks `dashboard.check_windows` for the slot bounds. It never computes a slot itself.
SQL only bins rows into slots (`date_bin`) and counts them.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Final

import psycopg
from psycopg_pool import AsyncConnectionPool

from saasx2x.dashboard import (
    CheckFacts,
    CheckWindows,
    DashboardFacts,
    LatestSlot,
    MonitoredCheck,
    ProbeActivity,
    TallyBucket,
    VerdictTally,
    check_windows,
)
from saasx2x.domain import AccountSlug

type _Connection = psycopg.AsyncConnection[tuple[Any, ...]]

READ_ONLY_OPTIONS: Final = "-c default_transaction_read_only=on"
"""Each session of the reader starts read-only. A test opens a connection with these options and
shows that an INSERT fails."""


class StoreUnavailable(Exception):
    """Exists in slice 1. Slice 2 also raises it when the schema is not migrated
    (`psycopg.errors.UndefinedTable`), so the API answers 503 and the next poll can work."""


async def _open_pool(database_url: str, *, read_only: bool) -> AsyncConnectionPool[_Connection]:
    """The pool code of `Store.connect`, moved here so `Store` and `DashboardReader` share it.

    kwargs = {"autocommit": True} plus {"options": READ_ONLY_OPTIONS} when read_only.
    Raise StoreUnavailable on PoolTimeout, as slice 1 does.
    """
    raise NotImplementedError


_MONITORED_CHECKS: Final = """
    SELECT c.id, c.account_id, c.kind, t.hostname, c.port, c.interval_s, c.created_at
      FROM checks c JOIN targets t ON t.id = c.target_id
     WHERE t.removed_at IS NULL
       AND c.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
"""

# One CTE, two final selects. `w` holds one row for each check: its id, its interval, and the
# bounds that `check_windows` gave. Bins use the current interval of the check, so a row from
# before an interval change goes into the slot that contains its `scheduled_at`.
# The tally is a jsonb object {verdict: count}. jsonb equality ignores key order, so equal
# tallies group together. No SQL text names a verdict value, so a new Verdict member needs no SQL
# change here.
_TALLIES: Final = """
    WITH w AS (
        SELECT * FROM unnest(%(check_ids)s::uuid[], %(interval_s)s::int[],
                             %(lo)s::timestamptz[], %(hi)s::timestamptz[])
                   AS w (check_id, interval_s, lo, hi)
    ), per_verdict AS (
        SELECT r.check_id,
               date_bin(make_interval(secs => w.interval_s), r.scheduled_at,
                        '1970-01-01 00:00:00+00') AS slot_start,
               r.verdict::text AS verdict,
               count(*) AS n
          FROM w JOIN check_results r
            ON r.check_id = w.check_id AND r.scheduled_at >= w.lo AND r.scheduled_at < w.hi
         WHERE r.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
         GROUP BY 1, 2, 3
    ), per_slot AS (
        SELECT check_id, slot_start, jsonb_object_agg(verdict, n) AS tally
          FROM per_verdict GROUP BY 1, 2
    )
"""
_STRIP_TALLIES: Final = _TALLIES + "SELECT check_id, slot_start, tally FROM per_slot"
_WEEK_BUCKETS: Final = (
    _TALLIES + "SELECT check_id, tally, count(*) AS slots FROM per_slot GROUP BY 1, 2"
)

# The primary key (check_id, scheduled_at, probe_id) serves both the max and the join.
_LATEST_SLOTS: Final = """
    SELECT k.check_id, r.scheduled_at, r.probe_id, r.reason::text
      FROM unnest(%(check_ids)s::uuid[]) AS k (check_id)
      CROSS JOIN LATERAL (SELECT max(scheduled_at) AS newest
                            FROM check_results WHERE check_id = k.check_id) AS l
      JOIN check_results r ON r.check_id = k.check_id AND r.scheduled_at = l.newest
"""

# Index check_results_account_probe_started (migration 0002) serves this.
_PROBE_ACTIVITY: Final = """
    SELECT p.id, n.written_at
      FROM probes p
      LEFT JOIN LATERAL (
          SELECT r.started_at + r.duration_ms * interval '1 millisecond' AS written_at
            FROM check_results r
           WHERE r.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
             AND r.probe_id = p.id
           ORDER BY r.started_at DESC
           LIMIT 1) AS n ON true
     ORDER BY p.id
"""


class DashboardReader:
    """The read side for the web process. One public method."""

    def __init__(self, pool: AsyncConnectionPool[_Connection]) -> None:
        self._pool = pool

    @classmethod
    @asynccontextmanager
    async def connect(cls, database_url: str) -> AsyncGenerator["DashboardReader"]:
        """Open a read-only pool (`_open_pool(read_only=True)`). Close it on exit."""
        raise NotImplementedError
        yield

    async def dashboard_facts(self, account: AccountSlug, now: datetime) -> DashboardFacts:
        """All facts for one page, from one snapshot.

        BEGIN ISOLATION LEVEL REPEATABLE READ, READ ONLY
          checks  = _MONITORED_CHECKS                     -> list[MonitoredCheck]
          windows = {id: check_windows(check, now)}       (pure, from dashboard.py)
          strip   = _STRIP_TALLIES with lo/hi = windows.strip
          week    = _WEEK_BUCKETS  with lo/hi = windows.week
          latest  = _LATEST_SLOTS
          probes  = _PROBE_ACTIVITY
        COMMIT
        Parse each row into the dashboard types here. No row leaves this method.

        Five statements for each page, whatever the number of checks. Rows back:
        strip  <= checks x 1,441 slots, week <= checks x (distinct tallies), latest <= checks x
        probes, probes = probe count.
        """
        raise NotImplementedError


def _monitored_check(row: tuple[Any, ...]) -> MonitoredCheck:
    raise NotImplementedError


def _tally(value: dict[str, int]) -> VerdictTally:
    """jsonb {verdict: count} -> VerdictTally. `Verdict(key)` raises on an unknown value."""
    raise NotImplementedError


def _check_facts(
    check: MonitoredCheck,
    windows: CheckWindows,
    strip: dict[datetime, VerdictTally],
    week: tuple[TallyBucket, ...],
    latest: LatestSlot | None,
) -> CheckFacts:
    raise NotImplementedError


def _probe_activity(row: tuple[Any, ...]) -> ProbeActivity:
    raise NotImplementedError
