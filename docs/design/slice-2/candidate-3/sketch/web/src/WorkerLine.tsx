import type { Worker } from "./api";

/**
 * One line, the same height in every state. Shows WORKER_LABEL[worker.state], the time of the
 * newest row ("last row 3 min ago, 14:05:03 UTC"), and the longest healthy gap
 * ("a row is due every 5 min"). With `newest_row_at === null`: "no row yet, first check
 * added 12 min ago".
 * `stalled` and `late` use text AND an icon shape, not color alone. `role="status"`, and
 * `aria-live="polite"` so a change to stalled is announced.
 * Props: the worker record and the board's `as_of`. Ages use `as_of`, never `Date.now()`.
 */
export function WorkerLine(props: { worker: Worker; asOfIso: string }): JSX.Element {
  throw new Error("not implemented");
}
