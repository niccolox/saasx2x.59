import type { ReactElement } from "react";
import type { SlotCounts } from "./api";
import { formatRatio } from "./time";

/**
 * One uptime cell. The server owns the formula: this component formats `counts.up_ratio` and
 * does no arithmetic on the counts.
 *
 *   99.65%
 *   3 not observed              (warning style; shown when not_observed > 0)
 *   2 blocked, 1 inconclusive   (shown when a count is more than 0)
 *
 * With `up_ratio === null` the first line is "no data". The count of "not observed" is always
 * beside the ratio, so a ratio from few rows cannot look complete.
 */
export function Uptime(props: { counts: SlotCounts; label: "24 h" | "7 d" }): ReactElement {
  const { counts, label } = props;
  const other = [
    counts.blocked > 0 ? `${counts.blocked} blocked` : "",
    counts.inconclusive > 0 ? `${counts.inconclusive} inconclusive` : "",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <div className="uptime">
      <span className="uptime-label">{label}</span>
      <span className="uptime-ratio">{formatRatio(counts.up_ratio)}</span>
      {counts.not_observed > 0 && (
        <span className="note note--warn">{counts.not_observed} not observed</span>
      )}
      {other && <span className="note">{other}</span>}
    </div>
  );
}
