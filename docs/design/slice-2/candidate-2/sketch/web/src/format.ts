// Text for numbers and times. Each age is relative to `as_of` of the snapshot, never to the
// browser clock.

/** "45 s", "4 min", "3 h 10 min", "2 d 4 h". */
export function ageText(asOf: string, at: string): string {
  throw new Error("not implemented");
}

/** "99.93 %". Round down to two decimals, so "100 %" shows only when down is 0. "no data" for null. */
export function ratioText(upRatio: number | null): string {
  throw new Error("not implemented");
}

/** "every 5 min", "every 60 s". */
export function intervalText(intervalS: number): string {
  throw new Error("not implemented");
}
