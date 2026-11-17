"""The app through httpx.ASGITransport, with a fixed clock and a scratch database. No socket."""


async def test_get_dashboard_returns_a_valid_dashboard_for_seeded_rows() -> None:
    raise NotImplementedError


async def test_write_methods_get_405() -> None:
    """POST, PUT, PATCH, DELETE on /api/dashboard and on /."""
    raise NotImplementedError


async def test_postgres_down_gives_503_with_a_detail() -> None:
    raise NotImplementedError


async def test_without_dist_the_api_works_and_root_says_page_not_built() -> None:
    raise NotImplementedError


def test_committed_json_schema_equals_the_model() -> None:
    """web/src/generated/dashboard.schema.json == dashboard_json_schema().
    The failure message says: run `uv run saasx2x schema > web/src/generated/dashboard.schema.json`.
    """
    raise NotImplementedError


def test_front_end_fixtures_are_valid_dashboards() -> None:
    """Each web/src/test/fixtures/*.json parses with Dashboard.model_validate_json."""
    raise NotImplementedError


def test_compose_publishes_web_on_127_0_0_1_only() -> None:
    """Parse compose.yml. Each `ports` entry of `web` starts with 127.0.0.1:."""
    raise NotImplementedError


def test_default_web_host_is_127_0_0_1() -> None:
    raise NotImplementedError
