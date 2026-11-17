import socket
import ssl

import pytest
import trustme

from saasx2x.domain import (
    BODY_HEAD_BYTES,
    HttpFailed,
    HttpResponded,
    TcpFailed,
    TlsFailed,
    parse_hostname,
)
from saasx2x.https_check import Timeouts, check_https, tls_context
from saasx2x.verdict import Verdict, decide_verdict
from tests.tls_servers import (
    answer,
    never_answer,
    self_signed_server_context,
    serve,
    trusted_server_context,
)

LOCALHOST = parse_hostname("localhost")
FAST = Timeouts(dns_s=2, tcp_s=2, tls_s=2, http_s=0.5)


@pytest.fixture(scope="module")
def ca() -> trustme.CA:
    return trustme.CA()


@pytest.fixture
def client_tls(ca: trustme.CA) -> ssl.SSLContext:
    context = tls_context()
    ca.configure_trust(context)
    return context


async def test_a_200_answer_is_up_and_the_request_names_saasx2x(
    ca: trustme.CA, client_tls: ssl.SSLContext
) -> None:
    requests: list[bytes] = []
    ok = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nServer: test\r\nConnection: close\r\n\r\nok"
    async with serve(answer(ok, requests), trusted_server_context(ca)) as port:
        observation = await check_https(LOCALHOST, port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, HttpResponded)
    assert (observation.status, observation.server, observation.body_head) == (200, "test", None)
    assert decide_verdict(observation).verdict is Verdict.UP
    head = requests[0].decode().lower().split("\r\n")
    assert head[0] == "get / http/1.1"
    assert f"host: localhost:{port}" in head
    assert any(line.startswith("user-agent: saasx2x-monitor/") for line in head)


async def test_an_untrusted_self_signed_certificate_is_a_tls_failure(
    client_tls: ssl.SSLContext,
) -> None:
    async with serve(answer(b"", []), self_signed_server_context()) as port:
        observation = await check_https(LOCALHOST, port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, TlsFailed)
    assert observation.error == "certificate_invalid"
    assert "self-signed" in observation.detail
    assert decide_verdict(observation).verdict is Verdict.DOWN


async def test_a_closed_port_is_a_refused_tcp_connection(client_tls: ssl.SSLContext) -> None:
    with socket.socket() as probe_port:
        probe_port.bind(("127.0.0.1", 0))
        closed_port = probe_port.getsockname()[1]

    observation = await check_https(LOCALHOST, closed_port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, TcpFailed)
    assert observation.error == "refused"
    assert decide_verdict(observation).verdict is Verdict.DOWN


async def test_a_server_that_never_answers_is_an_http_timeout(
    ca: trustme.CA, client_tls: ssl.SSLContext
) -> None:
    async with serve(never_answer, trusted_server_context(ca)) as port:
        observation = await check_https(LOCALHOST, port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, HttpFailed)
    assert observation.error == "timeout"
    assert decide_verdict(observation).verdict is Verdict.DOWN


async def test_an_error_answer_keeps_the_first_4096_body_bytes(
    ca: trustme.CA, client_tls: ssl.SSLContext
) -> None:
    body = b"<html>" + b"x" * 10_000
    raw = b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: %d\r\n\r\n%s" % (len(body), body)
    async with serve(answer(raw, []), trusted_server_context(ca)) as port:
        observation = await check_https(LOCALHOST, port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, HttpResponded)
    assert observation.status == 503
    assert observation.body_head == body[:BODY_HEAD_BYTES].decode()
    assert decide_verdict(observation).verdict is Verdict.DOWN


async def test_a_cloudflare_challenge_answer_is_blocked(
    ca: trustme.CA, client_tls: ssl.SSLContext
) -> None:
    body = b"<html><head><title>Just a moment...</title></head></html>"
    raw = (
        b"HTTP/1.1 403 Forbidden\r\nServer: cloudflare\r\ncf-mitigated: challenge\r\n"
        b"CF-RAY: 8f1d2c3b4a5e6f70-AMS\r\nContent-Length: %d\r\n\r\n%s" % (len(body), body)
    )
    async with serve(answer(raw, []), trusted_server_context(ca)) as port:
        observation = await check_https(LOCALHOST, port, tls=client_tls, timeouts=FAST)

    assert isinstance(observation, HttpResponded)
    assert observation.cf_ray == "8f1d2c3b4a5e6f70-AMS"
    assert decide_verdict(observation).verdict is Verdict.BLOCKED
