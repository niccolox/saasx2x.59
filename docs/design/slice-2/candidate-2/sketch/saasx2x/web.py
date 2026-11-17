"""The web process: one JSON route and the built page. Read only. Thin.

Only this module imports `fastapi`, `starlette` and `uvicorn` (a ruff banned-api rule, as for
`psycopg`). The route calls one store method and one pure function:

    GET /api/dashboard
      reader.dashboard_facts(account, clock())   store.py, one snapshot
      build_dashboard(facts)                     dashboard.py, pure
      -> Dashboard as JSON

Each other path serves a file of `web/dist` (the Vite build). The app has no POST, PUT, PATCH or
DELETE route, so each write method gets 405.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from saasx2x.config import Settings
from saasx2x.dashboard import Dashboard, build_dashboard
from saasx2x.domain import AccountSlug
from saasx2x.store import DashboardReader, StoreUnavailable

DIST_DIR: Final = Path(__file__).resolve().parents[2] / "web" / "dist"
"""The Vite build output. The Docker image copies it here from the Node build stage."""

type Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def current_account(settings: Settings) -> AccountSlug:
    """The account of the request. Slice 2: always `settings.account`.

    The sign-in slice replaces this function with a FastAPI dependency that reads the session.
    The route and the store already take an account, so nothing else changes.
    """
    return settings.account


def create_app(
    settings: Settings, *, clock: Clock = _utc_now, dist: Path = DIST_DIR
) -> FastAPI:
    """Build the app. Tests pass a fixed clock and a scratch database URL in `settings`.

    lifespan: async with DashboardReader.connect(settings.database_url) as reader: yield
      A Postgres that is down at start does not stop the app. The route answers 503 until
      Postgres answers. (TODO: open the pool with open=False and let the first route open it.)

    GET /api/dashboard -> Dashboard
      headers: Cache-Control: no-store
      StoreUnavailable -> 503 {"detail": "<message>"}

    GZipMiddleware(minimum_size=1024): a 1,440 mark strip is mostly repeats of one word.

    When `dist` exists: mount StaticFiles(directory=dist, html=True) at "/", after the API
    route. index.html gets Cache-Control: no-cache. Files under /assets/ have hashed names
    and get Cache-Control: public, max-age=31536000, immutable.
    When `dist` does not exist: GET / answers 503 with the text
    "page not built: run `npm --prefix web run build`". The API still works.
    """
    raise NotImplementedError


async def _store_unavailable(request: Request, error: StoreUnavailable) -> JSONResponse:
    raise NotImplementedError


async def serve(settings: Settings) -> None:
    """Run uvicorn on settings.web_host:settings.web_port until cancelled.

    uvicorn.Server(uvicorn.Config(create_app(settings), host=..., port=..., log_config=None,
                                  access_log=False)).serve()
    """
    raise NotImplementedError


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    raise NotImplementedError
    yield


__all__ = ["DIST_DIR", "Dashboard", "create_app", "current_account", "serve"]
