// One real browser, one real FastAPI process, one real Postgres. Offline, no credentials.
// `playwright.config.ts` starts two servers with `webServer`:
//   uv run python -m tests.e2e_serve --scenario healthy --port 55451
//   uv run python -m tests.e2e_serve --scenario stalled --port 55452
// Each one makes a scratch database on the Compose Postgres, seeds it, and serves the app.
import { test } from "@playwright/test";

test.describe("healthy worker (127.0.0.1:55451)", () => {
  test.todo("shows the checks in hostname order");
  test.todo("shows 'Worker is writing rows' and a last result for each check");
  test.todo("draws a visible mark for the seeded down run and one hatched blocked run");
  test.todo("shows 24 h uptime for the seeded rows and the not-observed count apart");
  test.todo("refreshes by itself: a row seeded after load shows after one refresh (REFRESH_MS shortened by a query param)");
  test.todo("works at a 400 px viewport with no horizontal scroll");
});

test.describe("stalled worker (127.0.0.1:55452)", () => {
  test.todo("the newest seeded row is 30 min old: the page shows 'Worker stopped writing rows'");
  test.todo("after the server stops, the page shows its own 'data is old' banner and keeps the board");
});
