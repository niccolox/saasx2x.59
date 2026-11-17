// The strip of the last 24 hours. SVG, one <rect> for each run, on a time axis.
//
// The server sends runs, not slots. A check that is up all day is one rectangle, for a 300 s
// interval (288 slots) and for a 60 s interval (1,440 slots). The work of the browser depends
// on the number of changes, not on the number of slots.
import type { ReactElement } from "react";
import type { Mark, Strip as StripData, StripRun } from "./api";

/** One rectangle in axis units. The axis is [0, axisSeconds). */
export interface RunBox {
  readonly x: number;
  readonly width: number;
  readonly mark: Mark;
  /** "down, TCP failed, 14:05 to 14:20 UTC, 15 min". The text of the SVG <title>. */
  readonly title: string;
}

/**
 * Pure layout: runs to rectangles, in `MARK_DRAW_ORDER`, so "down" is drawn last and on top.
 * x = (run.start - strip.start) in seconds. width = (run.end - run.start) in seconds.
 */
export function layoutStrip(strip: StripData): { axisSeconds: number; boxes: RunBox[] } {
  throw new Error("not implemented");
}

/**
 * <svg viewBox="0 0 {axisSeconds} 1" preserveAspectRatio="none" width="100%" height="28">
 *
 * - A run that is not "up" has a stroke in its own colour with
 *   `vector-effect: non-scaling-stroke` and a width of 2 px. One 60 s slot is 0.5 px on a
 *   720 px strip. The stroke keeps it at least 2 px wide, so one down slot is always visible.
 * - "not observed" has a hatch pattern, so it differs from "down" without colour.
 * - A part of the axis with no run shows the empty track: the check did not exist then.
 * - Each <rect> has a <title>, so the browser shows the time and the reason on hover.
 * - The <svg> has role="img" and an aria-label with the count of runs that are not "up".
 * - Below the strip: "24 h ago" at the left and "now" at the right.
 */
export function Strip(props: { strip: StripData }): ReactElement {
  throw new Error("not implemented");
}

/** The words of one run for the title. */
export function describeRun(run: StripRun): string {
  throw new Error("not implemented");
}
