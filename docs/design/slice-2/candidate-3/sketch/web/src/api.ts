// The only file that imports the generated types. Components import from here.
// Names mirror the Pydantic types in `src/saasx2x/status.py`. No field is declared by hand.
import type { components } from "./api.gen";

type S = components["schemas"];

export type StatusBoard = S["StatusBoard"];
export type CheckStatus = S["CheckStatus"];
export type Strip = S["Strip"];
export type Run = S["Run"];
export type Tally = S["Tally"];
export type Worker = S["Worker"];
export type LastResult = S["LastResult"];
export type Mark = S["Mark"];
export type Reason = S["Reason"];
export type WorkerState = S["WorkerState"];

export class BoardUnavailable extends Error {}

/** GET /api/status. Throws BoardUnavailable on 503 (the Problem body has `detail`) or on a
 *  network error. Never returns a partial board. */
export async function fetchBoard(signal: AbortSignal): Promise<StatusBoard> {
  throw new Error("not implemented");
}
