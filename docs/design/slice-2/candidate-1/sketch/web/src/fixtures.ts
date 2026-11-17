// Dashboards for the component tests. `satisfies Dashboard` makes `tsc` check each one against
// the generated types, so a fixture cannot keep an old shape.
import type { Dashboard } from "./api";

/** One check, 300 s interval, up all day except one down run and one slot not observed. */
export const oneOutage = {
  generated_at: "2026-11-16T14:05:07Z",
  refresh_after_s: 60,
  worker: { state: "writing", newest_row_at: "2026-11-16T14:03:21Z", expected_every_s: 300 },
  checks: [
    {
      check_id: "6f1c1f0e-5b0a-4f0e-9d53-0a6f6f2f8c11",
      hostname: "example.com",
      port: 443,
      kind: "https",
      interval_s: 300,
      last: { slot_start: "2026-11-16T14:00:00Z", reason: "status_ok", verdict: "up" },
      strip: {
        start: "2026-11-15T14:05:00Z",
        end: "2026-11-16T14:10:00Z",
        runs: [
          { start: "2026-11-15T14:05:00Z", end: "2026-11-16T03:10:00Z", reason: "status_ok", mark: "up" },
          { start: "2026-11-16T03:10:00Z", end: "2026-11-16T03:25:00Z", reason: "tcp_failed", mark: "down" },
          { start: "2026-11-16T03:25:00Z", end: "2026-11-16T09:00:00Z", reason: "status_ok", mark: "up" },
          { start: "2026-11-16T09:00:00Z", end: "2026-11-16T09:05:00Z", reason: null, mark: "not_observed" },
          { start: "2026-11-16T09:05:00Z", end: "2026-11-16T14:05:00Z", reason: "status_ok", mark: "up" },
        ],
      },
      day: { up: 284, down: 3, blocked: 0, inconclusive: 0, not_observed: 1, expected: 288, up_ratio: 0.9895 },
      week: { up: 2010, down: 3, blocked: 0, inconclusive: 2, not_observed: 1, expected: 2016, up_ratio: 0.9985 },
    },
  ],
} satisfies Dashboard;

// TODO: `stalledWorker` (state "stalled", newest row 16 hours old, each strip ends in a long
// "not observed" run) and `minuteCheckOneDownSlot` (60 s interval, 1,440 slots, one down slot).
