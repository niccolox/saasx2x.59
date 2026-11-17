import type { StatusBoard } from "./api";

export const REFRESH_MS = 60_000;
/** After this long with no good response, the page says its own data is old. */
export const STALE_AFTER_MS = 150_000;

export interface BoardState {
  board: StatusBoard | null; // the last good board. Kept on screen while a refresh fails.
  okAtMs: number | null; // performance.now() at the last good response. Monotonic: no clock skew.
  error: string | null; // the last error, cleared by a good response
}

export type BoardEvent =
  | { type: "ok"; board: StatusBoard; atMs: number }
  | { type: "fail"; message: string };

/** The page's own link to the server, not the worker's state. */
export type Link = "never" | "live" | "stale";

export const initialState: BoardState = { board: null, okAtMs: null, error: null };

/** Pure reducer. A failure never clears `board`. */
export function reduce(state: BoardState, event: BoardEvent): BoardState {
  throw new Error("not implemented");
}

/** "live" while the last good response is younger than STALE_AFTER_MS. */
export function link(state: BoardState, nowMs: number): Link {
  throw new Error("not implemented");
}

/**
 * Fetch now, then every REFRESH_MS after the previous response ends (a chained timeout, not
 * setInterval, so slow responses never overlap). Abort the fetch on unmount. Pause while
 * `document.hidden`, and refetch at once when the tab shows again after more than REFRESH_MS.
 * Re-render each 10 s so `link()` can flip to "stale" with no new data.
 */
export function useBoard(): { state: BoardState; link: Link } {
  throw new Error("not implemented");
}
