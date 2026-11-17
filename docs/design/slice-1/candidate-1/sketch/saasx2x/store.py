"""All Postgres access. Only this module imports `psycopg` and contains SQL.

Callers pass and receive domain types. No row, cursor or connection leaves this module.
Each write converges, so a caller can repeat each method after a crash.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from saasx2x.domain import AccountSlug, DueCheck, Hostname, ProbeId, ProbeName, Slot, Target
from saasx2x.verdict import CheckResult


class StoreUnavailable(Exception):
    """Postgres did not answer. The caller can try again later.

    No psycopg error leaves this module.
    """


class Store:
    @classmethod
    @asynccontextmanager
    async def connect(cls, database_url: str) -> AsyncIterator["Store"]:
        """Open a small connection pool. Close it on exit."""
        raise NotImplementedError
        yield  # pragma: no cover

    async def migrate(self) -> list[str]:
        """Apply each file in `migrations/` that the database does not have. Return their names.

        A second run applies nothing and returns an empty list.
        """
        # TODO: take `pg_advisory_lock`, so two starters do not apply one file twice.
        # TODO: `CREATE TABLE IF NOT EXISTS schema_migrations (name, sha256, applied_at)`.
        # TODO: for each file in name order: apply it and insert its row in ONE transaction.
        # TODO: raise if the sha256 of an applied file is different from its recorded sha256.
        raise NotImplementedError

    async def add_target(
        self, account: AccountSlug, hostname: Hostname, *, port: int = 443
    ) -> Target:
        """Make sure the account has an active target for `hostname` with one HTTPS check.

        One transaction. A second call changes nothing. A call after `remove_target` makes
        the same target row active again, so the target keeps its id and its result history.
        """
        # INSERT INTO accounts (slug) ... ON CONFLICT (slug) DO NOTHING
        # INSERT INTO targets (account_id, hostname) ...
        #   ON CONFLICT (account_id, hostname) DO UPDATE SET removed_at = NULL
        # INSERT INTO checks (target_id, kind, port) VALUES (.., 'https', ..)
        #   ON CONFLICT (target_id, kind, port) DO NOTHING
        raise NotImplementedError

    async def remove_target(self, account: AccountSlug, hostname: Hostname) -> bool:
        """Stop all checks of the target. Keep its results. Return False if none was active."""
        # UPDATE targets SET removed_at = now() WHERE ... AND removed_at IS NULL
        raise NotImplementedError

    async def list_targets(self, account: AccountSlug) -> list[Target]:
        """Return the active targets of the account, in hostname order."""
        raise NotImplementedError

    async def register_probe(self, name: ProbeName) -> ProbeId:
        """Return the id of the probe with this name. Insert the probe if it is new."""
        raise NotImplementedError

    async def due_checks(self, probe_id: ProbeId, slot: Slot) -> list[DueCheck]:
        """Return each check of an active target that has no result for this probe and slot.

        This query is the reconcile step of the schedule. After a crash, the worker gets
        only the checks that the slot still lacks.
        """
        # SELECT c.id, t.hostname, c.port
        #   FROM checks c JOIN targets t ON t.id = c.target_id
        #  WHERE t.removed_at IS NULL
        #    AND NOT EXISTS (SELECT 1 FROM check_results r
        #                     WHERE r.check_id = c.id
        #                       AND r.scheduled_at = %(slot_start)s
        #                       AND r.probe_id = %(probe_id)s)
        raise NotImplementedError

    async def record_result(self, result: CheckResult) -> None:
        """Insert one result row. If the row exists, keep the first row and do nothing."""
        # INSERT INTO check_results (check_id, scheduled_at, probe_id, started_at, duration_ms,
        #                            verdict, rules_version, observation)
        # VALUES (...)  -- observation = the Pydantic JSON of result.observation
        # ON CONFLICT (check_id, scheduled_at, probe_id) DO NOTHING
        raise NotImplementedError
