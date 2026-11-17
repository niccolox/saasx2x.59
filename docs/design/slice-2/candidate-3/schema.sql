-- migrations/0002_status_reads.sql
-- Slice 2 adds one index and no table. `check_results` does not change.
--
-- The status page asks one question that no index answers today: "what is the newest row for this
-- account?" The answer drives the worker line, which shows a stalled worker. Without this index,
-- Postgres scans every row of the account to find the newest `started_at`.
--
-- The other two reads use the primary key (check_id, scheduled_at, probe_id):
--   * the last result of one check:   ORDER BY scheduled_at DESC LIMIT 1 for one check_id
--   * the slot rows of the last 7 d:  check_id = ANY(...) AND scheduled_at >= :since
--
-- `account_id` leads the index so that row-level security by account (a later slice) can use it.

CREATE INDEX check_results_account_started_idx
    ON check_results (account_id, started_at DESC);
