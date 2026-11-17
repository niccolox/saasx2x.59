// The words and the style class of each mark and each reason.
// Each table is a `Record` over a generated union. When Python adds a verdict or a reason,
// `tsc` fails here until the table has the new key.
import type { Mark, Reason, WorkerStatus } from "./api";

export const MARK_LABEL: Record<Mark, string> = {
  up: "up",
  down: "down",
  blocked: "blocked",
  inconclusive: "inconclusive",
  not_observed: "not observed",
};

/** The draw order of the strip. A later mark is drawn over an earlier one. */
export const MARK_DRAW_ORDER: readonly Mark[] = [
  "up",
  "inconclusive",
  "blocked",
  "not_observed",
  "down",
];

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

export const WORKER_LABEL: Record<WorkerStatus["state"], string> = {
  idle: "No active check",
  waiting: "No row yet",
  writing: "Worker writes rows",
  stalled: "Worker stalled",
};
