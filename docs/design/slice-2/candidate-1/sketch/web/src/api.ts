// The boundary to the server. The only module that calls `fetch` and the only module that
// imports `api.gen.ts`.
//
// `api.gen.ts` is not in git. `npm run gen` writes it from `web/openapi.json`, and a Python
// test keeps `web/openapi.json` equal to the Pydantic classes in `saasx2x/dashboard.py`.
// So no type below is written by hand, and `tsc` fails when the page reads a field that the
// server does not send.
import type { components } from "./api.gen";

type Schemas = components["schemas"];

export type Dashboard = Schemas["Dashboard"];
export type WorkerStatus = Schemas["WorkerStatus"];
export type CheckStatus = Schemas["CheckStatus"];
export type LastResult = Schemas["LastResult"];
export type Strip = Schemas["Strip"];
export type StripRun = Schemas["StripRun"];
export type SlotCounts = Schemas["SlotCounts"];
export type Mark = Schemas["Mark"];
export type Verdict = Schemas["Verdict"];
export type Reason = Schemas["Reason"];

/** One answer of the server, with the time on the monotonic clock when it came. */
export interface Snapshot {
  readonly dashboard: Dashboard;
  /** `performance.now()` at receipt. Never a wall clock time. */
  readonly receivedAtMs: number;
}

/** The server did not give a dashboard: no connection, or a status that is not 200. */
export class DashboardUnavailable extends Error {}

/**
 * GET /api/dashboard. Reject with DashboardUnavailable for each failure.
 * The body is not validated here: the page and the API ship in one image.
 */
export async function fetchDashboard(signal: AbortSignal): Promise<Snapshot> {
  throw new Error("not implemented");
}
