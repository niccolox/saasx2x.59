// The words and the order of each mark, reason, and worker state.
// Each table is a `Record` over a generated union. When Python adds a verdict, a reason, or a
// worker state, `tsc` fails here until the table has the new key.
import type { Mark, Reason, WorkerState } from "./api";

export const MARK_LABEL: Record<Mark, string> = {
  up: "up",
  down: "down",
  blocked: "blocked",
  inconclusive: "inconclusive",
  not_observed: "not observed",
};

/**
 * When runs share one pixel column of the strip, the column shows the mark with the lowest
 * rank. A down slot must stay visible among 1,440 up slots.
 */
export const MARK_RANK: Record<Mark, number> = {
  down: 0,
  not_observed: 1,
  inconclusive: 2,
  blocked: 3,
  up: 4,
};

export const REASON_LABEL: Record<Reason, string> = {
  cloudflare_challenge: "Cloudflare challenge",
  cloudflare_block_page: "Cloudflare block page",
  rate_limited: "rate limited (429)",
  status_ok: "status OK",
  login_required: "login required (401)",
  error_status: "error status",
  dns_not_found: "DNS name not found",
  tcp_failed: "TCP failed",
  tls_failed: "TLS failed",
  http_failed: "HTTP failed",
  dns_unavailable: "DNS gave no answer",
  probe_failed: "probe fault",
};

export const WORKER_LABEL: Record<WorkerState, string> = {
  idle: "No active check",
  waiting: "Waiting for the first row",
  writing: "Worker writes rows",
  stalled: "Worker stalled",
};
