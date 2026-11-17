"""One end-to-end check in a real browser. Offline: a scratch database, a local server, Chromium.

Skipped with a reason when web/dist or the Playwright Chromium is missing. Run:
    npm --prefix web ci && npm --prefix web run build
    uv run playwright install chromium
    uv run pytest -m browser
"""

import pytest


@pytest.mark.browser
async def test_the_page_shows_a_stall_and_then_clears_it() -> None:
    """
    1. Seed two targets, b.example and a.example, 300 s, with rows up to 20 minutes ago.
    2. Start create_app(settings, clock=lambda: t) with uvicorn on 127.0.0.1:<free port>,
       in this event loop.
    3. page.clock.install(); page.goto("/").
    4. Expect a.example before b.example. Expect role=alert with "STALLED".
       Expect each strip <svg> to have an aria-label that names "not observed".
    5. Insert a row for the current slot. Move t forward 60 s. page.clock.run_for(60_000).
    6. Expect the alert to be gone and the worker line to say "writing rows".
    """
    raise NotImplementedError
