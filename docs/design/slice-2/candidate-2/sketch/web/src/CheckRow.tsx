import type { CheckPanel, MarkCounts } from "./generated/dashboard";
import { SlotStrip } from "./SlotStrip";

/**
 * One table row for one check.
 *   Target:      "<hostname>:<port>" and intervalText(interval_s)
 *   Last result: MARK_STYLE[last.mark].label, REASON_TEXT of each reason, ageText(asOf, slot_start)
 *                last === null -> "no result yet"
 *   Last 24 h:   <SlotStrip strip={panel.strip} />
 *   24 h, 7 d:   <Uptime counts={...} />
 */
export function CheckRow({ panel, asOf }: { panel: CheckPanel; asOf: string }) {
  throw new Error("not implemented");
}

/**
 * ratioText(up_ratio) on the first line. On the second line, only the non-zero counts that are
 * outside the ratio: "3 not observed · 1 blocked". The title attribute gives all six counts and
 * `expected`, so the owner can check the sum.
 */
export function Uptime({ counts }: { counts: MarkCounts }) {
  throw new Error("not implemented");
}
