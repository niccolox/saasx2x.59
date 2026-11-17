// Pure functions for the strip. No React. Unit tests in strip.test.ts.
import type { Mark, Strip } from "./generated/dashboard";
import { COLUMN_PRIORITY } from "./marks";

/** The narrowest column, in CSS pixels. Below this a mark is not readable. */
export const MIN_COLUMN_PX = 2;

/** min(slots, floor(widthPx / MIN_COLUMN_PX)). At least 1 when slots > 0. */
export function columnCount(widthPx: number, slots: number): number {
  throw new Error("not implemented");
}

/**
 * Put `marks` into `columns` columns of near equal slot counts. Each column shows the first mark
 * of COLUMN_PRIORITY that it holds. When columns >= marks.length, return the marks unchanged.
 * Column c holds slots [floor(c * n / columns), floor((c + 1) * n / columns)).
 */
export function columnMarks(marks: readonly Mark[], columns: number): Mark[] {
  throw new Error("not implemented");
}

export interface Run { mark: Mark; first: number; count: number }

/** Merge equal neighbours, so the SVG has one <rect> for each run, not one for each column.
 * A day that is all up is one rect. */
export function runs(columns: readonly Mark[]): Run[] {
  throw new Error("not implemented");
}

/** The slots that column `c` holds, as start and end instants. For the tooltip. */
export function columnSpan(strip: Strip, columns: number, c: number): { from: Date; to: Date } {
  throw new Error("not implemented");
}
