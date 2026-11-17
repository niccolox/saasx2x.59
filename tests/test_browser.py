"""The one end-to-end check in a real browser.

Python drives Chromium through `pytest-playwright`, so the test uses the slice 1 fixtures: a
scratch database on the Compose Postgres, and `Store` to write rows. The server is the real
`create_app` on a free port of 127.0.0.1 with a clock that the test moves. No network except
127.0.0.1.

The test skips with a reason when `web/dist/index.html` or Chromium is absent. Build the page
first: `npm --prefix web ci && npm --prefix web run build`. One time, also run
`uv run playwright install chromium`.
"""

import asyncio
import re
import socket
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
import uvicorn
from playwright.sync_api import Locator, Page, expect, sync_playwright

from saasx2x.config import Settings
from saasx2x.domain import AccountSlug
from saasx2x.domain import parse_hostname as host
from saasx2x.store import Store
from saasx2x.web import WEB_DIST_DIR, create_app
from tests.results import PROBE, TCP_REFUSED, UP, make_check_older, result_at

START = datetime(2026, 1, 2, 12, 0, 7, tzinfo=UTC)
OPEN_SLOT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
MISSING = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
DOWN = datetime(2026, 1, 2, 3, 10, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
MIN_MARK_PX = 3


def _why_skip() -> str | None:
    if not (WEB_DIST_DIR / "index.html").is_file():
        return "the page is not built. Run: npm --prefix web ci && npm --prefix web run build"
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            return "Chromium is not installed. Run: uv run playwright install chromium"
    return None


_SKIP = _why_skip()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")


@dataclass
class MovableClock:
    """The server clock of the test. `create_app(clock=clock)` reads it for each request."""

    now: datetime

    def __call__(self) -> datetime:
        return self.now


@dataclass
class Served:
    url: str
    clock: MovableClock
    server: uvicorn.Server
    thread: threading.Thread

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


async def _seed(database_url: str) -> None:
    """a.example: 60 s, made 2 days before START, up in each slot of the last 24 hours except
    one slot with no row and one slot with `tcp_failed`.
    b.example: 300 s, made 1 hour before START, `tcp_failed` in each expected slot."""
    async with Store.connect(database_url) as store:
        await store.migrate()
        async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
            await db.execute("TRUNCATE check_results, checks, targets, accounts, probes")
        await store.register_probe(PROBE)
        owner = AccountSlug("owner")
        a = await store.add_target(owner, host("a.example"), interval=MINUTE)
        b = await store.add_target(owner, host("b.example"), interval=5 * MINUTE)
        await make_check_older(database_url, a, START - timedelta(days=2))
        await make_check_older(database_url, b, START - timedelta(hours=1))
        day = [OPEN_SLOT - n * MINUTE for n in range(1, 1441)]
        rows = [result_at(a, slot, TCP_REFUSED if slot == DOWN else UP) for slot in day]
        rows += [result_at(b, OPEN_SLOT - n * 5 * MINUTE, TCP_REFUSED) for n in range(1, 12)]
        await asyncio.gather(
            *(store.record_result(row) for row in rows if row.scheduled_at != MISSING)
        )


@pytest.fixture
def served(database_url: str) -> Iterator[Served]:
    """Seed rows, start the server in a thread, yield its URL and its clock.

    The Playwright sync API runs an event loop in this thread, so the seed runs in its own.
    """
    with ThreadPoolExecutor(max_workers=1) as seeder:
        seeder.submit(asyncio.run, _seed(database_url)).result()
    clock = MovableClock(START)
    app = create_app(Settings(database_url=database_url), clock=clock)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "the server did not start"
        time.sleep(0.05)
    port = listener.getsockname()[1]
    served = Served(f"http://127.0.0.1:{port}/", clock, server, thread)
    yield served
    served.stop()
    listener.close()


def width_of(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None, "the element is not drawn"
    return box["width"]


@pytest.mark.browser
def test_the_owner_sees_each_check_and_then_sees_the_worker_stall(
    page: Page, served: Served
) -> None:
    page.clock.install()
    page.goto(served.url)

    expect(page.get_by_role("status")).to_have_text(re.compile(r"^Worker writes rows\."))
    rows = page.get_by_role("row").filter(has=page.get_by_role("rowheader"))
    expect(rows).to_have_count(2)
    a_row, b_row = rows.nth(0), rows.nth(1)
    expect(a_row.get_by_role("rowheader")).to_contain_text("a.example:443")
    expect(b_row.get_by_role("rowheader")).to_contain_text("b.example:443")
    expect(b_row.locator("td").nth(0)).to_contain_text("down")
    expect(b_row.locator("td").nth(0)).to_contain_text("TCP failed")

    not_observed = a_row.locator('rect[data-mark="not_observed"]')
    down = a_row.locator('rect[data-mark="down"]')
    expect(not_observed).to_have_count(1)
    expect(down).to_have_count(1)
    strip_px = width_of(a_row.get_by_role("img"))
    assert strip_px < 1440, "each 60 s slot is less than 1 px, so the minimum width matters"
    assert width_of(not_observed) >= MIN_MARK_PX
    assert width_of(down) >= MIN_MARK_PX

    b_strip = b_row.get_by_role("img").bounding_box()
    assert b_strip is not None
    b_axis_min = 24 * 60 + 5
    first_row_x = b_strip["x"] + b_strip["width"] * (b_axis_min - 60) / b_axis_min
    for box in (rect.bounding_box() for rect in b_row.locator("rect[data-mark]").all()):
        assert box is not None
        assert box["x"] >= first_row_x - 1, "b.example has no mark before it existed"

    expect(a_row.locator("td").nth(2)).to_contain_text("1 not observed")

    served.clock.now = START + 10 * MINUTE
    page.clock.fast_forward(61_000)
    stalled = page.get_by_role("alert").filter(has_text="Worker stalled")
    expect(stalled).to_be_visible()
    expect(page).to_have_title(re.compile(r"^STALLED"))

    served.stop()
    page.clock.fast_forward(61_000)
    expect(page.get_by_role("alert").filter(has_text="This page is not up to date")).to_be_visible()
    expect(rows).to_have_count(2)
    expect(stalled).to_be_visible()
