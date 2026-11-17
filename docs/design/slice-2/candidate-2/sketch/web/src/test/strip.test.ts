// vitest. Pure functions, no DOM.
import { describe, it } from "vitest";

describe("columnMarks", () => {
  it.todo("returns the marks unchanged when columns >= marks");
  it.todo("keeps one down slot visible in 1,440 slots on 360 columns");
  it.todo("keeps one not_observed slot visible among up slots");
  it.todo("gives each column the same slot count, plus or minus one");
});
describe("runs", () => {
  it.todo("gives one run for a day that is all up");
  it.todo("covers each column exactly one time");
});
describe("columnSpan", () => {
  it.todo("gives the start of slot 0 as first_slot_start and the end of the last slot");
});
