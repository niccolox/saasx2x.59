"""Postgres access. The only module that holds SQL or sees a database row.

Postgres is the one source of truth for targets. The CLI writes them here
and the worker reads them here, so there is no config file to keep in sync.
A paid API in stage 2 calls the same add_target() and remove_target().

Driver is psycopg 3 with an async pool. No ORM. Rows parse into domain types
inside this module and never leave it as dicts or tuples.

Migrations are plain SQL files in migrations/, applied in file-name order,
one transaction per file, under pg_advisory_xact_lock, with a sha256 per
applied file in schema_migration. A changed applied file fails migrate().
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from saasx2x.domain import (
    CheckId,
    CheckSpec,
    Frozen,
    Hostname,
    Observation,
    ProbeId,
    ResultKey,
    SlotStart,
    UrlPath,
)
from saasx2x.verdict import RULES_VERSION, judge


class TargetView(Frozen):
    """One line of `saasx2x target list`."""

    host: Hostname
    path: UrlPath
    added_at: datetime
    last_verdict: str | None
    last_slot: datetime | None


class Store:
    @classmethod
    async def open(cls, dsn: str, max_size: int = 4) -> Self:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def migrate(self) -> list[str]:
        """Apply pending migrations. Returns the file names applied. Idempotent."""
        raise NotImplementedError

    async def register_probe(self, name: str, region: str) -> ProbeId:
        """Upsert by name. Same name returns the same id on every restart."""
        raise NotImplementedError

    async def add_target(self, account: str, host: Hostname, path: UrlPath) -> CheckSpec:
        """Idempotent. Adds the target and its HTTPS check on port 443.

        A removed target with the same host comes back with its old id, so its
        result history stays attached. A second add of an active target
        updates the path and returns the same check.
        """
        raise NotImplementedError

    async def remove_target(self, account: str, host: Hostname) -> bool:
        """Sets removed_at. Keeps the rows and their results. False if not active."""
        raise NotImplementedError

    async def list_targets(self, account: str) -> list[TargetView]:
        raise NotImplementedError

    async def active_checks(self) -> list[CheckSpec]:
        """Every check whose target is not removed, across all accounts."""
        raise NotImplementedError

    async def recorded(self, probe_id: ProbeId, since: datetime) -> set[tuple[CheckId, SlotStart]]:
        """Keys this probe wrote with slot_start >= since. Uses check_result_probe_slot."""
        raise NotImplementedError

    async def record(
        self,
        key: ResultKey,
        account_id: int,
        due_at: datetime,
        observation: Observation,
    ) -> bool:
        """Insert one result row with judge(observation) and RULES_VERSION.

        INSERT ... ON CONFLICT (check_id, slot_start, probe_id) DO NOTHING.
        Returns False when the key already had a row. The first write wins.
        """
        _ = (judge, RULES_VERSION)
        raise NotImplementedError
