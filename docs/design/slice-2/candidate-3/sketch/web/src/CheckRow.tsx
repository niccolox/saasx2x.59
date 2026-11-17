import type { CheckStatus } from "./api";

/**
 * One check. Columns: host:port and interval | last result | strip | 24 h | 7 d.
 * Last result: verdict word, REASON_LABEL[reason], HTTP status if present, and the age of
 * `last.slot_start` against `as_of`. With `last === null`: "no result yet".
 * 24 h and 7 d: formatUptime(tally.uptime), then the four other counts as text:
 * "blocked 12, inconclusive 0, not observed 3". Not observed is never merged into another count.
 * At 400 px width the strip drops under the host line and takes the full width.
 */
export function CheckRow(props: {
  check: CheckStatus;
  asOfIso: string;
  windowStartIso: string;
}): JSX.Element {
  throw new Error("not implemented");
}
