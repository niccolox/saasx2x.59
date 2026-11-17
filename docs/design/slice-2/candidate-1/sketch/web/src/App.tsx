// The page: the worker line, then one row for each check, in the order that the server sends.
import type { ReactElement } from "react";
import type { Snapshot } from "./api";
import { CheckRow } from "./CheckRow";
import { useDashboard, useServerNow } from "./useDashboard";
import { WorkerLine } from "./WorkerLine";

export function App(): ReactElement {
  const state = useDashboard();
  switch (state.status) {
    case "loading":
      return <p role="status">Loading.</p>;
    case "unreachable":
      return <p role="alert">The dashboard server does not answer: {state.error}</p>;
    case "live":
      return <DashboardView snapshot={state.snapshot} pageError={null} />;
    case "stale":
      return <DashboardView snapshot={state.snapshot} pageError={state.error} />;
  }
}

/**
 * `pageError` is not null when the snapshot is old. The view then shows a warning above the
 * worker line with the age of the snapshot.
 *
 * Also sets `document.title`: "STALLED - SaaSX2X", "2 down - SaaSX2X", or "SaaSX2X", so the
 * state shows on a browser tab that is not in front.
 */
function DashboardView(props: { snapshot: Snapshot; pageError: string | null }): ReactElement {
  const serverNow = useServerNow(props.snapshot);
  const { worker, checks } = props.snapshot.dashboard;
  // TODO: the warning for pageError, the document title, and an empty state for no check
  // ("No target. Run: saasx2x target add HOSTNAME").
  return (
    <main>
      <WorkerLine worker={worker} serverNow={serverNow} />
      <table>
        <thead>
          <tr>
            <th>Target</th>
            <th>Last result</th>
            <th>Last 24 hours</th>
            <th>24 h</th>
            <th>7 d</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check) => (
            <CheckRow key={check.check_id} check={check} serverNow={serverNow} />
          ))}
        </tbody>
      </table>
    </main>
  );
}
