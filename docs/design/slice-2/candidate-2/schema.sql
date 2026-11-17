-- migrations/0002_dashboard_index.sql
-- Slice 2 adds one index and no table, view or column. `check_results` does not change.
--
-- The dashboard shows, for each probe, the newest row that it wrote for the account
-- (`_PROBE_ACTIVITY` in store.py). Without this index, that query reads the whole table once
-- each minute, and the table grows each slot.
--
-- The other dashboard queries use the primary key (check_id, scheduled_at, probe_id):
--   * the strip and week tallies: a range scan on (check_id, scheduled_at)
--   * the newest slot of each check: max(scheduled_at) for one check_id
--
-- The migration runner applies each file in one transaction, so this is a plain CREATE INDEX,
-- not CREATE INDEX CONCURRENTLY. The table is small in slice 2.

CREATE INDEX check_results_account_probe_started
    ON check_results (account_id, probe_id, started_at DESC);
