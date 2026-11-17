// Runs on a time axis to rectangles in whole pixels. Pure.
//
// The server sends runs, not slots. A check that is up all day is one rectangle, for a 300 s
// interval (288 slots) and for a 60 s interval (1,440 slots). The work depends on the number of
// changes and on the pixel width, not on the number of slots.
import type { Mark, Strip, StripRun } from "./api";
import { MARK_RANK } from "./marks";

/** A run that is not up is at least this wide, so one down slot of 60 s stays visible. */
export const MIN_MARK_PX = 3;

export interface StripRect {
  /** The first pixel column. */
  readonly x: number;
  readonly width: number;
  readonly mark: Mark;
  /** The runs with this mark that the rectangle shows, in time order. Never empty. */
  readonly runs: readonly StripRun[];
}

/**
 * Each pixel column of `[0, widthPx)` shows the run with the lowest `MARK_RANK` that touches
 * it. Columns in sequence with one mark become one rectangle. A column that no run touches
 * has no rectangle: the check did not exist then, or the open slot has no row.
 */
export function layoutStrip(strip: Strip, widthPx: number): StripRect[] {
  const width = Math.max(1, Math.floor(widthPx));
  const axisStart = Date.parse(strip.start);
  const pxPerMs = width / (Date.parse(strip.end) - axisStart);
  const shown: (StripRun | undefined)[] = new Array<StripRun | undefined>(width);

  for (const run of strip.runs) {
    const x0 = (Date.parse(run.start) - axisStart) * pxPerMs;
    const x1 = (Date.parse(run.end) - axisStart) * pxPerMs;
    let first = Math.floor(x0);
    let end = Math.ceil(x1);
    if (run.mark !== "up" && end - first < MIN_MARK_PX) {
      first = Math.max(0, Math.min(width - MIN_MARK_PX, Math.round((x0 + x1 - MIN_MARK_PX) / 2)));
      end = first + MIN_MARK_PX;
    }
    for (let column = Math.max(0, first); column < Math.min(width, end); column++) {
      const current = shown[column];
      if (current === undefined || MARK_RANK[run.mark] < MARK_RANK[current.mark]) {
        shown[column] = run;
      }
    }
  }

  const rects: { x: number; width: number; mark: Mark; runs: StripRun[] }[] = [];
  shown.forEach((run, column) => {
    if (run === undefined) return;
    const last = rects.at(-1);
    if (last !== undefined && last.x + last.width === column && last.mark === run.mark) {
      last.width += 1;
      if (last.runs.at(-1) !== run) last.runs.push(run);
    } else {
      rects.push({ x: column, width: 1, mark: run.mark, runs: [run] });
    }
  });
  return rects;
}
