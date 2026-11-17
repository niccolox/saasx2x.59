import { expect, test } from "vitest";
import type { Mark, Reason, Strip, Verdict } from "./api";
import { minuteCheckOneDownSlot, oneOutage } from "./fixtures";
import { layoutStrip, MIN_MARK_PX, type StripRect } from "./layoutStrip";

const HOUR_MS = 3_600_000;
const AXIS_START = Date.parse("2026-11-16T00:00:00Z");
const REASON_OF = {
  up: "status_ok",
  down: "tcp_failed",
  blocked: "rate_limited",
  inconclusive: "probe_failed",
} satisfies Record<Verdict, Reason>;

function iso(hours: number): string {
  return new Date(AXIS_START + hours * HOUR_MS).toISOString();
}

/** A strip of 24 hours with runs given in hours from its start. */
function strip(runs: [number, number, Mark][]): Strip {
  return {
    start: iso(0),
    end: iso(24),
    runs: runs.map(([start, end, mark]) => ({
      start: iso(start),
      end: iso(end),
      mark,
      reason: mark === "not_observed" ? null : REASON_OF[mark],
    })),
  };
}

function boxes(rects: StripRect[]): [number, number, Mark][] {
  return rects.map((rect) => [rect.x, rect.width, rect.mark]);
}

test("x and width come from the times of the runs", () => {
  const rects = layoutStrip(strip([[0, 12, "up"], [12, 24, "down"]]), 480);
  expect(boxes(rects)).toEqual([[0, 240, "up"], [240, 240, "down"]]);
});

test("a part of the axis with no run has no rectangle", () => {
  expect(boxes(layoutStrip(strip([[23, 24, "up"]]), 480))).toEqual([[460, 20, "up"]]);
});

test("one down slot among 1,440 slots of 60 s is 3 px wide at 720 px", () => {
  const { strip: day } = minuteCheckOneDownSlot.checks[0]!;
  // 03:10 is 785 min into an axis of 1,441 min: 392.2 px to 392.7 px, so 3 px from 391.
  expect(boxes(layoutStrip(day, 720))).toEqual([
    [0, 391, "up"],
    [391, MIN_MARK_PX, "down"],
    [394, 326, "up"],
  ]);
});

const PRIORITY: Mark[] = ["down", "not_observed", "inconclusive", "blocked", "up"];

test.each(PRIORITY.slice(0, -1).map((mark, n) => [mark, PRIORITY.slice(n)] as const))(
  "in one pixel column, %s wins over each mark after it",
  (winner, marks) => {
    const quarter = 1 / marks.length;
    const inColumn10 = [...marks]
      .reverse()
      .map((mark, n): [number, number, Mark] => [10 + n * quarter, 10 + (n + 1) * quarter, mark]);
    const rects = layoutStrip(strip([[0, 10, "up"], ...inColumn10, [11, 24, "up"]]), 24);
    const column10 = rects.find((rect) => rect.x <= 10 && 10 < rect.x + rect.width);
    expect(column10?.mark).toBe(winner);
  },
);

test.each([1, 37, 100, 720, 1999])("at %i px the rectangles are apart and inside the width", (width) => {
  const rects = layoutStrip(oneOutage.checks[0]!.strip, width);
  rects.forEach((rect, n) => {
    expect(rect.width).toBeGreaterThanOrEqual(1);
    expect(rect.x + rect.width).toBeLessThanOrEqual(rects[n + 1]?.x ?? width);
    expect(rect.runs.every((run) => run.mark === rect.mark)).toBe(true);
  });
});
