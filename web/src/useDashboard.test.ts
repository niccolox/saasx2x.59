import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { oneOutage, stalledWorker } from "./fixtures";
import { RETRY_AFTER_MS, useDashboard } from "./useDashboard";

function answer(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("the page asks at once, then again each refresh_after_s", async () => {
  const fetch = vi.fn(async () => answer(oneOutage));
  vi.stubGlobal("fetch", fetch);
  const { result } = renderHook(() => useDashboard());
  expect(result.current.status).toBe("loading");

  await advance(0);
  expect(result.current).toMatchObject({ status: "live", snapshot: { dashboard: oneOutage } });
  expect(fetch).toHaveBeenCalledTimes(1);
  await advance(59_999);
  expect(fetch).toHaveBeenCalledTimes(1);
  await advance(1);
  expect(fetch).toHaveBeenCalledTimes(2);
});

test("a failure keeps the snapshot as stale, and the next answer is live", async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(answer(oneOutage))
    .mockRejectedValueOnce(new TypeError("Failed to fetch"))
    .mockResolvedValueOnce(answer(stalledWorker));
  vi.stubGlobal("fetch", fetch);
  const { result } = renderHook(() => useDashboard());

  await advance(0);
  await advance(60_000);
  expect(result.current).toMatchObject({
    status: "stale",
    error: "No answer from the dashboard server.",
    snapshot: { dashboard: oneOutage },
  });
  await advance(RETRY_AFTER_MS);
  expect(result.current).toMatchObject({ status: "live", snapshot: { dashboard: stalledWorker } });
});

test("with no snapshot, an error answer is unreachable with the detail of the server", async () => {
  const detail = "Postgres has no SaaSX2X tables. Run: saasx2x migrate";
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => answer({ detail }, 503)),
  );
  const { result } = renderHook(() => useDashboard());
  await advance(0);
  expect(result.current).toEqual({
    status: "unreachable",
    error: `The dashboard server answered 503. ${detail}`,
  });
});

test("a tab that becomes visible asks at once and starts the wait again", async () => {
  const fetch = vi.fn(async () => answer(oneOutage));
  vi.stubGlobal("fetch", fetch);
  renderHook(() => useDashboard());
  await advance(10_000);
  expect(fetch).toHaveBeenCalledTimes(1);

  await act(async () => {
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(fetch).toHaveBeenCalledTimes(2);
  await advance(59_999);
  expect(fetch).toHaveBeenCalledTimes(2);
  await advance(1);
  expect(fetch).toHaveBeenCalledTimes(3);
});
