import type { Mark, Strip } from "./api";

export interface Rect {
  x: number; // px from the left edge
  width: number; // px, at least MIN_MARK_PX for each mark except `up`
  mark: Mark;
  fromIso: string; // for the tooltip: first slot start of the run
  slots: number; // for the tooltip: slots in the run
}

export const MIN_MARK_PX = 3;

/**
 * Pure. Turn a run-length strip into pixel rectangles on a TIME axis.
 *
 *   x(t) = (t - windowStart) / (windowEnd - windowStart) * widthPx
 *   run start slot = strip.lead + sum(count of earlier runs)
 *   run start time = strip.first_slot + startSlot * interval_s
 *
 * Rules, in this order:
 *  1. Skip the `lead` slots. Draw nothing there.
 *  2. A run of `up` or `not_observed` takes its true width. It can be thin or wide.
 *  3. A run of `down`, `blocked`, or `inconclusive` takes at least MIN_MARK_PX, centered on its
 *     true span, so one failed 60 s slot in 24 h (0.7 px at 1000 px) stays visible.
 *  4. Output order: `up` and `not_observed` first, the other marks last, so a wide mark is never
 *     hidden under a green run.
 *  5. At most one rect for each pixel column: merge neighbors of the same mark that touch. The
 *     worst case, a flapping check, then gives at most widthPx rects, not 1,440.
 *
 * Tests: empty runs; lead only; one down slot among 1,440 up slots is >= 3 px wide; the total
 * `up` width is within 1 px of the true share; two strips with intervals 60 s and 300 s place a
 * mark at the same x for the same time.
 */
export function layoutStrip(
  strip: Strip,
  windowStartIso: string,
  windowEndIso: string,
  widthPx: number,
): Rect[] {
  throw new Error("not implemented");
}

/** Text for `aria-label` of the strip: "24 h: 1 down run, 2 blocked runs, 3 slots not observed". */
export function describeStrip(strip: Strip): string {
  throw new Error("not implemented");
}
