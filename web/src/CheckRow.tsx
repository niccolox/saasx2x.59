import type { ReactElement } from "react";
import type { CheckStatus, LastResult } from "./api";
import { MARK_LABEL, REASON_LABEL } from "./marks";
import { Strip } from "./Strip";
import { formatAge } from "./time";
import { Uptime } from "./Uptime";

/**
 * One table row for one check:
 *
 *   example.com:443, every 300 s | down, TCP failed, 2 min ago | <Strip> | <Uptime day> | <Uptime week>
 *
 * "2 min ago" is the age of `last.slot_start`. With `last === null` the cell says "no result".
 * The verdict is text beside a colour mark, so the row does not depend on colour alone.
 */
export function CheckRow(props: { check: CheckStatus; serverNow: number }): ReactElement {
  const { check, serverNow } = props;
  return (
    <tr>
      <th scope="row">
        <span className="host">
          {check.hostname}
          <span className="port">:{check.port}</span>
        </span>
        <span className="note">every {check.interval_s} s</span>
      </th>
      <td data-label="Last result">
        <Last last={check.last} serverNow={serverNow} />
      </td>
      <td data-label="Last 24 hours" className="strip-cell">
        <Strip strip={check.strip} />
      </td>
      <td>
        <Uptime counts={check.day} label="24 h" />
      </td>
      <td>
        <Uptime counts={check.week} label="7 d" />
      </td>
    </tr>
  );
}

function Last(props: { last: LastResult | null; serverNow: number }): ReactElement {
  const { last, serverNow } = props;
  if (last === null) return <span className="note">no result</span>;
  return (
    <>
      <span className="verdict">
        <span className={`swatch mark--${last.verdict}`} aria-hidden="true" />
        {MARK_LABEL[last.verdict]}
      </span>
      <span className="note">
        {REASON_LABEL[last.reason]}, {formatAge(serverNow - Date.parse(last.slot_start))} ago
      </span>
    </>
  );
}
