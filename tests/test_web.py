"""The HTTP surface of `saasx2x web`, through the FastAPI test client."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from saasx2x.config import Settings
from saasx2x.domain import AccountSlug
from saasx2x.domain import parse_hostname as host
from saasx2x.store import Store
from saasx2x.web import PAGE_NOT_BUILT, create_app, openapi_document
from tests.conftest import scratch_database
from tests.results import PROBE, TCP_REFUSED, make_check_older, result_at

NOW = datetime(2026, 1, 2, 12, 0, 7, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
REPO = Path(__file__).resolve().parents[1]
LOCAL = "http://127.0.0.1"


def client(database_url: str, dist: Path) -> TestClient:
    app = create_app(Settings(database_url=database_url), clock=lambda: NOW, dist=dist)
    return TestClient(app, base_url=LOCAL)


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def test_the_dashboard_is_the_whole_page_at_the_server_instant(
    store: Store, database_url: str, tmp_path: Path
) -> None:
    await store.register_probe(PROBE)
    check = await store.add_target(AccountSlug("owner"), host("example.com"), interval=MINUTE)
    await make_check_older(database_url, check, NOW - timedelta(days=2))
    await store.record_result(
        result_at(check, datetime(2026, 1, 2, 11, 56, tzinfo=UTC), TCP_REFUSED)
    )
    for minute in (57, 58, 59):
        await store.record_result(result_at(check, datetime(2026, 1, 2, 11, minute, tzinfo=UTC)))

    with client(database_url, tmp_path) as http:
        response = http.get("/api/dashboard")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert iso(body["generated_at"]) == NOW
    assert body["refresh_after_s"] == 60
    assert body["worker"]["state"] == "writing"
    assert iso(body["worker"]["newest_row_at"]) == datetime(2026, 1, 2, 11, 59, 1, 250000, UTC)
    assert body["worker"]["expected_every_s"] == 60

    (row,) = body["checks"]
    assert (row["hostname"], row["port"], row["kind"], row["interval_s"]) == (
        "example.com",
        443,
        "https",
        60,
    )
    assert row["last"]["reason"] == "status_ok"
    assert row["last"]["verdict"] == "up"
    assert iso(row["last"]["slot_start"]) == datetime(2026, 1, 2, 11, 59, tzinfo=UTC)
    assert (iso(row["strip"]["start"]), iso(row["strip"]["end"])) == (
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        datetime(2026, 1, 2, 12, 1, tzinfo=UTC),
    )
    assert [
        (iso(run["end"]).minute, run["mark"], run["reason"]) for run in row["strip"]["runs"]
    ] == [
        (56, "not_observed", None),
        (57, "down", "tcp_failed"),
        (0, "up", "status_ok"),
    ]
    assert row["day"] == {
        "up": 3,
        "down": 1,
        "blocked": 0,
        "inconclusive": 0,
        "not_observed": 1436,
        "expected": 1440,
        "up_ratio": 0.75,
    }
    assert (row["week"]["expected"], row["week"]["not_observed"]) == (2879, 2875)


def test_a_database_with_no_schema_gives_503_with_the_command_to_fix_it(tmp_path: Path) -> None:
    with scratch_database() as url, client(url, tmp_path) as http:
        response = http.get("/api/dashboard")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "saasx2x migrate" in response.json()["detail"]


def test_a_request_for_a_different_host_name_is_refused(database_url: str, tmp_path: Path) -> None:
    with client(database_url, tmp_path) as http:
        assert http.get("/api/dashboard", headers={"host": "evil.example"}).status_code == 400
        assert http.get("/", headers={"host": "localhost:55441"}).status_code == 503


def test_the_built_page_is_served_at_the_root(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>SaaSX2X</title>")
    (tmp_path / "assets" / "app-1a2b.js").write_text("console.log(1)")
    http = client("postgresql://unused", tmp_path)

    page = http.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "<title>SaaSX2X</title>" in page.text
    assert http.get("/assets/app-1a2b.js").text == "console.log(1)"


def test_with_no_built_page_the_root_says_how_to_build_it(tmp_path: Path) -> None:
    page = client("postgresql://unused", tmp_path).get("/")
    assert page.status_code == 503
    assert page.text == PAGE_NOT_BUILT


def test_the_committed_openapi_document_is_the_current_api() -> None:
    committed = json.loads((REPO / "web" / "openapi.json").read_text())
    assert committed == json.loads(openapi_document(Settings())), (
        "web/openapi.json is old. Run: uv run saasx2x web --openapi > web/openapi.json"
    )
