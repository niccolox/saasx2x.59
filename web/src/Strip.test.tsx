import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { minuteCheckOneDownSlot, oneOutage } from "./fixtures";
import { Strip } from "./Strip";

test("the strip of 1,440 slots draws one down rectangle of 3 px with its time on hover", () => {
  const { container } = render(<Strip strip={minuteCheckOneDownSlot.checks[0]!.strip} />);
  const down = container.querySelectorAll('rect[data-mark="down"]');
  expect(down).toHaveLength(1);
  expect(down[0]!.getAttribute("width")).toBe("3");
  expect(down[0]!.querySelector("title")?.textContent).toBe(
    "down, TCP failed, Nov 16 03:10 to 03:11 UTC, 1 min",
  );
});

test("the strip names its runs that are not up", () => {
  const { getByRole } = render(<Strip strip={oneOutage.checks[0]!.strip} />);
  expect(getByRole("img").getAttribute("aria-label")).toBe(
    "Last 24 hours, runs that are not up: 1 down, 1 not observed",
  );
});
