import type { Strip } from "./api";

/**
 * SVG strip. Measures its own width with a ResizeObserver (a `useElementWidth` hook), calls the
 * pure `layoutStrip`, and draws one <rect> for each result, each with a <title> child for the
 * hover text ("down, 14:05 to 14:35 UTC, 7 slots"; touch devices see the same text in the row
 * detail). `role="img"` and `aria-label={describeStrip(strip)}`.
 *
 * Why SVG: at most `widthPx` rects (see layoutStrip rule 5), real hover text, scales in a
 * print or a zoom, and a test reads the rects from the DOM. Canvas has no hover text per mark
 * and no DOM for a test. One <div> for each of 1,440 slots is too many nodes for 20 checks, and
 * a slot is under 1 px wide.
 *
 * Before the first measure (width 0) it draws nothing, to avoid a flash of the wrong layout.
 */
export function StripChart(props: {
  strip: Strip;
  windowStartIso: string;
  windowEndIso: string;
}): JSX.Element {
  throw new Error("not implemented");
}
