// Test list (names are the plan; bodies come with the implementation).
import { describe, it } from "vitest";

describe("layoutStrip", () => {
  it.todo("returns no rect for a strip with no runs");
  it.todo("leaves the lead slots empty");
  it.todo("draws one down slot among 1,440 up slots at least MIN_MARK_PX wide");
  it.todo("draws the up share within 1 px of its true share");
  it.todo("puts a mark of a 60 s check and a 300 s check at the same x for the same time");
  it.todo("returns at most widthPx rects for a flapping strip");
  it.todo("orders up and not_observed before down, blocked, inconclusive");
});

describe("reduce and link", () => {
  it.todo("keeps the last good board when a refresh fails");
  it.todo("link is stale 150 s after the last good response, with no new event");
});

describe("page on the golden board", () => {
  // Uses src/fixtures/board.json. The Python test writes that file: both sides read one fixture.
  it.todo("lists hostnames in the order of the fixture");
  it.todo("shows 'Worker stopped writing rows' for a stalled fixture");
  it.todo("shows the not_observed count apart from the up count");
  it.todo("keeps the last board on screen and shows a banner after a failed refresh");
});
