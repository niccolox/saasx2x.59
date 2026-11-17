"""The rules of the page, with no database: which slots are expected, the probe fold, the strip,
the counts, and the stall rule."""

import itertools
import typing
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from saasx2x.dashboard import (
    DAY,
    WEEK,
    CheckStatus,
    Dashboard,
    Mark,
    SlotCounts,
    Strip,
    StripRun,
    WorkerStatus,
    build_dashboard,
)
from saasx2x.domain import (
    AccountId,
    ActiveCheck,
    CheckId,
    CheckKind,
    Hostname,
    expected_slots,
)
from saasx2x.store import EvidenceCount, MonitoredCheck, NewestRows, SlotEvidence
from saasx2x.verdict import Reason, Verdict, fold_probes

NOW = datetime(2026, 11, 16, 14, 5, 7, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
FIVE_MINUTES = timedelta(minutes=5)


def at(hour: int, minute: int, *, day: int = 16) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def every(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    return [start + n * step for n in range((end - start) // step)]


def monitored(
    *,
    interval: timedelta = FIVE_MINUTES,
    made: datetime = NOW - timedelta(hours=30),
    newest: NewestRows | None = None,
) -> MonitoredCheck:
    check = ActiveCheck(
        check_id=CheckId(uuid4()),
        account_id=AccountId(uuid4()),
        hostname=Hostname("example.com"),
        port=443,
        interval=interval,
    )
    return MonitoredCheck(check, CheckKind.HTTPS, made, newest)


def rows(check: MonitoredCheck, starts: Iterable[datetime], *reasons: Reason) -> list[SlotEvidence]:
    evidence = reasons or (Reason.STATUS_OK,)
    return [SlotEvidence(check.check.check_id, start, evidence) for start in starts]


def page(
    check: MonitoredCheck,
    day: Iterable[SlotEvidence] = (),
    week: Iterable[EvidenceCount] = (),
    now: datetime = NOW,
) -> CheckStatus:
    (status,) = build_dashboard([check], list(day), list(week), now).checks
    return status


def wrote(minutes_ago: float) -> NewestRows:
    return NewestRows(at(14, 0), NOW - timedelta(minutes=minutes_ago), (Reason.STATUS_OK,))


def worker(*checks: MonitoredCheck) -> WorkerStatus:
    return build_dashboard(checks, [], [], NOW).worker


def test_a_slot_that_started_before_the_check_existed_is_not_expected() -> None:
    made = datetime(2026, 11, 16, 13, 52, 30, tzinfo=UTC)
    expected = expected_slots(FIVE_MINUTES, made, NOW, DAY)
    assert list(expected.starts()) == [at(13, 55), at(14, 0)]


def test_a_slot_that_starts_at_the_creation_instant_is_expected() -> None:
    expected = expected_slots(FIVE_MINUTES, at(13, 55), NOW, DAY)
    assert list(expected.starts()) == [at(13, 55), at(14, 0)]


def test_the_open_slot_is_never_expected() -> None:
    assert expected_slots(FIVE_MINUTES, at(14, 5), NOW, DAY).count == 0
    assert expected_slots(FIVE_MINUTES, NOW + MINUTE, NOW, DAY).count == 0


def test_the_span_limits_the_range_to_the_slots_before_the_open_slot() -> None:
    expected = expected_slots(FIVE_MINUTES, NOW - timedelta(days=30), NOW, DAY)
    assert (expected.start, expected.end, expected.count) == (at(14, 5, day=15), at(14, 5), 288)
    assert expected_slots(FIVE_MINUTES, NOW - timedelta(days=30), NOW, WEEK).count == 2016
    assert expected_slots(MINUTE, NOW - timedelta(days=30), NOW, DAY).count == 1440


def test_an_interval_that_does_not_divide_24_hours_starts_at_the_first_whole_slot() -> None:
    seven = timedelta(minutes=7)
    expected = expected_slots(seven, NOW - timedelta(days=30), NOW, DAY)
    open_start = datetime(2026, 11, 16, 14, 1, tzinfo=UTC)
    assert (open_start - datetime(1970, 1, 1, tzinfo=UTC)) % seven == timedelta(0)
    assert expected.count == 205
    assert expected.start == open_start - 205 * seven
    assert expected.end == open_start


@pytest.mark.parametrize("reason", list(Reason))
def test_one_row_gives_that_row(reason: Reason) -> None:
    assert fold_probes([reason]) is reason


def test_the_order_of_the_rows_does_not_matter() -> None:
    rows = [Reason.TCP_FAILED, Reason.STATUS_OK, Reason.TLS_FAILED, Reason.TCP_FAILED]
    assert {fold_probes(order) for order in itertools.permutations(rows)} == {Reason.TCP_FAILED}


@pytest.mark.parametrize(
    ("reasons", "judgement"),
    [
        ([Reason.STATUS_OK, Reason.TCP_FAILED], Reason.STATUS_OK),
        ([Reason.TCP_FAILED, Reason.TCP_FAILED, Reason.STATUS_OK], Reason.TCP_FAILED),
        ([Reason.PROBE_FAILED, Reason.RATE_LIMITED], Reason.RATE_LIMITED),
        ([Reason.TCP_FAILED, Reason.DNS_UNAVAILABLE], Reason.DNS_UNAVAILABLE),
        ([Reason.TCP_FAILED, Reason.DNS_NOT_FOUND, Reason.DNS_NOT_FOUND], Reason.DNS_NOT_FOUND),
        ([Reason.TCP_FAILED, Reason.DNS_NOT_FOUND], Reason.DNS_NOT_FOUND),
    ],
)
def test_the_most_rows_win_and_a_tie_goes_to_the_milder_verdict(
    reasons: list[Reason], judgement: Reason
) -> None:
    assert fold_probes(reasons) is judgement


def test_a_slot_with_no_row_is_a_not_observed_run_between_two_up_runs() -> None:
    check = monitored()
    expected = expected_slots(FIVE_MINUTES, check.created_at, NOW, DAY)
    status = page(check, rows(check, (s for s in expected.starts() if s != at(9, 0))))

    assert [(run.start, run.end, run.mark) for run in status.strip.runs] == [
        (at(14, 5, day=15), at(9, 0), Verdict.UP),
        (at(9, 0), at(9, 5), "not_observed"),
        (at(9, 5), at(14, 5), Verdict.UP),
    ]
    assert (status.strip.start, status.strip.end) == (at(14, 5, day=15), at(14, 10))
    assert status.day.not_observed == 1
    assert status.day.up == 287


def test_the_strip_has_no_run_before_the_check_existed() -> None:
    status = page(monitored(made=NOW - timedelta(hours=1)))
    assert [(run.start, run.end, run.reason) for run in status.strip.runs] == [
        (at(13, 10), at(14, 5), None)
    ]
    assert status.day.not_observed == 11


def test_the_slot_of_creation_and_the_open_slot_show_a_row_but_are_not_counted() -> None:
    check = monitored(made=datetime(2026, 11, 16, 13, 52, 30, tzinfo=UTC))
    status = page(check, rows(check, [at(13, 50), at(13, 55), at(14, 0), at(14, 5)]))
    assert [(run.start, run.end) for run in status.strip.runs] == [(at(13, 50), at(14, 10))]
    assert (status.day.up, status.day.expected) == (2, 2)


def test_a_check_that_is_up_all_day_at_60_s_is_one_run_on_the_whole_axis() -> None:
    check = monitored(interval=MINUTE, made=NOW - timedelta(days=2))
    status = page(check, rows(check, every(at(14, 5, day=15), at(14, 6), MINUTE)))
    assert [(run.start, run.end, run.mark) for run in status.strip.runs] == [
        (at(14, 5, day=15), at(14, 6), Verdict.UP)
    ]
    assert (status.day.up, status.day.expected, status.day.up_ratio) == (1440, 1440, 1.0)


def test_slots_in_sequence_merge_only_when_their_reasons_are_equal() -> None:
    check = monitored(made=at(13, 0))
    day = rows(check, [at(13, 0), at(13, 5)], Reason.STATUS_OK)
    day += rows(check, [at(13, 10)], Reason.LOGIN_REQUIRED)
    day += rows(check, [at(13, 15), at(13, 20)], Reason.TCP_FAILED)
    day += rows(check, [at(13, 25)], Reason.DNS_NOT_FOUND)
    status = page(check, day)
    assert [(run.reason, run.mark) for run in status.strip.runs][:4] == [
        (Reason.STATUS_OK, Verdict.UP),
        (Reason.LOGIN_REQUIRED, Verdict.UP),
        (Reason.TCP_FAILED, Verdict.DOWN),
        (Reason.DNS_NOT_FOUND, Verdict.DOWN),
    ]


def test_two_probes_of_one_slot_show_one_mark() -> None:
    check = monitored(made=at(13, 55))
    status = page(check, rows(check, [at(13, 55)], Reason.STATUS_OK, Reason.TCP_FAILED))
    assert [run.reason for run in status.strip.runs] == [Reason.STATUS_OK, None]


def test_a_row_of_an_older_interval_is_not_on_the_strip() -> None:
    check = monitored(made=at(13, 52))
    status = page(check, rows(check, [at(13, 55), at(13, 57), at(14, 0)]))
    assert [(run.start, run.end) for run in status.strip.runs] == [(at(13, 55), at(14, 5))]


def test_two_runs_that_touch_with_one_reason_are_not_a_valid_strip() -> None:
    def run(start: datetime, end: datetime) -> StripRun:
        return StripRun(start=start, end=end, reason=Reason.STATUS_OK)

    with pytest.raises(ValidationError):
        Strip(
            start=at(13, 0),
            end=at(14, 0),
            runs=(run(at(13, 0), at(13, 5)), run(at(13, 5), at(13, 10))),
        )
    with pytest.raises(ValidationError):
        Strip(
            start=at(13, 0),
            end=at(14, 0),
            runs=(run(at(13, 0), at(13, 10)), run(at(13, 5), at(13, 15))),
        )
    with pytest.raises(ValidationError):
        Strip(start=at(13, 0), end=at(14, 0), runs=(run(at(12, 55), at(13, 5)),))


def test_the_field_names_of_the_counts_are_the_values_of_mark() -> None:
    marks = {str(value) for arm in typing.get_args(Mark.__value__) for value in _values(arm)}
    assert set(SlotCounts.model_fields) == marks


def _values(arm: object) -> list[object]:
    if isinstance(arm, type) and issubclass(arm, Verdict):
        return list(arm)
    return list(typing.get_args(arm))


def test_uptime_is_up_over_up_plus_down_and_not_observed_is_never_up() -> None:
    check = monitored(made=at(13, 0))
    day = rows(check, every(at(13, 0), at(13, 30), FIVE_MINUTES))
    day += rows(check, [at(13, 30)], Reason.TCP_FAILED)
    day += rows(check, [at(13, 35)], Reason.RATE_LIMITED)
    day += rows(check, [at(13, 40)], Reason.PROBE_FAILED)
    status = page(check, day)
    assert status.day == SlotCounts(up=6, down=1, blocked=1, inconclusive=1, not_observed=4)
    assert status.day.expected == 13
    assert status.day.up_ratio == 6 / 7


def test_a_span_with_no_up_or_down_slot_has_no_uptime() -> None:
    status = page(monitored(made=at(13, 0)))
    assert status.day.up_ratio is None
    assert status.day.not_observed == 13


def test_the_week_counts_add_the_counted_evidence_and_the_rest_is_not_observed() -> None:
    check = monitored()
    week = [
        EvidenceCount(check.check.check_id, (Reason.STATUS_OK,), 350),
        EvidenceCount(check.check.check_id, (Reason.TCP_FAILED,), 4),
        EvidenceCount(check.check.check_id, (Reason.STATUS_OK, Reason.TCP_FAILED), 2),
    ]
    status = page(check, week=week)
    total = expected_slots(FIVE_MINUTES, check.created_at, NOW, WEEK).count
    assert total == 359
    assert status.week == SlotCounts(up=352, down=4, blocked=0, inconclusive=0, not_observed=3)
    assert status.week.expected == total


def test_the_week_not_observed_count_is_never_below_zero() -> None:
    check = monitored(made=at(13, 0))
    status = page(check, week=[EvidenceCount(check.check.check_id, (Reason.STATUS_OK,), 99)])
    assert (status.week.up, status.week.not_observed) == (99, 0)


def test_the_counts_of_each_check_are_its_own() -> None:
    first, second = monitored(made=at(13, 0)), monitored(made=at(13, 0))
    day = rows(first, [at(13, 0)], Reason.TCP_FAILED) + rows(second, [at(13, 0)])
    week = [EvidenceCount(second.check.check_id, (Reason.STATUS_OK,), 1)]
    one, two = build_dashboard([first, second], day, week, NOW).checks
    assert (one.day.down, one.day.up, one.week.up) == (1, 0, 0)
    assert (two.day.down, two.day.up, two.week.up) == (0, 1, 1)


def test_the_last_result_is_the_newest_slot_also_when_it_is_older_than_the_strip() -> None:
    old = at(9, 0, day=13)
    newest = NewestRows(old, old + timedelta(seconds=2), (Reason.TCP_FAILED, Reason.TCP_FAILED))
    status = page(monitored(newest=newest))
    assert status.last is not None
    assert (status.last.slot_start, status.last.reason, status.last.verdict) == (
        old,
        Reason.TCP_FAILED,
        Verdict.DOWN,
    )
    assert page(monitored()).last is None


def test_no_active_check_is_idle() -> None:
    assert worker() == WorkerStatus(state="idle", newest_row_at=None, expected_every_s=None)


def test_a_new_check_with_no_row_waits_for_its_first_row() -> None:
    status = worker(monitored(interval=MINUTE, made=NOW - timedelta(seconds=110)))
    assert (status.state, status.newest_row_at, status.expected_every_s) == ("waiting", None, 60)


def test_a_check_with_no_row_after_one_interval_and_60_s_is_stalled() -> None:
    status = worker(monitored(interval=MINUTE, made=NOW - timedelta(seconds=121)))
    assert (status.state, status.newest_row_at) == ("stalled", None)


def test_a_row_inside_the_shortest_interval_plus_60_s_is_writing() -> None:
    status = worker(monitored(interval=MINUTE, made=at(9, 0), newest=wrote(1.9)))
    assert (status.state, status.newest_row_at) == ("writing", NOW - timedelta(minutes=1.9))


def test_the_shortest_interval_decides_the_stall() -> None:
    status = worker(
        monitored(interval=MINUTE, made=at(9, 0), newest=wrote(3.5)),
        monitored(interval=FIVE_MINUTES, made=at(9, 0), newest=wrote(3)),
    )
    assert (status.state, status.expected_every_s) == ("stalled", 60)
    assert status.newest_row_at == NOW - timedelta(minutes=3)


def test_a_new_check_starts_the_wait_again() -> None:
    old = monitored(interval=MINUTE, made=at(9, 0), newest=wrote(60))
    assert worker(old).state == "stalled"
    assert worker(old, monitored(interval=MINUTE, made=NOW - timedelta(seconds=30))).state == (
        "writing"
    )


def test_the_worker_line_cannot_disagree_with_its_state() -> None:
    with pytest.raises(ValidationError):
        WorkerStatus(state="idle", newest_row_at=None, expected_every_s=60)
    with pytest.raises(ValidationError):
        WorkerStatus(state="writing", newest_row_at=None, expected_every_s=60)
    with pytest.raises(ValidationError):
        WorkerStatus(state="waiting", newest_row_at=NOW, expected_every_s=60)


def test_the_page_says_when_it_was_made_and_when_to_ask_again() -> None:
    dashboard = build_dashboard([], [], [], NOW)
    assert dashboard == Dashboard(
        generated_at=NOW,
        refresh_after_s=60,
        worker=WorkerStatus(state="idle", newest_row_at=None, expected_every_s=None),
        checks=(),
    )
