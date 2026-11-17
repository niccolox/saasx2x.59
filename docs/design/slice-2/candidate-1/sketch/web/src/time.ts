// Time rules of the page. Pure. The browser wall clock is never compared with a server time.
import type { Snapshot } from "./api";

/**
 * The server time now, in ms since the epoch: `generated_at` plus the time since the answer
 * came, on the monotonic clock. Each "ago" text is `serverNowMs - instant`.
 */
export function serverNowMs(snapshot: Snapshot, monotonicNowMs: number): number {
  throw new Error("not implemented");
}

/** "12 s", "4 min", "3 h 10 min", "2 d 4 h". Never negative. */
export function formatAge(ms: number): string {
  throw new Error("not implemented");
}

/** "14:05 UTC" for today on the server clock, "Nov 15 14:05 UTC" for a different day. */
export function formatUtc(iso: string, serverNow: number): string {
  throw new Error("not implemented");
}

/** "99.65%". "no data" for null. Two decimals: one 5 minute slot in 7 days is 0.05%. */
export function formatRatio(ratio: number | null): string {
  throw new Error("not implemented");
}
