// The strip of the last 24 hours. SVG, one <rect> for each rectangle of `layoutStrip`.
import { type ReactElement, type RefObject, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Mark, Strip as StripData, StripRun } from "./api";
import { layoutStrip, type StripRect } from "./layoutStrip";
import { MARK_LABEL, MARK_RANK, REASON_LABEL } from "./marks";
import { formatAge, formatSpan } from "./time";

/** The width before the first measure, and in a test with no layout. */
export const DEFAULT_STRIP_PX = 720;
const STRIP_HEIGHT_PX = 28;
/** The id of the hatch pattern for "not observed". `App` draws it once for the page. */
export const NOT_OBSERVED_PATTERN = "not-observed-hatch";

/**
 * <svg> in pixel units, as wide as its box:
 *
 * - A part of the axis with no rectangle shows the empty track: the check did not exist then.
 * - "not observed" has a hatch pattern, so it differs from "down" without colour.
 * - Each <rect> has a <title>, so the browser shows the time and the reason on hover.
 * - The <svg> has role="img" and an aria-label with the count of runs that are not "up".
 * - Below the strip: "24 h ago" at the left and "now" at the right.
 */
export function Strip(props: { strip: StripData }): ReactElement {
  const { strip } = props;
  const [box, width] = useWidth<HTMLDivElement>(DEFAULT_STRIP_PX);
  const rects = useMemo(() => layoutStrip(strip, width), [strip, width]);
  return (
    <div ref={box} className="strip">
      <svg
        role="img"
        aria-label={describeStrip(strip.runs)}
        width={width}
        height={STRIP_HEIGHT_PX}
        viewBox={`0 0 ${width} ${STRIP_HEIGHT_PX}`}
      >
        <rect className="strip-track" x={0} y={0} width={width} height={STRIP_HEIGHT_PX} />
        {rects.map((rect) => (
          <rect
            key={rect.x}
            data-mark={rect.mark}
            className={`mark mark--${rect.mark}`}
            x={rect.x}
            y={0}
            width={rect.width}
            height={STRIP_HEIGHT_PX}
            fill={rect.mark === "not_observed" ? `url(#${NOT_OBSERVED_PATTERN})` : undefined}
          >
            <title>{describeRect(rect)}</title>
          </rect>
        ))}
      </svg>
      <div className="strip-axis" aria-hidden="true">
        <span>24 h ago</span>
        <span>now</span>
      </div>
    </div>
  );
}

/** "down, TCP failed, Nov 16 03:10 to 03:25 UTC, 15 min". */
export function describeRun(run: StripRun): string {
  const reason = run.reason === null ? "" : `, ${REASON_LABEL[run.reason]}`;
  const duration = formatAge(Date.parse(run.end) - Date.parse(run.start));
  return `${MARK_LABEL[run.mark]}${reason}, ${formatSpan(run.start, run.end)}, ${duration}`;
}

function describeRect(rect: StripRect): string {
  const [first, ...more] = rect.runs;
  const others = more.length === 0 ? "" : `, and ${more.length} more ${MARK_LABEL[rect.mark]}`;
  return first === undefined ? MARK_LABEL[rect.mark] : `${describeRun(first)}${others}`;
}

function describeStrip(runs: readonly StripRun[]): string {
  const marks = Object.keys(MARK_RANK) as Mark[];
  const parts = marks
    .filter((mark) => mark !== "up")
    .map((mark) => [mark, runs.filter((run) => run.mark === mark).length] as const)
    .filter(([, count]) => count > 0)
    .map(([mark, count]) => `${count} ${MARK_LABEL[mark]}`);
  return parts.length === 0
    ? "Last 24 hours: each observed slot is up"
    : `Last 24 hours, runs that are not up: ${parts.join(", ")}`;
}

function useWidth<T extends Element>(fallback: number): [RefObject<T | null>, number] {
  const box = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const element = box.current;
    if (element === null || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry !== undefined) setWidth(Math.max(1, Math.floor(entry.contentRect.width)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [box, width];
}
