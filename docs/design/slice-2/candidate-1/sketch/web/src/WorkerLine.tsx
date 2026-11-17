import type { ReactElement } from "react";
import type { WorkerStatus } from "./api";

/**
 * One line for the whole worker. Examples:
 *
 *   Worker writes rows. Newest row 14:03 UTC, 41 s ago. Expected: a row each 60 s.
 *   Worker stalled. Newest row Nov 15 22:10 UTC, 15 h 53 min ago. Expected: a row each 60 s.
 *   Worker stalled. No row. Expected: a row each 300 s.
 *   No active check.
 *
 * "stalled" has `role="alert"` and the alert style. The other states have `role="status"`.
 * The switch over `worker.state` has no default, so a new state fails `tsc`.
 */
export function WorkerLine(props: { worker: WorkerStatus; serverNow: number }): ReactElement {
  throw new Error("not implemented");
}
