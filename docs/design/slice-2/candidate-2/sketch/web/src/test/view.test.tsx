// vitest + @testing-library/react + jsdom. Renders DashboardView from committed fixtures.
// tests/test_web.py validates each fixture with Dashboard.model_validate_json, so a fixture
// cannot drift from the API.
import { describe, it } from "vitest";

describe("DashboardView", () => {
  it.todo("shows a stalled worker as an alert above the check rows (fixture stalled.json)");
  it.todo("keeps the check order of the snapshot");
  it.todo("shows 'no result yet' for a check with last === null");
  it.todo("shows a stale banner and keeps the old rows when the last poll failed");
  it.todo("shows the empty text when there is no check");
});
describe("useDashboard", () => {
  it.todo("polls again after REFRESH_MS (fake timers)");
  it.todo("goes to stale when the snapshot is older than STALE_AFTER_MS");
  it.todo("polls at once on visibilitychange to visible");
});
describe("format", () => {
  it.todo("ageText is relative to as_of, not to the browser clock");
  it.todo("ratioText shows 99.99 % for 1 down in 100,000, not 100 %");
});
