"""Slice 2 additions to `src/saasx2x/store.py`. Append them. `Store` stays as it is.

`ReadStore` is the store of the web process. It has no method that writes, and Postgres refuses
a write on each of its connections. All SQL of the dashboard is here. See `../../queries.sql`.
"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from saasx2x.domain import AccountSlug, ActiveCheck, CheckId, CheckKind
from saasx2x.verdict import Reason

# The types below are frozen dataclasses, not Pydantic models. Postgres already made each value
# valid (enum types, foreign keys), and one request can read 30,000 of them.


@dataclass(frozen=True, slots=True)
class NewestRows:
    """The rows of the newest slot of one check that has a row. One reason for each probe."""

    scheduled_at: datetime
    """The slot start."""
    finished_at: datetime
    """The latest `started_at + duration_ms` of these rows. The worker inserts a row at once
    after the check ends, so this is the time of the write, to the nearest second."""
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

    check_id: CheckId
    since: datetime
    until: datetime


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


class ReadStore:
    """Read access for the dashboard. No method writes."""

    @classmethod
    @asynccontextmanager
    async def connect(cls, database_url: str) -> AsyncGenerator["ReadStore"]:
        """Open a small pool. Close it on exit. Raise StoreUnavailable with no connection.

        Each connection has `default_transaction_read_only = on`, so Postgres rejects a write
        from this process. The rule does not depend on the SQL that a later edit adds.
        """
        # TODO: share the pool code with Store.connect through one private function
        #   _open_pool(database_url, *, read_only: bool), which adds
        #   kwargs["options"] = "-c default_transaction_read_only=on" for read_only.
        raise NotImplementedError
        yield  # pragma: no cover

    async def monitored_checks(self, account: AccountSlug) -> list[MonitoredCheck]:
        """Each check of each active target of the account, in hostname and port order.

        One statement. The newest slot of each check comes from the primary key, in reverse.
        Raise StoreUnavailable when Postgres does not answer or the schema is not there.
        """
        raise NotImplementedError

    async def slot_evidence(
        self, account: AccountSlug, windows: Sequence[EvidenceWindow]
    ) -> list[SlotEvidence]:
        """The evidence of each slot in the windows that has a row, in check and slot order.

        One statement, with the windows as arrays through `unnest`, as `Store.recorded` does.
        A row of a different account is never returned, also for a wrong check id.
        """
        raise NotImplementedError

    async def evidence_counts(
        self, account: AccountSlug, windows: Sequence[EvidenceWindow]
    ) -> list[EvidenceCount]:
        """For each check, the number of slots in its window for each kind of evidence.

        One statement. Postgres groups the slots, so 10,080 slots of a 60 s check in 7 days
        come back as a few rows. Postgres counts and does not judge: `fold_probes` judges.
        """
        raise NotImplementedError
