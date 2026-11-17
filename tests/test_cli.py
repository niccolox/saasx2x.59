import json

import pytest

from saasx2x.cli import main
from saasx2x.domain import parse_hostname


@pytest.mark.parametrize(
    ("raw", "hostname"),
    [
        ("Example.COM.", "example.com"),
        (" localhost ", "localhost"),
        ("bücher.example", "xn--bcher-kva.example"),
    ],
)
def test_owner_input_becomes_a_lowercase_ascii_hostname(raw: str, hostname: str) -> None:
    assert parse_hostname(raw) == hostname


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com",
        "example.com:443",
        "example.com/path",
        "192.0.2.1",
        "::1",
        "-a.com",
        "",
    ],
)
def test_target_add_rejects_input_that_is_not_a_hostname(
    raw: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["target", "add", raw])
    assert exit_info.value.code == 2
    assert "hostname" in capsys.readouterr().err


def test_target_add_rejects_an_interval_below_60_seconds() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["target", "add", "example.com", "--interval", "30"])
    assert exit_info.value.code == 2


def test_web_openapi_prints_the_api_document_with_no_postgres(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAASX2X_DATABASE_URL", "postgresql://saasx2x:saasx2x@127.0.0.1:1/none")
    assert main(["web", "--openapi"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert list(document["paths"]) == ["/api/dashboard"]
