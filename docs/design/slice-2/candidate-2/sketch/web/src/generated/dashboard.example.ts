// ILLUSTRATION ONLY. This is about what `npm run gen` writes to dashboard.ts from the schema of
// `saasx2x.dashboard.Dashboard`. It is here so a reader of the sketch can see the shape.
// The real file is generated and is not committed. Do not import this file.

export type Mark =
  | "up" | "down" | "blocked" | "inconclusive"
  | "mixed" | "not_observed" | "pending" | "outside";
export type Reason =
  | "cloudflare_challenge" | "cloudflare_block_page" | "rate_limited"
  | "status_ok" | "login_required" | "error_status"
  | "dns_not_found" | "tcp_failed" | "tls_failed" | "http_failed"
  | "dns_unavailable" | "probe_failed";
export type WorkerState = "writing" | "stalled" | "no_rows" | "idle";
export type CheckKind = "https";

export interface MarkCounts {
  up: number; down: number; blocked: number; inconclusive: number;
  mixed: number; not_observed: number;
  readonly expected: number;
  readonly up_ratio: number | null;
}
export interface Strip { first_slot_start: string; interval_s: number; marks: Mark[] }
export interface LastResult { slot_start: string; mark: Mark; reasons: Reason[]; probes: number }
export interface CheckPanel {
  check_id: string; kind: CheckKind; hostname: string; port: number; interval_s: number;
  last: LastResult | null; strip: Strip; day: MarkCounts; week: MarkCounts;
}
export interface WorkerLine {
  probe_id: string; state: WorkerState; newest_row_at: string | null; stall_after_s: number | null;
}
export interface Dashboard {
  account: string; as_of: string; workers: WorkerLine[]; checks: CheckPanel[];
}
