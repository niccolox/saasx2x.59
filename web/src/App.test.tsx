import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";
import type { Dashboard } from "./api";
import { oneOutage, stalledWorker } from "./fixtures";

function serve(dashboard: Dashboard): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(dashboard), { status: 200 })),
  );
}

beforeEach(() => {
  document.title = "";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a stalled worker is an alert, and the tab title starts with STALLED", async () => {
  serve(stalledWorker);
  render(<App />);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe(
    "Worker stalled. Newest row at Nov 15 22:10 UTC, 15 h 54 min ago. A row is due every 60 s.",
  );
  await waitFor(() => expect(document.title).toBe("STALLED - SaaSX2X"));
});

test("a writing worker is a status line, and each check is one row", async () => {
  serve(oneOutage);
  render(<App />);
  const status = await screen.findByText("Worker writes rows.");
  expect(status.closest("[role=status]")?.textContent).toBe(
    "Worker writes rows. Newest row at 14:03 UTC, 1 min ago. A row is due every 300 s.",
  );
  expect(screen.queryByRole("alert")).toBeNull();

  const row = screen.getByRole("row", { name: /example\.com/ });
  expect(within(row).getByRole("rowheader").textContent).toBe("example.com:443every 300 s");
  expect(row.textContent).toContain("upstatus OK, 5 min ago");
  expect(row.textContent).toContain("98.95%1 not observed");
  expect(row.textContent).toContain("99.85%1 not observed2 inconclusive");
  await waitFor(() => expect(document.title).toBe("SaaSX2X"));
});

test("with no target the page says how to add one", async () => {
  serve({ ...oneOutage, worker: { state: "idle", newest_row_at: null, expected_every_s: null }, checks: [] });
  render(<App />);
  const status = await screen.findByText("No active check.");
  expect(status.closest("[role=status]")?.textContent).toBe("No active check.");
  expect(screen.getByText(/No target/).textContent).toBe("No target. Run: saasx2x target add HOSTNAME");
});
