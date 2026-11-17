"""Run one check against the network and return an Observation.

This is the deep module of slice 1. One public function, observe(), hides
DNS resolution, address fallback, the TCP connect, the TLS handshake, the
HTTP/1.1 exchange (h11 over our own socket), per-stage time limits, the
errno-to-reason table, and Cloudflare page detection.

The TCP connect of brief step 1 and the HTTPS request of step 2 use the
same socket. The probe opens one connection per check, so each stage time
is measured on the connection that carried the request, and the target
sees one connection every 5 minutes, not two.
"""

from __future__ import annotations

import ssl
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address

from saasx2x.domain import (
    CheckSpec,
    CloudflarePage,
    Failure,
    Hostname,
    Observation,
    Stage,
)

USER_AGENT = "SaaSX2X-Monitor/0.1 (+https://saasx2x.example/bot)"
"""The only User-Agent any probe sends. Targets allowlist the probe by it."""

BODY_PREFIX_BYTES = 16_384
"""The probe reads at most this much body, then closes the connection."""


@dataclass(frozen=True, slots=True)
class Budget:
    """Time limits in seconds. Each stage gets min(stage limit, time left in total).

    total_s also bounds the body read. scheduler.py reads total_s to keep every
    check inside its slot.
    """

    dns_s: float = 5.0
    tcp_s: float = 5.0
    tls_s: float = 10.0
    http_s: float = 15.0
    total_s: float = 30.0


BUDGET = Budget()

Resolver = Callable[[Hostname, int], Awaitable[Sequence[IPv4Address | IPv6Address]]]
"""Returns addresses in connect order. Raises socket.gaierror on failure."""


@dataclass(frozen=True, slots=True)
class ProbeEnv:
    """What observe() needs from the host. Tests swap all three.

    Production: system resolver via loop.getaddrinfo, ssl.create_default_context(),
    BUDGET. Tests: a resolver that maps "localhost" to 127.0.0.1 or raises
    EAI_NONAME, a context that trusts the trustme test CA, a short budget.
    """

    resolve: Resolver
    tls: ssl.SSLContext
    budget: Budget = BUDGET


def default_env() -> ProbeEnv:
    raise NotImplementedError


async def observe(spec: CheckSpec, env: ProbeEnv) -> Observation:
    """Climb the ladder for one check. Never raises, except CancelledError.

    Any unexpected exception becomes Failure(stage=<current>, reason=PROBE_INTERNAL),
    so a probe bug writes a probe_error row instead of a missing row.
    """
    # TODO:
    # started = wall clock; deadline = monotonic + budget.total_s
    # DNS:  addrs = await wait_for(env.resolve(spec.host, spec.port), dns limit)
    #       gaierror EAI_NONAME/EAI_NODATA -> NXDOMAIN; EAI_AGAIN -> DNS_TEMPORARY;
    #       empty list -> DNS_NO_ADDRESS
    # TCP:  for addr in _connect_order(addrs): open_connection(str(addr), spec.port)
    #       first success wins, record remote_addr. Try the next address only after
    #       a local error (ENETUNREACH on IPv6 when the probe has no IPv6 route).
    #       All addresses ENETUNREACH -> NO_ROUTE. Last error otherwise decides.
    # TLS:  await writer.start_tls(env.tls, server_hostname=spec.host)
    #       SSLCertVerificationError -> TLS_CERT_INVALID; other SSLError -> TLS_HANDSHAKE
    # HTTP: h11 GET spec.path with headers Host, User-Agent=USER_AGENT, Accept: */*,
    #       Accept-Encoding: identity, Connection: close. Read until h11.Response.
    #       Then read body up to BODY_PREFIX_BYTES or deadline, whichever first.
    #       h11.RemoteProtocolError -> BAD_RESPONSE; EOF before Response -> CLOSED
    # Any stage: TimeoutError -> TIMEOUT; ECONNREFUSED -> REFUSED; ECONNRESET -> RESET;
    #       EHOSTUNREACH -> HOST_UNREACHABLE; EMFILE/ENOBUFS/EADDRNOTAVAIL -> LOCAL_RESOURCE
    # Always close the writer in a finally block.
    raise NotImplementedError


def _connect_order(
    addrs: Sequence[IPv4Address | IPv6Address],
) -> list[IPv4Address | IPv6Address]:
    """At most the first address of each family, resolver order kept."""
    raise NotImplementedError


def _failure(stage: Stage, exc: BaseException) -> Failure:
    """The errno and exception table from observe(), as one pure function."""
    raise NotImplementedError


def _cloudflare_page(status: int, server: str | None, body_prefix: bytes) -> CloudflarePage | None:
    """Match the body prefix against known Cloudflare interstitial markers.

    Runs only when server is "cloudflare" and status is 403, 429 or 503.
    CHALLENGE markers: "challenge-platform", "cf-chl-", "<title>Just a moment...".
    BLOCK markers: "cf-error-details" together with "Sorry, you have been blocked".
    """
    raise NotImplementedError
