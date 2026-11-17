// The strip of the last 24 hours, in SVG.
//
// Why SVG: one <rect> for each run of equal columns gives a few elements for each check, crisp at
// any zoom, with DOM nodes for tests and an accessible name. Canvas has no DOM to test and no
// text for a screen reader. One <div> for each slot gives 1,440 nodes for each 60 s check.
//
// Readability at 288 and 1,440 slots: a ResizeObserver gives the width in CSS pixels.
// columnCount(width, marks.length) columns of at least MIN_COLUMN_PX. columnMarks() puts the
// slots in the columns by COLUMN_PRIORITY, so one down slot or one gap is never lost in the
// down-sample. At 288 slots on a 720 px strip each slot gets its own 2.5 px column.
import type { Strip } from "./generated/dashboard";

export function SlotStrip({ strip }: { strip: Strip }) {
  // const [ref, width] = useWidth<SVGSVGElement>();
  // const cols = columnMarks(strip.marks, columnCount(width, strip.marks.length));
  // <svg ref width="100%" height={20} viewBox={`0 0 ${cols.length} 1`}
  //      preserveAspectRatio="none" role="img" aria-label={summary(strip)}>
  //   {runs(cols).map(r => <rect x={r.first} width={r.count} y={1 - h} height={h} .../>)}
  //   outline marks: stroke with vector-effect="non-scaling-stroke", no fill
  // </svg>
  // One shared tooltip: pointermove -> column index -> columnSpan() and the marks in it.
  // No event handler on each rect.
  throw new Error("not implemented");
}

/** "Last 24 hours: 280 up, 3 down, 5 not observed" from the marks, for aria-label. */
function summary(strip: Strip): string {
  throw new Error("not implemented");
}
