import { afterEach, expect, test, vi } from "vitest";
import { oneOutage } from "./fixtures";
import { formatAge, formatRatio, formatSpan, formatUtc, serverNowMs } from "./time";

afterEach(() => {
  vi.useRealTimers();
});

test("the server time is generated_at plus the monotonic time since the answer", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("1999-01-01T00:00:00Z"));
  const snapshot = { dashboard: oneOutage, receivedAtMs: 1_000 };
  expect(serverNowMs(snapshot, 6_000)).toBe(Date.parse("2026-11-16T14:05:12Z"));
});

test.each([
  [-5_000, "0 s"],
  [12_400, "12 s"],
  [4 * 60_000 + 59_000, "4 min"],
  [3 * 3_600_000, "3 h"],
  [3 * 3_600_000 + 10 * 60_000, "3 h 10 min"],
  [2 * 86_400_000, "2 d"],
  [2 * 86_400_000 + 4 * 3_600_000 + 59 * 60_000, "2 d 4 h"],
])("an age of %i ms is %s", (ms, text) => {
  expect(formatAge(ms)).toBe(text);
});

test("a time on the server day has no date, a time on a different day has one", () => {
  const now = Date.parse("2026-11-16T14:05:07Z");
  expect(formatUtc("2026-11-16T00:03:59Z", now)).toBe("00:03 UTC");
  expect(formatUtc("2026-11-15T22:10:31Z", now)).toBe("Nov 15 22:10 UTC");
  expect(formatSpan("2026-11-16T03:10:00Z", "2026-11-16T03:25:00Z")).toBe(
    "Nov 16 03:10 to 03:25 UTC",
  );
  expect(formatSpan("2026-11-15T22:00:00Z", "2026-11-16T03:25:00Z")).toBe(
    "Nov 15 22:00 to Nov 16 03:25 UTC",
  );
});

test.each([
  [null, "no data"],
  [1, "100.00%"],
  [0, "0.00%"],
  [0.9895, "98.95%"],
  [1439 / 1440, "99.93%"],
  [10079 / 10080, "99.99%"],
])("the uptime %s is %s, rounded down", (ratio, text) => {
  expect(formatRatio(ratio)).toBe(text);
});
