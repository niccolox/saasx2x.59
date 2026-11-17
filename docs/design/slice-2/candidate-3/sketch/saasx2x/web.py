"""The web process: one FastAPI app that serves the JSON board and the built React page.

    GET /api/status   -> StatusBoard (status.py), the whole page in one response
    GET /healthz      -> 200 {"ok": true} while the process runs (no Postgres call)
    GET /*            -> files of web/dist (index.html for "/"), when the folder exists

The file holds the shell only. Each rule is in `status.py`. Each query is in `store.py`.
The module is the third file in the longest call chain: web.py -> store.py -> status.py.

Read-only by construction, in three layers:
  1. The app depends on `StatusReader`. It has one method, a read.
  2. `ReadStore` has no write method.
  3. `ReadStore` sessions start with `default_transaction_read_only=on`.

Run `python -m saasx2x.web` to print the OpenAPI document. `npm run gen` in `web/` uses it.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from saasx2x.config import Settings
from saasx2x.domain import AccountSlug
from saasx2x.status import StatusBoard, StatusFacts

DIST_DIR: Final = Path(__file__).resolve().parents[2] / "web" / "dist"
"""Same pattern as `store.MIGRATIONS_DIR`. In the image, this is /app/web/dist."""

ALLOWED_HOSTS: Final = ["127.0.0.1", "localhost"]
"""Host header allow-list. A page on another site cannot read the board through DNS rebinding
to 127.0.0.1. The service has no sign-in, so this is its only gate."""

type Clock = Callable[[], datetime]


class StatusReader(Protocol):
    """What the app needs from the store. `ReadStore` satisfies it. A test passes a fake."""

    async def status_facts(
        self, account: AccountSlug, *, since: datetime, as_of: datetime
    ) -> StatusFacts: ...


class Problem(BaseModel):
    """Body of a 503. The page shows `detail` and keeps the last good board on screen."""

    detail: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    reader: StatusReader,
    *,
    account: AccountSlug,
    clock: Clock = _utc_now,
    dist: Path | None = DIST_DIR,
) -> FastAPI:
    """Build the app. Do no I/O here, so `openapi_json()` works with no Postgres.

    `account` fixes who the board is for. Today it is `Settings.account`. With sign-in, replace
    `current_account` below with a dependency that reads the session. No other line changes,
    because `status_facts` and `build_board` already take the account as an argument.

    TODO(pseudocode):
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)   # `app.openapi()` still works
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

        def current_account() -> AccountSlug: return account

        @app.get("/api/status", response_model=StatusBoard,
                 responses={503: {"model": Problem}})
        async def status(who: AccountSlug = Depends(current_account)) -> Response:
            as_of = clock()
            facts = await reader.status_facts(who, since=as_of - WINDOW_7D, as_of=as_of)
            board = await run_in_threadpool(build_board, facts, as_of)   # CPU, not the event loop
            return board with header `Cache-Control: no-store`

        @app.exception_handler(StoreUnavailable)
        -> JSONResponse(Problem(detail=str(error)), status_code=503, no-store)

        @app.get("/healthz") -> 200 {"ok": true} whenever the process runs. It does not touch
            Postgres. A Postgres fault shows as 503 on /api/status, and the page shows it.
            The Compose health check calls this route.

        if dist and (dist / "index.html").exists():
            app.mount("/", StaticFiles(directory=dist, html=True))   # after the API routes
        else:
            @app.get("/") -> 503 text "web/dist is missing: run `npm run build` in web/,
                             or open the Vite dev server on :5173"
    """
    raise NotImplementedError


def openapi_json() -> str:
    """The OpenAPI document of the app, as stable JSON (sorted keys, 2-space indent, newline).

    Builds the app with a reader that raises on use. A test compares the result with the
    committed `web/openapi.json`. The test fails when a type in `status.py` changed and the
    snapshot did not. This is the guard against a stale TypeScript contract.
    """
    raise NotImplementedError


async def serve(settings: Settings) -> None:
    """The body of `saasx2x web`.

        async with ReadStore.connect_read_only(settings.database_url) as reader:
            app = create_app(reader, account=settings.account)
            await uvicorn.Server(uvicorn.Config(
                app, host=settings.web_host, port=settings.web_port,
                log_level="info", access_log=False)).serve()

    It runs in the same event loop as the pool, so no thread holds a connection.
    """
    raise NotImplementedError


if __name__ == "__main__":
    print(openapi_json(), end="")
