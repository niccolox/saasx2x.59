// The refresh loop. The only state of the page.
import type { Snapshot } from "./api";

/**
 * What the page knows about its own data. A stalled page is as bad as a stalled worker, so a
 * snapshot that is old is never shown as current.
 *
 *   loading      the first request has no answer yet
 *   live         the newest request gave this snapshot
 *   stale        the newest request failed, or no answer came for 2 * refresh_after_s.
 *                The page shows the old snapshot with a warning and its age.
 *   unreachable  no request gave a snapshot
 */
export type DashboardState =
  | { readonly status: "loading" }
  | { readonly status: "live"; readonly snapshot: Snapshot }
  | { readonly status: "stale"; readonly snapshot: Snapshot; readonly error: string }
  | { readonly status: "unreachable"; readonly error: string };

/**
 * Fetch the dashboard now, then again `refresh_after_s` after each answer.
 *
 * - One request at a time. A new request aborts the old one.
 * - When the tab becomes visible, fetch at once. A browser slows the timers of a hidden tab,
 *   and the owner opens the tab one time each day.
 * - After a failure, try again after 5 s, then keep the last snapshot as "stale".
 */
export function useDashboard(): DashboardState {
  throw new Error("not implemented");
}

/** The server time now in ms, updated each second, for the "ago" texts. */
export function useServerNow(snapshot: Snapshot): number {
  throw new Error("not implemented");
}
