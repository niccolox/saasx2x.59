"""The only module that holds SQL. Owns the schema, the target list, and the result rows.

psycopg 3 async pool, hand-written SQL, no ORM. Callers see domain types only.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from domain import AccountId, DueCheck, Hostname, ProbeId, Target
from verdict import CheckResult

MIGRATIONS_DIR = Path(__file__).parent / "migrations"  # 0001_init.sql, 0002_*.sql, ...


class Store:
    def __init__(self, database_url: str) -> None:
        raise NotImplementedError

    async def migrate(self) -> list[str]:
        """Apply unapplied migrations/NNNN_*.sql files in name order.

        One transaction per file. A transaction-scoped advisory lock stops two processes
        from migrating at once. schema_migration(name, sha256) records each file.
        A changed checksum for an applied file raises. Returns the names applied now.
        """
        raise NotImplementedError

    async def register_probe(self, probe_id: ProbeId, region: str) -> None:
        """Upsert the probe row. Safe to call on every start."""
        raise NotImplementedError

    # ---- targets: the owner's list. The target table is the only source of truth. ----

    async def add_target(self, host: Hostname, interval_s: int,
                         account_id: AccountId | None = None) -> Target:
        """Insert target and its https_443 check in one transaction.
        account_id None means the only account. Raises if there are several accounts.
        Adding an active host again returns the existing target. It does not duplicate."""
        raise NotImplementedError

    async def remove_target(self, host: Hostname, account_id: AccountId | None = None) -> bool:
        """Set removed_at. Results stay. Returns False when no active target matched."""
        raise NotImplementedError

    async def list_targets(self, account_id: AccountId | None = None) -> list[Target]:
        raise NotImplementedError

    # ---- results ----

    async def due(self, probe_id: ProbeId, now: datetime) -> list[DueCheck]:
        """Active checks that have no row for this probe in their current slot.

        Two queries. Q1 reads active checks. Python computes Slot.containing(now, interval_s)
        for each. Q2 reads existing (check_id, slot_start) keys for this probe with unnest.
        The slot grid lives in Python only. The absence of a row is the only 'pending' state.
        """
        raise NotImplementedError

    async def write(self, result: CheckResult) -> bool:
        """INSERT ... ON CONFLICT (check_id, probe_id, slot_start) DO NOTHING.
        Returns True if this call inserted the row. The first writer for a slot wins."""
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError
