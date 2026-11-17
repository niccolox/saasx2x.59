import type { WorkerLine } from "./generated/dashboard";

/**
 * One line for each probe: "<probe_id>: <WORKER_TEXT[state]>, newest row <age> ago".
 * When any line is "stalled" or "no_rows", the banner has role="alert" and the stalled color,
 * and the page title starts with "STALLED · " so the tab shows it too.
 * With no probe at all: "No probe has registered. Start `saasx2x worker`."
 */
export function WorkerBanner({ workers, asOf }: { workers: readonly WorkerLine[]; asOf: string }) {
  throw new Error("not implemented");
}
