"""The dashboard read model. New module `src/saasx2x/dashboard.py`.

This module owns two things:

1. The JSON shape of `GET /api/dashboard`. The classes below are that shape. FastAPI writes the
   OpenAPI document from them, and the page makes its TypeScript types from that document.
2. The rules that turn rows into that shape: which marks a strip shows, what an uptime counts,
   and when the worker is stalled.

`build_dashboard` is pure. `read_dashboard` is the only function here that waits for I/O.
This module imports no `fastapi` and no `psycopg`.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final, Literal, Protocol, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    computed_field,
    model_validator,
)

from saasx2x.domain import AccountSlug, CheckId, CheckKind, Hostname
from saasx2x.store import EvidenceCount, EvidenceWindow, MonitoredCheck, SlotEvidence
from saasx2x.verdict import Reason, Verdict

DAY: Final = timedelta(hours=24)
"""The span of the strip and of the first uptime."""
WEEK: Final = timedelta(days=7)
"""The span of the second uptime."""
REFRESH_AFTER: Final = timedelta(seconds=60)
"""The page asks again after this time. The page reads it from each answer."""
STALL_SLACK: Final = timedelta(seconds=60)
"""A row can be this late before the worker counts as stalled. A check takes at most 30 s."""

type Mark = Verdict | Literal["not_observed"]
"""What one slot shows. A verdict when a probe wrote a row. "not_observed" when no probe wrote
a row for an expected slot. Derived from `Verdict`, so the two cannot differ."""


class _Wire(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StripRun(_Wire):
    """Slots in sequence that have the same judgement. One mark on the strip."""

    start: AwareDatetime
    """The start of the first slot."""
    end: AwareDatetime
    """The end of the last slot."""
    reason: Reason | None
    """None has one meaning: no probe wrote a row for these expected slots."""

    @computed_field
    @property
    def mark(self) -> Mark:
        return "not_observed" if self.reason is None else self.reason.verdict


class Strip(_Wire):
    """The last 24 hours of one check on a time axis.

    The axis is [start, end). `end` is the end of the open slot, and `start` is `DAY` before the
    start of the open slot. A part of the axis with no run is not a fault: the check did not
    exist then, or the slot is open and has no row.
    """

    start: AwareDatetime
    end: AwareDatetime
    runs: tuple[StripRun, ...]
    """In time order. Two runs do not overlap. Two runs that touch have different reasons."""

    @model_validator(mode="after")
    def _runs_in_order_inside_the_axis(self) -> Self:
        raise NotImplementedError


class SlotCounts(_Wire):
    """The expected slots of one span, counted by mark. The five numbers are disjoint."""

    up: NonNegativeInt
    down: NonNegativeInt
    blocked: NonNegativeInt
    inconclusive: NonNegativeInt
    not_observed: NonNegativeInt
    # A test fails when these field names differ from the values of `Mark`.

    @computed_field
    @property
    def expected(self) -> int:
        """The number of expected slots. Always the sum of the five numbers."""
        return self.up + self.down + self.blocked + self.inconclusive + self.not_observed

    @computed_field
    @property
    def up_ratio(self) -> float | None:
        """up / (up + down). None when no slot is up or down.

        "blocked", "inconclusive" and "not observed" are not in the ratio. The page shows them
        as numbers beside it. The only owner of the uptime formula is this property.
        """
        judged = self.up + self.down
        return self.up / judged if judged else None


class LastResult(_Wire):
    """The newest slot of a check that has a row. It can be older than the strip."""

    slot_start: AwareDatetime
    reason: Reason

    @computed_field
    @property
    def verdict(self) -> Verdict:
        return self.reason.verdict


class CheckStatus(_Wire):
    """One row of the page: one check of one active target."""

    check_id: CheckId
    hostname: Hostname
    port: int = Field(ge=1, le=65535)
    kind: CheckKind
    interval_s: int = Field(ge=60)
    last: LastResult | None
    """None: no probe wrote a row for this check."""
    strip: Strip
    day: SlotCounts
    week: SlotCounts


class WorkerStatus(_Wire):
    """One line for the whole worker.

    idle:     no active check, so no row is due.
    waiting:  no row yet, and the first row is not late.
    writing:  the newest row is not late.
    stalled:  the newest row is late, or no row came in time. The page shows this state first.
    """

    state: Literal["idle", "waiting", "writing", "stalled"]
    newest_row_at: AwareDatetime | None
    """The end of the newest check, which is when the worker wrote its row. None: no row."""
    expected_every_s: int | None
    """The shortest interval of an active check. None exactly when `state` is "idle"."""

    @model_validator(mode="after")
    def _state_agrees_with_the_fields(self) -> Self:
        # idle <=> expected_every_s is None; writing => newest_row_at; waiting => no newest_row_at
        raise NotImplementedError


class Dashboard(_Wire):
    """The whole page at one instant. The only body of `GET /api/dashboard`."""

    generated_at: AwareDatetime
    """The server clock for this answer. The page derives each "ago" text from it and from the
    time since the answer came, so the clock of the browser does not matter."""
    refresh_after_s: int
    worker: WorkerStatus
    checks: tuple[CheckStatus, ...]
    """In hostname and port order."""


class DashboardStore(Protocol):
    """What `read_dashboard` needs. `ReadStore` satisfies it. A test passes a fake."""

    async def monitored_checks(self, account: AccountSlug) -> list[MonitoredCheck]: ...
    async def slot_evidence(
        self, account: AccountSlug, windows: Sequence[EvidenceWindow]
    ) -> list[SlotEvidence]: ...
    async def evidence_counts(
        self, account: AccountSlug, windows: Sequence[EvidenceWindow]
    ) -> list[EvidenceCount]: ...


async def read_dashboard(store: DashboardStore, account: AccountSlug, now: datetime) -> Dashboard:
    """Read the rows that the page needs and build the page. Three statements, no write.

    The same shape as `worker.due_checks`: a pure plan, then the store, then a pure fold.
    """
    # TODO:
    #   checks = await store.monitored_checks(account)
    #   day = await store.slot_evidence(account, [_strip_window(c, now) for c in checks])
    #   week = await store.evidence_counts(account, [_week_window(c, now) for c in checks])
    #   return build_dashboard(checks, day, week, now)
    raise NotImplementedError


def build_dashboard(
    checks: Sequence[MonitoredCheck],
    day: Sequence[SlotEvidence],
    week: Sequence[EvidenceCount],
    now: datetime,
) -> Dashboard:
    """Turn rows into the page. Pure and total.

    For each check, with `open` the slot that contains `now`:

    strip   Each slot with a row on the axis shows `fold_probes(reasons)`. That includes the open
            slot and the slot in which the check was made. Each slot of
            `expected_slots(interval, created_at, now, DAY)` with no row shows "not observed".
            Slots in sequence with the same reason merge into one run.
    day     One count for each slot of `expected_slots(..., DAY)`: the verdict of its row, or
            "not observed". The open slot is not expected, so an uptime does not change inside
            a slot.
    week    `expected_slots(..., WEEK).count` is the total. Each EvidenceCount adds `slots` to
            the verdict of `fold_probes(reasons)`. "not observed" is the total minus that sum,
            and never less than 0.
    last    `fold_probes(newest.reasons)` with its slot start.
    """
    raise NotImplementedError


def _strip_window(check: MonitoredCheck, now: datetime) -> EvidenceWindow:
    """The rows on the strip axis: [open.start - DAY, open.end)."""
    raise NotImplementedError


def _week_window(check: MonitoredCheck, now: datetime) -> EvidenceWindow:
    """The rows of the expected slots of the last 7 days: [range.start, range.end)."""
    raise NotImplementedError


def _worker_status(checks: Sequence[MonitoredCheck], now: datetime) -> WorkerStatus:
    """The stall rule. Pure.

    No check: idle. Else let `shortest` be the shortest interval, `newest` the latest
    `finished_at` of a check, and `reference` the later of `newest` and the newest `created_at`
    (a new check starts the wait again). The row is late when
    `now - reference > shortest + STALL_SLACK`.

        late                -> stalled
        not late, no row    -> waiting
        not late, a row     -> writing
    """
    raise NotImplementedError
