// The refresh loop. The only state of the page.
import { useEffect, useState } from "react";
import { DashboardUnavailable, fetchDashboard, type Snapshot } from "./api";
import { serverNowMs } from "./time";

/** After a failure, the next request starts after this time. */
export const RETRY_AFTER_MS = 5_000;
/** A request with no answer after this time fails, so a hung server shows as a failure. */
const REQUEST_TIMEOUT_MS = 15_000;

/**
 * What the page knows about its own data. A stalled page is as bad as a stalled worker, so a
 * snapshot that is old is never shown as current.
 *
 *   loading      the first request has no answer yet
 *   live         the newest request gave this snapshot
 *   stale        the newest request failed. The page shows the old snapshot with a warning.
 *                The view also treats a live snapshot older than 2 * refresh_after_s as stale.
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
 * - After a failure, keep the last snapshot as "stale" and try again after `RETRY_AFTER_MS`.
 */
export function useDashboard(): DashboardState {
  const [state, setState] = useState<DashboardState>({ status: "loading" });

  useEffect(() => {
    let next: ReturnType<typeof setTimeout> | undefined;
    let inFlight: AbortController | undefined;

    const load = async (): Promise<void> => {
      clearTimeout(next);
      inFlight?.abort();
      const request = new AbortController();
      inFlight = request;
      const timeout = setTimeout(() => request.abort(), REQUEST_TIMEOUT_MS);
      try {
        const snapshot = await fetchDashboard(request.signal);
        if (inFlight !== request) return;
        setState({ status: "live", snapshot });
        next = setTimeout(load, snapshot.dashboard.refresh_after_s * 1000);
      } catch (error) {
        if (inFlight !== request) return;
        const message = error instanceof DashboardUnavailable ? error.message : String(error);
        setState((previous) =>
          "snapshot" in previous
            ? { status: "stale", snapshot: previous.snapshot, error: message }
            : { status: "unreachable", error: message },
        );
        next = setTimeout(load, RETRY_AFTER_MS);
      } finally {
        clearTimeout(timeout);
      }
    };

    const onVisibilityChange = (): void => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    void load();
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      clearTimeout(next);
      const request = inFlight;
      inFlight = undefined;
      request?.abort();
    };
  }, []);

  return state;
}

/** The server time now in ms, updated each second, for the "ago" texts. */
export function useServerNow(snapshot: Snapshot): number {
  const [monotonicNowMs, setMonotonicNowMs] = useState(() => performance.now());
  useEffect(() => {
    const tick = setInterval(() => setMonotonicNowMs(performance.now()), 1000);
    return () => clearInterval(tick);
  }, []);
  return serverNowMs(snapshot, Math.max(monotonicNowMs, snapshot.receivedAtMs));
}
