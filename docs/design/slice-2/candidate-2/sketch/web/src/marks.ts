// Display tables. Each table is `satisfies Record<Union, ...>` on a generated union, so a new
// Mark, Reason or WorkerState value from Python fails `tsc` until the table has a row for it.
import type { Mark, Reason, WorkerState } from "./generated/dashboard";

export interface MarkStyle {
  label: string;
  /** CSS custom property, set in styles.css for light and dark. */
  fill: string;
  /** Bar height as a fraction of the strip height. Down is full height, up is lower, so the
   * strip reads without color (red and green look the same to some owners). */
  height: number;
  /** Not observed and pending are drawn as an outline, not a fill: no data is not a color. */
  outline: boolean;
}

export const MARK_STYLE = {
  up:           { label: "up",           fill: "var(--mark-up)",           height: 0.55, outline: false },
  down:         { label: "down",         fill: "var(--mark-down)",         height: 1.0,  outline: false },
  blocked:      { label: "blocked",      fill: "var(--mark-blocked)",      height: 0.8,  outline: false },
  inconclusive: { label: "inconclusive", fill: "var(--mark-inconclusive)", height: 0.8,  outline: false },
  mixed:        { label: "probes disagree", fill: "var(--mark-mixed)",     height: 0.9,  outline: false },
  not_observed: { label: "not observed", fill: "var(--mark-gap)",          height: 1.0,  outline: true },
  pending:      { label: "in progress",  fill: "var(--mark-pending)",      height: 0.55, outline: true },
  outside:      { label: "before the check existed", fill: "transparent",  height: 0,    outline: false },
} as const satisfies Record<Mark, MarkStyle>;

/**
 * The order to pick one mark when one pixel column holds several slots. Display only: it is not a
 * verdict rule and no number on the page comes from it. The first mark in this list wins, so a
 * single down slot or a single gap stays visible at 1,440 slots.
 */
export const COLUMN_PRIORITY: readonly Mark[] = [
  "down", "not_observed", "mixed", "blocked", "inconclusive", "up", "pending", "outside",
];

export const REASON_TEXT = {
  cloudflare_challenge: "Cloudflare challenge",
  cloudflare_block_page: "Cloudflare block page",
  rate_limited: "rate limited (429)",
  status_ok: "status 200 to 399",
  login_required: "login required (401)",
  error_status: "error status",
  dns_not_found: "DNS name not found",
  tcp_failed: "TCP connection failed",
  tls_failed: "TLS failed",
  http_failed: "HTTP failed",
  dns_unavailable: "DNS gave no answer",
  probe_failed: "probe fault",
} as const satisfies Record<Reason, string>;

export const WORKER_TEXT = {
  writing: "writing rows",
  stalled: "STALLED: no new rows",
  no_rows: "no row yet",
  idle: "no active check",
} as const satisfies Record<WorkerState, string>;
