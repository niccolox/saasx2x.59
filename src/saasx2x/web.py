"""The web process. The only module that imports `fastapi` and `uvicorn`.

Thin: one JSON route, the files of the built page, and the errors of both.

    GET /api/dashboard   -> Dashboard, `Cache-Control: no-store`. 503 with JSON when Postgres
                            does not answer or has no schema.
    GET /                -> web/dist/index.html. 503 with plain text and the build command when
                            the page is not built.
    GET /assets/*        -> the hashed files that Vite built.

The process never writes: it opens only a `ReadStore`, and it never runs `migrate`.
"""

import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final

import uvicorn
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from saasx2x.config import Settings
from saasx2x.dashboard import Dashboard, read_dashboard
from saasx2x.domain import AccountSlug
from saasx2x.store import ReadStore, StoreUnavailable

WEB_DIST_DIR: Final = Path(__file__).resolve().parents[2] / "web" / "dist"
"""Where `npm run build` writes the page. The same layout rule as `store.MIGRATIONS_DIR`."""

ALLOWED_HOSTS: Final = ("127.0.0.1", "localhost")
"""The `Host` values that the process answers. With no sign-in, this stops a page of a different
site that points its own name at 127.0.0.1."""

PAGE_NOT_BUILT: Final = (
    "The page is not built. Run: npm --prefix web ci && npm --prefix web run build\n"
)

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

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[dict[str, ReadStore]]:
        async with ReadStore.connect(settings.database_url) as store:
            yield {"store": store}

    def current_account() -> AccountSlug:
        # The one place that says whose data a request can read. The sign-in slice changes
        # this body only. No route and no query takes an account from the URL.
        return settings.account

    app = FastAPI(
        title="SaaSX2X", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS))

    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(_: Request, error: StoreUnavailable) -> JSONResponse:
        return JSONResponse(
            {"detail": str(error)}, status_code=503, headers={"Cache-Control": "no-store"}
        )

    @app.get(
        "/api/dashboard",
        responses={503: {"description": "Postgres does not answer, or it has no schema."}},
    )
    async def get_dashboard(
        request: Request,
        response: Response,
        account: Annotated[AccountSlug, Depends(current_account)],
    ) -> Dashboard:
        response.headers["Cache-Control"] = "no-store"
        return await read_dashboard(request.state.store, account, clock())

    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True))
    else:

        @app.get("/", include_in_schema=False)
        async def page_not_built() -> PlainTextResponse:
            return PlainTextResponse(PAGE_NOT_BUILT, status_code=503)

    return app


def openapi_document(settings: Settings) -> str:
    """The OpenAPI document of the API as JSON text with sorted keys. Needs no Postgres.

    `web/openapi.json` is a copy of this text. A test fails when the two differ.
    """
    return json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True)


async def serve(settings: Settings) -> None:
    """Run uvicorn on `settings.web_host` and `settings.web_port` until stopped.

    When the application cannot start, for example with no connection to Postgres, uvicorn logs
    the cause and exits with code 3.
    """
    config = uvicorn.Config(
        create_app(settings), host=settings.web_host, port=settings.web_port, lifespan="on"
    )
    await uvicorn.Server(config).serve()
