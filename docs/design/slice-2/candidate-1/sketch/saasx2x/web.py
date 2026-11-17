"""The web process. New module `src/saasx2x/web.py`.

The only module that imports `fastapi` and `uvicorn` (a ruff rule, as for `psycopg`).
Thin: one JSON route, the files of the built page, and the errors of both.

    GET /api/dashboard   -> Dashboard, `Cache-Control: no-store`. 503 with JSON when Postgres
                            does not answer.
    GET /                -> web/dist/index.html. 503 with plain text and the build command when
                            the page is not built.
    GET /assets/*        -> the hashed files that Vite built.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fastapi import FastAPI

from saasx2x.config import Settings

WEB_DIST_DIR: Final = Path(__file__).resolve().parents[2] / "web" / "dist"
"""Where `npm run build` writes the page. The same layout rule as `store.MIGRATIONS_DIR`."""

ALLOWED_HOSTS: Final = ("127.0.0.1", "localhost")
"""The `Host` values that the process answers. With no sign-in, this stops a page of a different
site that points its own name at 127.0.0.1."""

type Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    settings: Settings, *, clock: Clock = _utc_now, dist: Path = WEB_DIST_DIR
) -> FastAPI:
    """Make the application. No I/O until the application starts.

    The lifespan opens one `ReadStore` and closes it at the end. Each request uses that store.
    A test passes a scratch database in `settings`, a fixed `clock`, and a `dist` in a temp folder.
    """
    # TODO:
    #   lifespan: async with ReadStore.connect(settings.database_url) as store: yield
    #
    #   def current_account() -> AccountSlug:
    #       # The one place that says whose data a request can read. Slice 2: the owner account
    #       # from the settings. The sign-in slice changes this body only. No route and no
    #       # query takes an account from the URL.
    #       return settings.account
    #
    #   @app.get("/api/dashboard", response_model=Dashboard)
    #   async def dashboard(
    #       account: Annotated[AccountSlug, Depends(current_account)],
    #   ) -> Dashboard:
    #       return await read_dashboard(store, account, clock())
    #
    #   exception handler: StoreUnavailable -> 503 {"detail": "..."}
    #   middleware: TrustedHostMiddleware(allowed_hosts=ALLOWED_HOSTS)
    #   if (dist / "index.html").is_file(): mount StaticFiles(directory=dist, html=True) at "/"
    #   else: GET / -> 503, plain text:
    #       "The page is not built. Run: npm --prefix web ci && npm --prefix web run build"
    raise NotImplementedError


def openapi_document(settings: Settings) -> str:
    """The OpenAPI document of the API as JSON text with sorted keys. Needs no Postgres.

    `web/openapi.json` is a copy of this text. A test fails when the two differ.
    """
    raise NotImplementedError


async def serve(settings: Settings) -> None:
    """Run uvicorn on `settings.web_host` and `settings.web_port` until cancelled."""
    raise NotImplementedError
