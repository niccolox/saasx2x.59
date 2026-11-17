/** Pure presentation helpers. No rule about up or down lives here. */

/** "3 min ago". `ageS` is measured on the server clock: board.as_of minus the event time. */
export function formatAge(ageS: number): string {
  throw new Error("not implemented");
}

/** "99.82 %", or "n/a" for null. The server computes the ratio. This function only rounds. */
export function formatUptime(uptime: number | null): string {
  throw new Error("not implemented");
}

/** Seconds between two ISO 8601 strings. */
export function secondsBetween(fromIso: string, toIso: string): number {
  throw new Error("not implemented");
}
