import type { ReactElement } from "react";
import type { CheckStatus } from "./api";

/**
 * One table row for one check:
 *
 *   example.com:443, each 300 s | down, TCP failed, 2 min ago | <Strip> | <Uptime day> | <Uptime week>
 *
 * "2 min ago" is the age of `last.slot_start`. With `last === null` the cell says "no result".
 * The verdict is text beside a colour mark, so the row does not depend on colour alone.
 */
export function CheckRow(props: { check: CheckStatus; serverNow: number }): ReactElement {
  throw new Error("not implemented");
}
