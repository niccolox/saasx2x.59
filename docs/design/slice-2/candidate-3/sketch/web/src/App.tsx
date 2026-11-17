import { useBoard } from "./useBoard";
import { CheckRow } from "./CheckRow";
import { WorkerLine } from "./WorkerLine";

/**
 * One screen. Top to bottom:
 *   1. WorkerLine   the stall signal. First, because it answers "is the data still arriving?".
 *   2. A banner when the PAGE lost the server (link "stale"), or the server answered 503.
 *      The last good board stays below it, dimmed.
 *   3. One CheckRow per check, in the order of `board.checks` (the server sorted it).
 *   4. "Waiting for the first board" before the first response.
 * It computes no verdict, no ratio, and no order.
 */
export function App(): JSX.Element {
  throw new Error("not implemented");
}
