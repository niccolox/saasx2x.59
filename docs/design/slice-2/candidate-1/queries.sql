-- The three read statements of the dashboard. They go in `ReadStore` in store.py.
-- Slice 2 has no migration: the primary key of check_results
-- (check_id, scheduled_at, probe_id) serves each statement.
-- If statement 3 gets slow with many 60 s checks, the later fix is one index:
--   CREATE INDEX check_results_reason ON check_results (check_id, scheduled_at) INCLUDE (reason);

-- 1. ReadStore.monitored_checks(account)
--    Each check of each active target, with the rows of its newest slot.
SELECT c.id, c.account_id, t.hostname, c.port, c.interval_s, c.kind::text, c.created_at,
       newest.scheduled_at, newest.finished_at, newest.reasons
  FROM checks c
  JOIN targets t ON t.id = c.target_id
  LEFT JOIN LATERAL (
        SELECT r.scheduled_at,
               max(r.started_at + r.duration_ms * interval '1 millisecond') AS finished_at,
               array_agg(r.reason::text ORDER BY r.reason) AS reasons
          FROM check_results r
         WHERE r.check_id = c.id
           AND r.scheduled_at = (SELECT max(scheduled_at) FROM check_results WHERE check_id = c.id)
         GROUP BY r.scheduled_at
       ) newest ON true
 WHERE t.removed_at IS NULL
   AND c.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
 ORDER BY t.hostname, c.port;

-- 2. ReadStore.slot_evidence(account, windows)
--    One row for each slot that has a row, with one reason for each probe.
--    Postgres does not make the slots that have no row. `expected_slots` in domain.py does.
SELECT r.check_id, r.scheduled_at, array_agg(r.reason::text ORDER BY r.reason) AS reasons
  FROM check_results r
  JOIN unnest(%(check_ids)s::uuid[], %(since)s::timestamptz[], %(until)s::timestamptz[])
       AS w (check_id, since, until)
    ON r.check_id = w.check_id AND r.scheduled_at >= w.since AND r.scheduled_at < w.until
 WHERE r.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
 GROUP BY r.check_id, r.scheduled_at
 ORDER BY r.check_id, r.scheduled_at;

-- 3. ReadStore.evidence_counts(account, windows)
--    Statement 2 as a subquery, then one row for each kind of evidence of each check.
--    Postgres counts equal evidence. It gives no verdict to a slot.
SELECT slot.check_id, slot.reasons, count(*) AS slots
  FROM (
        SELECT r.check_id, r.scheduled_at,
               array_agg(r.reason::text ORDER BY r.reason) AS reasons
          FROM check_results r
          JOIN unnest(%(check_ids)s::uuid[], %(since)s::timestamptz[], %(until)s::timestamptz[])
               AS w (check_id, since, until)
            ON r.check_id = w.check_id AND r.scheduled_at >= w.since AND r.scheduled_at < w.until
         WHERE r.account_id = (SELECT id FROM accounts WHERE slug = %(account)s)
         GROUP BY r.check_id, r.scheduled_at
       ) slot
 GROUP BY slot.check_id, slot.reasons;
