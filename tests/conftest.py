"""Postgres fixtures. Each one makes its own `saasx2x_test_*` database on the Compose server and
drops it after. No fixture writes to the main database.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from saasx2x.config import Settings
from saasx2x.store import Store

SERVER_URL = Settings().database_url


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # The Playwright sync API keeps an event loop in this thread until the session ends, and
    # an asyncio test cannot run inside it. So each browser test runs after the other tests.
    items.sort(key=lambda item: item.get_closest_marker("browser") is not None)


@contextmanager
def scratch_database() -> Iterator[str]:
    name = f"saasx2x_test_{uuid4().hex[:12]}"
    with psycopg.connect(SERVER_URL, autocommit=True) as server:
        server.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(SERVER_URL, dbname=name)
    finally:
        with psycopg.connect(SERVER_URL, autocommit=True) as server:
            server.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with scratch_database() as url:
        yield url


@pytest.fixture
async def store(database_url: str) -> AsyncIterator[Store]:
    """A migrated store with no rows."""
    async with Store.connect(database_url) as store:
        await store.migrate()
        async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
            await db.execute("TRUNCATE check_results, checks, targets, accounts, probes")
        yield store
