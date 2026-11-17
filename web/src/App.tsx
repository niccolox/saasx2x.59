// The page: the worker line, then one row for each check, in the order that the server sends.
import { type ReactElement, type ReactNode, useEffect } from "react";
import type { Dashboard, Mark, Snapshot } from "./api";
import { CheckRow } from "./CheckRow";
import { MARK_LABEL } from "./marks";
import { NOT_OBSERVED_PATTERN } from "./Strip";
import { formatAge } from "./time";
import { useDashboard, useServerNow } from "./useDashboard";
import { WorkerLine } from "./WorkerLine";

export function App(): ReactElement {
  const state = useDashboard();
  switch (state.status) {
    case "loading":
      return (
        <Page>
          <p role="status" className="banner">
            Loading.
          </p>
        </Page>
      );
    case "unreachable":
      return (
        <Page>
          <p role="alert" className="banner banner--alert">
            <strong>No data.</strong> {state.error} The page tries again.
          </p>
        </Page>
      );
    case "live":
      return <DashboardView snapshot={state.snapshot} pageError={null} />;
    case "stale":
      return <DashboardView snapshot={state.snapshot} pageError={state.error} />;
  }
}

/** "STALLED - SaaSX2X", "2 down - SaaSX2X", or "SaaSX2X", for a browser tab that is not in front. */
export function pageTitle(dashboard: Dashboard): string {
  if (dashboard.worker.state === "stalled") return "STALLED - SaaSX2X";
  const down = dashboard.checks.filter((check) => check.last?.verdict === "down").length;
  return down > 0 ? `${down} down - SaaSX2X` : "SaaSX2X";
}

/**
 * The view of one snapshot. The data is old when the newest request failed (`pageError`), or
 * when no answer came for 2 * refresh_after_s. The view then shows a warning with its age.
 */
function DashboardView(props: { snapshot: Snapshot; pageError: string | null }): ReactElement {
  const { snapshot, pageError } = props;
  const serverNow = useServerNow(snapshot);
  const { dashboard } = snapshot;
  const ageMs = serverNow - Date.parse(dashboard.generated_at);
  const old = pageError !== null || ageMs > 2 * dashboard.refresh_after_s * 1000;

  useEffect(() => {
    document.title = pageTitle(dashboard);
  }, [dashboard]);

  return (
    <Page>
      {old && (
        <p role="alert" className="banner banner--stale">
          <strong>This page is not up to date.</strong> The data is {formatAge(ageMs)} old.
          {pageError === null ? "" : ` ${pageError}`} The page tries again.
        </p>
      )}
      <WorkerLine worker={dashboard.worker} serverNow={serverNow} />
      {dashboard.checks.length === 0 ? (
        <p className="empty">
          No target. Run: <code>saasx2x target add HOSTNAME</code>
        </p>
      ) : (
        <>
          <table className="checks">
            <colgroup>
              <col className="col-target" />
              <col className="col-last" />
              <col />
              <col className="col-uptime" />
              <col className="col-uptime" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Target</th>
                <th scope="col">Last result</th>
                <th scope="col">Last 24 hours</th>
                <th scope="col">24 h</th>
                <th scope="col">7 d</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.checks.map((check) => (
                <CheckRow key={check.check_id} check={check} serverNow={serverNow} />
              ))}
            </tbody>
          </table>
          <Legend />
        </>
      )}
    </Page>
  );
}

function Page(props: { children: ReactNode }): ReactElement {
  return (
    <main className="page">
      <svg className="defs" width="0" height="0" aria-hidden="true" focusable="false">
        <defs>
          <pattern
            id={NOT_OBSERVED_PATTERN}
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect className="hatch-ground" width="6" height="6" />
            <line className="hatch-line" x1="0" y1="0" x2="0" y2="6" />
          </pattern>
        </defs>
      </svg>
      <header className="masthead">
        <h1>SaaSX2X</h1>
        <p className="note">Uptime is up / (up + down). All times are UTC.</p>
      </header>
      {props.children}
    </main>
  );
}

function Legend(): ReactElement {
  const marks = Object.keys(MARK_LABEL) as Mark[];
  return (
    <ul className="legend" aria-label="Strip marks">
      {marks.map((mark) => (
        <li key={mark}>
          <span className={`swatch mark--${mark}`} aria-hidden="true" />
          {MARK_LABEL[mark]}
        </li>
      ))}
      <li>
        <span className="swatch swatch--track" aria-hidden="true" />
        no check yet
      </li>
    </ul>
  );
}
