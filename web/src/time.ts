// Time rules of the page. Pure. The browser wall clock is never compared with a server time.
import type { Snapshot } from "./api";

/**
 * The server time now, in ms since the epoch: `generated_at` plus the time since the answer
 * came, on the monotonic clock. Each "ago" text is `serverNowMs - instant`.
 */
export function serverNowMs(snapshot: Snapshot, monotonicNowMs: number): number {
  return Date.parse(snapshot.dashboard.generated_at) + (monotonicNowMs - snapshot.receivedAtMs);
}

/** "12 s", "4 min", "3 h 10 min", "2 d 4 h". Never negative. */
export function formatAge(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`;
}

const MONTH = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" });

function clock(at: Date): string {
  const hh = String(at.getUTCHours()).padStart(2, "0");
  const mm = String(at.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function day(at: Date): string {
  return `${MONTH.format(at)} ${at.getUTCDate()}`;
}

/** "14:05 UTC" for today on the server clock, "Nov 15 14:05 UTC" for a different day. */
export function formatUtc(iso: string, serverNow: number): string {
  const at = new Date(iso);
  const sameDay = day(at) === day(new Date(serverNow));
  return sameDay ? `${clock(at)} UTC` : `${day(at)} ${clock(at)} UTC`;
}

/** "Nov 16 03:10 to 03:25 UTC", or "Nov 15 22:00 to Nov 16 03:25 UTC" across midnight. */
export function formatSpan(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const endDay = day(start) === day(end) ? "" : `${day(end)} `;
  return `${day(start)} ${clock(start)} to ${endDay}${clock(end)} UTC`;
}

/** "99.65%". "no data" for null. Two decimals: one 5 minute slot in 7 days is 0.05%. */
export function formatRatio(ratio: number | null): string {
  if (ratio === null) return "no data";
  // Round down, so a check with a down slot never shows 100.00%. The small margin keeps
  // 0.9895 (stored as 0.98949999...) at 98.95%.
  return `${(Math.floor(ratio * 10_000 + 1e-6) / 100).toFixed(2)}%`;
}
