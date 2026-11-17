"""The status read model. Pure: no I/O, no clock, no Postgres, no HTTP.

This module owns four rules, and no other module repeats them:

1. Which slots a check owes (`expected_slots`).
2. How the rows of one slot fold into one mark (`fold_probes`).
3. How a worker is judged stalled (`judge_worker`).
4. The order of the checks on the page (`build_board`).

The types below are the domain types AND the JSON shape of `GET /api/status`. FastAPI serializes
them as they are. The TypeScript types come from the OpenAPI document of that route. There is no
second set of field lists. To change the page data, change a type here.

Data flow, readable from the signatures:

    ReadStore.status_facts  ->  StatusFacts  --build_board-->  StatusBoard  -> JSON -> React
         (store.py)           (this module)      (this module)  (this module)
"""

from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field, model_validator

from saasx2x.domain import ActiveCheck, CheckId, Hostname, ProbeId, Slot
from saasx2x.verdict import Reason, Verdict

WINDOW_24H: Final = timedelta(hours=24)
WINDOW_7D: Final = timedelta(days=7)

LATE_AFTER_INTERVALS: Final = 1
STALLED_AFTER_INTERVALS: Final = 2
GRACE: Final = timedelta(seconds=40)
"""A row can land up to one check budget (30 s) plus the slot margin (10 s) after its due time.
A test asserts that `GRACE >= worker.CHECK_BUDGET + worker.SLOT_MARGIN`. Do not import
`worker` here: it pulls in I/O modules."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------------------------
# Marks
# --------------------------------------------------------------------------------------------


class Mark(StrEnum):
    """What one slot looks like on the page: a verdict, or "no row"."""

    UP = "up"
    DOWN = "down"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"
    NOT_OBSERVED = "not_observed"
    """The check owed a row for this slot and no probe wrote one. Never counted as up."""

    @classmethod
    def of(cls, verdict: Verdict) -> Self:
        """The mark of one verdict. A test fails when `Mark` and `Verdict` differ in members."""
        raise NotImplementedError


def fold_probes(first: Verdict, *rest: Verdict) -> Mark:
    """Fold the verdicts of all probes for ONE slot into one mark.

    The signature makes an empty slot unrepresentable: no row means `Mark.NOT_OBSERVED`, and the
    caller decides that before it calls this function. With one probe, this is `Mark.of`.

    Default rule for many probes (the owner can change it, see RATIONALE open questions):
        any UP         -> UP    (one probe reached the target, so the target is reachable)
        else any DOWN  -> DOWN
        else any BLOCKED -> BLOCKED
        else           -> INCONCLUSIVE
    """
    raise NotImplementedError


# --------------------------------------------------------------------------------------------
# Expected slots
# --------------------------------------------------------------------------------------------


class SlotRange(_Frozen):
    """A run of consecutive slots of one interval. The owed slots of a check are always one run.

    A range holds no per-slot object. 7 d of 60 s slots is 10,080 slots, and a `Slot` model
    validates on each construction. The range uses integer index arithmetic and builds a `Slot`
    for its first slot only. `Slot` stays the owner of epoch alignment.
    """

    first: Slot
    count: int = Field(ge=0)

    @property
    def interval(self) -> timedelta:
        return self.first.interval

    def index_of(self, start: datetime) -> int | None:
        """The index of the slot that starts at `start`. None if `start` is outside the range
        or not aligned to the interval. A row that is not on the grid (for example after the
        owner changed the interval) is ignored, not coerced."""
        raise NotImplementedError

    def clip_from(self, earliest: datetime) -> Self:
        """Keep the slots whose start is at or after `earliest`."""
        raise NotImplementedError

    def starts(self) -> Iterator[datetime]:
        """The start of each slot, in order. Call it for the 24 h range only (at most 1,440)."""
        raise NotImplementedError


def expected_slots(
    created_at: datetime,
    interval: timedelta,
    as_of: datetime,
    observed_starts: Sequence[datetime],
) -> SlotRange:
    """The slots that a check owed, from its first full slot to the last slot that has ended.

    This is the only definition of "not observed". A slot is owed when:
      * its start is at or after `created_at`. The slot that contains `created_at` is outside
        the life of the check. The worker does not own it, so it is not "not observed".
      * the slot has ended (`slot.end <= as_of`), OR a row for it exists. The slot that is open
        now has no row yet by design, because the check is due at an offset inside the slot.
        Calling it "not observed" would raise a false alarm.

    TODO(pseudocode):
        first = Slot.containing(created_at, interval); if first.start != created_at: first = first.next()
        open_slot = Slot.containing(as_of, interval)
        count = (open_slot.start - first.start) // interval          # the closed slots
        if open_slot.start in observed_starts: count += 1            # the open slot, if it has a row
        return SlotRange(first=first, count=max(count, 0))
    """
    raise NotImplementedError


# --------------------------------------------------------------------------------------------
# Facts: what the store reads. Narrow on purpose.
# --------------------------------------------------------------------------------------------


class SlotRow(_Frozen):
    """One row of `check_results`, reduced to what a mark needs. `probe_id` stays on the row, so
    a second probe needs no change to the reader."""

    scheduled_at: AwareDatetime
    probe_id: ProbeId
    verdict: Verdict


class LastResult(_Frozen):
    """The newest row of one check, by slot start. Reason and HTTP status are for people only.
    No rule reads them."""

    slot_start: AwareDatetime
    probe_id: ProbeId
    verdict: Verdict
    reason: Reason
    http_status: int | None
    duration_ms: float = Field(ge=0)


class CheckFacts(_Frozen):
    check: ActiveCheck
    created_at: AwareDatetime
    last: LastResult | None
    rows: tuple[SlotRow, ...]
    """All rows from `since` to `as_of`, any order, any probe."""


class NewestRow(_Frozen):
    started_at: AwareDatetime
    duration_ms: float = Field(ge=0)

    @property
    def written_at(self) -> datetime:
        """`check_results` has no write-time column and the schema must not change. The worker
        writes the row right after the check ends, so `started_at + duration` is the write time
        to within milliseconds."""
        return self.started_at + timedelta(milliseconds=self.duration_ms)


class StatusFacts(_Frozen):
    """Everything one board needs, read in one snapshot transaction."""

    checks: tuple[CheckFacts, ...]
    newest_row: NewestRow | None
    """The newest row of the account, from any probe, for any check (also a removed one)."""


# --------------------------------------------------------------------------------------------
# The board: domain type AND wire shape of GET /api/status
# --------------------------------------------------------------------------------------------


class Run(_Frozen):
    mark: Mark
    count: int = Field(ge=1)


class Strip(_Frozen):
    """The slots of the last 24 h of one check, in run-length form.

    The page draws on a TIME axis, not a slot axis, so a 60 s strip and a 300 s strip of two
    rows line up. `lead` counts the grid slots before the check existed. The page leaves them
    empty. `runs` cover the owed slots up to the newest. The right edge can be one slot before
    `as_of` (the open slot has no row yet).

    Run-length form keeps the JSON and the DOM small: a quiet day is one run, not 1,440 marks.
    """

    first_slot: AwareDatetime
    """Start of the first grid slot at or after `board.window_start`."""
    interval_s: int = Field(ge=60)
    lead: int = Field(ge=0)
    runs: tuple[Run, ...]

    @model_validator(mode="after")
    def _runs_are_canonical(self) -> Self:
        """Adjacent runs differ in mark. One slot sequence has one JSON form."""
        raise NotImplementedError

    @computed_field
    @property
    def slot_count(self) -> int:
        return self.lead + sum(run.count for run in self.runs)


class Tally(_Frozen):
    """Slots of a window, counted by mark. "Not observed" is a count of its own."""

    up: int = Field(ge=0)
    down: int = Field(ge=0)
    blocked: int = Field(ge=0)
    inconclusive: int = Field(ge=0)
    not_observed: int = Field(ge=0)

    @computed_field
    @property
    def uptime(self) -> float | None:
        """up / (up + down), from 0 to 1. None when up + down is 0.

        Blocked, inconclusive, and not observed slots give no evidence that the target was up or
        down. They stay out of both sides of the ratio and the page shows their counts. This is
        the only place that divides. The page never computes a ratio."""
        raise NotImplementedError


class CheckStatus(_Frozen):
    check_id: CheckId
    hostname: Hostname
    port: int = Field(ge=1, le=65535)
    interval_s: int = Field(ge=60)
    last: LastResult | None
    strip: Strip
    tally_24h: Tally
    tally_7d: Tally


class WorkerState(StrEnum):
    IDLE = "idle"
    """No active check, so no row is owed."""
    FRESH = "fresh"
    LATE = "late"
    STALLED = "stalled"


class Worker(_Frozen):
    """One line for the whole worker. It judges the newest row of the account."""

    state: WorkerState
    newest_row_at: AwareDatetime | None
    """When the newest row was written. None when the account has no row yet."""
    silent_s: int | None
    """Seconds since `newest_row_at`. With no row, seconds since the oldest active check was
    created, so a worker that never wrote a row also becomes late and then stalled. None if idle."""
    expected_every_s: int | None
    """The shortest interval of the active checks: the longest healthy gap between two rows."""


class StatusBoard(_Frozen):
    as_of: AwareDatetime
    """The server clock when the board was built. The page shows ages relative to this instant,
    so a wrong clock in the browser changes nothing."""
    window_start: AwareDatetime
    """Left edge of each strip: `as_of - 24 h`."""
    worker: Worker
    checks: tuple[CheckStatus, ...]
    """In hostname order, then port. `build_board` sorts. The store does not promise an order."""


# --------------------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------------------


def run_length(marks: Sequence[Mark]) -> tuple[Run, ...]:
    """Encode marks as runs. Adjacent runs always differ."""
    raise NotImplementedError


def judge_worker(facts: StatusFacts, as_of: datetime) -> Worker:
    """The state of the worker, from the age of the newest row.

        shortest = min(interval of each active check); none -> IDLE
        since    = newest_row.written_at, or min(created_at of the active checks) when no row
        silent   = as_of - since
        STALLED  if silent > STALLED_AFTER_INTERVALS * shortest + GRACE
        LATE     if silent > LATE_AFTER_INTERVALS * shortest + GRACE
        FRESH    otherwise
    The shortest interval gives the strictest healthy gap, because the check with that interval
    writes a row at each of its slots.
    """
    raise NotImplementedError


def build_check_status(facts: CheckFacts, as_of: datetime) -> CheckStatus:
    """One check: its strip and its two tallies. One pass over the rows, one slot range.

    TODO(pseudocode):
        observed = {row.scheduled_at for row in facts.rows}
        owed = expected_slots(facts.created_at, interval, as_of, observed).clip_from(as_of - WINDOW_7D)
        verdicts_by_index: dict[int, list[Verdict]] = {}
        for row in facts.rows:
            if (i := owed.index_of(row.scheduled_at)) is not None:
                verdicts_by_index.setdefault(i, []).append(row.verdict)
        mark_at = {i: fold_probes(*vs) for i, vs in verdicts_by_index.items()}
        tally_7d  = Tally(counts of mark_at.values(),
                          not_observed = owed.count - len(mark_at))
        owed_24h  = owed.clip_from(as_of - WINDOW_24H)         # a suffix of `owed`
        offset    = owed.count - owed_24h.count
        marks_24h = [mark_at.get(offset + i, Mark.NOT_OBSERVED) for i in range(owed_24h.count)]
        tally_24h = Tally(counts of marks_24h)
        grid_first = first aligned slot start >= as_of - WINDOW_24H
        lead       = (owed_24h.first.start - grid_first) // interval
        strip      = Strip(first_slot=grid_first, interval_s=..., lead=lead, runs=run_length(marks_24h))
    Cost: O(rows + 1,440). It never builds one object for each of the 10,080 slots of 7 d.
    """
    raise NotImplementedError


def build_board(facts: StatusFacts, as_of: datetime) -> StatusBoard:
    """The whole page data. Pure, so a test passes `as_of` and a list of facts and compares JSON.

    Sorts the checks by (hostname, port). Calls `judge_worker` and `build_check_status`.
    """
    raise NotImplementedError
