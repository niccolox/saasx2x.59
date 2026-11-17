"""The dashboard rules. Pure, no I/O.

This module is the only owner of three rules:

1. The expected slots: which slots a check should have a row for. It derives them from `Slot`
   and the life of the check. No SQL computes a slot list.
2. The fold: how the rows of one slot (one row for each probe) become one mark.
3. The stall rule: when the newest row is too old, so the worker is stalled.

The store gives facts (`DashboardFacts`). `build_dashboard` turns the facts into `Dashboard`.
`Dashboard` is the JSON body of `GET /api/dashboard`, and the TypeScript types are generated from
`dashboard_json_schema()`. No other type describes that JSON.
"""

from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Final, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    computed_field,
    model_validator,
)

from saasx2x.domain import (
    AccountSlug,
    ActiveCheck,
    CheckId,
    CheckKind,
    Hostname,
    ProbeId,
    Slot,
)
from saasx2x.verdict import Reason, Verdict

DAY: Final = timedelta(days=1)
WEEK: Final = timedelta(days=7)
STALL_AFTER_INTERVALS: Final = 2
"""The worker is stalled when its newest row is older than this many of the shortest active
interval. One slot can have its row late in the slot and the next row early in its slot, so
one interval of silence is normal. Two is not."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Marks and the fold -------------------------------------------------------------------------


class Mark(StrEnum):
    """What the page shows for one slot. The first four values equal the `Verdict` values."""

    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"
    MIXED = "mixed"
    """The probes disagree about the slot. This cannot occur with one probe."""
    NOT_OBSERVED = "not_observed"
    """A complete slot in the life of the check, with no row."""
    PENDING = "pending"
    """The current slot. It is not complete, and it has no row yet."""
    OUTSIDE = "outside"
    """A slot that starts before the check existed. It has no row. It is not "not observed"."""

    @classmethod
    def of(cls, verdict: Verdict) -> "Mark":
        return cls(verdict.value)


COUNTED_MARKS: Final = frozenset(
    {Mark.UP, Mark.DOWN, Mark.BLOCKED, Mark.INCONCLUSIVE, Mark.MIXED, Mark.NOT_OBSERVED}
)
"""The marks that an uptime window counts. PENDING and OUTSIDE are never counted."""


class VerdictTally(_Frozen):
    """The rows of one slot, counted by verdict. At least one row.

    The tally is lossless for each fold rule that uses only counts (all agree, majority,
    quorum). A later rule that needs the region of each probe adds a region key here.
    """

    counts: dict[Verdict, PositiveInt] = Field(min_length=1)

    @property
    def rows(self) -> int:
        return sum(self.counts.values())

    def fold(self) -> Mark:
        """The one place that folds the probes of a slot into one mark.

        Slice 2 rule: when all rows have one verdict, the mark of that verdict. Else MIXED.
        This rule decides nothing about agreement. The alert slice replaces this body with its
        quorum rule, and the page follows with no other change.
        """
        raise NotImplementedError


# --- Slot ranges and the expected slots --------------------------------------------------------


class SlotRange(_Frozen):
    """Consecutive slots of one interval, from `start` (included) to `stop` (excluded).

    Both ends are slot boundaries. The range is empty when `start == stop`.
    """

    start: AwareDatetime
    stop: AwareDatetime
    interval: timedelta

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        # TODO: Slot(start=self.start, interval=self.interval) validates the alignment.
        # Require stop >= start and (stop - start) % interval == 0.
        raise NotImplementedError

    @property
    def count(self) -> int:
        return (self.stop - self.start) // self.interval

    def slots(self) -> Iterator[Slot]:
        raise NotImplementedError

    def __contains__(self, slot_start: object) -> bool:
        raise NotImplementedError


class MonitoredCheck(_Frozen):
    """An active check and the time it was made. The start of its life."""

    check: ActiveCheck
    kind: CheckKind
    created_at: AwareDatetime


class CheckWindows(_Frozen):
    """The slot ranges of one check at one instant. `check_windows` is the only maker.

    Invariants: `day` and `week` end at `current.start`. `day` is inside `strip`. No range
    holds a slot that starts before `created_at`, except `strip`, which shows the whole day.
    """

    current: Slot
    strip: SlotRange
    """The slots that start in (now - DAY, now]. The last slot is `current`."""
    day: SlotRange
    """The complete slots of `strip` that start at or after `created_at`."""
    week: SlotRange
    """The complete slots that start in (now - WEEK, now) and at or after `created_at`."""


def check_windows(check: MonitoredCheck, now: datetime) -> CheckWindows:
    """The expected slots of one check. This is the only owner of that rule.

    current    = Slot.containing(now, interval)
    life_start = the first slot start at or after created_at
    strip      = Slot.containing(now - DAY, interval).next() .. current.end
    day        = max(strip.start, life_start) .. current.start   (empty if negative)
    week       = max(Slot.containing(now - WEEK).next().start, life_start) .. current.start

    The slot that contains `created_at` is outside the life of the check. The worker can still
    write a row for it. The strip then shows that row, but no uptime window counts it.
    """
    raise NotImplementedError


# --- Facts: what the store reads ---------------------------------------------------------------


class ProbeReason(_Frozen):
    """One row of a slot. The verdict is `reason.verdict`, so the two cannot disagree."""

    probe_id: ProbeId
    reason: Reason


class LatestSlot(_Frozen):
    """The rows of the newest slot of a check that has rows. One row for each probe."""

    slot_start: AwareDatetime
    rows: tuple[ProbeReason, ...] = Field(min_length=1)

    def tally(self) -> VerdictTally:
        raise NotImplementedError


class TallyBucket(_Frozen):
    """`slots` slots of a window that have the same tally. The store groups them in SQL, so a
    week of 60 s slots comes back as a few buckets, not as 10,080 rows."""

    tally: VerdictTally
    slots: PositiveInt


class CheckFacts(_Frozen):
    check: MonitoredCheck
    windows: CheckWindows
    strip_tallies: dict[AwareDatetime, VerdictTally]
    """Slot start to tally, for each slot of `windows.strip` that has a row. Other slots of the
    strip have no row."""
    week_buckets: tuple[TallyBucket, ...]
    """The slots of `windows.week` that have a row, grouped by tally."""
    latest: LatestSlot | None
    """The newest slot with a row, at any age. None when the check has no row."""


class ProbeActivity(_Frozen):
    probe_id: ProbeId
    newest_row_at: AwareDatetime | None
    """`started_at + duration_ms` of the newest row of this probe for the account. The table has
    no insert time, and this is the time the worker wrote the row, less a few milliseconds.
    None when the probe has no row for the account."""


class DashboardFacts(_Frozen):
    account: AccountSlug
    as_of: AwareDatetime
    checks: tuple[CheckFacts, ...]
    probes: tuple[ProbeActivity, ...]


# --- The response: what the page shows ---------------------------------------------------------


class MarkCounts(_Frozen):
    """The counted slots of one window. Each counted slot is in exactly one field."""

    up: NonNegativeInt
    down: NonNegativeInt
    blocked: NonNegativeInt
    inconclusive: NonNegativeInt
    mixed: NonNegativeInt
    not_observed: NonNegativeInt

    @computed_field
    @property
    def expected(self) -> int:
        """All counted slots of the window."""
        raise NotImplementedError

    @computed_field
    @property
    def up_ratio(self) -> float | None:
        """up / (up + down). None when up + down is 0.

        NOT_OBSERVED, BLOCKED, INCONCLUSIVE and MIXED are outside the ratio. They give no
        evidence that the target is up or down. The page shows each one beside the ratio.
        """
        raise NotImplementedError

    @classmethod
    def of(cls, marks: Iterable[Mark]) -> "MarkCounts":
        """Count marks. Raise ValueError for PENDING or OUTSIDE: no window counts those."""
        raise NotImplementedError


class Strip(_Frozen):
    """One mark for each slot of the last 24 hours. Mark `i` is the slot that starts at
    `first_slot_start + i * interval_s`. No mark carries its own time."""

    first_slot_start: AwareDatetime
    interval_s: PositiveInt
    marks: tuple[Mark, ...]


class LastResult(_Frozen):
    slot_start: AwareDatetime
    mark: Mark
    """The fold of the rows of the slot. One of the four verdict marks, or MIXED."""
    reasons: tuple[Reason, ...] = Field(min_length=1)
    """The distinct reasons of the rows, in `Reason` order. One reason with one probe."""
    probes: PositiveInt


class CheckPanel(_Frozen):
    check_id: CheckId
    kind: CheckKind
    hostname: Hostname
    port: int
    interval_s: PositiveInt
    last: LastResult | None
    strip: Strip
    day: MarkCounts
    week: MarkCounts


class WorkerState(StrEnum):
    WRITING = "writing"
    STALLED = "stalled"
    """The newest row is older than STALL_AFTER_INTERVALS times the shortest interval."""
    NO_ROWS = "no_rows"
    """There are active checks, and this probe never wrote a row for the account."""
    IDLE = "idle"
    """There is no active check. No row is expected."""


class WorkerLine(_Frozen):
    probe_id: ProbeId
    state: WorkerState
    newest_row_at: AwareDatetime | None
    stall_after_s: PositiveInt | None
    """The silence that makes the state STALLED. None when the state is IDLE."""


class Dashboard(_Frozen):
    """The body of `GET /api/dashboard`. The page is a pure function of this value."""

    model_config = ConfigDict(frozen=True, extra="forbid", title="Dashboard")

    account: AccountSlug
    as_of: AwareDatetime
    """The instant of the snapshot. The page shows each age relative to this, not to the browser
    clock, so a wrong browser clock gives no wrong age."""
    workers: tuple[WorkerLine, ...]
    checks: tuple[CheckPanel, ...]
    """In hostname order, then port order. Python sorts: SQL collation order is different for
    `-` and `.`."""


# --- The build ----------------------------------------------------------------------------------


def build_dashboard(facts: DashboardFacts) -> Dashboard:
    """Turn the facts into the page. Total and pure.

    for each check: panel(check_facts)
    shortest = min interval of the checks, or None
    for each probe: worker_line(probe, shortest, facts.as_of)
    sort the panels by (hostname, port)
    """
    raise NotImplementedError


def strip_marks(facts: CheckFacts) -> tuple[Mark, ...]:
    """One mark for each slot of `facts.windows.strip`.

    for slot in strip:
        tally exists     -> tally.fold()            (a row wins over each other rule)
        slot is current  -> PENDING
        slot in day      -> NOT_OBSERVED
        else             -> OUTSIDE                  (before the life of the check)
    """
    raise NotImplementedError


def day_counts(facts: CheckFacts, marks: tuple[Mark, ...]) -> MarkCounts:
    """MarkCounts.of(the marks of the slots in `facts.windows.day`). The day comes from the strip,
    so the strip and the 24 h numbers cannot disagree."""
    raise NotImplementedError


def week_counts(facts: CheckFacts) -> MarkCounts:
    """Each bucket adds `slots` of `bucket.tally.fold()`.

    not_observed = windows.week.count - sum(bucket.slots)
    Raise AssertionError when that is negative. That can occur only if SQL bins a row into a
    slot that `check_windows` does not expect.
    """
    raise NotImplementedError


def last_result(latest: LatestSlot | None) -> LastResult | None:
    raise NotImplementedError


def worker_line(probe: ProbeActivity, shortest: timedelta | None, now: datetime) -> WorkerLine:
    """shortest is None               -> IDLE
    probe.newest_row_at is None       -> NO_ROWS
    now - newest > STALL_AFTER_INTERVALS * shortest -> STALLED
    else                              -> WRITING
    """
    raise NotImplementedError


def dashboard_json_schema() -> dict[str, Any]:
    """`Dashboard.model_json_schema(mode="serialization")`. Computed fields are in it.

    `saasx2x schema` prints it. The committed copy is
    `web/src/generated/dashboard.schema.json`, and a test compares the two.
    """
    raise NotImplementedError
