"""DashboardReader against a scratch database on the Compose Postgres (conftest.py).

The tests write rows with psycopg directly (test code may write). The reader never writes.
"""


async def test_date_bin_puts_each_instant_in_the_slot_of_slot_containing() -> None:
    """For many instants and intervals 60, 300, 420, 3600: SQL date_bin == Slot.containing."""
    raise NotImplementedError


async def test_strip_tallies_count_each_probe_row_of_a_slot() -> None:
    """Two probes, one slot, one up and one down -> {up: 1, down: 1}."""
    raise NotImplementedError


async def test_week_buckets_group_equal_tallies() -> None:
    """A full week of one 300 s check (2,015 complete slots), 3 down -> {up: 1} x 2012, {down: 1} x 3."""
    raise NotImplementedError


async def test_rows_from_before_an_interval_change_bin_into_the_current_slots() -> None:
    raise NotImplementedError


async def test_latest_slot_has_all_probe_rows_of_the_newest_slot() -> None:
    raise NotImplementedError


async def test_probe_activity_gives_started_at_plus_duration_of_the_newest_row() -> None:
    raise NotImplementedError


async def test_facts_of_one_account_never_include_a_check_of_another_account() -> None:
    raise NotImplementedError


async def test_a_removed_target_is_not_in_the_facts() -> None:
    raise NotImplementedError


async def test_a_session_with_the_reader_options_cannot_insert() -> None:
    """psycopg.connect(url, options=READ_ONLY_OPTIONS); INSERT -> ReadOnlySqlTransaction."""
    raise NotImplementedError


async def test_reader_raises_store_unavailable_before_migrate() -> None:
    raise NotImplementedError


async def test_probe_activity_uses_the_new_index() -> None:
    """EXPLAIN with enable_seqscan = off: the plan names check_results_account_probe_started."""
    raise NotImplementedError
