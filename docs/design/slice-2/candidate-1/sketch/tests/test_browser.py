"""The one end-to-end check in a real browser. New file `tests/test_browser.py`.

Python drives Chromium through `pytest-playwright`, so the test uses the slice 1 fixtures: a
scratch database on the Compose Postgres, and `Store` to write rows. The server is the real
`create_app` on a free port of 127.0.0.1 with a clock that the test moves. No network except
127.0.0.1.

The test skips with a reason when `web/dist/index.html` is absent. Build the page first:
`npm --prefix web ci && npm --prefix web run build`. One time, also run
`uv run playwright install chromium`.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Page

START = datetime(2026, 1, 2, 12, 0, 7, tzinfo=UTC)


class MovableClock:
    """The server clock of the test. `create_app(clock=clock)` reads it for each request."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def served(database_url: str) -> Iterator[tuple[str, MovableClock]]:
    """Seed rows, start the server in a thread, yield its URL and its clock.

    Rows, written through `Store.record_result` with `asyncio.run`:
      a.example  60 s interval, made 2 days before START, up in each slot of the last 24 hours
                 except one slot with no row and one slot with `tcp_failed`
      b.example  300 s interval, made 1 hour before START, `tcp_failed` in each slot
    """
    raise NotImplementedError


@pytest.mark.browser
def test_the_owner_sees_each_check_and_then_sees_the_worker_stall(
    page: Page, served: tuple[str, MovableClock]
) -> None:
    """
    1. Open the URL. The worker line says "Worker writes rows".
    2. The rows are a.example then b.example. b.example shows "down" and "TCP failed".
    3. The strip of a.example has one "not observed" rectangle and one "down" rectangle, each
       at least 2 px wide (`bounding_box()`), with 1,440 slots on the axis.
    4. The strip of b.example starts 1 hour before the right edge: no rectangle before that.
    5. The 24 h cell of a.example shows "1 not observed".
    6. Move the server clock 10 minutes. Move the browser clock 61 s with `page.clock`.
       The worker line has role "alert" and says "Worker stalled". The tab title starts with
       "STALLED".
    7. Stop the server. Move the browser clock 61 s. The page keeps the rows and shows the
       warning that its data is old.
    """
    raise NotImplementedError
