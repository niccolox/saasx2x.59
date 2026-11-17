"""The HTTPS check. This module does all network I/O of a check.

Only this module imports `socket`, `ssl` and `h11`.
"""

import asyncio
import errno
import socket
import ssl
from contextlib import suppress
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Final

import h11
from pydantic import BaseModel, ConfigDict, PositiveFloat

from saasx2x.domain import (
    BODY_HEAD_BYTES,
    DnsFailed,
    Hostname,
    HttpError,
    HttpFailed,
    HttpResponded,
    HttpsObservation,
    ProbeFailed,
    Stage,
    TcpError,
    TcpFailed,
    TlsError,
    TlsFailed,
)

USER_AGENT: Final = "SaaSX2X-Monitor/0.1 (+https://github.com/niccolox/saasx2x)"
"""Each request sends this value. It is not a parameter, so no caller can send a different one."""


class Timeouts(BaseModel):
    """One budget for each stage. The sum is the longest time that one check can use."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dns_s: PositiveFloat = 5.0
    tcp_s: PositiveFloat = 5.0
    tls_s: PositiveFloat = 5.0
    http_s: PositiveFloat = 15.0

    @property
    def total_s(self) -> float:
        return self.dns_s + self.tcp_s + self.tls_s + self.http_s


def tls_context() -> ssl.SSLContext:
    """The trust policy for all checks: the system CA store, chain and hostname verified."""
    context = ssl.create_default_context()
    context.set_alpn_protocols(["http/1.1"])
    return context


_DNS_NOT_FOUND: Final = frozenset(
    {socket.EAI_NONAME, getattr(socket, "EAI_NODATA", socket.EAI_NONAME)}
)
_DNS_UNAVAILABLE: Final = frozenset({socket.EAI_AGAIN, socket.EAI_FAIL})
_TARGET_TCP_ERRORS: Final[dict[int, TcpError]] = {
    errno.ECONNREFUSED: "refused",
    errno.ETIMEDOUT: "timeout",
    errno.EHOSTUNREACH: "unreachable",
    errno.ECONNRESET: "reset",
}
_TRANSPORT_ERRORS: Final = (ConnectionError, EOFError, ssl.SSLError, h11.RemoteProtocolError)

type _Address = IPv4Address | IPv6Address
type _AddrInfo = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str,
    tuple[str, int] | tuple[str, int, int, int] | tuple[int, bytes],
]


async def check_https(
    hostname: Hostname, port: int, *, tls: ssl.SSLContext, timeouts: Timeouts
) -> HttpsObservation:
    """Do one HTTPS check on one connection and return what the probe saw.

    Total: the function returns an observation for each failure. It raises only CancelledError.
    It makes no decision about up or down. `verdict.decide_verdict` does that.
    """
    loop = asyncio.get_running_loop()
    stage: Stage = "dns"
    writer: asyncio.StreamWriter | None = None
    try:
        started = loop.time()
        try:
            async with asyncio.timeout(timeouts.dns_s):
                addresses = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except TimeoutError:
            return DnsFailed(error="unavailable")
        except socket.gaierror as error:
            if error.errno in _DNS_NOT_FOUND:
                return DnsFailed(error="not_found")
            if error.errno in _DNS_UNAVAILABLE:
                return DnsFailed(error="unavailable")
            raise
        dns_ms = _ms_since(started)

        stage = "tcp"
        started = loop.time()
        ip, connected = await _connect(addresses, timeouts.tcp_s)
        if isinstance(connected, OSError):
            return ProbeFailed(stage="tcp", detail=repr(connected))
        if not isinstance(connected, socket.socket):
            return TcpFailed(ip=ip, dns_ms=dns_ms, error=connected)
        reader, writer = await asyncio.open_connection(sock=connected)
        tcp_connect_ms = _ms_since(started)

        stage = "tls"
        started = loop.time()
        if (tls_failure := await _start_tls(writer, tls, hostname, timeouts.tls_s)) is not None:
            error, detail = tls_failure
            return TlsFailed(
                ip=ip, dns_ms=dns_ms, tcp_connect_ms=tcp_connect_ms, error=error, detail=detail
            )
        tls_handshake_ms = _ms_since(started)

        stage = "http"
        started = loop.time()
        deadline = started + timeouts.http_s
        connection = h11.Connection(our_role=h11.CLIENT)
        try:
            async with asyncio.timeout_at(deadline):
                writer.write(connection.send(_request(hostname, port)) or b"")
                writer.write(connection.send(h11.EndOfMessage()) or b"")
                await writer.drain()
                response = await _read_response(connection, reader)
        except (TimeoutError, *_TRANSPORT_ERRORS) as error:
            return HttpFailed(
                ip=ip,
                dns_ms=dns_ms,
                tcp_connect_ms=tcp_connect_ms,
                tls_handshake_ms=tls_handshake_ms,
                error=_http_error(error),
            )
        http_ms = _ms_since(started)

        body_head: str | None = None
        if response.status_code >= 400:
            body = bytearray()
            with suppress(TimeoutError, *_TRANSPORT_ERRORS):
                async with asyncio.timeout_at(deadline):
                    await _read_body_head(connection, reader, body)
            # Postgres rejects \u0000 inside jsonb text, so a NUL byte becomes U+FFFD.
            text = bytes(body[:BODY_HEAD_BYTES]).decode("utf-8", errors="replace")
            body_head = text.replace("\x00", "\ufffd")

        headers = {
            name.decode("latin-1"): value.decode("latin-1") for name, value in response.headers
        }
        return HttpResponded(
            ip=ip,
            dns_ms=dns_ms,
            tcp_connect_ms=tcp_connect_ms,
            tls_handshake_ms=tls_handshake_ms,
            http_ms=http_ms,
            status=response.status_code,
            server=headers.get("server"),
            cf_mitigated=headers.get("cf-mitigated"),
            cf_ray=headers.get("cf-ray"),
            body_head=body_head,
        )
    except Exception as error:
        return ProbeFailed(stage=stage, detail=repr(error))
    finally:
        if writer is not None:
            writer.transport.abort()


async def _connect(
    addresses: list[_AddrInfo], budget_s: float
) -> tuple[_Address, socket.socket | TcpError | OSError]:
    """Try each address in resolver order inside one budget. Report the failure of the last one."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_s
    ip: _Address = ip_address(addresses[0][4][0])
    failure: TcpError | OSError = "timeout"
    for family, kind, proto, _, sockaddr in addresses:
        ip = ip_address(sockaddr[0])
        sock = socket.socket(family, kind, proto)
        sock.setblocking(False)
        try:
            async with asyncio.timeout_at(deadline):
                await loop.sock_connect(sock, sockaddr)
        except TimeoutError:
            sock.close()
            return ip, "timeout"
        except OSError as error:
            sock.close()
            failure = _TARGET_TCP_ERRORS.get(error.errno or 0, error)
            continue
        except BaseException:
            sock.close()
            raise
        return ip, sock
    return ip, failure


def _request(hostname: Hostname, port: int) -> h11.Request:
    host = hostname if port == 443 else f"{hostname}:{port}"
    return h11.Request(
        method="GET",
        target="/",
        headers=[
            ("Host", host),
            ("User-Agent", USER_AGENT),
            ("Accept", "*/*"),
            ("Accept-Encoding", "identity"),
            ("Connection", "close"),
        ],
    )


async def _next_event(connection: h11.Connection, reader: asyncio.StreamReader) -> object:
    while (event := connection.next_event()) is h11.NEED_DATA:
        connection.receive_data(await reader.read(65536))
    return event


async def _start_tls(
    writer: asyncio.StreamWriter, tls: ssl.SSLContext, hostname: Hostname, budget_s: float
) -> tuple[TlsError, str] | None:
    try:
        async with asyncio.timeout(budget_s):
            await writer.start_tls(tls, server_hostname=hostname)
    except TimeoutError:
        return "timeout", "handshake timed out"
    except ssl.SSLCertVerificationError as error:
        return "certificate_invalid", error.verify_message or str(error)
    except (ssl.SSLError, ConnectionError, EOFError) as error:
        return "handshake_failed", str(error) or repr(error)
    return None


async def _read_response(connection: h11.Connection, reader: asyncio.StreamReader) -> h11.Response:
    """Return the final response head. Skip 1xx responses."""
    while True:
        event = await _next_event(connection, reader)
        if isinstance(event, h11.Response):
            return event
        if not isinstance(event, h11.InformationalResponse):
            raise EOFError("connection closed before a response")


async def _read_body_head(
    connection: h11.Connection, reader: asyncio.StreamReader, body: bytearray
) -> None:
    while len(body) < BODY_HEAD_BYTES:
        event = await _next_event(connection, reader)
        if not isinstance(event, h11.Data):
            return
        body += event.data


def _http_error(error: Exception) -> HttpError:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, h11.RemoteProtocolError):
        return "protocol_error"
    return "connection_closed"


def _ms_since(started: float) -> float:
    return (asyncio.get_running_loop().time() - started) * 1000
