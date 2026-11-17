// The page. A pure function of DashboardState. Order from the top:
//   1. WorkerBanner: one line for each probe. A stall is the first thing on the page.
//   2. A stale banner when the last poll failed or the snapshot is old.
//   3. One CheckRow for each check, in the order of the snapshot (hostname, then port).
import type { Dashboard } from "./generated/dashboard";
import { useDashboard, type DashboardState } from "./api";
import { CheckRow } from "./CheckRow";
import { WorkerBanner } from "./WorkerBanner";

export function App() {
  return <DashboardView state={useDashboard()} />;
}

/** Exported for tests: render any state with no fetch. */
export function DashboardView({ state }: { state: DashboardState }) {
  // switch (state.kind):
  //   loading -> "Loading"
  //   failed  -> "No answer from the dashboard API: <error>". No check rows.
  //   fresh   -> <Snapshot snapshot={...} />
  //   stale   -> <StaleBanner fetchedAt error /> above <Snapshot dimmed />
  throw new Error("not implemented");
}

function Snapshot({ snapshot, dimmed }: { snapshot: Dashboard; dimmed: boolean }) {
  // <header> account, "as of <as_of>" </header>
  // <WorkerBanner workers={snapshot.workers} asOf={snapshot.as_of} />
  // checks.length === 0 -> "No active target. Add one with `saasx2x target add HOSTNAME`."
  // <table> head: Target | Last result | Last 24 h | 24 h | 7 d
  //   {snapshot.checks.map(c => <CheckRow key={c.check_id} panel={c} asOf={snapshot.as_of} />)}
  throw new Error("not implemented");
}

function StaleBanner({ fetchedAt, error }: { fetchedAt: number; error: string | null }) {
  // role="alert". "This data is from <time>. <error or 'The page did not refresh.'>"
  throw new Error("not implemented");
}
