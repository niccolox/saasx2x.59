"""ADDITIONS to src/saasx2x/store.py. This file is not a module. It shows what changes in store.py.

Rule kept: only store.py imports psycopg and holds SQL. The web process gets a `ReadStore`.
`ReadStore` has no write method, and its connections refuse writes at the Postgres level.

Change 1. Move `connect`, `_connection`, and the pool setup of `Store` into a private base
class `_Pooled`. `Store(_Pooled)` keeps all its methods and signatures. `Store.connect` keeps its
behavior. This is the only edit to existing code.

Change 2. Add `ReadStore(_Pooled)`, below.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Final, Self

import psycopg
from psycopg_pool import AsyncConnectionPool

from saasx2x.domain import AccountSlug
from saasx2x.status import StatusFacts

type _Connection = psycopg.AsyncConnection[tuple[Any, ...]]

_READ_ONLY_OPTIONS: Final = "-c default_transaction_read_only=on -c statement_timeout=10000"
"""Each session starts read-only. A bug in the web process cannot write a row.
The statement timeout stops a slow query from holding a connection."""


class _Pooled:
    """Sketch of the shared base. Holds the pool. `_connection()` maps `psycopg.OperationalError`,
    `PoolTimeout`, and `psycopg.errors.UndefinedTable` ("run saasx2x migrate") to `StoreUnavailable`.
    """

    def __init__(self, pool: AsyncConnectionPool[_Connection]) -> None:
        self._pool = pool

    @classmethod
    @asynccontextmanager
    async def connect(
        cls, database_url: str, *, wait: bool = True, options: str | None = None
    ) -> AsyncGenerator[Self]:
        """Open a small pool. With `wait=False`, return at once and let the pool connect in the
        background. The web process uses this: if Postgres is down at start, each request answers
        503 until it is up, and the process does not exit."""
        raise NotImplementedError
        yield  # pragma: no cover


class ReadStore(_Pooled):
    @classmethod
    def connect_read_only(cls, database_url: str):  # -> AbstractAsyncContextManager[ReadStore]
        """`connect(database_url, wait=False, options=_READ_ONLY_OPTIONS)`."""
        raise NotImplementedError

    async def status_facts(
        self, account: AccountSlug, *, since: datetime, as_of: datetime
    ) -> StatusFacts:
        """Read everything one board needs, in ONE `REPEATABLE READ` read-only transaction.

        One snapshot means the worker line and the strips come from the same database state.
        Three statements, no loop over checks, so the cost does not grow with a query for each
        check:

        1. Active checks and the last row of each (the lateral join uses the primary key):

            SELECT c.id, c.account_id, t.hostname, c.port, c.interval_s, c.created_at,
                   l.scheduled_at, l.probe_id, l.duration_ms, l.verdict, l.reason,
                   (l.observation->>'status')::int
              FROM checks c
              JOIN targets t ON t.id = c.target_id
              LEFT JOIN LATERAL (
                    SELECT r.scheduled_at, r.probe_id, r.duration_ms, r.verdict, r.reason,
                           r.observation
                      FROM check_results r
                     WHERE r.check_id = c.id
                     ORDER BY r.scheduled_at DESC, r.started_at DESC
                     LIMIT 1) l ON true
             WHERE t.removed_at IS NULL
               AND c.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)

        2. Slot rows of the window, narrow (4 columns), by the primary key:

            SELECT check_id, scheduled_at, probe_id, verdict
              FROM check_results
             WHERE check_id = ANY(%(ids)s::uuid[])
               AND scheduled_at >= %(since)s AND scheduled_at < %(as_of)s

           Group the rows by `check_id` in Python. No verdict rule is in SQL. `fold_probes`
           and `expected_slots` own the meaning.

        3. The newest row of the account (uses `check_results_account_started_idx`):

            SELECT started_at, duration_ms
              FROM check_results
             WHERE account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
             ORDER BY started_at DESC LIMIT 1

        Returns domain types only. No row, cursor, or connection leaves this method.
        Raises `StoreUnavailable` when Postgres does not answer or the schema is missing.
        """
        raise NotImplementedError
