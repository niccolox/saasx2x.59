"""The dashboard read model.

This module owns two things:

1. The JSON shape of `GET /api/dashboard`. The classes below are that shape. FastAPI writes the
   OpenAPI document from them, and the page makes its TypeScript types from that document.
2. The rules that turn rows into that shape: which marks a strip shows, what an uptime counts,
   and when the worker is stalled.

`build_dashboard` is pure. `read_dashboard` is the only function here that waits for I/O.
This module imports no `fastapi` and no `psycopg`.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
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

from saasx2x.domain import (
    AccountSlug,
    CheckId,
    CheckKind,
    Hostname,
    Slot,
    SlotRange,
    expected_slots,
)
from saasx2x.store import (
    DashboardRows,
    EvidenceCount,
    EvidenceWindow,
    MonitoredCheck,
    ReadWindows,
    SlotEvidence,
    WindowPlan,
)
from saasx2x.verdict import Reason, Verdict, fold_probes

DAY: Final = timedelta(hours=24)
"""The span of the strip and of the first uptime."""
WEEK: Final = timedelta(days=7)
"""The span of the second uptime."""
REFRESH_AFTER: Final = timedelta(seconds=60)
"""The page asks again after this time. The page reads it from each answer."""
STALL_SLACK: Final = timedelta(seconds=60)
"""A row can be this late before the worker counts as stalled. A check takes at most 30 s."""

NOT_OBSERVED: Final = "not_observed"

type Mark = Verdict | Literal["not_observed"]
"""What one slot shows. A verdict when a probe wrote a row. "not_observed" when no probe wrote
a row for an expected slot. Derived from `Verdict`, so the two cannot differ."""

type WorkerState = Literal["idle", "waiting", "writing", "stalled"]


def _mark(reason: Reason | None) -> Mark:
    return NOT_OBSERVED if reason is None else reason.verdict


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
        return _mark(self.reason)


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
        edge, previous = self.start, None
        for run in self.runs:
            if not edge <= run.start < run.end <= self.end:
                raise ValueError("runs must be in time order, apart, and inside the axis")
            if previous is not None and previous.end == run.start and previous.reason == run.reason:
                raise ValueError("two runs that touch must have different reasons")
            edge, previous = run.end, run
        return self


class SlotCounts(_Wire):
    """The expected slots of one span, counted by mark. The five numbers are disjoint."""

    up: NonNegativeInt
    down: NonNegativeInt
    blocked: NonNegativeInt
    inconclusive: NonNegativeInt
    not_observed: NonNegativeInt

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

    state: WorkerState
    newest_row_at: AwareDatetime | None
    """The end of the newest check, which is when the worker wrote its row. None: no row."""
    expected_every_s: int | None
    """The shortest interval of an active check. None exactly when `state` is "idle"."""

    @model_validator(mode="after")
    def _state_agrees_with_the_fields(self) -> Self:
        if (self.state == "idle") != (self.expected_every_s is None):
            raise ValueError("expected_every_s is None exactly when the state is idle")
        if (self.state == "writing") and self.newest_row_at is None:
            raise ValueError("a writing worker has a newest row")
        if self.state in ("idle", "waiting") and self.newest_row_at is not None:
            raise ValueError(f"a worker in state {self.state} has no row")
        return self


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
    """What `read_dashboard` needs. `ReadStore` satisfies it."""

    async def dashboard_rows(self, account: AccountSlug, windows: WindowPlan) -> DashboardRows: ...


async def read_dashboard(store: DashboardStore, account: AccountSlug, now: datetime) -> Dashboard:
    """Read the rows that the page needs and build the page. One snapshot, no write."""
    rows = await store.dashboard_rows(account, lambda check: _read_windows(check, now))
    return build_dashboard(rows.checks, rows.slots, rows.counts, now)


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
            Slots in sequence with the same reason merge into one run. A row that is not on the
            slot grid of the current interval is not on the strip: it is from an older interval.
    day     One count for each slot of `expected_slots(..., DAY)`: the verdict of its row, or
            "not observed". The open slot is not expected, so an uptime does not change inside
            a slot.
    week    `expected_slots(..., WEEK).count` is the total. Each EvidenceCount adds `slots` to
            the verdict of `fold_probes(reasons)`. "not observed" is the total minus that sum,
            and never less than 0.
    last    `fold_probes(newest.reasons)` with its slot start.
    """
    slots_of: defaultdict[CheckId, dict[datetime, tuple[Reason, ...]]] = defaultdict(dict)
    for evidence in day:
        slots_of[evidence.check_id][evidence.scheduled_at] = evidence.reasons
    counts_of: defaultdict[CheckId, list[EvidenceCount]] = defaultdict(list)
    for count in week:
        counts_of[count.check_id].append(count)
    return Dashboard(
        generated_at=now,
        refresh_after_s=int(REFRESH_AFTER.total_seconds()),
        worker=_worker_status(checks, now),
        checks=tuple(
            _check_status(
                check, slots_of[check.check.check_id], counts_of[check.check.check_id], now
            )
            for check in checks
        ),
    )


def _strip_axis(interval: timedelta, now: datetime) -> EvidenceWindow:
    open_slot = Slot.containing(now, interval)
    return EvidenceWindow(open_slot.start - DAY, open_slot.end)


def _read_windows(check: MonitoredCheck, now: datetime) -> ReadWindows:
    """The strip reads each slot on its axis. The 7 day uptime reads only counts."""
    week = expected_slots(check.check.interval, check.created_at, now, WEEK)
    return ReadWindows(
        slots=_strip_axis(check.check.interval, now),
        counts=EvidenceWindow(week.start, week.end),
    )


def _check_status(
    check: MonitoredCheck,
    slots: Mapping[datetime, tuple[Reason, ...]],
    counts: Sequence[EvidenceCount],
    now: datetime,
) -> CheckStatus:
    interval = check.check.interval
    judged = {
        start: fold_probes(reasons)
        for start, reasons in slots.items()
        if Slot.containing(start, interval).start == start
    }
    day = expected_slots(interval, check.created_at, now, DAY)
    week = expected_slots(interval, check.created_at, now, WEEK)

    day_marks = Counter[str](_mark(judged.get(start)) for start in day.starts())
    week_marks = Counter[str]()
    for count in counts:
        week_marks[fold_probes(count.reasons).verdict] += count.slots
    week_marks[NOT_OBSERVED] = max(0, week.count - week_marks.total())

    newest = check.newest
    return CheckStatus(
        check_id=check.check.check_id,
        hostname=check.check.hostname,
        port=check.check.port,
        kind=check.kind,
        interval_s=int(interval.total_seconds()),
        last=None
        if newest is None
        else LastResult(slot_start=newest.scheduled_at, reason=fold_probes(newest.reasons)),
        strip=_strip(judged, day, now),
        day=_slot_counts(day_marks),
        week=_slot_counts(week_marks),
    )


def _strip(judged: Mapping[datetime, Reason], day: SlotRange, now: datetime) -> Strip:
    interval = day.first.interval
    marks: dict[datetime, Reason | None] = dict.fromkeys(day.starts())
    marks.update(judged)
    runs: list[tuple[datetime, datetime, Reason | None]] = []
    for start in sorted(marks):
        reason = marks[start]
        if runs and runs[-1][1] == start and runs[-1][2] == reason:
            runs[-1] = (runs[-1][0], start + interval, reason)
        else:
            runs.append((start, start + interval, reason))
    axis = _strip_axis(interval, now)
    return Strip(
        start=axis.since,
        end=axis.until,
        runs=tuple(StripRun(start=start, end=end, reason=reason) for start, end, reason in runs),
    )


def _slot_counts(marks: Counter[str]) -> SlotCounts:
    return SlotCounts(
        up=marks[Verdict.UP],
        down=marks[Verdict.DOWN],
        blocked=marks[Verdict.BLOCKED],
        inconclusive=marks[Verdict.INCONCLUSIVE],
        not_observed=marks[NOT_OBSERVED],
    )


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
    if not checks:
        return WorkerStatus(state="idle", newest_row_at=None, expected_every_s=None)
    shortest = min(check.check.interval for check in checks)
    newest = max((check.newest.finished_at for check in checks if check.newest), default=None)
    reference = max(check.created_at for check in checks)
    if newest is not None:
        reference = max(reference, newest)
    state: WorkerState
    if now - reference > shortest + STALL_SLACK:
        state = "stalled"
    else:
        state = "waiting" if newest is None else "writing"
    return WorkerStatus(
        state=state, newest_row_at=newest, expected_every_s=int(shortest.total_seconds())
    )
