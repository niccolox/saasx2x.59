import type { Mark, Reason, WorkerState } from "./api";

// `Record<Union, string>` makes the compiler fail when Python adds a Mark, Reason, or
// WorkerState and this file does not. The generated union is the single list.

export const MARK_LABEL: Record<Mark, string> = {
  up: "Up",
  down: "Down",
  blocked: "Blocked",
  inconclusive: "Inconclusive",
  not_observed: "Not observed",
};

export const REASON_LABEL: Record<Reason, string> = {
  cloudflare_challenge: "Cloudflare challenge",
  cloudflare_block_page: "Cloudflare block page",
  rate_limited: "Rate limited (429)",
  status_ok: "Status 2xx or 3xx",
  login_required: "Login required (401)",
  error_status: "Error status",
  dns_not_found: "DNS name not found",
  tcp_failed: "TCP connection failed",
  tls_failed: "TLS failed",
  http_failed: "HTTP failed",
  dns_unavailable: "DNS did not answer",
  probe_failed: "Probe fault",
};

export const WORKER_LABEL: Record<WorkerState, string> = {
  idle: "No active check",
  fresh: "Worker is writing rows",
  late: "Worker is late",
  stalled: "Worker stopped writing rows",
};

/** Mark appearance. Shape carries the meaning, so the page works without color vision.
 *  height is a fraction of the strip height. */
export const MARK_STYLE: Record<Mark, { fill: string; height: number; hatch: boolean }> = {
  up: { fill: "var(--mark-up)", height: 0.55, hatch: false },
  down: { fill: "var(--mark-down)", height: 1, hatch: false },
  blocked: { fill: "var(--mark-blocked)", height: 1, hatch: true },
  inconclusive: { fill: "var(--mark-inconclusive)", height: 0.8, hatch: false },
  not_observed: { fill: "none", height: 1, hatch: false }, // outline only
};
