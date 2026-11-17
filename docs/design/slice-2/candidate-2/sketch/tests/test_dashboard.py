"""Pure tests of dashboard.py. No database. Table-driven, like tests/test_verdict.py."""

import pytest


def test_each_verdict_value_is_a_mark_value() -> None:
    raise NotImplementedError


@pytest.mark.parametrize("interval_s", [60, 300, 420, 3600])
def test_strip_has_one_slot_for_each_interval_in_a_day_and_ends_with_the_current_slot(
    interval_s: int,
) -> None:
    """420 s does not divide a day. The strip has ceil(86400 / 420) slots."""
    raise NotImplementedError


def test_a_check_made_two_hours_ago_counts_only_slots_that_start_after_it() -> None:
    raise NotImplementedError


def test_a_check_made_in_the_current_slot_has_empty_day_and_week_ranges() -> None:
    raise NotImplementedError


def test_a_row_in_the_slot_that_contains_created_at_shows_in_the_strip_and_is_not_counted() -> None:
    raise NotImplementedError


def test_a_complete_slot_with_no_row_is_not_observed_and_the_current_one_is_pending() -> None:
    raise NotImplementedError


def test_fold_gives_the_verdict_when_all_rows_agree_and_mixed_when_they_do_not() -> None:
    raise NotImplementedError


def test_up_ratio_leaves_out_not_observed_blocked_inconclusive_and_mixed() -> None:
    """100 up, 0 down, 50 not observed -> 1.0, and not_observed == 50 on its own."""
    raise NotImplementedError


def test_up_ratio_is_none_with_no_up_and_no_down() -> None:
    raise NotImplementedError


def test_mark_counts_reject_pending_and_outside() -> None:
    raise NotImplementedError


def test_week_not_observed_is_expected_minus_observed_slots() -> None:
    raise NotImplementedError


def test_day_counts_equal_the_counts_of_the_strip_marks() -> None:
    raise NotImplementedError


@pytest.mark.parametrize(
    ("silence_s", "state"), [(None, "no_rows"), (599, "writing"), (601, "stalled")]
)
def test_worker_state_with_a_300_s_check(silence_s: int | None, state: str) -> None:
    raise NotImplementedError


def test_worker_is_idle_with_no_active_check() -> None:
    raise NotImplementedError


def test_checks_are_in_python_hostname_order_not_sql_collation_order() -> None:
    """a-b.example sorts before a.example in Python and after it in en_US collation."""
    raise NotImplementedError
