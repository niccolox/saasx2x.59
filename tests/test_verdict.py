from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from saasx2x.domain import (
    AccountId,
    CheckId,
    DnsFailed,
    HttpFailed,
    HttpResponded,
    HttpsObservation,
    ProbeFailed,
    ProbeId,
    TcpFailed,
    TlsFailed,
)
from saasx2x.verdict import CheckResult, Reason, Verdict, decide_verdict

FIXTURES = Path(__file__).parent / "fixtures"
CHALLENGE_PAGE = (FIXTURES / "cloudflare_challenge.html").read_text()
BLOCK_PAGE = (FIXTURES / "cloudflare_block.html").read_text()
IP = ip_address("192.0.2.10")


def responded(
    status: int,
    *,
    server: str | None = None,
    cf_mitigated: str | None = None,
    body: str | None = None,
) -> HttpResponded:
    return HttpResponded(
        ip=IP,
        dns_ms=1,
        tcp_connect_ms=2,
        tls_handshake_ms=3,
        http_ms=4,
        status=status,
        server=server,
        cf_mitigated=cf_mitigated,
        cf_ray=None,
        body_head=(body if body is not None else "") if status >= 400 else None,
    )


VERDICT_TABLE: list[tuple[str, HttpsObservation, Reason, Verdict]] = [
    (
        "cf-mitigated challenge, any status",
        responded(200, server="cloudflare", cf_mitigated="challenge"),
        Reason.CLOUDFLARE_CHALLENGE,
        Verdict.BLOCKED,
    ),
    (
        "cloudflare 403 with a block page marker",
        responded(403, server="cloudflare", body=BLOCK_PAGE),
        Reason.CLOUDFLARE_BLOCK_PAGE,
        Verdict.BLOCKED,
    ),
    ("any 429", responded(429, server="nginx"), Reason.RATE_LIMITED, Verdict.BLOCKED),
    ("200", responded(200), Reason.STATUS_OK, Verdict.UP),
    ("399", responded(399), Reason.STATUS_OK, Verdict.UP),
    ("401", responded(401, server="nginx"), Reason.LOGIN_REQUIRED, Verdict.UP),
    ("404", responded(404), Reason.ERROR_STATUS, Verdict.DOWN),
    ("500", responded(500), Reason.ERROR_STATUS, Verdict.DOWN),
    ("dns not found", DnsFailed(error="not_found"), Reason.DNS_NOT_FOUND, Verdict.DOWN),
    (
        "tcp failed",
        TcpFailed(ip=IP, dns_ms=1, error="refused"),
        Reason.TCP_FAILED,
        Verdict.DOWN,
    ),
    (
        "tls failed",
        TlsFailed(
            ip=IP,
            dns_ms=1,
            tcp_connect_ms=2,
            error="certificate_invalid",
            detail="certificate has expired",
        ),
        Reason.TLS_FAILED,
        Verdict.DOWN,
    ),
    (
        "http failed",
        HttpFailed(ip=IP, dns_ms=1, tcp_connect_ms=2, tls_handshake_ms=3, error="timeout"),
        Reason.HTTP_FAILED,
        Verdict.DOWN,
    ),
    (
        "dns unavailable",
        DnsFailed(error="unavailable"),
        Reason.DNS_UNAVAILABLE,
        Verdict.INCONCLUSIVE,
    ),
    (
        "local socket error",
        ProbeFailed(stage="tcp", detail="OSError(24, 'Too many open files')"),
        Reason.PROBE_FAILED,
        Verdict.INCONCLUSIVE,
    ),
]


@pytest.mark.parametrize(
    ("observation", "reason", "verdict"),
    [case[1:] for case in VERDICT_TABLE],
    ids=[case[0] for case in VERDICT_TABLE],
)
def test_verdict_table(observation: HttpsObservation, reason: Reason, verdict: Verdict) -> None:
    assert decide_verdict(observation) is reason
    assert reason.verdict is verdict


def test_cloudflare_challenge_page_is_blocked() -> None:
    page = responded(403, server="cloudflare", cf_mitigated="challenge", body=CHALLENGE_PAGE)
    assert decide_verdict(page).verdict is Verdict.BLOCKED


def test_cloudflare_challenge_page_without_the_header_is_blocked_by_its_marker() -> None:
    page = responded(503, server="cloudflare", body=CHALLENGE_PAGE)
    assert decide_verdict(page) is Reason.CLOUDFLARE_BLOCK_PAGE


def test_origin_503_behind_cloudflare_without_a_marker_is_down() -> None:
    origin = responded(503, server="cloudflare", body="<html><h1>Service Unavailable</h1></html>")
    assert decide_verdict(origin).verdict is Verdict.DOWN


def test_block_marker_from_a_server_that_is_not_cloudflare_is_down() -> None:
    assert decide_verdict(responded(403, server="nginx", body=BLOCK_PAGE)).verdict is Verdict.DOWN


def test_401_is_up() -> None:
    assert decide_verdict(responded(401)).verdict is Verdict.UP


def test_429_is_blocked() -> None:
    assert decide_verdict(responded(429)).verdict is Verdict.BLOCKED


def test_each_reason_has_a_verdict_and_the_table_covers_each_reason() -> None:
    assert {case[2] for case in VERDICT_TABLE} == set(Reason)


def test_a_body_head_below_status_400_is_not_representable() -> None:
    with pytest.raises(ValidationError):
        HttpResponded(
            ip=IP,
            dns_ms=1,
            tcp_connect_ms=2,
            tls_handshake_ms=3,
            http_ms=4,
            status=200,
            server=None,
            cf_mitigated=None,
            cf_ray=None,
            body_head="<html>",
        )


def test_a_status_code_on_a_dns_failure_is_not_representable() -> None:
    raw = {"outcome": "dns_failed", "error": "not_found", "status": 200}
    with pytest.raises(ValidationError):
        TypeAdapter(HttpsObservation).validate_python(raw)


def test_a_stored_observation_gives_the_same_reason_when_judged_again() -> None:
    stored = responded(403, server="cloudflare", body=BLOCK_PAGE).model_dump_json()
    replayed = TypeAdapter(HttpsObservation).validate_json(stored)
    assert decide_verdict(replayed) is Reason.CLOUDFLARE_BLOCK_PAGE


def test_check_result_derives_reason_and_verdict_from_the_observation() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    result = CheckResult(
        check_id=CheckId(uuid4()),
        account_id=AccountId(uuid4()),
        probe_id=ProbeId("local-1"),
        scheduled_at=now,
        due_at=now,
        started_at=now,
        duration_ms=5,
        observation=DnsFailed(error="unavailable"),
    )
    dumped = result.model_dump(mode="json")
    assert (dumped["reason"], dumped["verdict"]) == ("dns_unavailable", "inconclusive")
    with pytest.raises(ValidationError):
        CheckResult.model_validate({**dumped, "verdict": "up"})
