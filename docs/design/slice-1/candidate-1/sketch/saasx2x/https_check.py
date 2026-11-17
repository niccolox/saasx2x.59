"""The HTTPS check. This module does all network I/O of a check.

Only this module imports `socket`, `ssl` and `h11`.
"""

import ssl
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, PositiveFloat

from saasx2x.domain import Hostname, HttpsObservation

USER_AGENT: Final = "SaaSX2X-Monitor/0.1 (+https://saasx2x.example/bot)"
"""Each request sends this value. It is not a parameter, so no caller can send a different one."""

_ERROR_BODY_SAMPLE_BYTES: Final = 4096

TlsContext = ssl.SSLContext


class Timeouts(BaseModel):
    """One budget for each stage. The sum is the longest time that one check can use."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dns_s: PositiveFloat = 5.0
    tcp_s: PositiveFloat = 5.0
    tls_s: PositiveFloat = 5.0
    http_s: PositiveFloat = 15.0

    @property
    def total_s(self) -> float:
        raise NotImplementedError


def tls_context(ca_file: Path | None = None) -> TlsContext:
    """Make the trust policy for all checks of one worker.

    None: the system CA store. A path: that CA file also, for a private CA or the test CA.
    The context verifies the certificate chain and the hostname. It offers ALPN `http/1.1` only.
    """
    raise NotImplementedError


async def check_https(
    hostname: Hostname, port: int, *, tls: TlsContext, timeouts: Timeouts
) -> HttpsObservation:
    """Do one HTTPS check on one connection and return what the probe saw.

    Total: the function returns an observation for each failure. It raises only CancelledError.
    The function is done in at most `timeouts.total_s` seconds.
    It makes no decision about up or down. `verdict.decide_verdict` does that.
    """
    # TODO stage 1, DNS (budget dns_s): `loop.getaddrinfo(hostname, port, type=SOCK_STREAM)`.
    #   gaierror EAI_NONAME, EAI_NODATA      -> DnsFailed(not_found)
    #   gaierror EAI_AGAIN, EAI_FAIL, timeout -> DnsFailed(unavailable)
    # TODO stage 2, TCP (budget tcp_s for all addresses): try each address in resolver order.
    #   Stop at the first address that connects. Report the failure of the last address.
    #   ConnectionRefusedError -> refused; TimeoutError -> timeout; EHOSTUNREACH -> unreachable;
    #   ConnectionResetError -> reset.
    #   ENETUNREACH, EADDRNOTAVAIL, EMFILE, ENFILE, ENOBUFS -> ProbeFailed(stage="tcp").
    # TODO stage 3, TLS (budget tls_s): `writer.start_tls(tls, server_hostname=hostname)`
    #   on the same socket.
    #   SSLCertVerificationError -> certificate_invalid, detail = verify_message;
    #   other SSLError, EOF, reset -> handshake_failed; TimeoutError -> timeout.
    # TODO stage 4, HTTP (budget http_s): with h11, send
    #     GET / HTTP/1.1, Host: <hostname>, User-Agent: USER_AGENT, Accept: */*, Connection: close
    #   Read the response headers. Ignore 1xx responses. Do not follow a redirect.
    #   If status >= 400, read at most _ERROR_BODY_SAMPLE_BYTES of the body. Then close.
    #   TimeoutError -> timeout; EOF or reset before the headers end -> connection_closed;
    #   h11.RemoteProtocolError -> protocol_error.
    # TODO: an exception that no rule above names -> ProbeFailed(stage, detail=repr(error)).
    raise NotImplementedError
