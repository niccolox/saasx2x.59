import type { ReactElement } from "react";
import type { WorkerStatus } from "./api";
import { WORKER_LABEL } from "./marks";
import { formatAge, formatUtc } from "./time";

/**
 * One line for the whole worker. Examples:
 *
 *   Worker writes rows. Newest row at 14:03 UTC, 41 s ago. A row is due every 60 s.
 *   Worker stalled. Newest row at Nov 15 22:10 UTC, 15 h 53 min ago. A row is due every 60 s.
 *   Worker stalled. No row yet. A row is due every 300 s.
 *   No active check.
 *
 * "stalled" has `role="alert"` and the alert style. The other states have `role="status"`.
 * The switch over `worker.state` has no default, so a new state fails `tsc`.
 */
export function WorkerLine(props: { worker: WorkerStatus; serverNow: number }): ReactElement {
  const { worker, serverNow } = props;
  const newest =
    worker.newest_row_at === null
      ? "No row yet."
      : `Newest row at ${formatUtc(worker.newest_row_at, serverNow)}, ${formatAge(
          serverNow - Date.parse(worker.newest_row_at),
        )} ago.`;
  const due =
    worker.expected_every_s === null ? "" : `A row is due every ${worker.expected_every_s} s.`;
  const line = (role: "alert" | "status", details: string): ReactElement => (
    <p role={role} className={`worker worker--${worker.state}`}>
      <strong>{WORKER_LABEL[worker.state]}.</strong>
      {details === "" ? "" : ` ${details}`}
    </p>
  );
  switch (worker.state) {
    case "stalled":
      return line("alert", `${newest} ${due}`);
    case "writing":
      return line("status", `${newest} ${due}`);
    case "waiting":
      return line("status", due);
    case "idle":
      return line("status", "");
  }
}
