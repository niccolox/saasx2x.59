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

/** One 60 s check, 1,440 slots on the axis, one down slot at 03:10. */
export const minuteCheckOneDownSlot = {
  generated_at: "2026-11-16T14:05:07Z",
  refresh_after_s: 60,
  worker: { state: "writing", newest_row_at: "2026-11-16T14:04:01Z", expected_every_s: 60 },
  checks: [
    {
      check_id: "0b0e6d1c-34a1-4b8e-9a43-3f1b5f0c2d77",
      hostname: "a.example",
      port: 443,
      kind: "https",
      interval_s: 60,
      last: { slot_start: "2026-11-16T14:04:00Z", reason: "status_ok", verdict: "up" },
      strip: {
        start: "2026-11-15T14:05:00Z",
        end: "2026-11-16T14:06:00Z",
        runs: [
          { start: "2026-11-15T14:05:00Z", end: "2026-11-16T03:10:00Z", reason: "status_ok", mark: "up" },
          { start: "2026-11-16T03:10:00Z", end: "2026-11-16T03:11:00Z", reason: "tcp_failed", mark: "down" },
          { start: "2026-11-16T03:11:00Z", end: "2026-11-16T14:05:00Z", reason: "status_ok", mark: "up" },
        ],
      },
      day: { up: 1439, down: 1, blocked: 0, inconclusive: 0, not_observed: 0, expected: 1440, up_ratio: 1439 / 1440 },
      week: { up: 10079, down: 1, blocked: 0, inconclusive: 0, not_observed: 0, expected: 10080, up_ratio: 10079 / 10080 },
    },
  ],
} satisfies Dashboard;

/** The worker wrote its last row 15 h 54 min ago. Each strip ends in a long "not observed" run. */
export const stalledWorker = {
  generated_at: "2026-11-16T14:05:07Z",
  refresh_after_s: 60,
  worker: { state: "stalled", newest_row_at: "2026-11-15T22:10:31Z", expected_every_s: 60 },
  checks: [
    {
      check_id: "9a7c0f5e-1d2b-4c3a-8e9f-0a1b2c3d4e5f",
      hostname: "example.com",
      port: 443,
      kind: "https",
      interval_s: 60,
      last: { slot_start: "2026-11-15T22:10:00Z", reason: "status_ok", verdict: "up" },
      strip: {
        start: "2026-11-15T14:05:00Z",
        end: "2026-11-16T14:06:00Z",
        runs: [
          { start: "2026-11-15T14:05:00Z", end: "2026-11-15T22:11:00Z", reason: "status_ok", mark: "up" },
          { start: "2026-11-15T22:11:00Z", end: "2026-11-16T14:05:00Z", reason: null, mark: "not_observed" },
        ],
      },
      day: { up: 486, down: 0, blocked: 0, inconclusive: 0, not_observed: 954, expected: 1440, up_ratio: 1 },
      week: { up: 9126, down: 0, blocked: 0, inconclusive: 0, not_observed: 954, expected: 10080, up_ratio: 1 },
    },
  ],
} satisfies Dashboard;
