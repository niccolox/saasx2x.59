// The only module that calls fetch. The JSON type is the generated one. There is no second,
// hand-written TypeScript model of the response.
//
// Trust boundary: the server is this repository's own process, and its type is generated from
// the same Pydantic model. The client checks the HTTP status and the content type, then trusts
// the type. A runtime schema check (zod and similar) would be a hand-written copy of the shape.
import { useEffect, useState } from "react";
import type { Dashboard } from "./generated/dashboard";

export const REFRESH_MS = 60_000;
/** A snapshot older than this is stale, for example after the laptop slept. */
export const STALE_AFTER_MS = 3 * REFRESH_MS;

/**
 * The state of the page. Each state that has a snapshot keeps the last good one, so a failed
 * poll never blanks the page and never shows an old snapshot as if it were new.
 */
export type DashboardState =
  | { kind: "loading" }
  | { kind: "failed"; error: string } // no snapshot yet
  | { kind: "fresh"; snapshot: Dashboard; fetchedAt: number }
  | { kind: "stale"; snapshot: Dashboard; fetchedAt: number; error: string | null };

export async function fetchDashboard(signal: AbortSignal): Promise<Dashboard> {
  // GET /api/dashboard. Throw on a status other than 200, with the `detail` of a 503 body.
  throw new Error("not implemented");
}

/**
 * Poll every REFRESH_MS. Also poll at once when the tab becomes visible again.
 * Each poll aborts the poll before it. `now` is injected for tests (fake timers).
 *
 * TODO transitions:
 *   loading --ok--> fresh            loading --error--> failed
 *   fresh   --ok--> fresh            fresh   --error--> stale(error)
 *   fresh   --now - fetchedAt > STALE_AFTER_MS--> stale(null)
 *   stale   --ok--> fresh
 */
export function useDashboard(now: () => number = Date.now): DashboardState {
  const [state] = useState<DashboardState>({ kind: "loading" });
  useEffect(() => {
    throw new Error("not implemented");
  }, [now]);
  return state;
}
